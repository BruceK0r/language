from datetime import date, timedelta

from paper_agent.agents.recommender_agent import RecommenderAgent
from paper_agent.memory.repository import MemoryRepository
from paper_agent.schemas import Paper


def test_recommender_ranks_by_profile_and_query(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    repo.create_initial_profile("demo_user", ["RAG", "Agent Memory", "NLP", "Vision", "Safety"])
    agent = RecommenderAgent(memory=repo)
    recent = date.today().isoformat()
    older = (date.today() - timedelta(days=300)).isoformat()
    papers = [
        Paper(
            paper_id="p1",
            title="Retrieval-Augmented Agent Memory for LLM Agents",
            authors=["Ada"],
            abstract="RAG and agent memory improve long-horizon planning.",
            published_date=recent,
            url="https://example.com/p1",
            pdf_url="https://example.com/p1.pdf",
            source="mock",
            citation_count=80,
        ),
        Paper(
            paper_id="p2",
            title="Unrelated Vision Dataset",
            authors=["Ben"],
            abstract="A dataset for image classification.",
            published_date=older,
            url="https://example.com/p2",
            source="mock",
            citation_count=5,
        ),
    ]

    result = agent.recommend("demo_user", "agent memory RAG", papers, top_k=1, task_id="task-1")

    assert result["recommendations"][0]["paper_id"] == "p1"
    assert result["recommendations"][0]["score"] > result["follow_up_recommendations"][0]["score"]
    assert result["recommendations"][0]["matched_interests"]
    assert "推荐原因" in result["recommendations"][0]["reason"]


def test_recommender_filters_seen_papers_and_logs_shown(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    repo.create_initial_profile("demo_user", ["RAG", "Agent Memory", "NLP", "Vision", "Safety"])
    repo.log_recommendations("demo_user", "old-task", [{"paper_id": "seen"}])
    agent = RecommenderAgent(memory=repo)

    result = agent.recommend(
        "demo_user",
        "RAG",
        [
            {
                "paper_id": "seen",
                "title": "Seen RAG Paper",
                "abstract": "RAG",
                "published_date": date.today().isoformat(),
                "url": "https://example.com/seen",
            },
            {
                "paper_id": "fresh",
                "title": "Fresh RAG Paper",
                "abstract": "RAG",
                "published_date": date.today().isoformat(),
                "url": "https://example.com/fresh",
            },
        ],
        top_k=1,
        task_id="task-2",
    )

    assert [item["paper_id"] for item in result["recommendations"]] == ["fresh"]
    assert "fresh" in repo.get_seen_paper_ids("demo_user")


def test_recommender_uses_seen_fallback_when_unseen_pool_is_small(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    repo.create_initial_profile("demo_user", ["RAG", "Agent Memory", "NLP", "Vision", "Safety"])
    repo.log_recommendations("demo_user", "old-task", [{"paper_id": "seen"}])
    agent = RecommenderAgent(memory=repo)

    result = agent.recommend(
        "demo_user",
        "RAG",
        [
            {
                "paper_id": "seen",
                "title": "Seen RAG Paper",
                "abstract": "RAG",
                "published_date": date.today().isoformat(),
                "url": "https://example.com/seen",
            },
            {
                "paper_id": "fresh",
                "title": "Fresh RAG Paper",
                "abstract": "RAG",
                "published_date": date.today().isoformat(),
                "url": "https://example.com/fresh",
            },
        ],
        top_k=2,
        task_id="task-3",
    )

    assert [item["paper_id"] for item in result["recommendations"]] == ["fresh", "seen"]
    assert result["recommendations"][1]["was_seen"] is True
    assert result["used_seen_fallback"] is True


def test_recommender_handles_empty_candidates(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    agent = RecommenderAgent(memory=repo)

    result = agent.recommend("demo_user", "RAG", [], top_k=5, task_id="task-empty")

    assert result["recommendations"] == []
    assert result["follow_up_recommendations"] == []
    assert "候选论文为空" in result["message"]


def test_recommender_returns_three_follow_ups_and_tolerates_missing_fields(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    repo.create_initial_profile("demo_user", ["RAG", "Agent Memory", "NLP", "Vision", "Safety"])
    agent = RecommenderAgent(memory=repo)

    papers = [
        {"paper_id": f"p{index}", "title": f"RAG Agent Memory Paper {index}", "abstract": "RAG agent memory"}
        for index in range(5)
    ]

    result = agent.recommend("demo_user", "RAG agent memory", papers, top_k=2, task_id="task-follow-up")

    assert len(result["recommendations"]) == 2
    assert len(result["follow_up_recommendations"]) == 3
    assert all(item["score"] >= 0 for item in result["recommendations"])
    assert all("reason" in item for item in result["follow_up_recommendations"])


def test_recommender_uses_updated_score_weights(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    repo.create_initial_profile("demo_user", ["RAG", "Agent Memory", "NLP", "Vision", "Safety"])
    agent = RecommenderAgent(memory=repo)

    result = agent.recommend(
        "demo_user",
        "RAG agent memory",
        [
            Paper(
                paper_id="weighted",
                title="RAG Agent Memory",
                authors=["Ada"],
                abstract="RAG agent memory for planning.",
                published_date=date.today().isoformat(),
                url="https://arxiv.org/abs/2601.00001",
                pdf_url="https://arxiv.org/pdf/2601.00001",
                source="arxiv",
                citation_count=25,
            )
        ],
        top_k=1,
        task_id="task-weights",
    )

    breakdown = result["recommendations"][0]["score_breakdown"]
    expected = (
        0.30 * breakdown["profile_match_score"]
        + 0.20 * breakdown["query_relevance_score"]
        + 0.20 * breakdown["recency_score"]
        + 0.15 * breakdown["citation_score"]
        + 0.05 * breakdown["novelty_score"]
        + 0.05 * breakdown["quality_score"]
        + 0.05 * breakdown["diversity_score"]
    )
    assert abs(breakdown["final_score"] - round(expected, 6)) <= 0.000002
