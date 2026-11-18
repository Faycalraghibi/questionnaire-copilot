"""`make seed`: generate the synthetic files, migrate, and load the database.

Phase 2 (decisions D1, D6): ingests policies (MD, PDF, DOCX) into sections, chunks and
embeddings via `qc.ingest`, skipping embeddings when chunk text hashes are unchanged so `make seed`
stays idempotent. Phase 3 replaces the known questionnaire layouts with header detection.

Usage: uv run python -m data.seed
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import psycopg
import yaml
from openpyxl import load_workbook
from psycopg.types.json import Jsonb

from data.make_questionnaires import LAYOUTS, make_all
from data.render import render_all
from qc.db import connect, migrate
from qc.embed import Embedder, get_embedder
from qc.ingest import ingest_policy
from qc.markdown import split_front_matter

DATA = Path(__file__).parent
REPO = DATA.parent
POLICY_DIR = DATA / "policies"
MIN_QUESTION_CHARS = 15  # spec 7.2
_NON_POLICY_TABLES = [
    "run_steps",
    "reviews",
    "drafts",
    "questions",
    "questionnaires",
    "answer_library",
]


@dataclass(frozen=True)
class PolicyFile:
    policy_id: str
    title: str
    version: int
    effective_date: dt.date
    path: Path


def discover_policies(policy_dir: Path = POLICY_DIR) -> list[PolicyFile]:
    """Markdown files carry front matter; PDF and DOCX files are described by manifest.yaml."""
    found = []
    for path in sorted(policy_dir.glob("*.md")):
        meta, _ = split_front_matter(path.read_text(encoding="utf-8"))
        found.append(
            PolicyFile(
                meta["policy_id"],
                meta["title"],
                int(meta["version"]),
                _date(meta["effective_date"]),
                path,
            )
        )
    manifest = policy_dir / "manifest.yaml"
    if manifest.exists():
        for e in yaml.safe_load(manifest.read_text(encoding="utf-8")) or []:
            found.append(
                PolicyFile(
                    e["policy_id"],
                    e["title"],
                    int(e["version"]),
                    _date(e["effective_date"]),
                    policy_dir / e["file"],
                )
            )
    return found


def _date(value) -> dt.date:
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))


def sync_policies(
    conn: psycopg.Connection,
    files: list[PolicyFile],
    *,
    embedder: Embedder | None = None,
) -> tuple[int, int]:
    """Ingest all discovered policy versions, pruning any versions not in `files`."""
    expected_versions = {(f.policy_id, f.version) for f in files}
    expected_policies = {f.policy_id for f in files}

    existing_versions = conn.execute("SELECT policy_id, version FROM policy_versions").fetchall()
    for pid, ver in existing_versions:
        if (pid, ver) not in expected_versions:
            conn.execute(
                "DELETE FROM policy_versions WHERE policy_id = %s AND version = %s",
                (pid, ver),
            )
    existing_policies = conn.execute("SELECT policy_id FROM policies").fetchall()
    for (pid,) in existing_policies:
        if pid not in expected_policies:
            conn.execute("DELETE FROM policies WHERE policy_id = %s", (pid,))

    emb = embedder or get_embedder()
    total_embedded = 0
    total_skipped = 0
    for f in sorted(files, key=lambda item: (item.policy_id, item.version)):
        res = ingest_policy(
            conn,
            f.path,
            policy_id=f.policy_id,
            title=f.title,
            version=f.version,
            effective_date=f.effective_date,
            source_file=f.path.relative_to(REPO).as_posix(),
            embedder=emb,
        )
        total_embedded += res.embedded
        total_skipped += res.skipped
    return total_embedded, total_skipped


def read_known_layout(path: Path, layout: dict, qid_prefix: str | None) -> list[dict]:
    """Read question rows with a known layout. `qid_prefix` numbers rows across sheets
    (Questionnaire B, decision D13); otherwise the qid comes from the ID column."""
    wb = load_workbook(path, read_only=True)
    out = []
    for sheet, cfg in layout.items():
        ws = wb[sheet]
        for row_idx, row in enumerate(
            ws.iter_rows(min_row=cfg["header_row"] + 1, values_only=True),
            start=cfg["header_row"] + 1,
        ):
            text = row[cfg["col_question"] - 1]
            if not isinstance(text, str) or len(text.strip()) < MIN_QUESTION_CHARS:
                continue
            qid = f"{qid_prefix}-{len(out) + 1:03d}" if qid_prefix else str(row[cfg["col_qid"] - 1])
            out.append(
                {
                    "qid": qid,
                    "sheet": sheet,
                    "row": row_idx,
                    "col_question": cfg["col_question"],
                    "col_answer": cfg["col_answer"],
                    "text": text.strip(),
                }
            )
    wb.close()
    return out


def load_questionnaire(
    conn: psycopg.Connection, name: str, path: Path, layout: dict, qid_prefix: str | None
) -> int:
    questions = read_known_layout(path, layout, qid_prefix)
    qn_id = conn.execute(
        "INSERT INTO questionnaires (name, file_path, sheet_map) VALUES (%s, %s, %s) RETURNING id",
        (name, path.relative_to(REPO).as_posix(), Jsonb(layout)),
    ).fetchone()[0]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO questions "
            "(questionnaire_id, qid, sheet, row, col_question, col_answer, text) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [
                (
                    qn_id,
                    q["qid"],
                    q["sheet"],
                    q["row"],
                    q["col_question"],
                    q["col_answer"],
                    q["text"],
                )
                for q in questions
            ],
        )
    return len(questions)


def seed(conn: psycopg.Connection, *, embedder: Embedder | None = None) -> dict:
    render_all()
    paths = make_all()
    migrate(conn)
    conn.execute(f"TRUNCATE {', '.join(_NON_POLICY_TABLES)} RESTART IDENTITY CASCADE")
    embedded, skipped = sync_policies(conn, discover_policies(), embedder=embedder)
    counts = {"embedded": embedded, "skipped": skipped}
    for name, prefix in [("acme_vendor_security_2026", None), ("globex_supplier_review", "B")]:
        counts[name] = load_questionnaire(conn, name, paths[name], LAYOUTS[name], prefix)
    conn.commit()
    counts["policies"] = conn.execute("SELECT count(*) FROM policies").fetchone()[0]
    counts["versions"] = conn.execute("SELECT count(*) FROM policy_versions").fetchone()[0]
    counts["current"] = conn.execute(
        "SELECT count(*) FROM policy_versions WHERE is_current"
    ).fetchone()[0]
    counts["chunks"] = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    return counts


def main() -> None:
    with connect() as conn:
        c = seed(conn)
    print(
        f"{c['policies']} policies, {c['versions']} versions, "
        f"{c['acme_vendor_security_2026']} + {c['globex_supplier_review']} questions "
        f"({c['chunks']} chunks: {c['embedded']} embedded, {c['skipped']} cached)"
    )


if __name__ == "__main__":
    main()
