"""Draft security questionnaire answers from retrieved policy passages (spec 7.4)."""

from __future__ import annotations

from dataclasses import dataclass

import psycopg
from psycopg.types.json import Jsonb

from qc.checks import CheckedDraft, Draft, check_draft
from qc.config import get_settings
from qc.embed import Embedder
from qc.llm import LLM, LLMUsage, get_llm
from qc.retrieve import ChunkHit, retrieve

DRAFT_SYSTEM_PROMPT = """You are a security compliance assistant answering a customer security \
questionnaire for Northbeam Cloud.

Rules:
1. Use ONLY the provided policy passages. Never use outside knowledge or assumptions.
2. Cite the exact chunk_id integers from the provided passages that support your answer.
3. If the passages do not fully answer the question, set can_answer=false and leave short_answer \
null.
4. Absence of a statement is not a No: if the passages do not mention the topic (for example, \
BYOK, customer-run penetration tests, database access headcount, PCI DSS, FedRAMP, cyber \
insurance, Uptime tier, or physical guards), set can_answer=false instead of answering "no".
5. Write for a customer's security reviewer in plain business language:
   - short_answer: "yes", "no", "partially", or "text" (use "yes"/"no"/"partially" for yes/no \
questions; use "text" for open questions like timelines, locations, or frequencies).
   - answer_text: 1 concise sentence when short_answer is "text", otherwise null.
   - explanation: 1 to 3 sentences grounded in the cited passages.
6. Never promise anything the passages do not explicitly state."""


@dataclass
class DraftOutcome:
    question_id: int
    qid: str
    source: str  # 'library' | 'policies' | 'none'
    status: str  # 'drafted' | 'needs_input'
    short_answer: str | None
    answer_text: str | None
    explanation: str | None
    citations: list[dict]
    confidence: str
    check_reasons: list[str]
    best_score: float
    usage: LLMUsage | None = None


def _format_passages(chunks: list[ChunkHit]) -> str:
    parts = []
    for c in chunks:
        parts.append(
            f"[chunk_id={c.id}] {c.policy_id} v{c.version} | {c.section} "
            f"(score={c.score:.4f})\n{c.text}"
        )
    return "\n\n---\n\n".join(parts)


def _log_run_step(
    conn: psycopg.Connection,
    *,
    run_id: str,
    item_id: str,
    step: str,
    input_data: dict,
    output_data: dict,
    usage: LLMUsage | None = None,
    error: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO run_steps (run_id, item_id, step, input, output, "
        "tokens_in, tokens_out, cost_usd, latency_ms, error) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            run_id,
            item_id,
            step,
            Jsonb(input_data),
            Jsonb(output_data),
            usage.input_tokens if usage else 0,
            usage.output_tokens if usage else 0,
            usage.cost_usd if usage else 0.0,
            usage.latency_ms if usage else 0,
            error,
        ),
    )


def _save_draft(conn: psycopg.Connection, run_id: str, outcome: DraftOutcome) -> None:
    db_short = (
        outcome.answer_text or outcome.short_answer
        if outcome.short_answer == "text"
        else outcome.short_answer
    )
    conn.execute(
        "INSERT INTO drafts "
        "(question_id, run_id, source, short_answer, explanation, citations, confidence, status) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (
            outcome.question_id,
            run_id,
            outcome.source,
            db_short,
            outcome.explanation,
            Jsonb(outcome.citations),
            outcome.confidence,
            outcome.status,
        ),
    )


def _current_versions(conn: psycopg.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT policy_id, version FROM policy_versions WHERE is_current = TRUE"
    ).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def draft_question(
    conn: psycopg.Connection,
    question_id: int,
    qid: str,
    question_text: str,
    *,
    run_id: str,
    llm: LLM | None = None,
    embedder: Embedder | None = None,
    min_evidence: float | None = None,
    reuse_threshold: float | None = None,
    persist: bool = True,
) -> DraftOutcome:
    settings = get_settings()
    min_ev = settings.min_evidence if min_evidence is None else min_evidence
    res = retrieve(
        conn,
        question_text,
        embedder=embedder,
        reuse_threshold=reuse_threshold,
    )

    if res.library_hit is not None:
        hit = res.library_hit
        outcome = DraftOutcome(
            question_id=question_id,
            qid=qid,
            source="library",
            status="drafted",
            short_answer=hit.short_answer,
            answer_text=None,
            explanation=hit.explanation,
            citations=hit.citations,
            confidence="high",
            check_reasons=[],
            best_score=hit.similarity,
        )
        if persist:
            _log_run_step(
                conn,
                run_id=run_id,
                item_id=qid,
                step="library_reuse",
                input_data={"question": question_text},
                output_data={"library_id": hit.id, "similarity": hit.similarity},
            )
            _save_draft(conn, run_id, outcome)
        return outcome

    best_score = res.chunks[0].score if res.chunks else 0.0
    if not res.chunks or best_score < min_ev:
        outcome = DraftOutcome(
            question_id=question_id,
            qid=qid,
            source="none",
            status="needs_input",
            short_answer=None,
            answer_text=None,
            explanation=None,
            citations=[],
            confidence="low",
            check_reasons=[f"best_score {best_score:.4f} < min_evidence {min_ev:.4f}"],
            best_score=best_score,
        )
        if persist:
            _log_run_step(
                conn,
                run_id=run_id,
                item_id=qid,
                step="below_evidence",
                input_data={"question": question_text, "min_evidence": min_ev},
                output_data={"best_score": best_score, "status": "needs_input"},
            )
            _save_draft(conn, run_id, outcome)
        return outcome

    model_client = llm or get_llm()
    user_prompt = f"Question: {question_text}\n\nPolicy passages:\n\n{_format_passages(res.chunks)}"
    raw_draft, usage = model_client.structured(
        DRAFT_SYSTEM_PROMPT,
        [{"role": "user", "content": user_prompt}],
        Draft,
    )
    assert isinstance(raw_draft, Draft)
    checked: CheckedDraft = check_draft(
        raw_draft,
        res.chunks,
        current_versions=_current_versions(conn),
    )

    source = "policies" if checked.status == "drafted" else "none"
    outcome = DraftOutcome(
        question_id=question_id,
        qid=qid,
        source=source,
        status=checked.status,
        short_answer=checked.short_answer,
        answer_text=checked.answer_text,
        explanation=checked.explanation,
        citations=checked.citations,
        confidence=checked.confidence,
        check_reasons=checked.reasons,
        best_score=best_score,
        usage=usage,
    )
    if persist:
        _log_run_step(
            conn,
            run_id=run_id,
            item_id=qid,
            step="draft",
            input_data={
                "question": question_text,
                "chunk_ids": [c.id for c in res.chunks],
                "best_score": best_score,
            },
            output_data={
                "status": checked.status,
                "short_answer": checked.short_answer,
                "confidence": checked.confidence,
                "citations": checked.citations,
                "reasons": checked.reasons,
            },
            usage=usage,
        )
        _save_draft(conn, run_id, outcome)
    return outcome
