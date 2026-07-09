from datetime import date, timedelta

from paper_agent.agents.retrieval_agent import RetrievalAgent
from paper_agent.schemas import Paper


class StaticTool:
    def search(self, *args, **kwargs):
        return [
            Paper(
                paper_id="p1",
                title="Agent Memory RAG",
                authors=["Ada"],
                abstract="RAG for agent memory.",
                published_date=date.today().isoformat(),
                url="https://example.com/p1",
                pdf_url=None,
                source="static",
            )
        ]


def test_retrieval_agent_reuses_tools_and_returns_candidates():
    agent = RetrievalAgent(arxiv_tool=StaticTool(), semantic_scholar_tool=StaticTool(), use_mock_search=False)
    papers, errors = agent.retrieve({"keywords": ["agent memory"], "top_k": 1, "time_range": "last_180_days"})

    assert errors == []
    assert len(papers) == 1
    assert papers[0].paper_id == "p1"


def test_retrieval_agent_returns_empty_with_errors_when_tools_fail():
    class FailingTool:
        def search(self, *args, **kwargs):
            raise RuntimeError("offline")

    agent = RetrievalAgent(arxiv_tool=FailingTool(), semantic_scholar_tool=FailingTool(), use_mock_search=False)
    papers, errors = agent.retrieve({"keywords": ["agent memory"], "top_k": 1, "time_range": "last_180_days"})

    assert papers == []
    assert errors


def test_retrieval_agent_default_mode_does_not_hide_external_failures_with_demo_data():
    class FailingTool:
        def search(self, *args, **kwargs):
            raise RuntimeError("offline")

    agent = RetrievalAgent(arxiv_tool=FailingTool(), semantic_scholar_tool=FailingTool())
    papers, errors = agent.retrieve({"keywords": ["agent memory"], "top_k": 2, "time_range": "last_180_days"})

    assert papers == []
    assert any("arXiv bucket" in error for error in errors)
    assert any("Semantic Scholar failed" in error for error in errors)
    assert not any("using Mock papers for demo" in error for error in errors)


def test_retrieval_agent_uses_demo_fallback_only_when_explicitly_enabled():
    class FailingTool:
        def search(self, *args, **kwargs):
            raise RuntimeError("offline")

    agent = RetrievalAgent(
        arxiv_tool=FailingTool(),
        semantic_scholar_tool=FailingTool(),
        use_mock_search=True,
    )
    papers, errors = agent.retrieve({"keywords": ["agent memory"], "top_k": 2, "time_range": "last_180_days"})

    assert len(papers) >= 2
    assert all(paper.source == "mock" for paper in papers)
    assert any("using Mock papers for demo" in error for error in errors)


def test_retrieval_agent_selects_candidates_from_time_buckets():
    class BucketTool:
        def __init__(self):
            self.calls = []

        def search(self, keywords, start_date, end_date, max_results):
            self.calls.append(
                {
                    "start_date": start_date,
                    "end_date": end_date,
                    "max_results": max_results,
                }
            )
            papers = []
            for index in range(max_results):
                published = end_date - timedelta(days=index % max(1, (end_date - start_date).days + 1))
                papers.append(
                    Paper(
                        paper_id=f"{end_date.isoformat()}-{index}",
                        title=f"RAG bucket paper {end_date.isoformat()} {index}",
                        authors=["Ada"],
                        abstract="RAG agent memory",
                        published_date=published.isoformat(),
                        url=f"https://arxiv.org/abs/{end_date:%Y%m%d}.{index}",
                        source="arxiv",
                        citation_count=max_results - index,
                    )
                )
            return papers

    class EmptySemanticTool:
        def search(self, *args, **kwargs):
            return []

    arxiv_tool = BucketTool()
    agent = RetrievalAgent(arxiv_tool=arxiv_tool, semantic_scholar_tool=EmptySemanticTool(), use_mock_search=False)

    papers, errors = agent.retrieve({"keywords": ["agent memory"], "top_k": 5, "time_range": "last_90_days"})

    assert errors == []
    assert len(arxiv_tool.calls) == 4
    assert [call["max_results"] for call in arxiv_tool.calls] == [20, 40, 40, 60]
    assert len(papers) == 40
    today = date.today()
    bucket_counts = {
        "0-7d": 0,
        "8-30d": 0,
        "31-60d": 0,
        "61-90d": 0,
    }
    for paper in papers:
        days_old = (today - date.fromisoformat(paper.published_date)).days
        if 0 <= days_old <= 7:
            bucket_counts["0-7d"] += 1
        elif 8 <= days_old <= 30:
            bucket_counts["8-30d"] += 1
        elif 31 <= days_old <= 60:
            bucket_counts["31-60d"] += 1
        elif 61 <= days_old <= 90:
            bucket_counts["61-90d"] += 1

    assert bucket_counts == {"0-7d": 5, "8-30d": 10, "31-60d": 10, "61-90d": 15}
