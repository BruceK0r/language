from __future__ import annotations

from pydantic import BaseModel, Field

from paper_agent.schemas import Paper, PaperSummary, RankedPaper


class AgentState(BaseModel):
    user_query: str
    parsed_request: dict = Field(default_factory=dict)
    expanded_keywords: list[str] = Field(default_factory=list)
    candidate_papers: list[Paper] = Field(default_factory=list)
    ranked_papers: list[RankedPaper] = Field(default_factory=list)
    paper_summaries: list[PaperSummary] = Field(default_factory=list)
    final_report: str = ""
    memory_updates: dict = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)

