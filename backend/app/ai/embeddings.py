"""EmbeddingProvider interface. Default: local feature-hashing embeddings (no downloads, deterministic)."""

import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from app.config import get_settings
from app.textnorm import normalize

_STOP = frozenset(
    "a al algo como con de del el en es esta este esto ha hay la las lo los mas me mi muy no nos o para pero por que se si sin su sus te tu un una uno y ya le les ni".split()
)


class EmbeddingProvider(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]: ...


class HashingEmbeddingProvider:
    """Signed feature hashing over word unigrams, bigrams and character 4-grams, L2-normalized."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def _bucket(self, feature: str) -> tuple[int, float]:
        h = hashlib.blake2b(feature.encode(), digest_size=8).digest()
        n = int.from_bytes(h, "little")
        return n % self.dim, 1.0 if (n >> 63) & 1 else -1.0

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        words = [w for w in re.findall(r"[a-zñ0-9]+", normalize(text)) if w not in _STOP]
        feats: list[tuple[str, float]] = [(f"w:{w}", 1.0) for w in words]
        feats += [(f"b:{a}_{b}", 0.7) for a, b in zip(words, words[1:], strict=False)]
        for w in words:
            padded = f"_{w}_"
            feats += [(f"c:{padded[i:i + 4]}", 0.35) for i in range(max(1, len(padded) - 3))]
        for feat, weight in feats:
            idx, sign = self._bucket(feat)
            vec[idx] += sign * weight
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


@lru_cache
def get_embedder() -> EmbeddingProvider:
    s = get_settings()
    return HashingEmbeddingProvider(s.embedding_dim)


def embed(text: str) -> list[float]:
    return get_embedder().embed(text or "")
