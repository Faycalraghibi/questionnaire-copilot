"""Deterministic post-draft code checks (spec 7.5)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from qc.retrieve import ChunkHit

_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_CONF_RANK = {"low": 0, "medium": 1, "high": 2}


class Draft(BaseModel):
    can_answer: bool
    short_answer: Literal["yes", "no", "partially", "text"] | None
    answer_text: str | None = None
    explanation: str | None = None
    citation_chunk_ids: list[int] = []
    confidence: Literal["high", "medium", "low"] = "medium"


@dataclass
class CheckedDraft:
    status: Literal["drafted", "needs_input"]
    short_answer: str | None
    answer_text: str | None
    explanation: str | None
    citations: list[dict]
    confidence: Literal["high", "medium", "low"]
    reasons: list[str] = field(default_factory=list)


def _cap_confidence(
    current: str, ceiling: Literal["high", "medium", "low"]
) -> Literal["high", "medium", "low"]:
    if _CONF_RANK[current] > _CONF_RANK[ceiling]:
        return ceiling
    return current  # type: ignore[return-value]


def check_draft(
    draft: Draft,
    retrieved_chunks: list[ChunkHit],
    *,
    current_versions: dict[str, int] | None = None,
) -> CheckedDraft:
    """Validate citations, current versions, and confidence rules on a model Draft."""
    by_id = {c.id: c for c in retrieved_chunks}
    reasons: list[str] = []

    if not draft.can_answer:
        reasons.append("model set can_answer=false")
        return CheckedDraft(
            status="needs_input",
            short_answer=None,
            answer_text=None,
            explanation=draft.explanation,
            citations=[],
            confidence="low",
            reasons=reasons,
        )

    if not draft.citation_chunk_ids:
        reasons.append("no citations provided")
        return CheckedDraft(
            status="needs_input",
            short_answer=None,
            answer_text=None,
            explanation=draft.explanation,
            citations=[],
            confidence="low",
            reasons=reasons,
        )

    cited_chunks: list[ChunkHit] = []
    for cid in draft.citation_chunk_ids:
        chunk = by_id.get(cid)
        if chunk is None:
            reasons.append(f"cited chunk_id {cid} not in retrieved chunks")
            return CheckedDraft(
                status="needs_input",
                short_answer=None,
                answer_text=None,
                explanation=None,
                citations=[],
                confidence="low",
                reasons=reasons,
            )
        if current_versions is not None and chunk.version != current_versions.get(chunk.policy_id):
            reasons.append(
                f"cited {chunk.policy_id} v{chunk.version} is not current "
                f"(current v{current_versions.get(chunk.policy_id)})"
            )
            return CheckedDraft(
                status="needs_input",
                short_answer=None,
                answer_text=None,
                explanation=None,
                citations=[],
                confidence="low",
                reasons=reasons,
            )
        cited_chunks.append(chunk)

    confidence: Literal["high", "medium", "low"] = draft.confidence
    distinct_policies = {c.policy_id for c in cited_chunks}
    if len(distinct_policies) > 2:
        confidence = _cap_confidence(confidence, "medium")
        reasons.append(f"cited {len(distinct_policies)} policies (>2); confidence capped at medium")

    passage_numbers = set(_NUMBER_RE.findall("\n".join(c.text for c in cited_chunks)))
    answer_blob = " ".join(p for p in [draft.answer_text, draft.explanation] if p)
    answer_numbers = set(_NUMBER_RE.findall(answer_blob))
    extra_numbers = answer_numbers - passage_numbers
    if extra_numbers:
        confidence = _cap_confidence(confidence, "low")
        reasons.append(
            f"number(s) {sorted(extra_numbers)} not in cited passages; confidence capped at low"
        )

    citations = [
        {
            "chunk_id": c.id,
            "policy_id": c.policy_id,
            "version": c.version,
            "section": c.section,
        }
        for c in cited_chunks
    ]

    return CheckedDraft(
        status="drafted",
        short_answer=draft.short_answer,
        answer_text=draft.answer_text,
        explanation=draft.explanation,
        citations=citations,
        confidence=confidence,
        reasons=reasons,
    )
