from __future__ import annotations

import re
from typing import Any

from paper_agent.schemas import Paper


def _paper_to_dict(paper: Any) -> dict[str, Any]:
    if isinstance(paper, Paper):
        return paper.model_dump()
    if hasattr(paper, "model_dump"):
        return paper.model_dump()
    return dict(paper)


def _sentences(text: str, limit: int = 3) -> list[str]:
    chunks = re.split(r"(?<=[.!?。！？])\s+", (text or "").strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()][:limit]


def _short_text(text: str, max_length: int = 220) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[:max_length].rstrip()}..."


class ReaderAgent:
    def __init__(self, llm_provider: Any | None = None) -> None:
        self.llm = llm_provider

    def enrich_recommendation_reasons(
        self,
        papers: list[Any],
        query: str,
        purpose: str = "top",
    ) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for item in papers:
            paper = _paper_to_dict(item)
            fallback = str(paper.get("reason") or "该论文与当前查询或用户画像存在关键词匹配。")
            reason = self._generate_recommendation_reason(paper, query=query, purpose=purpose, fallback=fallback)
            paper["reason"] = reason
            paper["llm_reason"] = reason
            enriched.append(paper)
        return enriched

    def _generate_recommendation_reason(
        self,
        paper: dict[str, Any],
        query: str,
        purpose: str,
        fallback: str,
    ) -> str:
        if self.llm is None or not hasattr(self.llm, "chat"):
            return fallback
        prompt_kind = "Top-K 主推荐" if purpose == "top" else "额外拓展推荐"
        try:
            reason = self.llm.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是科研论文推荐助手。只基于给定论文标题、摘要、分数和用户问题，"
                            "用中文输出一段不超过80字的推荐原因。不要编造论文不存在的信息。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"推荐类型：{prompt_kind}\n"
                            f"用户问题：{query}\n"
                            f"论文标题：{paper.get('title', 'Untitled')}\n"
                            f"摘要：{_short_text(paper.get('abstract', ''), max_length=900)}\n"
                            f"匹配兴趣：{paper.get('matched_interests', [])}\n"
                            f"匹配关键词：{paper.get('matched_query_keywords', [])}\n"
                            f"综合分：{paper.get('score')}\n"
                            "请直接输出推荐原因，不要使用列表。"
                        ),
                    },
                ],
                temperature=0.2,
            )
        except Exception:  # noqa: BLE001
            return fallback
        cleaned = _short_text(reason, max_length=160)
        return cleaned or fallback

    def summarize(self, papers: list[Any], query: str) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for item in papers:
            paper = _paper_to_dict(item)
            abstract = str(paper.get("abstract") or "")
            evidence = _sentences(abstract, limit=3)
            first = evidence[0] if evidence else "检索结果未提供 abstract。"
            second = evidence[1] if len(evidence) > 1 else first
            summaries.append(
                {
                    "paper_id": paper.get("paper_id") or paper.get("id") or paper.get("url"),
                    "title": paper.get("title") or "Untitled",
                    "authors": paper.get("authors") or [],
                    "published_date": paper.get("published_date") or paper.get("published") or "",
                    "url": paper.get("url") or "",
                    "problem": f"围绕“{paper.get('title') or 'Untitled'}”与用户问题“{query}”的相关研究问题。",
                    "method": second,
                    "contribution": first,
                    "limitation": "当前摘要基于检索元数据和 abstract，未解析全文时不推断额外局限。",
                    "why_recommended": paper.get("reason") or "该论文与当前查询或用户画像存在关键词匹配。",
                    "evidence": evidence,
                }
            )
        return summaries
