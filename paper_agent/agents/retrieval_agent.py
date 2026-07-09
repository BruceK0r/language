from __future__ import annotations

from datetime import date
from typing import Any

from paper_agent.config import get_settings
from paper_agent.providers.mock import MockLLMProvider
from paper_agent.schemas import Paper
from paper_agent.tools.dedup import deduplicate_papers
from paper_agent.tools.arxiv_tool import ArxivTool
from paper_agent.tools.semantic_scholar_tool import SemanticScholarTool
from paper_agent.tools.time_buckets import build_default_time_buckets, select_papers_by_time_buckets


def _parse_time_range(value: str | None) -> int:
    mapping = {
        "last_30_days": 30,
        "last_90_days": 90,
        "last_180_days": 180,
        "last_6_months": 180,
        "last_12_months": 365,
    }
    return mapping.get(value or "", 180)


class RetrievalAgent:
    def __init__(
        self,
        arxiv_tool: Any | None = None,
        semantic_scholar_tool: Any | None = None,
        use_mock_search: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.arxiv_tool = arxiv_tool or ArxivTool(timeout=settings.request_timeout_seconds)
        self.semantic_scholar_tool = semantic_scholar_tool or SemanticScholarTool(
            api_key=settings.semantic_scholar_api_key,
            timeout=settings.request_timeout_seconds,
        )
        self.use_mock_search = bool(use_mock_search)
        self.mock = MockLLMProvider()

    def retrieve(self, planned_query: dict[str, Any]) -> tuple[list[Paper], list[str]]:
        keywords = [str(keyword) for keyword in planned_query.get("keywords", []) if str(keyword).strip()]
        if not keywords:
            return [], ["RetrievalAgent: no keywords available."]
        top_k = int(planned_query.get("top_k") or 5)
        days = _parse_time_range(planned_query.get("time_range"))
        end = date.today()
        buckets = build_default_time_buckets(end, max_window_days=min(days, 90))
        total_bucket_limit = sum(bucket.limit for bucket in buckets)
        start, _ = buckets[-1].date_range(end) if buckets else (end, end)
        max_results = max(total_bucket_limit, top_k * 6, 20)
        papers: list[Paper] = []
        errors: list[str] = []
        for bucket in buckets:
            bucket_start, bucket_end = bucket.date_range(end)
            try:
                papers.extend(
                    self.arxiv_tool.search(
                        keywords,
                        start_date=bucket_start,
                        end_date=bucket_end,
                        max_results=bucket.limit * 4,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"RetrievalAgent arXiv bucket {bucket.name} failed: {exc}")
        try:
            papers.extend(
                self.semantic_scholar_tool.search(
                    " ".join(keywords[:4]),
                    start_date=start,
                    end_date=end,
                    max_results=max_results,
                )
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"RetrievalAgent Semantic Scholar failed: {exc}")
        papers = deduplicate_papers(papers)
        if not papers and self.use_mock_search:
            papers = self.mock.sample_papers(start_date=start, max_results=max(top_k + 3, 5))
            errors.append("RetrievalAgent found no external results; using Mock papers for demo.")
        if papers and buckets:
            papers = select_papers_by_time_buckets(
                papers,
                keywords=keywords,
                buckets=buckets,
                anchor_date=end,
            )
        return papers[:total_bucket_limit] if total_bucket_limit else papers, errors
