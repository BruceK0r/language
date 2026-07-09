from paper_agent.agents.coordinator_agent import CoordinatorAgent
from paper_agent.memory.repository import MemoryRepository
from paper_agent.schemas import Paper


class UploadedImage:
    type = "image/png"

    def getvalue(self):
        return b"fake-image"


class StaticVisionAgent:
    def analyze(self, image_bytes, mime_type="image/png", question=""):
        assert image_bytes == b"fake-image"
        assert mime_type == "image/png"
        assert question == "What papers are related to this architecture?"
        return {
            "image_type": "model_architecture",
            "main_content": "A multi-agent RAG architecture with agent memory and retrieval modules.",
            "key_findings": ["The diagram connects retrieval with agent memory."],
            "possible_related_topics": ["RAG", "Multi-Agent", "LLM Agent"],
            "recommendation_keywords": ["rag", "multi-agent", "agent memory"],
            "provider_available": True,
            "raw_explanation": "A multi-agent RAG architecture with agent memory and retrieval modules.",
        }


class StaticRetrievalAgent:
    def retrieve(self, planned_query):
        assert "rag" in planned_query["keywords"]
        assert planned_query["top_k"] == 1
        return [
            Paper(
                paper_id="p1",
                title="RAG Agent Memory Architecture",
                authors=["Ada"],
                abstract="RAG agent memory and retrieval for LLM agents.",
                published_date="2026-01-01",
                url="https://example.com/p1",
                source="static",
                citation_count=40,
            ),
            Paper(
                paper_id="p2",
                title="Multi-Agent Retrieval Planning",
                authors=["Ben"],
                abstract="Multi-agent retrieval planning.",
                published_date="2026-01-02",
                url="https://example.com/p2",
                source="static",
                citation_count=20,
            ),
        ], []


def test_coordinator_runs_vision_query_and_updates_profile(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    repo.create_initial_profile("demo_user", ["RAG", "Agent Memory", "NLP", "Vision", "Safety"])
    coordinator = CoordinatorAgent(
        memory=repo,
        retrieval_agent=StaticRetrievalAgent(),
        vision_agent=StaticVisionAgent(),
    )

    result = coordinator.run_vision_query(
        "demo_user",
        UploadedImage(),
        question="What papers are related to this architecture?",
        top_k=1,
    )

    assert result["vision_result"]["image_type"] == "model_architecture"
    assert result["planned_query"]["keywords"] == ["rag", "multi-agent", "agent memory"]
    assert result["related_recommendations"][0]["paper_id"] == "p1"
    assert len(result["follow_up_recommendations"]) == 1
    assert result["profile_update"]["updated_keywords"]
    assert repo.get_user_profile("demo_user")["stats"]["image_interactions"] == 1
    assert "model_architecture" in result["answer"]
    assert "RAG" in result["answer"]
