"""Hybrid retrieval over current policy chunks and the approved answer library."""

from __future__ import annotations

import re
from dataclasses import dataclass

import psycopg

from qc.config import get_settings
from qc.embed import Embedder, get_embedder, vector_literal

_WORD_RE = re.compile(r"[a-zA-Z0-9]+")


@dataclass(frozen=True)
class LibraryHit:
    id: int
    question_text: str
    short_answer: str | None
    explanation: str | None
    citations: list[dict]
    policy_versions: list[dict]
    similarity: float


@dataclass(frozen=True)
class ChunkHit:
    id: int
    policy_id: str
    version: int
    section: str
    text: str
    vec_score: float
    ft_score: float
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    library_hit: LibraryHit | None
    chunks: list[ChunkHit]


def build_or_tsquery(question: str) -> str:
    """Build an OR-joined websearch query string from alphanumeric tokens (decision D2)."""
    tokens = _WORD_RE.findall(question.lower())
    return " OR ".join(dict.fromkeys(tokens))


def search_library(
    conn: psycopg.Connection,
    query_vec: list[float],
    threshold: float | None = None,
) -> LibraryHit | None:
    thresh = get_settings().reuse_threshold if threshold is None else threshold
    vec_str = vector_literal(query_vec)
    row = conn.execute(
        "SELECT id, question_text, short_answer, explanation, citations, policy_versions, "
        "1.0 - (embedding <=> %s::vector) AS similarity "
        "FROM answer_library "
        "WHERE NOT stale AND embedding IS NOT NULL "
        "ORDER BY embedding <=> %s::vector ASC "
        "LIMIT 1",
        (vec_str, vec_str),
    ).fetchone()
    if not row:
        return None
    sim = float(row[6])
    if sim < thresh:
        return None
    return LibraryHit(
        id=row[0],
        question_text=row[1],
        short_answer=row[2],
        explanation=row[3],
        citations=row[4] or [],
        policy_versions=row[5] or [],
        similarity=sim,
    )


def search_policies(
    conn: psycopg.Connection,
    question: str,
    query_vec: list[float],
    top_k: int = 6,
) -> list[ChunkHit]:
    vec_str = vector_literal(query_vec)
    or_query = build_or_tsquery(question)
    rows = conn.execute(
        """
        WITH scored AS (
            SELECT
                c.id,
                c.policy_id,
                c.version,
                c.section,
                c.text,
                GREATEST(0.0, 1.0 - (c.embedding <=> %s::vector)) AS vec_score,
                CASE
                    WHEN %s = '' THEN 0.0
                    ELSE ts_rank_cd(c.tsv, websearch_to_tsquery('english', %s), 32)
                END AS ft_raw
            FROM chunks c
            JOIN policy_versions pv
              ON c.policy_id = pv.policy_id AND c.version = pv.version
            WHERE pv.is_current = TRUE
              AND c.embedding IS NOT NULL
        )
        SELECT
            id,
            policy_id,
            version,
            section,
            text,
            vec_score,
            ft_raw / (ft_raw + 1.0) AS ft_score,
            0.6 * vec_score + 0.4 * (ft_raw / (ft_raw + 1.0)) AS score
        FROM scored
        ORDER BY score DESC, id ASC
        LIMIT %s
        """,
        (vec_str, or_query, or_query, top_k),
    ).fetchall()
    return [
        ChunkHit(
            id=r[0],
            policy_id=r[1],
            version=r[2],
            section=r[3],
            text=r[4],
            vec_score=float(r[5]),
            ft_score=float(r[6]),
            score=float(r[7]),
        )
        for r in rows
    ]


def search_policies_fulltext(
    conn: psycopg.Connection,
    question: str,
    top_k: int = 6,
) -> list[ChunkHit]:
    """Full-text only search over current policy versions."""
    or_query = build_or_tsquery(question)
    if not or_query:
        return []
    rows = conn.execute(
        """
        SELECT
            c.id,
            c.policy_id,
            c.version,
            c.section,
            c.text,
            ts_rank_cd(c.tsv, websearch_to_tsquery('english', %s), 32) AS ft_raw
        FROM chunks c
        JOIN policy_versions pv
          ON c.policy_id = pv.policy_id AND c.version = pv.version
        WHERE pv.is_current = TRUE
          AND c.tsv @@ websearch_to_tsquery('english', %s)
        ORDER BY ft_raw DESC, c.id ASC
        LIMIT %s
        """,
        (or_query, or_query, top_k),
    ).fetchall()
    return [
        ChunkHit(
            id=r[0],
            policy_id=r[1],
            version=r[2],
            section=r[3],
            text=r[4],
            vec_score=0.0,
            ft_score=float(r[5]) / (float(r[5]) + 1.0),
            score=float(r[5]) / (float(r[5]) + 1.0),
        )
        for r in rows
    ]


def retrieve(
    conn: psycopg.Connection,
    question: str,
    *,
    embedder: Embedder | None = None,
    top_k: int = 6,
    reuse_threshold: float | None = None,
) -> RetrievalResult:
    emb = embedder or get_embedder()
    query_vec = emb.embed_queries([question])[0]
    lib_hit = search_library(conn, query_vec, threshold=reuse_threshold)
    if lib_hit is not None:
        return RetrievalResult(library_hit=lib_hit, chunks=[])
    chunks = search_policies(conn, question, query_vec, top_k=top_k)
    return RetrievalResult(library_hit=None, chunks=chunks)
