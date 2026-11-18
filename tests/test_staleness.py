"""Tests for answer library approval, staleness detection, and re-approval."""

from __future__ import annotations

from pathlib import Path

from qc.embed import FakeEmbedder, vector_literal
from qc.ingest import ingest_policy
from qc.library import count_stale, reapprove_library_entry, review_draft
from qc.retrieve import retrieve

V4_PATH = Path(__file__).parent.parent / "data" / "policies_updates" / "data-retention-v4.md"


def _insert_lib_entry(
    conn,
    emb: FakeEmbedder,
    question: str,
    short_answer: str,
    citations: list[dict],
    policy_versions: list[dict],
) -> int:
    from psycopg.types.json import Jsonb

    q_vec = vector_literal(emb.embed_queries([question])[0])
    row = conn.execute(
        "INSERT INTO answer_library "
        "(question_text, embedding, short_answer, explanation, citations, policy_versions, "
        "approved_by, stale) "
        "VALUES (%s, %s::vector, %s, %s, %s, %s, 'tester', FALSE) RETURNING id",
        (
            question,
            q_vec,
            short_answer,
            "Approved explanation.",
            Jsonb(citations),
            Jsonb(policy_versions),
        ),
    ).fetchone()
    return int(row[0])


def test_new_policy_version_flags_exact_dependent_entries(db_conn):
    emb = FakeEmbedder()
    try:
        id_ret = _insert_lib_entry(
            db_conn,
            emb,
            "How long are backups retained?",
            "35 days",
            [{"policy_id": "data-retention", "version": 3, "section": "Backups"}],
            [{"policy_id": "data-retention", "version": 3}],
        )
        id_both = _insert_lib_entry(
            db_conn,
            emb,
            "Are backups encrypted and how long are they kept?",
            "yes",
            [
                {"policy_id": "data-retention", "version": 3, "section": "Backups"},
                {"policy_id": "encryption-standard", "version": 2, "section": "Data at rest"},
            ],
            [
                {"policy_id": "data-retention", "version": 3},
                {"policy_id": "encryption-standard", "version": 2},
            ],
        )
        id_enc = _insert_lib_entry(
            db_conn,
            emb,
            "How often are encryption keys rotated?",
            "12 months",
            [{"policy_id": "encryption-standard", "version": 2, "section": "Key management"}],
            [{"policy_id": "encryption-standard", "version": 2}],
        )

        # Ingest data-retention v4 -> flags id_ret and id_both, leaves id_enc untouched.
        ingest_policy(db_conn, V4_PATH, embedder=emb)

        flags = dict(
            db_conn.execute(
                "SELECT id, stale FROM answer_library WHERE id = ANY(%s)",
                ([id_ret, id_both, id_enc],),
            ).fetchall()
        )
        assert flags == {id_ret: True, id_both: True, id_enc: False}
        assert count_stale(db_conn) == 2

        # Stale entry must not be reused by retrieval.
        res_stale = retrieve(
            db_conn, "How long are backups retained?", embedder=emb, reuse_threshold=0.90
        )
        assert res_stale.library_hit is None

        # Re-approve id_ret against v4 -> stale becomes False and reuse resumes.
        reapprove_library_entry(
            db_conn, id_ret, reviewer="faycal", short_answer="30 days", explanation="Kept 30 days."
        )
        row = db_conn.execute(
            "SELECT stale, policy_versions, short_answer FROM answer_library WHERE id = %s",
            (id_ret,),
        ).fetchone()
        assert row[0] is False
        assert row[1] == [{"policy_id": "data-retention", "version": 4}]
        assert row[2] == "30 days"

        res_fresh = retrieve(
            db_conn, "How long are backups retained?", embedder=emb, reuse_threshold=0.90
        )
        assert res_fresh.library_hit is not None
        assert res_fresh.library_hit.id == id_ret
    finally:
        db_conn.rollback()


def _insert_draft(conn, q_id: int, ans: str, exp: str, cites: list[dict], conf: str) -> int:
    from psycopg.types.json import Jsonb

    row = conn.execute(
        "INSERT INTO drafts "
        "(question_id, run_id, source, short_answer, explanation, citations, confidence, status) "
        "VALUES (%s, 'r1', 'policies', %s, %s, %s, %s, 'drafted') RETURNING id",
        (q_id, ans, exp, Jsonb(cites), conf),
    ).fetchone()
    return int(row[0])


def test_review_draft_approve_edit_reject(db_conn):
    emb = FakeEmbedder()
    q_row = db_conn.execute("SELECT id FROM questions LIMIT 1").fetchone()
    assert q_row is not None
    q_id = q_row[0]

    try:
        cites = [
            {"chunk_id": 1, "policy_id": "access-control", "version": 1, "section": "Authorization"}
        ]
        d1 = _insert_draft(db_conn, q_id, "yes", "RBAC.", cites, "high")
        d2 = _insert_draft(db_conn, q_id, "no", "Old.", cites, "medium")
        d3 = _insert_draft(db_conn, q_id, "yes", "Bad.", cites, "low")

        lib1 = review_draft(db_conn, d1, reviewer="faycal", action="approve", embedder=emb)
        lib2 = review_draft(
            db_conn,
            d2,
            reviewer="faycal",
            action="edit",
            final_answer="yes",
            final_explanation="Updated RBAC explanation.",
            embedder=emb,
        )
        lib3 = review_draft(db_conn, d3, reviewer="faycal", action="reject", embedder=emb)

        assert lib1 is not None
        assert lib2 is not None
        assert lib3 is None

        statuses = dict(
            db_conn.execute(
                "SELECT id, status FROM drafts WHERE id = ANY(%s)", ([d1, d2, d3],)
            ).fetchall()
        )
        assert statuses == {d1: "approved", d2: "edited", d3: "rejected"}
    finally:
        db_conn.rollback()
