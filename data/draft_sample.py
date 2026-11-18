"""Phase 4 acceptance script: draft 10 questions from Questionnaire A.

Uses `get_llm()` (configured via LLM_PROVIDER and LLM_MODEL in .env).

Usage: uv run python -m data.draft_sample
"""

from __future__ import annotations

import uuid

from qc.db import connect
from qc.draft import draft_question
from qc.embed import E5Embedder
from qc.llm import get_llm

SAMPLE_QIDS = [
    "A-001",
    "A-004",
    "A-009",
    "A-012",
    "A-015",
    "A-017",
    "A-019",
    "A-021",
    "A-040",
    "A-044",
]


def main() -> None:
    run_id = f"sample-{uuid.uuid4().hex[:8]}"
    llm = get_llm()
    emb = E5Embedder()
    with connect() as conn:
        rows_list = conn.execute(
            "SELECT q.qid, q.id, q.text FROM questions q "
            "JOIN questionnaires qn ON q.questionnaire_id = qn.id "
            "WHERE qn.name = 'acme_vendor_security_2026' AND q.qid = ANY(%s)",
            (SAMPLE_QIDS,),
        ).fetchall()
        by_qid = {r[0]: (r[1], r[2]) for r in rows_list}
        for qid in SAMPLE_QIDS:
            q_id, q_text = by_qid[qid]
            out = draft_question(
                conn,
                q_id,
                qid,
                q_text,
                run_id=run_id,
                llm=llm,
                embedder=emb,
                persist=False,
            )
            cites = ", ".join(
                f"{c['policy_id']} v{c['version']} ({c['section']})" for c in out.citations
            )
            print(
                f"{qid} [{out.status} | {out.confidence}]: "
                f"{out.answer_text or out.short_answer or '-'} | cites: {cites or 'none'}"
            )


if __name__ == "__main__":
    main()
