"""Text embeddings: local multilingual-e5-small (384 dims) and a deterministic fake for tests."""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from qc.config import get_settings

EMBED_DIM = 384
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...
    def embed_queries(self, texts: list[str]) -> list[list[float]]: ...


def vector_literal(vec: list[float]) -> str:
    """Format a float vector as a pgvector literal."""
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


class E5Embedder:
    """Local sentence-transformers embedder for intfloat/multilingual-e5-small."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or get_settings().embed_model

    @property
    def _model(self):
        return _load_e5_model(self.model_name)

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        prefixed = [f"passage: {t}" for t in texts]
        vectors = self._model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        prefixed = [f"query: {t}" for t in texts]
        vectors = self._model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]


@lru_cache(maxsize=2)
def _load_e5_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


class FakeEmbedder:
    """Deterministic 384-dim unit-norm bag-of-words projection for offline unit tests."""

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * EMBED_DIM
        tokens = _TOKEN_RE.findall(text.lower())
        if not tokens:
            vec[0] = 1.0
            return vec
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % EMBED_DIM
            sign = 1.0 if (digest[4] & 1) == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0.0:
            vec[0] = 1.0
            return vec
        return [x / norm for x in vec]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(f"passage {t}") for t in texts]

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(f"query {t}") for t in texts]


def get_embedder(provider: str | None = None) -> Embedder:
    selected = (provider or get_settings().embed_provider).lower()
    if selected == "fake":
        return FakeEmbedder()
    if selected == "e5":
        return E5Embedder()
    raise ValueError(f"Unknown embed_provider: {selected}")
