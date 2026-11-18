"""Tests for post-draft code checks and near-miss unanswerable fixtures."""

from __future__ import annotations

import pytest

from qc.checks import Draft, check_draft
from qc.llm import StubLLM
from qc.retrieve import ChunkHit


def _chunk(
    cid: int,
    policy_id: str = "encryption-standard",
    version: int = 2,
    section: str = "Data at rest",
    text: str = "AES-256 encryption at rest for databases, backups and object storage.",
) -> ChunkHit:
    return ChunkHit(
        id=cid,
        policy_id=policy_id,
        version=version,
        section=section,
        text=text,
        vec_score=0.85,
        ft_score=0.30,
        score=0.63,
    )


def test_citation_outside_retrieved_set_downgraded():
    draft = Draft(
        can_answer=True,
        short_answer="yes",
        explanation="Data is encrypted with AES-256.",
        citation_chunk_ids=[999],
        confidence="high",
    )
    checked = check_draft(draft, [_chunk(1)], current_versions={"encryption-standard": 2})
    assert checked.status == "needs_input"
    assert checked.citations == []
    assert any("not in retrieved chunks" in r for r in checked.reasons)


def test_old_version_citation_downgraded():
    draft = Draft(
        can_answer=True,
        short_answer="text",
        answer_text="Keys are rotated every 24 months.",
        explanation="Keys are rotated every 24 months.",
        citation_chunk_ids=[10],
        confidence="high",
    )
    old_chunk = _chunk(
        10, policy_id="encryption-standard", version=1, text="Rotated every 24 months."
    )
    checked = check_draft(draft, [old_chunk], current_versions={"encryption-standard": 2})
    assert checked.status == "needs_input"
    assert any("not current" in r for r in checked.reasons)


def test_can_answer_false_or_empty_citations_needs_input():
    d1 = Draft(can_answer=False, short_answer=None, citation_chunk_ids=[1], confidence="high")
    c1 = check_draft(d1, [_chunk(1)], current_versions={"encryption-standard": 2})
    assert c1.status == "needs_input"

    d2 = Draft(can_answer=True, short_answer="yes", citation_chunk_ids=[], confidence="high")
    c2 = check_draft(d2, [_chunk(1)], current_versions={"encryption-standard": 2})
    assert c2.status == "needs_input"


def test_more_than_two_policies_caps_confidence_at_medium():
    chunks = [
        _chunk(1, policy_id="p1", version=1, text="Fact 1."),
        _chunk(2, policy_id="p2", version=1, text="Fact 2."),
        _chunk(3, policy_id="p3", version=1, text="Fact 3."),
    ]
    draft = Draft(
        can_answer=True,
        short_answer="yes",
        explanation="Supported across three policies.",
        citation_chunk_ids=[1, 2, 3],
        confidence="high",
    )
    checked = check_draft(draft, chunks, current_versions={"p1": 1, "p2": 1, "p3": 1})
    assert checked.status == "drafted"
    assert checked.confidence == "medium"
    assert any(">2" in r for r in checked.reasons)


def test_number_not_in_passage_caps_confidence_at_low():
    chunk = _chunk(1, text="Backups are kept for 35 days.")
    draft = Draft(
        can_answer=True,
        short_answer="text",
        answer_text="Backups are kept for 90 days.",
        explanation="Backups are retained for 90 days.",
        citation_chunk_ids=[1],
        confidence="high",
    )
    checked = check_draft(draft, [chunk], current_versions={"encryption-standard": 2})
    assert checked.status == "drafted"
    assert checked.confidence == "low"
    assert any("90" in r for r in checked.reasons)


def test_number_present_in_passage_keeps_high_confidence():
    chunk = _chunk(1, text="AES-256 encryption at rest. Keys rotated every 12 months.")
    draft = Draft(
        can_answer=True,
        short_answer="text",
        answer_text="Keys are rotated every 12 months.",
        explanation="Encryption uses AES-256 and keys rotate every 12 months.",
        citation_chunk_ids=[1],
        confidence="high",
    )
    checked = check_draft(draft, [chunk], current_versions={"encryption-standard": 2})
    assert checked.status == "drafted"
    assert checked.confidence == "high"
    assert checked.reasons == []


@pytest.mark.parametrize(
    "question",
    [
        "Do you support customer-managed encryption keys (BYOK)?",
        "Do you allow customers to perform their own penetration tests?",
        "How many employees have production database access?",
        "Do you hold PCI DSS certification?",
    ],
)
def test_near_miss_unanswerable_fixtures(question: str):
    llm = StubLLM()
    raw, _ = llm.structured("system", [{"role": "user", "content": question}], Draft)
    assert isinstance(raw, Draft)
    checked = check_draft(raw, [_chunk(1)], current_versions={"encryption-standard": 2})
    assert checked.status == "needs_input"
