from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from paper_agent.schemas import Paper
from paper_agent.tools.ranking import citation_score, semantic_relevance_score


@dataclass(frozen=True)
class TimeBucket:
    name: str
    min_days_old: int
    max_days_old: int
    limit: int

    def contains(self, published_date: date, anchor_date: date) -> bool:
        days_old = (anchor_date - published_date).days
        return self.min_days_old <= days_old <= self.max_days_old

    def date_range(self, anchor_date: date) -> tuple[date, date]:
        start_date = anchor_date - timedelta(days=self.max_days_old)
        end_date = anchor_date - timedelta(days=self.min_days_old)
        return start_date, end_date


def build_default_time_buckets(anchor_date: date, max_window_days: int = 90) -> list[TimeBucket]:
    raw_buckets = [
        TimeBucket("0-7d", 0, 7, 5),
        TimeBucket("8-30d", 8, 30, 10),
        TimeBucket("31-60d", 31, 60, 10),
        TimeBucket("61-90d", 61, 90, 15),
    ]
    return [bucket for bucket in raw_buckets if bucket.min_days_old <= max_window_days]


def parse_paper_date(value: str) -> date | None:
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


def bucket_heat_score(paper: Paper, keywords: list[str]) -> float:
    citation_heat = citation_score(paper.citation_count)
    relevance = semantic_relevance_score(paper, keywords)
    has_pdf = 1.0 if paper.pdf_url else 0.0
    return 0.75 * citation_heat + 0.15 * relevance + 0.10 * has_pdf


def select_papers_by_time_buckets(
    papers: list[Paper],
    keywords: list[str],
    buckets: list[TimeBucket],
    anchor_date: date | None = None,
) -> list[Paper]:
    anchor = anchor_date or date.today()
    selected: list[Paper] = []
    selected_ids: set[str] = set()

    for bucket in buckets:
        bucket_papers: list[Paper] = []
        for paper in papers:
            published = parse_paper_date(paper.published_date)
            if published and bucket.contains(published, anchor):
                bucket_papers.append(paper)
        bucket_papers.sort(
            key=lambda paper: (
                bucket_heat_score(paper, keywords),
                paper.citation_count or 0,
                paper.published_date,
            ),
            reverse=True,
        )
        picked_in_bucket = 0
        for paper in bucket_papers:
            if paper.paper_id in selected_ids:
                continue
            selected.append(paper)
            selected_ids.add(paper.paper_id)
            picked_in_bucket += 1
            if picked_in_bucket >= bucket.limit:
                break

    return selected
