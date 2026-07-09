from __future__ import annotations

from typing import Any


class CriticAgent:
    def __init__(self, llm_provider: Any | None = None) -> None:
        self.llm = llm_provider

    def review(
        self,
        summaries: list[dict[str, Any]],
        source_texts: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        reviewed: list[dict[str, Any]] = []
        for summary in summaries:
            reviewed.append(
                {
                    **summary,
                    "critic_skipped": True,
                    "critic_note": "未启用独立事实审查模型，保留基于 abstract 的保守摘要。",
                }
            )
        return reviewed
