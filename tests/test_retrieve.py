"""Tests for hybrid retrieval, current-version isolation, and library reuse."""

from __future__ import annotations

from pathlib import Path

import pytest

from qc.embed import E5Embedder, FakeEmbedder, vector_literal
from qc.ingest import ingest_policy
from qc.retrieve import (
    build_or_tsquery,
    retrieve,
    search_policies,
    search_policies_fulltext,
)


def test_build_or_tsquery():
    assert build_or_tsquery("How often are encryption keys rotated?") == (
        "how OR often OR are OR encryption OR keys OR rotated"
    )


def test_only_current_version_returned_hybrid_and_fulltext(db_conn, tmp_path: Path):
    v1 = tmp_path / "ret-v1.md"
    v1.write_text(
        "---\npolicy_id: test-ret-policy\ntitle: Test Retrieval Policy\n"
        "version: 1\neffective_date: 2025-01-01\n---\n\n"
        "# Test Retrieval Policy\n\n## Retention\n\n"
        "Legacy rule zephyrcryptv1 applies for 999 days.\n",
        encoding="utf-8",
    )
    v2 = tmp_path / "ret-v2.md"
    v2.write_text(
        "---\npolicy_id: test-ret-policy\ntitle: Test Retrieval Policy\n"
        "version: 2\neffective_date: 2026-01-01\n---\n\n"
        "# Test Retrieval Policy\n\n## Retention\n\n"
        "Current rule zephyrcryptv2 applies for 30 days.\n",
        encoding="utf-8",
    )

    emb = FakeEmbedder()
    try:
        ingest_policy(db_conn, v1, embedder=emb)
        ingest_policy(db_conn, v2, embedder=emb)

        # Full-text search alone must never return non-current v1.
        ft_hits_v1 = search_policies_fulltext(db_conn, "zephyrcryptv1", top_k=10)
        assert all(not (h.policy_id == "test-ret-policy" and h.version == 1) for h in ft_hits_v1)

        # Hybrid search must never return non-current v1.
        q_vec = emb.embed_queries(["zephyrcryptv1"])[0]
        hyb_hits_v1 = search_policies(db_conn, "zephyrcryptv1", q_vec, top_k=10)
        assert all(not (h.policy_id == "test-ret-policy" and h.version == 1) for h in hyb_hits_v1)

        # Searching for v2 term returns v2.
        ft_hits_v2 = search_policies_fulltext(db_conn, "zephyrcryptv2", top_k=6)
        assert any(h.policy_id == "test-ret-policy" and h.version == 2 for h in ft_hits_v2)
    finally:
        db_conn.rollback()


def test_library_hit_above_threshold_returned_first(db_conn):
    emb = FakeEmbedder()
    question = "Do you encrypt customer data at rest? If so, with what algorithm?"
    q_vec = vector_literal(emb.embed_queries([question])[0])
    try:
        db_conn.execute(
            "INSERT INTO answer_library "
            "(question_text, embedding, short_answer, explanation, citations, policy_versions, "
            "approved_by, stale) "
            "VALUES (%s, %s::vector, %s, %s, '[]'::jsonb, '[]'::jsonb, 'tester', FALSE)",
            (question, q_vec, "yes", "AES-256 encryption at rest."),
        )

        res = retrieve(db_conn, question, embedder=emb, reuse_threshold=0.90)
        assert res.library_hit is not None
        assert res.library_hit.short_answer == "yes"
        assert res.library_hit.similarity >= 0.90
        assert res.chunks == []

        # Marking the entry stale must bypass library reuse.
        db_conn.execute(
            "UPDATE answer_library SET stale = TRUE WHERE question_text = %s",
            (question,),
        )
        res_stale = retrieve(db_conn, question, embedder=emb, reuse_threshold=0.90)
        assert res_stale.library_hit is None
    finally:
        db_conn.rollback()


@pytest.mark.slow
def test_e5_retrieval_on_seeded_data(db_conn):
    count = db_conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    if count == 0:
        pytest.skip("Run `make seed` first to populate chunks")

    emb = E5Embedder()
    res_a009 = retrieve(
        db_conn,
        "How long are customer data retained after contract termination?",
        embedder=emb,
        top_k=3,
    )
    assert res_a009.chunks
    assert res_a009.chunks[0].policy_id == "data-retention"
    assert res_a009.chunks[0].version == 3
    assert res_a009.chunks[0].section == "Customer data"

    res_a012 = retrieve(
        db_conn,
        "How often are encryption keys rotated?",
        embedder=emb,
        top_k=3,
    )
    assert res_a012.chunks
    assert res_a012.chunks[0].policy_id == "encryption-standard"
    assert res_a012.chunks[0].version == 2
    assert res_a012.chunks[0].section == "Key management"
