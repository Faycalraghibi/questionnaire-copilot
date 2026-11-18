"""Tests proving below-evidence-threshold questions never call the model."""

from __future__ import annotations

from qc.draft import draft_question
from qc.embed import FakeEmbedder
from qc.llm import StubLLM


def test_below_evidence_threshold_never_calls_model(db_conn):
    row = db_conn.execute(
        "SELECT q.id, q.qid, q.text FROM questions q "
        "JOIN questionnaires qn ON q.questionnaire_id = qn.id "
        "WHERE qn.name = 'acme_vendor_security_2026' AND q.qid = 'A-015'"
    ).fetchone()
    if row is None:
        raise AssertionError("Seeded question A-015 not found; run make seed")

    llm = StubLLM()
    emb = FakeEmbedder()
    try:
        outcome = draft_question(
            db_conn,
            row[0],
            row[1],
            row[2],
            run_id="test-below-ev",
            llm=llm,
            embedder=emb,
            min_evidence=0.99,
            persist=False,
        )
        assert outcome.status == "needs_input"
        assert outcome.source == "none"
        assert len(llm.calls) == 0
    finally:
        db_conn.rollback()
