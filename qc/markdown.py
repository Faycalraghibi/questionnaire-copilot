"""Minimal Markdown policy reader: YAML front matter, title and `##` sections.

Front matter is parsed here on purpose (no python-frontmatter dependency, decision D14).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class PolicyDoc:
    meta: dict
    title: str
    preamble: list[str] = field(default_factory=list)
    sections: list[tuple[str, list[str]]] = field(default_factory=list)  # (name, paragraphs)

    def section_text(self, name: str) -> str:
        for sec_name, paras in self.sections:
            if sec_name == name:
                return "\n\n".join(paras)
        raise KeyError(name)

    def full_text(self) -> str:
        parts = [self.title, *self.preamble]
        for name, paras in self.sections:
            parts.append(name)
            parts.extend(paras)
        return "\n\n".join(parts)


def split_front_matter(text: str) -> tuple[dict, str]:
    """Return (metadata, body). Raises ValueError when the front matter is missing."""
    text = text.replace("\r\n", "\n")
    match = _FRONT_MATTER.match(text)
    if not match:
        raise ValueError("missing YAML front matter")
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError("front matter must be a mapping")
    return meta, text[match.end() :]


def _paragraphs(lines: list[str]) -> list[str]:
    paras, buf = [], []
    for line in lines:
        if line.strip():
            buf.append(line.strip())
        elif buf:
            paras.append(" ".join(buf))
            buf = []
    if buf:
        paras.append(" ".join(buf))
    return paras


def parse_policy(text: str) -> PolicyDoc:
    meta, body = split_front_matter(text)
    title = meta.get("title", "")
    pre: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current: list[str] = pre
    for line in body.split("\n"):
        if line.startswith("## "):
            current = []
            sections.append((line[3:].strip(), current))
        elif line.startswith("# "):
            title = line[2:].strip()
        else:
            current.append(line)
    return PolicyDoc(
        meta=meta,
        title=title,
        preamble=_paragraphs(pre),
        sections=[(name, _paragraphs(lines)) for name, lines in sections],
    )
