"""Tests for policy parsing (MD, PDF, DOCX), chunking, and idempotent ingestion."""

from __future__ import annotations

from pathlib import Path

from data.render import DATA, FORMATS, OUT_DIR, SRC_DIR, render_all
from qc.embed import FakeEmbedder
from qc.ingest import chunk_sections, ingest_policy, parse_file, parse_markdown
from qc.markdown import parse_policy


class _CountingEmbedder(FakeEmbedder):
    def __init__(self) -> None:
        self.passage_calls = 0

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        self.passage_calls += len(texts)
        return super().embed_passages(texts)


def test_rendered_section_names_match_source_markdown():
    render_all()
    for src in sorted(SRC_DIR.glob("*.md")):
        src_doc = parse_markdown(src)
        fmt = FORMATS[src_doc.policy_id]
        rendered = OUT_DIR / f"{src.stem}.{fmt}"
        parsed = parse_file(rendered)
        assert [name for name, _ in parsed.sections] == [name for name, _ in src_doc.sections], (
            f"Section mismatch for {rendered.name}"
        )
        assert parsed.title == src_doc.title
        assert len(parsed.sections) >= 3


def test_parse_markdown_extracts_metadata_and_sections():
    sample = DATA / "policies" / "encryption-standard-v2.md"
    parsed = parse_markdown(sample)
    raw = parse_policy(sample.read_text(encoding="utf-8"))
    assert parsed.policy_id == "encryption-standard"
    assert parsed.version == 2
    assert [n for n, _ in parsed.sections] == [n for n, _ in raw.sections]


def test_chunk_sections_splits_long_sections_on_paragraph_boundaries():
    paras = ["A" * 500, "B" * 500, "C" * 500]
    chunks = chunk_sections([("LongSection", paras)], max_chars=1100)
    assert len(chunks) == 2
    assert chunks[0].section == "LongSection"
    assert chunks[0].text == "A" * 500 + "\n\n" + "B" * 500
    assert chunks[1].text == "C" * 500


def test_ingest_versions_and_idempotent_hash_skip(db_conn, tmp_path: Path):
    v1 = tmp_path / "sample-v1.md"
    v1.write_text(
        "---\npolicy_id: test-ingest-policy\ntitle: Test Policy\n"
        "version: 1\neffective_date: 2025-01-01\n---\n\n"
        "# Test Policy\n\n## Alpha\n\nFirst version alpha text.\n",
        encoding="utf-8",
    )
    v2 = tmp_path / "sample-v2.md"
    v2.write_text(
        "---\npolicy_id: test-ingest-policy\ntitle: Test Policy\n"
        "version: 2\neffective_date: 2026-01-01\n---\n\n"
        "# Test Policy\n\n## Alpha\n\nSecond version alpha text.\n\n"
        "## Beta\n\nSecond version beta text.\n",
        encoding="utf-8",
    )

    emb = _CountingEmbedder()
    try:
        r1 = ingest_policy(db_conn, v1, embedder=emb)
        assert r1.chunks_total == 1
        assert r1.embedded == 1
        assert r1.skipped == 0

        r2 = ingest_policy(db_conn, v2, embedder=emb)
        assert r2.chunks_total == 2
        assert r2.embedded == 2
        assert emb.passage_calls == 3

        rows = db_conn.execute(
            "SELECT version, is_current FROM policy_versions "
            "WHERE policy_id = 'test-ingest-policy' ORDER BY version"
        ).fetchall()
        assert rows == [(1, False), (2, True)]

        # Re-ingesting unchanged v2 must skip all embeddings.
        r2_again = ingest_policy(db_conn, v2, embedder=emb)
        assert r2_again.embedded == 0
        assert r2_again.skipped == 2
        assert emb.passage_calls == 3
    finally:
        db_conn.rollback()
