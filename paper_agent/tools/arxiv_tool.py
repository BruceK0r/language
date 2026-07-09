from __future__ import annotations

import logging
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date

import requests

from paper_agent.schemas import Paper

logger = logging.getLogger(__name__)


class ArxivTool:
    endpoint = "https://export.arxiv.org/api/query"

    def __init__(self, timeout: float = 30) -> None:
        self.timeout = timeout

    def search(
        self,
        keywords: list[str],
        start_date: date,
        end_date: date,
        max_results: int = 30,
    ) -> list[Paper]:
        if not keywords:
            return []
        query_parts = [f'all:"{keyword}"' for keyword in keywords[:4]]
        date_query = f"submittedDate:[{start_date:%Y%m%d}0000 TO {end_date:%Y%m%d}2359]"
        params = {
            "search_query": f"({' OR '.join(query_parts)}) AND {date_query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"{self.endpoint}?{urllib.parse.urlencode(params)}"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return self._parse_response(response.text, start_date=start_date, end_date=end_date)

    def _parse_response(self, xml_text: str, start_date: date, end_date: date) -> list[Paper]:
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        root = ET.fromstring(xml_text)
        papers: list[Paper] = []
        for entry in root.findall("atom:entry", ns):
            published = (entry.findtext("atom:published", default="", namespaces=ns) or "")[:10]
            try:
                published_date = date.fromisoformat(published)
            except ValueError:
                published_date = start_date
            if published_date < start_date or published_date > end_date:
                continue

            entry_id = entry.findtext("atom:id", default="", namespaces=ns) or ""
            arxiv_id = entry_id.rstrip("/").split("/")[-1]
            title = " ".join((entry.findtext("atom:title", default="", namespaces=ns) or "").split())
            abstract = " ".join((entry.findtext("atom:summary", default="", namespaces=ns) or "").split())
            authors = [
                author.findtext("atom:name", default="", namespaces=ns) or ""
                for author in entry.findall("atom:author", ns)
            ]
            authors = [author for author in authors if author]
            pdf_url = None
            html_url = entry_id
            for link in entry.findall("atom:link", ns):
                href = link.attrib.get("href")
                if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                    pdf_url = href
                if link.attrib.get("rel") == "alternate" and href:
                    html_url = href
            doi = entry.findtext("arxiv:doi", default=None, namespaces=ns)
            papers.append(
                Paper(
                    paper_id=f"arxiv:{arxiv_id}",
                    title=title or arxiv_id,
                    authors=authors,
                    abstract=abstract,
                    published_date=published_date.isoformat(),
                    url=html_url,
                    pdf_url=pdf_url,
                    source="arxiv",
                    doi=doi,
                    arxiv_id=arxiv_id,
                )
            )
        return papers
