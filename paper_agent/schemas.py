from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class Paper(BaseModel):
    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    published_date: str
    url: str
    pdf_url: str | None = None
    source: str
    citation_count: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    venue: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ParsedRequest(BaseModel):
    domain: str
    query_terms: list[str] = Field(default_factory=list)
    start_date: str
    end_date: str
    time_window_days: int = 90
    top_k: int = 5
    language: str = "zh"
    summary_depth: str = "standard"


class RankingScores(BaseModel):
    semantic_relevance: float
    recency_score: float
    citation_score: float
    source_quality_score: float
    has_pdf_score: float
    user_memory_match_score: float
    final_score: float

    @field_validator("*")
    @classmethod
    def score_must_be_unit_interval(cls, value: float) -> float:
        return max(0.0, min(1.0, float(value)))


class RankedPaper(BaseModel):
    paper: Paper
    scores: RankingScores
    ranking_reason: str


class PaperSummary(BaseModel):
    title: str
    authors: list[str]
    published_date: str
    url: str
    pdf_url: str | None = None
    research_problem: str
    core_method: str
    main_contributions: list[str]
    experiments: str
    results: str
    limitations: list[str]
    why_important: str
    relevance_to_user_query: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str]


class SearchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_query: str | None = Field(default=None, description="Natural language research request")
    query: str | None = Field(default=None, description="Alias of user_query")
    top_k: int = Field(default=5, ge=1, le=20)
    time_range: str | None = Field(default=None, description="Examples: last_90_days, last_3_months")
    user_id: str = Field(default="default")

    @model_validator(mode="after")
    def require_query(self) -> "SearchRequest":
        if not (self.user_query or self.query):
            raise ValueError("user_query or query is required")
        if self.user_query is None:
            self.user_query = self.query
        return self


class SearchResponse(BaseModel):
    task_id: str
    final_report: str
    expanded_keywords: list[str]
    candidate_count: int
    ranked_papers: list[RankedPaper]
    paper_summaries: list[PaperSummary]
    errors: list[str] = Field(default_factory=list)


class VisionResponse(BaseModel):
    explanation: str
    model: str
    used_mock: bool = False
    paper_id: str | None = None


def today_iso() -> str:
    return date.today().isoformat()

