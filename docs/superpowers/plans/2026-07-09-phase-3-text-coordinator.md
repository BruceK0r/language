# Phase 3 Text Coordinator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight multi-agent text-query workflow that plans a user query, retrieves papers, ranks them with `RecommenderAgent`, summarizes them, applies non-blocking critique metadata, reports Markdown, and updates the user profile.

**Architecture:** Keep the old `PaperRadarWorkflow` and `/search` untouched. Add small classes under `paper_agent/agents/` with dependency injection so tests can use static retrieval without network calls; `CoordinatorAgent.run_text_query()` composes the agents and returns the phase-3 contract.

**Tech Stack:** Python 3.11, pytest, existing `Paper`/`PaperSummary` schemas, existing tools/providers, phase-1 `ProfileAgent`, phase-2 `RecommenderAgent`.

## Global Constraints

- Do not change Streamlit pages in phase 3.
- Do not change or replace old `/search`.
- Do not introduce a complex multi-agent framework.
- Retrieval must reuse existing arXiv / Semantic Scholar tools when real retrieval is used.
- LLM unavailable must use deterministic fallback and must not crash.
- Empty retrieval must return a Markdown answer and empty recommendation lists.
- Every text query must update the user profile from query keywords.
- Every text query result must include `answer`, `recommendations`, `follow_up_recommendations`, `profile_update`, and `planned_query`.

---

### Task 1: Planning, Reading, Critic, Report Agents

**Files:**
- Create: `paper_agent/agents/query_planner_agent.py`
- Create: `paper_agent/agents/reader_agent.py`
- Create: `paper_agent/agents/critic_agent.py`
- Create: `paper_agent/agents/report_agent.py`
- Modify: `paper_agent/agents/__init__.py`
- Test: `tests/test_text_agents.py`

**Interfaces:**
- Produces: `QueryPlannerAgent.plan(query: str, top_k: int = 5) -> dict`
- Produces: `ReaderAgent.summarize(papers: list[dict], query: str) -> list[dict]`
- Produces: `CriticAgent.review(summaries: list[dict], source_texts: dict[str, str] | None = None) -> list[dict]`
- Produces: `ReportAgent.build_text_query_report(...) -> str`

- [ ] **Step 1: Write failing tests**

```python
from paper_agent.agents.query_planner_agent import QueryPlannerAgent
from paper_agent.agents.reader_agent import ReaderAgent
from paper_agent.agents.critic_agent import CriticAgent
from paper_agent.agents.report_agent import ReportAgent


def test_query_planner_rule_fallback_extracts_keywords_and_defaults():
    plan = QueryPlannerAgent(llm_provider=None).plan(
        "Find recent multi-agent RAG papers about agent memory",
        top_k=4,
    )

    assert plan["task_type"] == "paper_recommendation"
    assert plan["top_k"] == 4
    assert plan["time_range"] == "last_180_days"
    assert "multi-agent" in plan["keywords"]
    assert "rag" in plan["keywords"]


def test_reader_critic_and_report_generate_structured_markdown():
    papers = [
        {
            "paper_id": "p1",
            "title": "RAG Agent Memory",
            "authors": ["Ada"],
            "abstract": "This paper studies agent memory. It proposes retrieval augmented generation for agents.",
            "published_date": "2026-01-01",
            "url": "https://example.com/p1",
            "score": 0.91,
            "reason": "推荐原因：matched",
        }
    ]

    summaries = ReaderAgent(llm_provider=None).summarize(papers, "agent memory")
    reviewed = CriticAgent(llm_provider=None).review(summaries)
    report = ReportAgent().build_text_query_report(
        query="agent memory",
        planned_query={"keywords": ["agent memory"], "top_k": 1, "time_range": "last_180_days"},
        recommendations=papers,
        summaries=reviewed,
        follow_up_recommendations=[],
        profile_update={"summary": "Profile updated."},
        errors=[],
    )

    assert summaries[0]["problem"]
    assert reviewed[0]["critic_skipped"] is True
    assert "## 查询理解" in report
    assert "RAG Agent Memory" in report
```

- [ ] **Step 2: Verify red**

