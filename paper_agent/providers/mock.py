from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta
from typing import Any

from paper_agent.schemas import Paper, PaperSummary


def _sentences(text: str, limit: int = 3) -> list[str]:
    chunks = re.split(r"(?<=[.!?。！？])\s+", text.strip())
    return [chunk[:260] for chunk in chunks if chunk][:limit]


class MockLLMProvider:
    name = "mock"

    def parse_request(self, user_query: str, top_k: int = 5, time_range: str | None = None) -> dict[str, Any]:
        from paper_agent.agent.workflow import parse_user_request_heuristic

        return parse_user_request_heuristic(user_query, top_k=top_k, time_range=time_range).model_dump()

    def expand_keywords(self, user_query: str, parsed_request: dict[str, Any]) -> list[str]:
        text = user_query.lower()
        keywords = [
            parsed_request.get("domain") or user_query,
            "large language model agents",
            "LLM agent memory",
            "episodic memory for agents",
            "retrieval augmented agent memory",
        ]
        if "memory" not in text and "记忆" not in text:
            keywords.append("AI agents")
        return list(dict.fromkeys(k for k in keywords if k))

    def summarize_paper(self, paper: Paper, source_text: str, user_query: str) -> PaperSummary:
        evidence = _sentences(source_text or paper.abstract, limit=3)
        if not evidence:
            evidence = [paper.title]
        return PaperSummary(
            title=paper.title,
            authors=paper.authors,
            published_date=paper.published_date,
            url=paper.url,
            pdf_url=paper.pdf_url,
            research_problem=f"论文围绕“{paper.title}”相关问题展开；该结论来自检索摘要文本。",
            core_method=evidence[0],
            main_contributions=evidence[:2],
            experiments=evidence[1] if len(evidence) > 1 else "检索结果未提供明确实验细节。",
            results=evidence[2] if len(evidence) > 2 else "检索结果未提供可量化结果。",
            limitations=["当前 Mock 摘要仅基于 abstract/PDF 解析片段，未推断未出现的限制。"],
            why_important="该论文与用户关键词高度匹配，且排序函数综合考虑了相关性、时效性和 PDF 可读性。",
            relevance_to_user_query=f"标题和摘要与用户问题“{user_query}”存在关键词重叠。",
            confidence=0.66,
            evidence=evidence,
        )

    def critique_summary(self, summary: PaperSummary, source_text: str) -> PaperSummary:
        return summary

    def generate_report(
        self,
        user_query: str,
        parsed_request: dict[str, Any],
        expanded_keywords: list[str],
        candidate_count: int,
        ranked_papers: list[Any],
        paper_summaries: list[PaperSummary],
        errors: list[str],
    ) -> str:
        from paper_agent.agent.workflow import build_markdown_report

        return build_markdown_report(
            user_query=user_query,
            parsed_request=parsed_request,
            expanded_keywords=expanded_keywords,
            candidate_count=candidate_count,
            ranked_papers=ranked_papers,
            paper_summaries=paper_summaries,
            errors=errors,
        )

    def sample_papers(self, start_date: date, max_results: int = 5) -> list[Paper]:
        base_titles = [
            "LLM Agent Memory with Episodic Retrieval",
            "Long-Term Memory Architectures for Tool-Using Language Agents",
            "Reflective Memory Improves Multi-Step Agent Planning",
            "Benchmarking Retrieval-Augmented Memory in LLM Agents",
            "Safety Limits of Persistent Memory for Autonomous Agents",
        ]
        papers: list[Paper] = []
        for index, title in enumerate(base_titles[:max_results]):
            digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:8]
            published = start_date + timedelta(days=min(index * 7, 80))
            papers.append(
                Paper(
                    paper_id=f"mock:{digest}",
                    title=title,
                    authors=["Mock Researcher", f"Author {index + 1}"],
                    abstract=(
                        f"We study {title.lower()}. The paper proposes a memory module for LLM agents, "
                        "evaluates it on planning and question answering tasks, and reports improvements over "
                        "non-memory baselines while noting limits from retrieval noise."
                    ),
                    published_date=published.isoformat(),
                    url=f"https://example.com/papers/{digest}",
                    pdf_url=f"https://example.com/papers/{digest}.pdf",
                    source="mock",
                    citation_count=10 * (max_results - index),
                )
            )
        return papers


class MockVisionProvider:
    def __init__(self, model: str = "glm-4.6v") -> None:
        self.model = f"mock-{model}"

    def analyze_image(self, image_bytes: bytes, mime_type: str, prompt: str | None = None) -> str:
        size_kb = len(image_bytes) / 1024
        note = f" 用户说明：{prompt}" if prompt else ""
        return (
            f"Mock 图片解释：收到一张 {mime_type} 图片，大小约 {size_kb:.1f} KB。"
            "未配置 ZHIPU_API_KEY，因此未调用多模态模型。"
            f"{note}"
        )

