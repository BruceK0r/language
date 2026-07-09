from datetime import date, timedelta

from paper_agent.schemas import Paper
from paper_agent.agent.workflow import PaperRadarWorkflow
from paper_agent.memory.repository import MemoryRepository
from paper_agent.providers.mock import MockLLMProvider
from paper_agent.tools.time_buckets import build_default_time_buckets, select_papers_by_time_buckets


def make_paper(days_old: int, index: int, citations: int) -> Paper:
    published = date.today() - timedelta(days=days_old)
    return Paper(
        paper_id=f"p-{days_old}-{index}",
        title=f"Embodied AI Robot Learning Paper {days_old}-{index}",
        authors=["A"],
        abstract="Embodied AI robot learning manipulation locomotion.",
        published_date=published.isoformat(),
        url=f"https://example.com/{days_old}/{index}",
        pdf_url="https://example.com/paper.pdf",
        source="semantic_scholar",
        citation_count=citations,
    )


def test_select_papers_by_time_buckets_keeps_bucket_quotas_and_heat_order():
    papers = []
    for days_old, count in [(2, 8), (14, 14), (45, 14), (75, 20)]:
        for index in range(count):
            papers.append(make_paper(days_old, index, citations=index))

    selected = select_papers_by_time_buckets(
        papers,
        keywords=["embodied ai", "robot learning"],
        buckets=build_default_time_buckets(date.today(), max_window_days=90),
    )

    assert len(selected) == 40
    assert sum(0 <= (date.today() - date.fromisoformat(p.published_date)).days <= 7 for p in selected) == 5
    assert sum(8 <= (date.today() - date.fromisoformat(p.published_date)).days <= 30 for p in selected) == 10
    assert sum(31 <= (date.today() - date.fromisoformat(p.published_date)).days <= 60 for p in selected) == 10
    assert sum(61 <= (date.today() - date.fromisoformat(p.published_date)).days <= 90 for p in selected) == 15
    assert "p-2-7" in {paper.paper_id for paper in selected}
    assert "p-2-0" not in {paper.paper_id for paper in selected}


class RecordingArxivTool:
    def __init__(self) -> None:
        self.calls = []

    def search(self, keywords, start_date, end_date, max_results):
        self.calls.append((start_date, end_date, max_results))
        return [
            Paper(
                paper_id=f"arxiv:{start_date.isoformat()}",
                title=f"Embodied AI bucket {start_date.isoformat()}",
                authors=["A"],
                abstract="Embodied AI robot learning manipulation.",
                published_date=start_date.isoformat(),
                url=f"https://arxiv.org/abs/{start_date.isoformat()}",
                pdf_url=f"https://arxiv.org/pdf/{start_date.isoformat()}",
                source="arxiv",
                arxiv_id=start_date.isoformat(),
            )
        ]


class EmptySearchTool:
    def search(self, *args, **kwargs):
        return []


def test_workflow_queries_arxiv_once_per_time_bucket(tmp_path):
    arxiv_tool = RecordingArxivTool()
    workflow = PaperRadarWorkflow(
        llm_provider=MockLLMProvider(),
        memory=MemoryRepository(tmp_path / "memory.db"),
        arxiv_tool=arxiv_tool,
        semantic_scholar_tool=EmptySearchTool(),
        enable_pdf_download=False,
        use_mock_search=False,
    )

    state = workflow.run(
        user_query="Embodied AI important papers Top 1",
        top_k=1,
        time_range="last_90_days",
        user_id="bucket-test",
    )

    assert len(arxiv_tool.calls) == 4
    assert [call[2] for call in arxiv_tool.calls] == [20, 40, 40, 60]
    assert len(state.candidate_papers) == 4
