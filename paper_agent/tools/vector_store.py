from __future__ import annotations

import math
import re
from collections import Counter

from paper_agent.schemas import Paper


TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_\-]+")


def embed_text(text: str) -> Counter[str]:
    return Counter(token.lower() for token in TOKEN_RE.findall(text or ""))


def cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(left[key] * right.get(key, 0) for key in left)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


class LocalVectorIndex:
    """Small dependency-free vector-like index for MVP memory matching."""

    def __init__(self) -> None:
        self._items: list[tuple[Paper, Counter[str]]] = []

    def add_paper(self, paper: Paper) -> None:
        self._items.append((paper, embed_text(f"{paper.title} {paper.abstract}")))

    def search(self, query: str, top_k: int = 5) -> list[tuple[Paper, float]]:
        query_vector = embed_text(query)
        scored = [(paper, cosine_similarity(query_vector, vector)) for paper, vector in self._items]
        return sorted(scored, key=lambda item: item[1], reverse=True)[:top_k]

