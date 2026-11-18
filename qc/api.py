"""FastAPI backend for Questionnaire Copilot (spec section 7 & 8)."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from qc.config import get_settings
from qc.db import connect
from qc.draft import draft_question
from qc.embed import Embedder, get_embedder
from qc.ingest import ingest_policy
from qc.library import count_stale, reapprove_library_entry, review_draft
from qc.llm import LLM, get_llm
from qc.xlsx_io import ColumnMapping, ExportRow, export_questionnaire, read_questionnaire

REPO_ROOT = Path(__file__).parent.parent

app = FastAPI(title="Questionnaire Copilot API", version="0.1.0")


def _stored_path(path: Path) -> str:
    return (
        path.relative_to(REPO_ROOT).as_posix()
        if path.is_relative_to(REPO_ROOT)
        else path.as_posix()
    )


def _resolve_path(stored: str) -> Path:
    p = Path(stored)
    return p if p.is_absolute() else REPO_ROOT / p


def get_db() -> Generator[psycopg.Connection, None, None]:
    with connect() as conn:
        yield conn


def get_llm_dep() -> LLM:
    return get_llm()


def get_embedder_dep() -> Embedder:
    return get_embedder()


class _HeaderGuess(BaseModel):
    col_question: int
    col_answer: int | None
    col_explanation: int | None


def _llm_header_resolver(llm: LLM):
    def _resolve(headers: list[str]) -> ColumnMapping:
        prompt = "Identify 1-based column indices from these header cells:\n" + "\n".join(
            f"{i + 1}: {h}" for i, h in enumerate(headers)
        )
        parsed, _ = llm.structured(
            "Return 1-based column indices for question, answer, and explanation (or null).",
            [{"role": "user", "content": prompt}],
            _HeaderGuess,
            max_tokens=200,
        )
        assert isinstance(parsed, _HeaderGuess)
        return ColumnMapping(
            col_question=parsed.col_question,
            col_answer=parsed.col_answer,
            col_explanation=parsed.col_explanation,
        )

    return _resolve


class ReviewRequest(BaseModel):
    reviewer: str
    action: str  # approve | edit | reject
    final_answer: str | None = None
    final_explanation: str | None = None


class ReapproveRequest(BaseModel):
    reviewer: str
    short_answer: str | None = None
    explanation: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/config/reviewers")
def list_reviewers() -> dict:
    raw = get_settings().reviewers
    names = [n.strip() for n in raw.split(",") if n.strip()]
    return {"reviewers": names}


@app.get("/policies")
def list_policies(conn: Annotated[psycopg.Connection, Depends(get_db)]) -> dict:
    rows = conn.execute(
        """
        SELECT p.policy_id, p.title, pv.version, pv.effective_date, pv.source_file, pv.is_current
        FROM policy_versions pv
        JOIN policies p ON pv.policy_id = p.policy_id
        ORDER BY p.policy_id, pv.version DESC
        """
    ).fetchall()
    items = [
        {
            "policy_id": r[0],
            "title": r[1],
            "version": r[2],
            "effective_date": str(r[3]),
            "source_file": r[4],
            "is_current": r[5],
        }
        for r in rows
    ]
    return {"policies": items, "stale_count": count_stale(conn)}


@app.post("/policies/upload")
def upload_policy(
    file: Annotated[UploadFile, File(...)],
    policy_id: Annotated[str, Form(...)],
    title: Annotated[str, Form(...)],
    version: Annotated[int, Form(...)],
    effective_date: Annotated[str, Form(...)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    embedder: Annotated[Embedder, Depends(get_embedder_dep)],
) -> dict:
    filename = Path(file.filename or "policy.md").name
    dest_dir = REPO_ROOT / get_settings().uploads_dir / "policies"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{policy_id}-v{version}{Path(filename).suffix.lower()}"
    dest_path.write_bytes(file.file.read())

    try:
        eff = dt.date.fromisoformat(effective_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date: {effective_date}") from exc

    res = ingest_policy(
        conn,
        dest_path,
        policy_id=policy_id,
        title=title,
        version=version,
        effective_date=eff,
        source_file=_stored_path(dest_path),
        embedder=embedder,
    )
    conn.commit()
    return {
        "policy_id": res.policy_id,
        "version": res.version,
        "chunks_total": res.chunks_total,
        "embedded": res.embedded,
        "skipped": res.skipped,
        "stale_count": count_stale(conn),
    }


@app.get("/questionnaires")
def list_questionnaires(conn: Annotated[psycopg.Connection, Depends(get_db)]) -> dict:
    rows = conn.execute(
        """
        SELECT qn.id, qn.name, qn.file_path, qn.sheet_map, qn.created_at,
               count(q.id) AS question_count
        FROM questionnaires qn
        LEFT JOIN questions q ON q.questionnaire_id = qn.id
        GROUP BY qn.id
        ORDER BY qn.id DESC
        """
    ).fetchall()
    return {
        "questionnaires": [
            {
                "id": r[0],
                "name": r[1],
                "file_path": r[2],
                "sheet_map": r[3],
                "created_at": r[4].isoformat(),
                "question_count": r[5],
            }
            for r in rows
        ]
    }


@app.post("/questionnaires/upload")
def upload_questionnaire(
    file: Annotated[UploadFile, File(...)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    llm: Annotated[LLM, Depends(get_llm_dep)],
    qid_prefix: Annotated[str | None, Form()] = None,
) -> dict:
    filename = Path(file.filename or "questionnaire.xlsx").name
    dest_dir = REPO_ROOT / get_settings().uploads_dir / "questionnaires"
    dest_dir.mkdir(parents=True, exist_ok=True)
    unique = f"{uuid.uuid4().hex[:8]}_{filename}"
    dest_path = dest_dir / unique
    dest_path.write_bytes(file.file.read())

    try:
        detected = read_questionnaire(
            dest_path,
            qid_prefix=qid_prefix or None,
            fallback_resolver=_llm_header_resolver(llm),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    name = Path(filename).stem
    qn_id = conn.execute(
        "INSERT INTO questionnaires (name, file_path, sheet_map) VALUES (%s, %s, %s) RETURNING id",
        (name, _stored_path(dest_path), Jsonb(detected.sheet_map)),
    ).fetchone()[0]

    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO questions "
            "(questionnaire_id, qid, sheet, row, col_question, col_answer, text) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [
                (qn_id, q.qid, q.sheet, q.row, q.col_question, q.col_answer, q.text)
                for q in detected.questions
            ],
        )
    conn.commit()
    return {
        "id": qn_id,
        "name": name,
        "sheet_map": detected.sheet_map,
        "question_count": len(detected.questions),
    }


@app.post("/questionnaires/{questionnaire_id}/draft")
def draft_questionnaire(
    questionnaire_id: int,
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    llm: Annotated[LLM, Depends(get_llm_dep)],
    embedder: Annotated[Embedder, Depends(get_embedder_dep)],
) -> dict:
    q_rows = conn.execute(
        "SELECT id, qid, text FROM questions WHERE questionnaire_id = %s ORDER BY id",
        (questionnaire_id,),
    ).fetchall()
    if not q_rows:
        raise HTTPException(status_code=404, detail="Questionnaire not found or has no questions")

    run_id = f"run-{uuid.uuid4().hex[:8]}"
    outcomes = []
    for q_id, qid, q_text in q_rows:
        out = draft_question(
            conn,
            q_id,
            qid,
            q_text,
            run_id=run_id,
            llm=llm,
            embedder=embedder,
            persist=True,
        )
        outcomes.append(out)
    conn.commit()

    return {
        "run_id": run_id,
        "total": len(outcomes),
        "drafted": sum(1 for o in outcomes if o.status == "drafted"),
        "needs_input": sum(1 for o in outcomes if o.status == "needs_input"),
        "library_reused": sum(1 for o in outcomes if o.source == "library"),
    }


@app.get("/questionnaires/{questionnaire_id}/drafts")
def get_questionnaire_drafts(
    questionnaire_id: int,
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict:
    rows = conn.execute(
        """
        SELECT q.id, q.qid, q.sheet, q.row, q.text,
               d.id, d.source, d.short_answer, d.explanation, d.citations, d.confidence, d.status
        FROM questions q
        LEFT JOIN LATERAL (
            SELECT id, source, short_answer, explanation, citations, confidence, status
            FROM drafts
            WHERE question_id = q.id
            ORDER BY id DESC
            LIMIT 1
        ) d ON TRUE
        WHERE q.questionnaire_id = %s
        ORDER BY q.id
        """,
        (questionnaire_id,),
    ).fetchall()

    chunk_ids: set[int] = set()
    for r in rows:
        for c in r[9] or []:
            if isinstance(c, dict) and "chunk_id" in c:
                chunk_ids.add(int(c["chunk_id"]))

    chunk_texts: dict[int, str] = {}
    if chunk_ids:
        c_rows = conn.execute(
            "SELECT id, text FROM chunks WHERE id = ANY(%s)", (list(chunk_ids),)
        ).fetchall()
        chunk_texts = {int(cr[0]): cr[1] for cr in c_rows}

    items = []
    for r in rows:
        cites = []
        for c in r[9] or []:
            if isinstance(c, dict):
                cid = c.get("chunk_id")
                cites.append({**c, "text": chunk_texts.get(int(cid), "") if cid else ""})
        items.append(
            {
                "question_id": r[0],
                "qid": r[1],
                "sheet": r[2],
                "row": r[3],
                "text": r[4],
                "draft_id": r[5],
                "source": r[6],
                "short_answer": r[7],
                "explanation": r[8],
                "citations": cites,
                "confidence": r[10],
                "status": r[11] or "undrafted",
            }
        )
    return {"items": items}


@app.post("/drafts/{draft_id}/review")
def post_review(
    draft_id: int,
    body: ReviewRequest,
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    embedder: Annotated[Embedder, Depends(get_embedder_dep)],
) -> dict:
    try:
        lib_id = review_draft(
            conn,
            draft_id,
            reviewer=body.reviewer,
            action=body.action,
            final_answer=body.final_answer,
            final_explanation=body.final_explanation,
            embedder=embedder,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    conn.commit()
    row = conn.execute("SELECT status FROM drafts WHERE id = %s", (draft_id,)).fetchone()
    return {"draft_id": draft_id, "status": row[0] if row else body.action, "library_id": lib_id}


@app.get("/library")
def list_library(conn: Annotated[psycopg.Connection, Depends(get_db)]) -> dict:
    rows = conn.execute(
        """
        SELECT id, question_text, short_answer, explanation, citations, policy_versions,
               approved_by, approved_at, stale
        FROM answer_library
        ORDER BY stale DESC, id DESC
        """
    ).fetchall()

    # Load current section texts so stale entries can render side-by-side comparison (D12).
    cur_rows = conn.execute(
        """
        SELECT c.policy_id, c.version, c.section, c.text
        FROM chunks c
        JOIN policy_versions pv ON c.policy_id = pv.policy_id AND c.version = pv.version
        WHERE pv.is_current = TRUE
        """
    ).fetchall()
    current_sections: dict[tuple[str, str], tuple[int, str]] = {}
    for pid, ver, sec, txt in cur_rows:
        key = (pid, sec)
        if key in current_sections:
            prev_ver, prev_txt = current_sections[key]
            current_sections[key] = (ver, f"{prev_txt}\n\n{txt}")
        else:
            current_sections[key] = (ver, txt)

    items = []
    for r in rows:
        cites = r[4] or []
        current_passages = []
        if r[8]:
            for c in cites:
                key = (c.get("policy_id", ""), c.get("section", ""))
                if key in current_sections:
                    ver, txt = current_sections[key]
                    current_passages.append(
                        {"policy_id": key[0], "version": ver, "section": key[1], "text": txt}
                    )
        items.append(
            {
                "id": r[0],
                "question_text": r[1],
                "short_answer": r[2],
                "explanation": r[3],
                "citations": cites,
                "policy_versions": r[5] or [],
                "approved_by": r[6],
                "approved_at": r[7].isoformat(),
                "stale": r[8],
                "current_passages": current_passages,
            }
        )
    return {"items": items, "stale_count": count_stale(conn)}


@app.post("/library/{library_id}/reapprove")
def post_reapprove(
    library_id: int,
    body: ReapproveRequest,
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict:
    try:
        reapprove_library_entry(
            conn,
            library_id,
            reviewer=body.reviewer,
            short_answer=body.short_answer,
            explanation=body.explanation,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    conn.commit()
    return {"id": library_id, "stale": False}


@app.get("/questionnaires/{questionnaire_id}/export")
def export_questionnaire_file(
    questionnaire_id: int,
    conn: Annotated[psycopg.Connection, Depends(get_db)],
):
    qn = conn.execute(
        "SELECT name, file_path, sheet_map FROM questionnaires WHERE id = %s",
        (questionnaire_id,),
    ).fetchone()
    if qn is None:
        raise HTTPException(status_code=404, detail="Questionnaire not found")
    name, rel_path, sheet_map = qn
    src_path = _resolve_path(rel_path)
    if not src_path.exists():
        raise HTTPException(status_code=404, detail="Source questionnaire file missing")

    rows = conn.execute(
        """
        SELECT q.sheet, q.row, d.short_answer, d.explanation, d.citations, d.source, d.status
        FROM questions q
        LEFT JOIN LATERAL (
            SELECT short_answer, explanation, citations, source, status
            FROM drafts
            WHERE question_id = q.id
            ORDER BY id DESC
            LIMIT 1
        ) d ON TRUE
        WHERE q.questionnaire_id = %s
        ORDER BY q.id
        """,
        (questionnaire_id,),
    ).fetchall()

    export_rows: list[ExportRow] = []
    for sheet, row_num, short_ans, exp, cites, src, status in rows:
        cite_str = "; ".join(
            f"{c['policy_id']} v{c['version']} ({c['section']})"
            for c in (cites or [])
            if isinstance(c, dict)
        )
        export_rows.append(
            ExportRow(
                sheet=sheet,
                row=row_num,
                short_answer=short_ans,
                answer_text=None,
                explanation=exp,
                source=cite_str or (src or ""),
                status=status or "undrafted",
            )
        )

    out_dir = REPO_ROOT / get_settings().uploads_dir / "exports"
    out_path = out_dir / f"{name}_filled{src_path.suffix}"
    export_questionnaire(src_path, out_path, sheet_map, export_rows)
    return FileResponse(path=out_path, filename=out_path.name)


@app.get("/eval/report")
def get_eval_report() -> dict:
    report_path = REPO_ROOT / "evals" / "report.md"
    if not report_path.exists():
        return {"exists": False, "content": ""}
    return {"exists": True, "content": report_path.read_text(encoding="utf-8")}
