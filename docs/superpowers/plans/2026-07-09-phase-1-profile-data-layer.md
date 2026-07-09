# Phase 1 Profile Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add user profile, recommendation log, image interaction, and action logging support without changing Streamlit or the existing search workflow.

**Architecture:** Extend the existing SQLite initialization and `MemoryRepository` so old `user_memory` behavior keeps working. Add a small `ProfileAgent` under `paper_agent/agents/` that delegates persistence to `MemoryRepository` and uses deterministic keyword fallback when no LLM extraction is available.

**Tech Stack:** Python 3.11, SQLite, pytest, existing `paper_agent.memory` and `paper_agent.schemas` modules.

## Global Constraints

- Do not change Streamlit pages in phase 1.
- Do not change the main recommendation/search workflow in phase 1.
- Preserve existing `/search`, `/vision/analyze`, `PaperRadarWorkflow`, and `user_memory` behavior.
- Onboarding interests start with `weight = 1.0`.
- Query keywords add `+0.2`; image keywords add `+0.15`; later action keyword updates use `+0.3` for favorited and `-0.2` for disliked with a floor of `0`.
- Profile reads return raw weights and normalized percentages.
- LLM unavailable must fall back to rules and must not crash.

---

### Task 1: Profile Persistence

**Files:**
- Modify: `paper_agent/memory/db.py`
- Modify: `paper_agent/memory/repository.py`
- Test: `tests/test_profile_memory.py`

**Interfaces:**
- Produces: `MemoryRepository.create_user_if_not_exists(user_id: str) -> None`
- Produces: `MemoryRepository.create_initial_profile(user_id: str, interests: list[str]) -> None`
- Produces: `MemoryRepository.get_user_profile(user_id: str) -> dict`
- Produces: `MemoryRepository.update_interest_weights(user_id: str, keywords: list[str], delta: float, source: str) -> None`

- [ ] **Step 1: Write failing tests**

```python
from paper_agent.memory.repository import MemoryRepository


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_profile_memory.py::test_initial_profile_stores_five_interests_with_percentages -v`

Expected: FAIL because `create_initial_profile` does not exist.

- [ ] **Step 3: Implement minimal persistence**

Add the five new tables to `init_db`. Add methods to insert/update users, upsert interests, and calculate profile percentages.

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_profile_memory.py::test_initial_profile_stores_five_interests_with_percentages -v`

Expected: PASS.

### Task 2: Profile Updates and Logs

**Files:**
- Modify: `paper_agent/memory/repository.py`
- Test: `tests/test_profile_memory.py`

**Interfaces:**
- Produces: `MemoryRepository.update_profile_from_query(user_id: str, query: str, extracted_keywords: list[str] | None = None) -> None`
- Produces: `MemoryRepository.update_profile_from_image(user_id: str, vision_result: dict) -> None`
- Produces: `MemoryRepository.log_user_action(user_id: str, paper_id: str, action_type: str) -> None`
- Produces: `MemoryRepository.get_seen_paper_ids(user_id: str) -> set[str]`
- Produces: `MemoryRepository.log_recommendations(user_id: str, task_id: str, papers: list[dict]) -> None`
- Produces: `MemoryRepository.filter_unseen_papers(user_id: str, papers: list[dict]) -> list[dict]`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_profile_memory.py::test_profile_updates_logs_and_filters_seen_papers -v`

Expected: FAIL because update/logging methods do not exist.

- [ ] **Step 3: Implement update and logging methods**

Use `recommendation_logs` plus `user_actions` for seen paper ids. Store image keywords as JSON text in `image_interactions.extracted_keywords`.

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_profile_memory.py::test_profile_updates_logs_and_filters_seen_papers -v`

Expected: PASS.

### Task 3: ProfileAgent

**Files:**
- Create: `paper_agent/agents/__init__.py`
- Create: `paper_agent/agents/profile_agent.py`
- Test: `tests/test_profile_agent.py`

**Interfaces:**
- Produces: `ProfileAgent.create_initial_profile(user_id: str, interests: list[str]) -> None`
- Produces: `ProfileAgent.get_profile(user_id: str) -> dict`
- Produces: `ProfileAgent.extract_keywords_from_query(query: str) -> list[str]`
- Produces: `ProfileAgent.extract_keywords_from_vision(vision_result: dict) -> list[str]`
- Produces: `ProfileAgent.update_profile_from_query(user_id: str, query: str, extracted_keywords: list[str] | None = None) -> dict`
- Produces: `ProfileAgent.update_profile_from_image(user_id: str, vision_result: dict) -> dict`
- Produces: `ProfileAgent.summarize_profile(user_id: str) -> str`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_profile_agent.py::test_profile_agent_uses_rule_fallback_and_summary -v`

Expected: FAIL because `paper_agent.agents.profile_agent` does not exist.

- [ ] **Step 3: Implement ProfileAgent**

Keep it thin. Use repository methods for persistence and regex/rule fallback for extraction.

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_profile_agent.py::test_profile_agent_uses_rule_fallback_and_summary -v`

Expected: PASS.

### Task 4: Regression Verification

**Files:**
- Test: existing `tests/`

- [ ] **Step 1: Run focused profile tests**

Run: `py -m pytest tests/test_profile_memory.py tests/test_profile_agent.py -v`

Expected: all phase-1 tests pass.

- [ ] **Step 2: Run full suite**

Run: `py -m pytest`

Expected: existing `/search` workflow tests still pass. A `.pytest_cache` permission warning may appear in this workspace and is not a phase-1 failure.
