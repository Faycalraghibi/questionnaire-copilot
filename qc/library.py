"""Answer library: approval, reuse storage, staleness detection, and re-approval."""

from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb

from qc.embed import Embedder, get_embedder, vector_literal


def _extract_policy_versions(citations: list[dict]) -> list[dict]:
    pairs = sorted({(c["policy_id"], int(c["version"])) for c in citations})
    return [{"policy_id": pid, "version": ver} for pid, ver in pairs]


def mark_stale_for_policy(conn: psycopg.Connection, policy_id: str, new_version: int) -> int:
    """Flag non-stale library entries that relied on an older version of `policy_id`."""
    cur = conn.execute(
        """
        UPDATE answer_library
        SET stale = TRUE
        WHERE NOT stale
          AND EXISTS (
              SELECT 1
              FROM jsonb_array_elements(policy_versions) AS pv
              WHERE pv->>'policy_id' = %s
                AND (pv->>'version')::int < %s
          )
        """,
        (policy_id, new_version),
    )
    return cur.rowcount


def review_draft(
    conn: psycopg.Connection,
    draft_id: int,
    *,
    reviewer: str,
    action: str,
    final_answer: str | None = None,
    final_explanation: str | None = None,
    final_citations: list[dict] | None = None,
    embedder: Embedder | None = None,
) -> int | None:
    """Record a review action (`approve`, `edit`, `reject`) and update the answer library."""
    row = conn.execute(
        """
        SELECT d.short_answer, d.explanation, d.citations, q.text
        FROM drafts d
        JOIN questions q ON d.question_id = q.id
        WHERE d.id = %s
        """,
        (draft_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Draft {draft_id} not found")

    orig_answer, orig_explanation, orig_citations, question_text = row
    norm_action = action.lower()
    if norm_action in ("reject", "rejected"):
        conn.execute(
            "INSERT INTO reviews (draft_id, reviewer, action, final_answer, final_explanation) "
            "VALUES (%s, %s, 'rejected', %s, %s)",
            (draft_id, reviewer, final_answer, final_explanation),
        )
        conn.execute("UPDATE drafts SET status = 'rejected' WHERE id = %s", (draft_id,))
        return None

    is_edit = norm_action in ("edit", "edited")
    new_status = "edited" if is_edit else "approved"
    ans = final_answer if final_answer is not None else orig_answer
    exp = final_explanation if final_explanation is not None else orig_explanation
    cites = final_citations if final_citations is not None else (orig_citations or [])

    conn.execute(
        "INSERT INTO reviews (draft_id, reviewer, action, final_answer, final_explanation) "
        "VALUES (%s, %s, %s, %s, %s)",
        (draft_id, reviewer, new_status, ans, exp),
    )
    conn.execute(
        "UPDATE drafts SET status = %s, short_answer = %s, explanation = %s, citations = %s "
        "WHERE id = %s",
        (new_status, ans, exp, Jsonb(cites), draft_id),
    )

    emb = embedder or get_embedder()
    q_vec = vector_literal(emb.embed_queries([question_text])[0])
    policy_versions = _extract_policy_versions(cites)

    lib_row = conn.execute(
        "INSERT INTO answer_library "
        "(question_text, embedding, short_answer, explanation, citations, policy_versions, "
        "approved_by, stale) "
        "VALUES (%s, %s::vector, %s, %s, %s, %s, %s, FALSE) "
        "RETURNING id",
        (question_text, q_vec, ans, exp, Jsonb(cites), Jsonb(policy_versions), reviewer),
    ).fetchone()
    assert lib_row is not None
    return int(lib_row[0])


def reapprove_library_entry(
    conn: psycopg.Connection,
    library_id: int,
    *,
    reviewer: str,
    short_answer: str | None = None,
    explanation: str | None = None,
) -> None:
    """Re-approve a stale library entry against current policy versions."""
    row = conn.execute(
        "SELECT short_answer, explanation, citations FROM answer_library WHERE id = %s",
        (library_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Library entry {library_id} not found")

    orig_ans, orig_exp, orig_cites = row
    current_vers = dict(
        conn.execute(
            "SELECT policy_id, version FROM policy_versions WHERE is_current = TRUE"
        ).fetchall()
    )

    updated_cites = []
    for c in orig_cites or []:
        pid = c["policy_id"]
        cur_ver = current_vers.get(pid, c["version"])
        updated_cites.append({**c, "version": cur_ver})

    updated_pvs = _extract_policy_versions(updated_cites)
    conn.execute(
        "UPDATE answer_library "
        "SET short_answer = %s, explanation = %s, citations = %s, policy_versions = %s, "
        "approved_by = %s, approved_at = now(), stale = FALSE "
        "WHERE id = %s",
        (
            short_answer if short_answer is not None else orig_ans,
            explanation if explanation is not None else orig_exp,
            Jsonb(updated_cites),
            Jsonb(updated_pvs),
            reviewer,
            library_id,
        ),
    )


def count_stale(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT count(*) FROM answer_library WHERE stale = TRUE").fetchone()
    return int(row[0]) if row else 0
