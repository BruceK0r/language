from __future__ import annotations

import re
from typing import Any

from paper_agent.config import get_settings
from paper_agent.memory.repository import MemoryRepository


PHRASE_PATTERNS = [
    "large language models",
    "llm agent",
    "multi-agent systems",
    "multi-agent",
    "retrieval-augmented generation",
    "retrieval augmented generation",
    "rag",
    "prompt engineering",
    "natural language processing",
    "multimodal learning",
    "computer vision",
    "recommendation systems",
    "information retrieval",
    "knowledge graphs",
    "agent memory",
    "ai safety",
    "trustworthy ai",
    "reinforcement learning",
]
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]{2,}")


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


class ProfileAgent:
    def __init__(self, memory: MemoryRepository | None = None) -> None:
        settings = get_settings()
        self.memory = memory or MemoryRepository(settings.database_path)

    def create_user_if_not_exists(self, user_id: str) -> None:
        self.memory.create_user_if_not_exists(user_id)

    def create_initial_profile(self, user_id: str, interests: list[str]) -> None:
        self.memory.create_initial_profile(user_id, interests)

    def get_profile(self, user_id: str) -> dict[str, Any]:
        return self.memory.get_user_profile(user_id)

    def extract_keywords_from_query(self, query: str) -> list[str]:
        lowered = (query or "").lower()
        keywords = [phrase for phrase in PHRASE_PATTERNS if phrase in lowered]
        keywords.extend(token.lower() for token in TOKEN_RE.findall(query or ""))
        stopwords = {"about", "with", "from", "that", "this", "care", "into", "paper", "papers"}
        return [keyword for keyword in _clean_keywords(keywords) if keyword.lower() not in stopwords][:10]

    def extract_keywords_from_vision(self, vision_result: dict) -> list[str]:
        keywords = [
            *(vision_result.get("recommendation_keywords") or []),
            *(vision_result.get("possible_related_topics") or []),
        ]
        if not keywords:
            keywords.extend(self.extract_keywords_from_query(str(vision_result.get("main_content") or "")))
        return _clean_keywords(keywords)[:10]

    def update_profile_from_query(
        self,
        user_id: str,
        query: str,
        extracted_keywords: list[str] | None = None,
    ) -> dict[str, Any]:
        keywords = _clean_keywords(extracted_keywords or self.extract_keywords_from_query(query))
        self.memory.update_profile_from_query(user_id, query, keywords)
        return {
            "updated_keywords": keywords,
            "profile": self.get_profile(user_id),
            "summary": self.summarize_profile(user_id),
        }

    def update_profile_from_image(self, user_id: str, vision_result: dict) -> dict[str, Any]:
        keywords = self.extract_keywords_from_vision(vision_result)
        enriched_result = {**vision_result, "recommendation_keywords": keywords}
        self.memory.update_profile_from_image(user_id, enriched_result)
        return {
            "updated_keywords": keywords,
            "profile": self.get_profile(user_id),
            "summary": self.summarize_profile(user_id),
        }

    def log_user_action(self, user_id: str, paper_id: str, action_type: str) -> None:
        self.memory.log_user_action(user_id, paper_id, action_type)

    def get_seen_paper_ids(self, user_id: str) -> set[str]:
        return self.memory.get_seen_paper_ids(user_id)

    def log_recommendations(self, user_id: str, task_id: str, papers: list[dict]) -> None:
        self.memory.log_recommendations(user_id, task_id, papers)

    def filter_unseen_papers(self, user_id: str, papers: list[dict]) -> list[dict]:
        return self.memory.filter_unseen_papers(user_id, papers)

    def summarize_profile(self, user_id: str) -> str:
        profile = self.get_profile(user_id)
        interests = profile.get("interests", [])[:5]
        if not interests:
            return f"Profile for {user_id}: no research interests have been recorded yet."
        pieces = [
            f"{item['interest_name']} ({item['weight']:.2f}, {item['percentage']:.1f}%)"
            for item in interests
        ]
        return f"Profile for {user_id}: top interests are " + ", ".join(pieces) + "."
