"""Tests for evaluation metrics, key-phrase alternatives (D24), and report generation."""

from __future__ import annotations

from pathlib import Path

from qc.draft import DraftOutcome
from qc.embed import FakeEmbedder
from qc.evaluate import check_answer_correct, check_citation_correct, phrase_in, run_evaluation
from qc.llm import StubLLM


def test_phrase_alternatives_d24():
    assert phrase_in("once a year | annual", "Policies are reviewed on an annual basis.")
    assert phrase_in("once a year | annual", "Policies are reviewed once a year.")
    assert not phrase_in("once a year | annual", "Policies are reviewed every 2 years.")


def test_check_answer_and_citation_correct():
    truth = {
        "short_answer": "yes",
        "key_phrases": ["AES-256"],
        "forbidden_phrases": ["90 days"],
        "sources": [{"policy_id": "encryption-standard", "version": 2, "section": "Data at rest"}],
    }
    good = DraftOutcome(
        question_id=1,
        qid="A-001",
        source="policies",
        status="drafted",
        short_answer="yes",
        answer_text=None,
        explanation="Customer data is encrypted with AES-256.",
        citations=[{"policy_id": "encryption-standard", "version": 2, "section": "Data at rest"}],
        confidence="high",
        check_reasons=[],
        best_score=0.75,
    )
    assert check_answer_correct(good, truth) == (True, None)
    assert check_citation_correct(good, truth) == (True, None)

    bad_short = DraftOutcome(**{**good.__dict__, "short_answer": "no"})
    assert check_answer_correct(bad_short, truth)[0] is False


def test_run_evaluation_offline_stub(db_conn, tmp_path: Path):
    class _NoCommitConn:
        def __init__(self, inner):
            self._inner = inner

        def commit(self):
            pass

        def __getattr__(self, name):
            return getattr(self._inner, name)

    report_path = tmp_path / "report.md"
    try:
        res = run_evaluation(
            _NoCommitConn(db_conn),  # type: ignore[arg-type]
            llm=StubLLM(),
            embedder=FakeEmbedder(),
            report_path=report_path,
        )
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "Questionnaire A (calibration set" in content
        assert "Questionnaire B (held-out" in content
        assert "Staleness Check" in content
        assert res["staleness"]["rate"] == 1.0
    finally:
        db_conn.rollback()
