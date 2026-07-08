from paper_agent.agent.workflow import PaperRadarWorkflow
from paper_agent.memory.repository import MemoryRepository
from paper_agent.providers.mock import MockLLMProvider
from paper_agent.schemas import Paper


class StaticArxivTool:
    def search(self, keywords, start_date, end_date, max_results):
        return [
            Paper(
                paper_id="arxiv:1111.1111",
                title="LLM Agent Memory with Episodic Retrieval",
                authors=["Alice Zhang", "Bo Li"],
                abstract="We propose episodic retrieval memory for LLM agents. Experiments show improved task success on planning benchmarks.",
                published_date=start_date.isoformat(),
                url="https://arxiv.org/abs/1111.1111",
                pdf_url="https://arxiv.org/pdf/1111.1111",
                source="arxiv",
                arxiv_id="1111.1111",
            )
        ]


class EmptySemanticScholarTool:
    def search(self, query, start_date, end_date, max_results):
        return []


def test_mock_workflow_returns_traceable_report(tmp_path):
    repo = MemoryRepository(db_path=tmp_path / "memory.db")
    workflow = PaperRadarWorkflow(
        llm_provider=MockLLMProvider(),
        memory=repo,
        arxiv_tool=StaticArxivTool(),
        semantic_scholar_tool=EmptySemanticScholarTool(),
        enable_pdf_download=False,
    )

    state = workflow.run(
        user_query="检索最近三个月关于 LLM Agent Memory 的重要论文，并总结 Top 1。",
        top_k=1,
        time_range="last_90_days",
        user_id="pytest-user",
    )

    assert state.final_report.startswith("# 领域论文检索与摘要简报")
    assert state.expanded_keywords
    assert len(state.candidate_papers) == 1
    assert len(state.ranked_papers) == 1
    assert len(state.paper_summaries) == 1
    assert state.paper_summaries[0].evidence
    assert "LLM Agent Memory with Episodic Retrieval" in state.final_report
    assert state.memory_updates["task_id"]
