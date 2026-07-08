from __future__ import annotations

import logging
from datetime import date
from typing import Any

import requests

from paper_agent.schemas import Paper

logger = logging.getLogger(__name__)


class SemanticScholarTool:
    endpoint = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(self, api_key: str | None = None, timeout: float = 30) -> None:
        self.api_key = api_key
        self.timeout = timeout

    def search(
        self,
        query: str,
        start_date: date,
        end_date: date,
        max_results: int = 30,
    ) -> list[Paper]:
        if not query:
            return []
        headers = {"x-api-key": self.api_key} if self.api_key else {}
        params = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": "title,authors,abstract,publicationDate,year,url,externalIds,citationCount,openAccessPdf,venue",
        }
        response = requests.get(self.endpoint, params=params, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        return self._parse_response(data.get("data", []), start_date=start_date, end_date=end_date)

    def _parse_response(self, rows: list[dict[str, Any]], start_date: date, end_date: date) -> list[Paper]:
        papers: list[Paper] = []
        for row in rows:
            published = row.get("publicationDate") or (f"{row.get('year')}-01-01" if row.get("year") else "")
            try:
                published_date = date.fromisoformat(str(published)[:10])
            except ValueError:
                continue
            if published_date < start_date or published_date > end_date:
                continue
            external = row.get("externalIds") or {}
            pdf = row.get("openAccessPdf") or {}
            authors = [author.get("name", "") for author in row.get("authors", [])]
            papers.append(
                Paper(
                    paper_id=f"s2:{row.get('paperId')}",
                    title=row.get("title") or "Untitled",
                    authors=[author for author in authors if author],
                    abstract=row.get("abstract") or "",
                    published_date=published_date.isoformat(),
                    url=row.get("url") or "",
                    pdf_url=pdf.get("url"),
                    source="semantic_scholar",
                    citation_count=row.get("citationCount"),
                    doi=external.get("DOI"),
                    arxiv_id=external.get("ArXiv"),
                    venue=row.get("venue"),
                    extra={"external_ids": external},
                )
            )
        return papers

