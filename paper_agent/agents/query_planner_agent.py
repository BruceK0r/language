from __future__ import annotations

import re
from typing import Any


PHRASES = [
    "large language models",
    "llm agent",
    "multi-agent systems",
    "multi-agent",
    "retrieval-augmented generation",
    "retrieval augmented generation",
    "agent memory",
    "information retrieval",
    "recommendation systems",
    "computer vision",
    "rag",
]
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]{2,}")


def _clean(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = " ".join(str(item or "").strip().split())
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        cleaned.append(value)
        seen.add(key)
    return cleaned


class QueryPlannerAgent:
    def __init__(self, llm_provider: Any | None = None) -> None:
        self.llm = llm_provider

    def plan(self, query: str, top_k: int = 5) -> dict[str, Any]:
        fallback = self._rule_plan(query, top_k=top_k)
        if self.llm is None or not hasattr(self.llm, "parse_request"):
            return fallback
        try:
            parsed = self.llm.parse_request(query, top_k=top_k, time_range=fallback["time_range"])
        except Exception:
            return fallback
        keywords = parsed.get("query_terms") if isinstance(parsed, dict) else None
        if keywords:
            fallback["keywords"] = _clean([*fallback["keywords"], *(str(item) for item in keywords)])[:10]
        if isinstance(parsed, dict) and parsed.get("top_k"):
            fallback["top_k"] = max(1, min(20, int(parsed["top_k"])))
        return fallback

    def _rule_plan(self, query: str, top_k: int) -> dict[str, Any]:
        lowered = (query or "").lower()
        keywords = [phrase for phrase in PHRASES if phrase in lowered]
        keywords.extend(token.lower() for token in TOKEN_RE.findall(query or "") if token.lower() not in {"find", "about", "papers", "recent"})
        return {
            "task_type": "paper_recommendation",
            "keywords": _clean(keywords)[:10] or [query],
            "time_range": self._parse_time_range(query),
            "top_k": max(1, min(20, int(top_k or 5))),
            "preference": "application-oriented",
        }

    def _parse_time_range(self, query: str) -> str:
        text = (query or "").lower()
        if "last_90" in text or "90 days" in text or "three months" in text or "三个月" in text:
            return "last_90_days"
        if "last_30" in text or "30 days" in text or "one month" in text or "一个月" in text:
            return "last_30_days"
        return "last_180_days"
