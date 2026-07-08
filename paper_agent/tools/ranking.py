from __future__ import annotations

import math
import re
from datetime import date, datetime

from paper_agent.schemas import Paper, RankedPaper, RankingScores


TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_\-]+")


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text or "") if len(token) > 1}


def semantic_relevance_score(paper: Paper, keywords: list[str]) -> float:
    keyword_tokens = set().union(*(_tokens(keyword) for keyword in keywords)) if keywords else set()
    if not keyword_tokens:
        return 0.0
    title_tokens = _tokens(paper.title)
    abstract_tokens = _tokens(paper.abstract)
    title_hits = len(keyword_tokens & title_tokens)
    abstract_hits = len(keyword_tokens & abstract_tokens)
    score = (title_hits * 1.5 + abstract_hits) / max(1.0, len(keyword_tokens) * 1.4)
    return max(0.0, min(1.0, score))


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def recency_score(published_date: str, time_window_days: int) -> float:
    published = _parse_date(published_date)
    if not published:
        return 0.0
    days_old = max(0, (date.today() - published).days)
    if days_old > time_window_days:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (days_old / max(1, time_window_days)) * 0.8))


def citation_score(citation_count: int | None) -> float:
    if citation_count is None or citation_count <= 0:
        return 0.0
    return max(0.0, min(1.0, math.log1p(citation_count) / math.log1p(1000)))


def source_quality_score(source: str) -> float:
    return {
        "semantic_scholar": 0.95,
        "openalex": 0.90,
        "arxiv": 0.85,
        "mock": 0.70,
    }.get((source or "").lower(), 0.60)


def user_memory_match_score(paper: Paper, user_memory: dict) -> float:
    preferred_domains = user_memory.get("preferred_domains", []) or []
    seen_papers = set(user_memory.get("seen_papers", []) or [])
    if paper.paper_id in seen_papers or paper.url in seen_papers:
        return 0.0
    if not preferred_domains:
        return 0.0
    text_tokens = _tokens(f"{paper.title} {paper.abstract}")
    domain_tokens = set().union(*(_tokens(domain) for domain in preferred_domains))
    if not domain_tokens:
        return 0.0
    return min(1.0, len(text_tokens & domain_tokens) / max(1, len(domain_tokens)))


def rank_papers(
    papers: list[Paper],
    keywords: list[str],
    time_window_days: int = 90,
    user_memory: dict | None = None,
) -> list[RankedPaper]:
    ranked: list[RankedPaper] = []
    memory = user_memory or {}
    for paper in papers:
        semantic = semantic_relevance_score(paper, keywords)
        recency = recency_score(paper.published_date, time_window_days)
        citations = citation_score(paper.citation_count)
        source_quality = source_quality_score(paper.source)
        has_pdf = 1.0 if paper.pdf_url else 0.0
        memory_match = user_memory_match_score(paper, memory)
        final = (
            0.35 * semantic
            + 0.20 * recency
            + 0.15 * citations
            + 0.15 * source_quality
            + 0.10 * has_pdf
            + 0.05 * memory_match
        )
        scores = RankingScores(
            semantic_relevance=semantic,
            recency_score=recency,
            citation_score=citations,
            source_quality_score=source_quality,
            has_pdf_score=has_pdf,
            user_memory_match_score=memory_match,
            final_score=final,
        )
        reason = (
            f"综合分 {scores.final_score:.3f}：语义相关 {semantic:.2f}，"
            f"时效 {recency:.2f}，引用 {citations:.2f}，来源质量 {source_quality:.2f}，"
            f"PDF {has_pdf:.0f}，用户记忆匹配 {memory_match:.2f}。"
        )
        ranked.append(RankedPaper(paper=paper, scores=scores, ranking_reason=reason))
    return sorted(ranked, key=lambda item: item.scores.final_score, reverse=True)

