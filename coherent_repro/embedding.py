"""Embedding utilities for COHERENT.

Primary model: sentence-transformers/all-mpnet-base-v2, 768 dimensions.
Fallback: deterministic hashing vectorizer for environments without the model.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable, List


def _l2_normalize(vec: List[float]) -> List[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


class Embedder:
    def __init__(self, model_name: str = "sentence-transformers/all-mpnet-base-v2", dim: int = 768):
        self.model_name = model_name
        self.dim = dim
        self._model = None
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._model = SentenceTransformer(model_name)
        except Exception:
            self._model = None

    def encode(self, texts: Iterable[str]) -> List[List[float]]:
        texts = list(texts)
        if self._model is not None:
            vectors = self._model.encode(texts, normalize_embeddings=True)
            return [list(map(float, v)) for v in vectors]
        return [self._hash_embed(t) for t in texts]

    def _hash_embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
        for tok in tokens:
            digest = hashlib.sha256(tok.encode()).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        return _l2_normalize(vec)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Vectors must have the same length")
    return sum(x * y for x, y in zip(a, b))
