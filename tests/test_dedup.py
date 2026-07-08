from paper_agent.schemas import Paper
from paper_agent.tools.dedup import deduplicate_papers


def test_deduplicate_papers_prefers_richer_duplicate_records():
    sparse = Paper(
        paper_id="arxiv:1234.5678",
        title="LLM Agent Memory: A Survey",
        authors=["A"],
        abstract="Short abstract.",
        published_date="2026-05-01",
        url="https://arxiv.org/abs/1234.5678",
        pdf_url=None,
        source="arxiv",
    )
    rich = Paper(
        paper_id="s2:abc",
        title="LLM Agent Memory - A Survey",
        authors=["A", "B"],
        abstract="Longer abstract with more detail about memory for agents.",
        published_date="2026-05-01",
        url="https://www.semanticscholar.org/paper/abc",
        pdf_url="https://arxiv.org/pdf/1234.5678",
        source="semantic_scholar",
        citation_count=42,
        doi="10.1000/example",
        arxiv_id="1234.5678",
    )
    other = Paper(
        paper_id="arxiv:9999.0000",
        title="Tool Learning for Agents",
        authors=["C"],
        abstract="Another paper.",
        published_date="2026-05-02",
        url="https://arxiv.org/abs/9999.0000",
        source="arxiv",
    )

    deduped = deduplicate_papers([sparse, rich, other])

    assert len(deduped) == 2
    assert any(p.paper_id == "s2:abc" and p.pdf_url for p in deduped)
    assert any(p.paper_id == "arxiv:9999.0000" for p in deduped)

