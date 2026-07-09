from __future__ import annotations

import math
import re
import uuid
from datetime import date, datetime
from typing import Any

from paper_agent.config import get_settings
from paper_agent.memory.repository import MemoryRepository
from paper_agent.schemas import Paper


TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]+")


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text or "") if len(token) > 1}


def _clean_keywords(keywords: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        value = " ".join(str(keyword or "").strip().split())
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        cleaned.append(value)
        seen.add(key)
    return cleaned


def _extract_query_keywords(query: str) -> list[str]:
    phrases = [
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
    lowered = (query or "").lower()
    keywords = [phrase for phrase in phrases if phrase in lowered]
    keywords.extend(token.lower() for token in TOKEN_RE.findall(query or "") if len(token) > 2)
    return _clean_keywords(keywords)[:10]


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _paper_to_dict(paper: Any) -> dict[str, Any]:
    if isinstance(paper, Paper):
        data = paper.model_dump()
    elif hasattr(paper, "model_dump"):
        data = paper.model_dump()
    elif isinstance(paper, dict):
        data = dict(paper)
    else:
        data = {
            "paper_id": getattr(paper, "paper_id", "") or getattr(paper, "id", ""),
            "title": getattr(paper, "title", ""),
            "authors": getattr(paper, "authors", []),
            "abstract": getattr(paper, "abstract", ""),
            "published_date": getattr(paper, "published_date", "") or getattr(paper, "published", ""),
            "url": getattr(paper, "url", ""),
            "pdf_url": getattr(paper, "pdf_url", None),
            "source": getattr(paper, "source", ""),
            "citation_count": getattr(paper, "citation_count", None),
        }
    if data.get("paper") and isinstance(data["paper"], dict):
        data = {**data["paper"], **{key: value for key, value in data.items() if key != "paper"}}
    data["paper_id"] = str(data.get("paper_id") or data.get("id") or data.get("url") or data.get("title") or "")
    data["title"] = str(data.get("title") or "Untitled")
    data["authors"] = data.get("authors") or []
    data["abstract"] = str(data.get("abstract") or "")
    data["published_date"] = str(data.get("published_date") or data.get("published") or data.get("year") or "")
    data["url"] = str(data.get("url") or "")
    data["pdf_url"] = data.get("pdf_url") or data.get("pdf")
    data["source"] = str(data.get("source") or "")
    data["citation_count"] = data.get("citation_count", data.get("citations"))
    return data


def _keyword_match_score(text: str, keywords: list[str]) -> tuple[float, list[str]]:
    text_tokens = _tokens(text)
    matched: list[str] = []
    for keyword in keywords:
        keyword_tokens = _tokens(keyword)
        if keyword_tokens and keyword_tokens <= text_tokens:
            matched.append(keyword)
        elif keyword and keyword.lower() in (text or "").lower():
            matched.append(keyword)
    if not keywords:
        return 0.0, []
    return min(1.0, len(matched) / max(1, len(keywords))), _clean_keywords(matched)


def _recency_score(published_date: str) -> float:
    published = _parse_date(published_date)
    if published is None:
        return 0.5
    days_old = max(0, (date.today() - published).days)
    if days_old <= 30:
        return 1.0
    if days_old <= 180:
        return 0.85
    if days_old <= 365:
        return 0.65
    if days_old <= 730:
        return 0.4
    return 0.2


def _citation_score(citation_count: Any) -> float:
    if citation_count is None:
        return 0.3
    try:
        citations = max(0, int(citation_count))
    except (TypeError, ValueError):
        return 0.3
    return max(0.0, min(1.0, math.log1p(citations) / math.log1p(1000)))


def _quality_score(paper: dict[str, Any]) -> float:
    score = 0.25
    if paper.get("abstract"):
        score += 0.30
    if paper.get("url"):
        score += 0.20
    if paper.get("pdf_url"):
        score += 0.20
    if paper.get("authors"):
        score += 0.05
    return max(0.0, min(1.0, score))


class RecommenderAgent:
    def __init__(self, memory: MemoryRepository | None = None) -> None:
        settings = get_settings()
        self.memory = memory or MemoryRepository(settings.database_path)

    def recommend(
        self,
        user_id: str,
        query: str,
        candidate_papers: list[Any],
        top_k: int = 5,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        if not candidate_papers:
            return {
                "recommendations": [],
                "follow_up_recommendations": [],
                "message": "候选论文为空，暂时无法生成推荐。",
                "used_seen_fallback": False,
            }

        task = task_id or str(uuid.uuid4())
        profile = self.memory.get_user_profile(user_id)
        interests = profile.get("interests", [])
        interest_names = [item["interest_name"] for item in interests]
        interest_weights = {item["interest_name"].lower(): float(item["weight"]) for item in interests}
        query_keywords = _extract_query_keywords(query)
        seen_ids = self.memory.get_seen_paper_ids(user_id)

        scored = [
            self._score_paper(_paper_to_dict(paper), interest_names, interest_weights, query_keywords, seen_ids)
            for paper in candidate_papers
        ]
        scored.sort(key=lambda item: item["score"], reverse=True)

        unseen = [item for item in scored if not item["was_seen"]]
        seen = [item for item in scored if item["was_seen"]]
        selected = unseen[:top_k]
        used_seen_fallback = False
        if len(selected) < top_k and seen:
            used_seen_fallback = True
            selected.extend(seen[: top_k - len(selected)])

        selected_ids = {item["paper_id"] for item in selected}
        follow_up_pool = [item for item in unseen if item["paper_id"] not in selected_ids]
        follow_up = follow_up_pool[:3]

        self.memory.log_recommendations(user_id, task, [*selected, *follow_up])
        return {
            "recommendations": selected,
            "follow_up_recommendations": follow_up,
            "message": "推荐完成。",
            "used_seen_fallback": used_seen_fallback,
            "task_id": task,
        }

    def _score_paper(
        self,
        paper: dict[str, Any],
        interest_names: list[str],
        interest_weights: dict[str, float],
        query_keywords: list[str],
        seen_ids: set[str],
    ) -> dict[str, Any]:
        text = f"{paper.get('title', '')} {paper.get('abstract', '')}"
        profile_match_score, matched_interests = self._profile_match_score(text, interest_names, interest_weights)
        query_relevance_score, matched_query_keywords = _keyword_match_score(text, query_keywords)
        recency_score = _recency_score(paper.get("published_date", ""))
        citation_score = _citation_score(paper.get("citation_count"))
        was_seen = paper["paper_id"] in seen_ids or paper.get("url") in seen_ids
        novelty_score = 0.0 if was_seen else 1.0
        quality_score = _quality_score(paper)
        diversity_score = 0.5
        final_score = (
            0.30 * profile_match_score
            + 0.20 * query_relevance_score
            + 0.20 * recency_score
            + 0.15 * citation_score
            + 0.05 * novelty_score
            + 0.05 * quality_score
            + 0.05 * diversity_score
        )
        reason = (
            "推荐原因：该论文与您的兴趣方向 "
            f"{', '.join(matched_interests) or '暂无明显匹配'} 匹配，"
            f"并且与当前查询 {', '.join(matched_query_keywords) or ', '.join(query_keywords) or '暂无关键词'} 相关。"
        )
        return {
            **paper,
            "score": round(final_score, 6),
            "reason": reason,
            "matched_interests": matched_interests,
            "query_keywords": query_keywords,
            "matched_query_keywords": matched_query_keywords,
            "was_seen": was_seen,
            "score_breakdown": {
                "profile_match_score": round(profile_match_score, 6),
                "query_relevance_score": round(query_relevance_score, 6),
                "recency_score": round(recency_score, 6),
                "citation_score": round(citation_score, 6),
                "novelty_score": round(novelty_score, 6),
                "quality_score": round(quality_score, 6),
                "diversity_score": diversity_score,
                "final_score": round(final_score, 6),
            },
        }

    def _profile_match_score(
        self,
        text: str,
        interest_names: list[str],
        interest_weights: dict[str, float],
    ) -> tuple[float, list[str]]:
        text_tokens = _tokens(text)
        total_weight = sum(interest_weights.get(name.lower(), 0.0) for name in interest_names)
        matched_weight = 0.0
        matched: list[str] = []
        for name in interest_names:
            keyword_tokens = _tokens(name)
            is_match = bool(keyword_tokens and keyword_tokens <= text_tokens) or name.lower() in text.lower()
            if is_match:
                matched.append(name)
                matched_weight += interest_weights.get(name.lower(), 0.0)
        if not total_weight:
            return 0.0, []
        return min(1.0, matched_weight / total_weight), matched
