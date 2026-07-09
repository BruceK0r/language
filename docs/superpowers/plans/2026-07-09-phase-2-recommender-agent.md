# Phase 2 Recommender Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `RecommenderAgent` with hybrid personalized ranking, seen-paper filtering, recommendation reasons, follow-up recommendations, and recommendation logging.

**Architecture:** Keep the legacy `PaperRadarWorkflow` untouched. Implement a new thin agent in `paper_agent/agents/recommender_agent.py` that consumes phase-1 profile/logging methods from `MemoryRepository`, accepts existing `Paper` objects or compatible dicts, and returns dict payloads suitable for phase 3/4 integration.

**Tech Stack:** Python 3.11, pytest, existing `paper_agent.schemas.Paper`, existing `paper_agent.memory.repository.MemoryRepository`.

## Global Constraints

- Do not change Streamlit pages in phase 2.
- Do not refactor the old workflow in phase 2.
- Preserve existing `/search`, `/vision/analyze`, `PaperRadarWorkflow`, and ranking tests.
- Ranking formula is exactly `0.30 * profile_match_score + 0.20 * query_relevance_score + 0.15 * recency_score + 0.10 * citation_score + 0.10 * novelty_score + 0.10 * quality_score + 0.05 * diversity_score`.
- Do not let an LLM decide ranking.
- Empty candidate pools return empty recommendations and a friendly message.
- Missing paper fields must not crash.
- Prefer filtering seen papers; only use seen fallback when the unseen pool is insufficient, and mark fallback items.

---

### Task 1: Hybrid Scoring

**Files:**
- Create: `paper_agent/agents/recommender_agent.py`
- Modify: `paper_agent/agents/__init__.py`
- Test: `tests/test_recommender_agent.py`

**Interfaces:**
- Consumes: `MemoryRepository.get_user_profile(user_id: str) -> dict`
- Produces: `RecommenderAgent.recommend(user_id: str, query: str, candidate_papers: list, top_k: int = 5, task_id: str | None = None) -> dict`

- [ ] **Step 1: Write failing test**

```python
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
```

- [ ] **Step 2: Verify red**

Run: `py -m pytest tests/test_recommender_agent.py::test_recommender_ranks_by_profile_and_query -v`

Expected: FAIL because `paper_agent.agents.recommender_agent` does not exist.

- [ ] **Step 3: Implement scoring**

Create paper normalization, token matching, recency/citation/quality scoring, final formula, and template reasons.

- [ ] **Step 4: Verify green**

Run: `py -m pytest tests/test_recommender_agent.py::test_recommender_ranks_by_profile_and_query -v`

Expected: PASS.

### Task 2: Seen Filtering and Logging

**Files:**
- Modify: `paper_agent/agents/recommender_agent.py`
- Test: `tests/test_recommender_agent.py`

**Interfaces:**
- Consumes: `MemoryRepository.get_seen_paper_ids(user_id: str) -> set[str]`
- Consumes: `MemoryRepository.log_recommendations(user_id: str, task_id: str, papers: list[dict]) -> None`

- [ ] **Step 1: Write failing tests**

```python
def test_recommender_filters_seen_papers_and_logs_shown(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    repo.create_initial_profile("demo_user", ["RAG", "Agent Memory", "NLP", "Vision", "Safety"])
    repo.log_recommendations("demo_user", "old-task", [{"paper_id": "seen"}])
    agent = RecommenderAgent(memory=repo)

    result = agent.recommend(
        "demo_user",
        "RAG",
        [
            {"paper_id": "seen", "title": "Seen RAG Paper", "abstract": "RAG", "published_date": "2026-01-01", "url": "https://example.com/seen"},
            {"paper_id": "fresh", "title": "Fresh RAG Paper", "abstract": "RAG", "published_date": "2026-01-02", "url": "https://example.com/fresh"},
        ],
        top_k=1,
        task_id="task-2",
    )

    assert [item["paper_id"] for item in result["recommendations"]] == ["fresh"]
    assert "fresh" in repo.get_seen_paper_ids("demo_user")
```

- [ ] **Step 2: Verify red**

Run: `py -m pytest tests/test_recommender_agent.py::test_recommender_filters_seen_papers_and_logs_shown -v`

Expected: FAIL until filtering/logging is implemented.

- [ ] **Step 3: Implement filtering and logging**

Filter seen ids first; if insufficient unseen items exist, append seen fallback items with `was_seen=True`. Log both top recommendations and follow-up recommendations as shown.

- [ ] **Step 4: Verify green**

Run: `py -m pytest tests/test_recommender_agent.py::test_recommender_filters_seen_papers_and_logs_shown -v`

Expected: PASS.

### Task 3: Empty and Sparse Candidates

**Files:**
- Modify: `paper_agent/agents/recommender_agent.py`
- Test: `tests/test_recommender_agent.py`

**Interfaces:**
- Produces: empty candidate response with `message`
- Produces: `follow_up_recommendations` with up to 3 items

- [ ] **Step 1: Write failing tests**

```python
def test_recommender_handles_empty_candidates(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    agent = RecommenderAgent(memory=repo)

    result = agent.recommend("demo_user", "RAG", [], top_k=5, task_id="task-empty")

    assert result["recommendations"] == []
    assert result["follow_up_recommendations"] == []
    assert "候选论文为空" in result["message"]
```

- [ ] **Step 2: Verify red**

Run: `py -m pytest tests/test_recommender_agent.py::test_recommender_handles_empty_candidates -v`

Expected: FAIL until empty handling exists.

- [ ] **Step 3: Implement empty handling**

Return stable empty payload and never call logging for an empty list.

- [ ] **Step 4: Verify green**

Run: `py -m pytest tests/test_recommender_agent.py::test_recommender_handles_empty_candidates -v`

Expected: PASS.

### Task 4: Regression Verification

**Files:**
- Test: existing `tests/`

- [ ] **Step 1: Run recommender tests**

Run: `py -m pytest tests/test_recommender_agent.py -v`

Expected: all phase-2 tests pass.

- [ ] **Step 2: Run profile and recommender tests together**

Run: `py -m pytest tests/test_profile_memory.py tests/test_profile_agent.py tests/test_recommender_agent.py -v`

Expected: all profile and recommender tests pass.

- [ ] **Step 3: Run full suite**

Run: `py -m pytest`

Expected: all tests pass. A `.pytest_cache` permission warning may appear in this workspace and is not a phase-2 failure.
