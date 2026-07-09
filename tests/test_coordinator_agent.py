from paper_agent.agents.coordinator_agent import CoordinatorAgent
from paper_agent.agents.query_planner_agent import QueryPlannerAgent
from paper_agent.agents.reader_agent import ReaderAgent
from paper_agent.memory.repository import MemoryRepository
from paper_agent.schemas import Paper


class StaticRetrievalAgent:
    def retrieve(self, planned_query):
        return [
            Paper(
                paper_id="p1",
                title="RAG Agent Memory",
                authors=["Ada"],
                abstract="RAG agent memory for planning.",
                published_date="2026-01-01",
                url="https://example.com/p1",
                pdf_url="https://example.com/p1.pdf",
                source="static",
                citation_count=20,
            ),
            Paper(
                paper_id="p2",
                title="Multi-Agent Tool Learning",
                authors=["Ben"],
                abstract="Multi-agent tool learning.",
                published_date="2026-01-02",
                url="https://example.com/p2",
                source="static",
                citation_count=10,
            ),
        ], []


class EmptyRetrievalAgent:
    def retrieve(self, planned_query):
        return [], ["offline"]


class ReasonLLM:
    def __init__(self):
        self.calls = []

    def chat(self, messages, temperature=0.2):
        self.calls.append(messages)
        return f"LLM reason {len(self.calls)}"


def test_coordinator_runs_text_query_and_updates_profile(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    repo.create_initial_profile("demo_user", ["RAG", "Agent Memory", "NLP", "Vision", "Safety"])
    coordinator = CoordinatorAgent(
        memory=repo,
        planner=QueryPlannerAgent(llm_provider=None),
        retrieval_agent=StaticRetrievalAgent(),
    )

    result = coordinator.run_text_query("demo_user", "agent memory RAG", top_k=1)

    assert result["recommendations"][0]["paper_id"] == "p1"
    assert len(result["follow_up_recommendations"]) == 1
    assert "## 查询理解" in result["answer"]
    assert result["profile_update"]["updated_keywords"]
    assert result["planned_query"]["top_k"] == 1


def test_coordinator_adds_llm_reasons_to_top_and_follow_up_recommendations(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    repo.create_initial_profile("demo_user", ["RAG", "Agent Memory", "NLP", "Vision", "Safety"])
    llm = ReasonLLM()
    coordinator = CoordinatorAgent(
        memory=repo,
        planner=QueryPlannerAgent(llm_provider=None),
        retrieval_agent=StaticRetrievalAgent(),
        reader=ReaderAgent(llm_provider=llm),
    )

    result = coordinator.run_text_query("demo_user", "agent memory RAG", top_k=1)

    assert result["recommendations"][0]["reason"] == "LLM reason 1"
    assert result["follow_up_recommendations"][0]["reason"] == "LLM reason 2"
    assert len(llm.calls) == 2


def test_coordinator_handles_empty_retrieval_without_crashing(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    repo.create_initial_profile("demo_user", ["RAG", "Agent Memory", "NLP", "Vision", "Safety"])
    coordinator = CoordinatorAgent(
        memory=repo,
        planner=QueryPlannerAgent(llm_provider=None),
        retrieval_agent=EmptyRetrievalAgent(),
    )

    result = coordinator.run_text_query("demo_user", "agent memory RAG", top_k=3)

    assert result["recommendations"] == []
    assert result["follow_up_recommendations"] == []
    assert "未检索到候选论文" in result["answer"]
    assert result["profile_update"]["updated_keywords"]
