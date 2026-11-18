"""Policy ingestion: parse MD, PDF, DOCX -> sections -> chunks -> embeddings."""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
import psycopg
from docx import Document

from qc.config import get_settings
from qc.embed import Embedder, get_embedder, vector_literal
from qc.library import mark_stale_for_policy
from qc.markdown import parse_policy


@dataclass
class ParsedPolicy:
    policy_id: str | None
    title: str
    version: int | None
    effective_date: dt.date | None
    preamble: list[str] = field(default_factory=list)
    sections: list[tuple[str, list[str]]] = field(default_factory=list)


@dataclass(frozen=True)
class ChunkSpec:
    section: str
    text: str
    text_hash: str


@dataclass(frozen=True)
class IngestResult:
    policy_id: str
    version: int
    chunks_total: int
    embedded: int
    skipped: int


def compute_chunk_hash(section: str, text: str) -> str:
    return hashlib.sha256(f"{section}\0{text}".encode()).hexdigest()


def parse_markdown(path: Path) -> ParsedPolicy:
    doc = parse_policy(path.read_text(encoding="utf-8"))
    raw_date = doc.meta.get("effective_date")
    eff_date = (
        raw_date
        if isinstance(raw_date, dt.date)
        else (dt.date.fromisoformat(str(raw_date)) if raw_date else None)
    )
    return ParsedPolicy(
        policy_id=doc.meta.get("policy_id"),
        title=doc.title,
        version=int(doc.meta["version"]) if "version" in doc.meta else None,
        effective_date=eff_date,
        preamble=doc.preamble,
        sections=doc.sections,
    )


def _group_pdf_lines(words: list[dict], y_tol: float = 3.0) -> list[list[dict]]:
    if not words:
        return []
    ordered = sorted(words, key=lambda w: (float(w["top"]), float(w["x0"])))
    lines: list[list[dict]] = [[ordered[0]]]
    for w in ordered[1:]:
        if abs(float(w["top"]) - float(lines[-1][0]["top"])) <= y_tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    for line in lines:
        line.sort(key=lambda w: float(w["x0"]))
    return lines


def _is_pdf_section_heading(line: list[dict]) -> bool:
    """Match data/render.py SectionHeading style: bold and 14pt."""
    return all(
        "Bold" in str(w.get("fontname", "")) and abs(float(w.get("size", 0)) - 14.0) <= 0.5
        for w in line
    )


def _is_pdf_title(line: list[dict]) -> bool:
    return all(float(w.get("size", 0)) >= 17.0 for w in line)


def _lines_to_paragraphs(lines: list[tuple[float, str]], gap_threshold: float = 15.0) -> list[str]:
    if not lines:
        return []
    paras: list[str] = []
    buf: list[str] = [lines[0][1]]
    prev_top = lines[0][0]
    for top, text in lines[1:]:
        if top < prev_top or (top - prev_top) > gap_threshold:
            paras.append(" ".join(buf))
            buf = [text]
        else:
            buf.append(text)
        prev_top = top
    if buf:
        paras.append(" ".join(buf))
    return paras


