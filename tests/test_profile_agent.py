from paper_agent.agents.profile_agent import ProfileAgent
from paper_agent.memory.repository import MemoryRepository


def test_profile_agent_uses_rule_fallback_and_summary(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    agent = ProfileAgent(memory=repo)
    agent.create_initial_profile("demo_user", ["LLM Agent", "RAG", "NLP", "Vision", "Safety"])

    query_keywords = agent.extract_keywords_from_query("I care about multi-agent RAG and agent memory.")
    assert "multi-agent" in query_keywords
    assert "rag" in query_keywords

    update = agent.update_profile_from_query("demo_user", "agent memory", ["Agent Memory"])
    assert update["updated_keywords"] == ["Agent Memory"]
    assert "demo_user" in agent.summarize_profile("demo_user")


def test_profile_agent_extracts_vision_keywords(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    agent = ProfileAgent(memory=repo)
    agent.create_initial_profile("demo_user", ["LLM Agent", "RAG", "NLP", "Vision", "Safety"])

    update = agent.update_profile_from_image(
        "demo_user",
        {
            "image_type": "experiment_chart",
            "main_content": "A chart about retrieval augmented generation",
            "possible_related_topics": ["RAG"],
            "recommendation_keywords": ["Agent Memory", "Evaluation"],
        },
    )

    assert update["updated_keywords"] == ["Agent Memory", "Evaluation", "RAG"]
    profile = agent.get_profile("demo_user")
    assert any(item["interest_name"] == "Agent Memory" for item in profile["interests"])
