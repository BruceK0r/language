from datetime import date, timedelta

from paper_agent.schemas import Paper
from paper_agent.tools.ranking import rank_papers


def test_rank_papers_uses_weighted_scores_and_handles_missing_citations():
    recent = date.today().isoformat()
    older = (date.today() - timedelta(days=80)).isoformat()
    papers = [
        Paper(
            paper_id="p1",
            title="LLM Agent Memory for Long Horizon Planning",
            authors=["Ada"],
            abstract="A paper about agent memory and long horizon planning.",
            published_date=recent,
            url="https://arxiv.org/abs/1234.5678",
            pdf_url="https://arxiv.org/pdf/1234.5678",
            source="arxiv",
            citation_count=None,
        ),
        Paper(
            paper_id="p2",
            title="Unrelated Vision Benchmark",
            authors=["Ben"],
            abstract="A benchmark about image classification.",
            published_date=older,
            url="https://example.com/p2",
            pdf_url=None,
            source="semantic_scholar",
            citation_count=150,
        ),
    ]

    ranked = rank_papers(
        papers,
        keywords=["llm agent memory", "long horizon planning"],
        time_window_days=90,
        user_memory={},
    )

    assert ranked[0].paper.paper_id == "p1"
    assert ranked[0].scores.citation_score == 0.0
    assert ranked[0].scores.has_pdf_score == 1.0
    assert 0.0 <= ranked[0].scores.final_score <= 1.0
    assert "semantic_relevance" in ranked[0].scores.model_dump()
    assert ranked[0].ranking_reason