def parse_pdf(path: Path) -> ParsedPolicy:
    title = ""
    preamble_lines: list[tuple[float, str]] = []
    sections_raw: list[tuple[str, list[tuple[float, str]]]] = []
    current_lines = preamble_lines

    with pdfplumber.open(path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            words = page.extract_words(extra_attrs=["fontname", "size"])
            for line in _group_pdf_lines(words):
                text = " ".join(w["text"] for w in line).strip()
                if not text:
                    continue
                top = float(line[0]["top"]) + page_idx * 10000.0
                if not title and _is_pdf_title(line):
                    title = text
                    continue
                if _is_pdf_section_heading(line):
                    current_lines = []
                    sections_raw.append((text, current_lines))
                else:
                    current_lines.append((top, text))

    return ParsedPolicy(
        policy_id=None,
        title=title or path.stem,
        version=None,
        effective_date=None,
        preamble=_lines_to_paragraphs(preamble_lines),
        sections=[(name, _lines_to_paragraphs(lines)) for name, lines in sections_raw],
    )


def parse_docx(path: Path) -> ParsedPolicy:
    doc = Document(str(path))
    title = ""
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current = preamble

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        style_name = p.style.name if p.style else ""
        if style_name == "Title" and not title:
            title = text
        elif style_name == "Heading 2":
            current = []
            sections.append((text, current))
        else:
            current.append(text)

    return ParsedPolicy(
        policy_id=None,
        title=title or path.stem,
        version=None,
        effective_date=None,
        preamble=preamble,
        sections=sections,
    )


def parse_file(path: Path) -> ParsedPolicy:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return parse_markdown(path)
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix == ".docx":
        return parse_docx(path)
    raise ValueError(f"Unsupported policy file type: {path.suffix}")


def chunk_sections(
    sections: list[tuple[str, list[str]]],
    max_chars: int | None = None,
) -> list[ChunkSpec]:
    limit = max_chars or get_settings().chunk_max_chars
    chunks: list[ChunkSpec] = []
    for section, paras in sections:
        clean_paras = [p.strip() for p in paras if p.strip()]
        if not clean_paras:
            continue
        buf: list[str] = []
        buf_len = 0
        for para in clean_paras:
            added_len = len(para) + (2 if buf else 0)
            if buf and (buf_len + added_len) > limit:
                text = "\n\n".join(buf)
                chunks.append(ChunkSpec(section, text, compute_chunk_hash(section, text)))
                buf = [para]
                buf_len = len(para)
            else:
                buf.append(para)
                buf_len += added_len
        if buf:
            text = "\n\n".join(buf)
            chunks.append(ChunkSpec(section, text, compute_chunk_hash(section, text)))
    return chunks


def _refresh_current_version(conn: psycopg.Connection, policy_id: str) -> int | None:
    row = conn.execute(
        "SELECT MAX(version) FROM policy_versions WHERE policy_id = %s", (policy_id,)
    ).fetchone()
    if not row or row[0] is None:
        return None
    latest_ver = int(row[0])
    conn.execute(
        "UPDATE policy_versions SET is_current = FALSE "
        "WHERE policy_id = %s AND is_current AND version <> %s",
        (policy_id, latest_ver),
    )
    conn.execute(
        "UPDATE policy_versions SET is_current = TRUE WHERE policy_id = %s AND version = %s",
        (policy_id, latest_ver),
    )
    return latest_ver


def ingest_policy(
    conn: psycopg.Connection,
    path: Path,
    *,
    policy_id: str | None = None,
    title: str | None = None,
    version: int | None = None,
    effective_date: dt.date | None = None,
    source_file: str | None = None,
    embedder: Embedder | None = None,
) -> IngestResult:
    parsed = parse_file(path)
    pid = policy_id or parsed.policy_id
    ver = version if version is not None else parsed.version
    eff = effective_date or parsed.effective_date
    ptitle = title or parsed.title
    if not pid or ver is None or eff is None:
        raise ValueError(f"Missing policy_id, version, or effective_date for {path}")

    src = source_file or path.as_posix()
    conn.execute(
        "INSERT INTO policies (policy_id, title) VALUES (%s, %s) "
        "ON CONFLICT (policy_id) DO UPDATE SET title = EXCLUDED.title",
        (pid, ptitle),
    )
    conn.execute(
        "INSERT INTO policy_versions (policy_id, version, effective_date, source_file, is_current) "
        "VALUES (%s, %s, %s, %s, FALSE) "
        "ON CONFLICT (policy_id, version) DO UPDATE SET "
        "effective_date = EXCLUDED.effective_date, source_file = EXCLUDED.source_file",
        (pid, ver, eff, src),
    )
    latest_ver = _refresh_current_version(conn, pid)
    if latest_ver is not None:
        mark_stale_for_policy(conn, pid, latest_ver)

    specs = chunk_sections(parsed.sections)
    existing = conn.execute(
        "SELECT section, text_hash, embedding::text FROM chunks "
        "WHERE policy_id = %s AND version = %s ORDER BY id",
        (pid, ver),
    ).fetchall()

    if [(r[0], r[1]) for r in existing] == [(c.section, c.text_hash) for c in specs] and all(
        r[2] is not None for r in existing
    ):
        return IngestResult(pid, ver, len(specs), embedded=0, skipped=len(specs))

    cached_vecs = {(r[0], r[1]): r[2] for r in existing if r[2] is not None}
    to_embed_idx = [i for i, c in enumerate(specs) if (c.section, c.text_hash) not in cached_vecs]

    new_vecs: dict[int, str] = {}
    if to_embed_idx:
        emb = embedder or get_embedder()
        texts = [f"{specs[i].section}: {specs[i].text}" for i in to_embed_idx]
        vectors = emb.embed_passages(texts)
        for idx, vec in zip(to_embed_idx, vectors, strict=True):
            new_vecs[idx] = vector_literal(vec)

    conn.execute("DELETE FROM chunks WHERE policy_id = %s AND version = %s", (pid, ver))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO chunks (policy_id, version, section, text, text_hash, embedding) "
            "VALUES (%s, %s, %s, %s, %s, %s::vector)",
            [
                (
                    pid,
                    ver,
                    c.section,
                    c.text,
                    c.text_hash,
                    cached_vecs.get((c.section, c.text_hash)) or new_vecs[i],
                )
                for i, c in enumerate(specs)
            ],
        )

    return IngestResult(
        pid,
        ver,
        len(specs),
        embedded=len(to_embed_idx),
        skipped=len(specs) - len(to_embed_idx),
    )
