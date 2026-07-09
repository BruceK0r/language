from paper_agent.memory.repository import MemoryRepository
from paper_agent.schemas import Paper


def test_initial_profile_stores_five_interests_with_percentages(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")

    repo.create_initial_profile(
        "demo_user",
        [
            "Large Language Models",
            "LLM Agent",
            "Multi-Agent Systems",
            "Retrieval-Augmented Generation",
            "Information Retrieval",
        ],
    )

    profile = repo.get_user_profile("demo_user")

    assert profile["user"]["user_id"] == "demo_user"
    assert profile["user"]["onboarding_done"] is True
    assert len(profile["interests"]) == 5
    assert {item["weight"] for item in profile["interests"]} == {1.0}
    assert round(sum(item["percentage"] for item in profile["interests"]), 2) == 100.0


def test_profile_updates_logs_and_filters_seen_papers(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    repo.create_initial_profile("demo_user", ["LLM Agent", "RAG", "NLP", "Vision", "Safety"])

    repo.update_profile_from_query("demo_user", "multi-agent rag memory", ["RAG", "Agent Memory"])
    repo.update_profile_from_image(
        "demo_user",
        {
            "image_type": "model_architecture",
            "user_question": "explain the diagram",
            "main_content": "RAG architecture",
            "recommendation_keywords": ["Multi-Agent Systems", "RAG"],
        },
    )
    repo.log_recommendations(
        "demo_user",
        "task-1",
        [
            {"paper_id": "p1", "score": 0.9, "reason": "matched RAG"},
            {"paper": {"paper_id": "p2"}, "score": 0.8, "reason": "matched agents"},
        ],
    )
    repo.log_user_action("demo_user", "p3", "read")

    profile = repo.get_user_profile("demo_user")
    assert any(item["interest_name"] == "RAG" and item["weight"] > 1.0 for item in profile["interests"])
    assert repo.get_seen_paper_ids("demo_user") == {"p1", "p2", "p3"}
    assert repo.filter_unseen_papers("demo_user", [{"paper_id": "p1"}, {"paper_id": "p4"}]) == [{"paper_id": "p4"}]


def test_reset_user_profile_memory_clears_user_preferences_but_keeps_papers(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    repo.create_initial_profile("demo_user", ["LLM Agent", "RAG", "NLP", "Vision", "Safety"])
    repo.upsert_paper(
        Paper(
            paper_id="paper-1",
            title="Real Paper",
            authors=["Ada"],
            abstract="RAG agent memory.",
            published_date="2026-01-01",
            url="https://arxiv.org/abs/2601.00001",
            source="arxiv",
        )
    )
    repo.update_profile_from_query("demo_user", "multi-agent rag memory", ["RAG", "Agent Memory"])
    repo.update_profile_from_image(
        "demo_user",
        {
            "image_type": "model_architecture",
            "user_question": "explain",
            "main_content": "RAG architecture",
            "recommendation_keywords": ["RAG"],
        },
    )
    repo.log_recommendations("demo_user", "task-1", [{"paper_id": "paper-1", "score": 0.9, "reason": "matched"}])
    repo.update_user_memory("demo_user", "RAG", "zh", "standard", [])

    reset_summary = repo.reset_user_profile_memory("demo_user")

    profile = repo.get_user_profile("demo_user")
    assert reset_summary == {
        "deleted_interests": 6,
        "deleted_actions": 1,
        "deleted_recommendation_logs": 1,
        "deleted_image_interactions": 1,
        "deleted_user_memory": 1,
    }
    assert profile["user"]["onboarding_done"] is False
    assert profile["interests"] == []
    assert repo.get_seen_paper_ids("demo_user") == set()
    assert repo.get_task("missing-task") is None
    repo.upsert_paper(
        Paper(
            paper_id="paper-1",
            title="Real Paper Updated",
            authors=["Ada"],
            abstract="Still cached.",
            published_date="2026-01-01",
            url="https://arxiv.org/abs/2601.00001",
            source="arxiv",
        )
    )