Run: `py -m pytest tests/test_text_agents.py -v`

Expected: FAIL because these agent modules do not exist.

- [ ] **Step 3: Implement deterministic agents**

Keep implementation minimal. Query planner uses regex and phrase matching. Reader summarizes abstract first sentences. Critic marks `critic_skipped=True` without blocking. Report generates Markdown sections required by phase 3.

- [ ] **Step 4: Verify green**

Run: `py -m pytest tests/test_text_agents.py -v`

Expected: PASS.

### Task 2: Retrieval Agent

**Files:**
- Create: `paper_agent/agents/retrieval_agent.py`
- Test: `tests/test_retrieval_agent.py`

**Interfaces:**
- Produces: `RetrievalAgent.retrieve(planned_query: dict) -> tuple[list[Paper], list[str]]`

- [ ] **Step 1: Write failing test**

```python
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
                published_date="2026-01-01",
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
```

- [ ] **Step 2: Verify red**

Run: `py -m pytest tests/test_retrieval_agent.py -v`

Expected: FAIL because `retrieval_agent.py` does not exist.

- [ ] **Step 3: Implement RetrievalAgent**

Parse `time_range`, call existing tools, deduplicate, and return `(papers, errors)`. If no tools return papers and `use_mock_search=True`, return `MockLLMProvider.sample_papers`.

- [ ] **Step 4: Verify green**

Run: `py -m pytest tests/test_retrieval_agent.py -v`

Expected: PASS.

### Task 3: CoordinatorAgent Text Flow

**Files:**
- Create: `paper_agent/agents/coordinator_agent.py`
- Modify: `paper_agent/agents/__init__.py`
- Test: `tests/test_coordinator_agent.py`

**Interfaces:**
- Produces: `CoordinatorAgent.run_text_query(user_id: str, query: str, top_k: int = 5) -> dict`

- [ ] **Step 1: Write failing test**

```python
from paper_agent.agents.coordinator_agent import CoordinatorAgent
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


def test_coordinator_runs_text_query_and_updates_profile(tmp_path):
    repo = MemoryRepository(tmp_path / "memory.db")
    repo.create_initial_profile("demo_user", ["RAG", "Agent Memory", "NLP", "Vision", "Safety"])
    coordinator = CoordinatorAgent(memory=repo, retrieval_agent=StaticRetrievalAgent())

    result = coordinator.run_text_query("demo_user", "agent memory RAG", top_k=1)

    assert result["recommendations"][0]["paper_id"] == "p1"
    assert len(result["follow_up_recommendations"]) == 1
    assert "## 查询理解" in result["answer"]
    assert result["profile_update"]["updated_keywords"]
    assert result["planned_query"]["top_k"] == 1
```

- [ ] **Step 2: Verify red**

Run: `py -m pytest tests/test_coordinator_agent.py -v`

Expected: FAIL because `coordinator_agent.py` does not exist.

- [ ] **Step 3: Implement CoordinatorAgent**

Compose planner, retrieval, recommender, reader, critic, report, profile. Convert recommended papers to summaries, update profile after query, and return the required dict shape. On empty retrieval, return empty lists and Markdown answer.

- [ ] **Step 4: Verify green**

Run: `py -m pytest tests/test_coordinator_agent.py -v`

Expected: PASS.

### Task 4: Regression Verification

**Files:**
- Test: existing `tests/`

- [ ] **Step 1: Run phase-3 tests**

Run: `py -m pytest tests/test_text_agents.py tests/test_retrieval_agent.py tests/test_coordinator_agent.py -v`

Expected: all phase-3 tests pass.

- [ ] **Step 2: Run profile/recommender/coordinator tests together**

Run: `py -m pytest tests/test_profile_memory.py tests/test_profile_agent.py tests/test_recommender_agent.py tests/test_text_agents.py tests/test_retrieval_agent.py tests/test_coordinator_agent.py -v`

Expected: all staged agent tests pass.

- [ ] **Step 3: Run full suite**

Run: `py -m pytest`

Expected: all tests pass. A `.pytest_cache` permission warning may appear in this workspace and is not a phase-3 failure.
