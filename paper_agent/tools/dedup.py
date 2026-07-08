from __future__ import annotations

import re
from urllib.parse import urlparse

from paper_agent.schemas import Paper


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", title.lower())).strip()


def normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return f"{parsed.netloc.lower()}{path.lower()}"


def _fingerprints(paper: Paper) -> set[str]:
    values: set[str] = set()
    if paper.doi:
        values.add(f"doi:{paper.doi.lower().strip()}")
    if paper.arxiv_id:
        values.add(f"arxiv:{paper.arxiv_id.lower().strip()}")
    for url in [paper.url, paper.pdf_url]:
        normalized = normalize_url(url)
        if normalized:
            values.add(f"url:{normalized}")
            arxiv_match = re.search(r"arxiv\.org/(?:abs|pdf)/([^/?]+)", url or "", re.I)
            if arxiv_match:
                values.add(f"arxiv:{arxiv_match.group(1).removesuffix('.pdf').lower()}")
    title_key = normalize_title(paper.title)
    if title_key:
        values.add(f"title:{title_key}")
    return values


def _richness(paper: Paper) -> tuple[int, int, int, int, int]:
    return (
        1 if paper.pdf_url else 0,
        paper.citation_count or 0,
        len(paper.abstract or ""),
        len(paper.authors),
        {"semantic_scholar": 3, "openalex": 2, "arxiv": 1, "mock": 0}.get(paper.source, 0),
    )


def _merge_papers(preferred: Paper, other: Paper) -> Paper:
    data = preferred.model_dump()
    for key, value in other.model_dump().items():
        if key == "extra":
            data["extra"] = {**other.extra, **preferred.extra}
        elif key == "authors" and not data.get(key):
            data[key] = value
        elif data.get(key) in (None, "", []):
            data[key] = value
    return Paper.model_validate(data)


def deduplicate_papers(papers: list[Paper]) -> list[Paper]:
    selected: list[Paper] = []
    fingerprint_to_index: dict[str, int] = {}

    for paper in papers:
        fps = _fingerprints(paper)
        duplicate_indexes = {fingerprint_to_index[fp] for fp in fps if fp in fingerprint_to_index}
        if not duplicate_indexes:
            selected.append(paper)
            index = len(selected) - 1
            for fp in fps:
                fingerprint_to_index[fp] = index
            continue

        index = min(duplicate_indexes)
        existing = selected[index]
        if _richness(paper) > _richness(existing):
            selected[index] = _merge_papers(paper, existing)
        else:
            selected[index] = _merge_papers(existing, paper)
        for fp in fps | _fingerprints(selected[index]):
            fingerprint_to_index[fp] = index

    return selected

