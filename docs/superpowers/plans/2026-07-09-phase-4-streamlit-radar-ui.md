# Phase 4 Streamlit Radar UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single Streamlit demo screen with phase-4 navigation for onboarding, radar home, and text query while preserving legacy search and image explanation entry points.

**Architecture:** Put testable UI business rules in `paper_agent/ui/streamlit_helpers.py`; keep `app_streamlit.py` focused on Streamlit rendering and calls into `ProfileAgent`, `CoordinatorAgent`, and legacy `PaperRadarWorkflow`.

**Tech Stack:** Streamlit, Python 3.11, pytest, existing phase 1-3 agents.

## Global Constraints

- Initial interest selection must use `st.multiselect("请选择 5 个你感兴趣的科研方向", BROAD_RESEARCH_KEYWORDS, ...)`.
- User must select exactly 5 interests before onboarding can run.
- Do not delete old search or old image explanation functions; move them behind a compatible legacy page.
- If a user has not completed onboarding, radar/text-query pages must prompt them to initialize interests first.
- No API key or empty retrieval must not crash the page.
- Favorited and disliked actions must write logs and update the user profile; read actions write logs.
- Phase 4 does not implement phase 5 multimodal radar flow or phase 6 profile chart page.

---

### Task 1: UI Helpers

**Files:**
- Create: `paper_agent/ui/__init__.py`
- Create: `paper_agent/ui/streamlit_helpers.py`
- Test: `tests/test_streamlit_helpers.py`

**Interfaces:**
- Produces: `BROAD_RESEARCH_KEYWORDS: list[str]`
- Produces: `validate_interest_selection(interests: list[str]) -> tuple[bool, str]`
- Produces: `build_initial_recommendation_query(interests: list[str]) -> str`
- Produces: `paper_id_from_payload(paper: dict) -> str`
- Produces: `format_authors(authors: object) -> str`
- Produces: `action_delta(action_type: str) -> float | None`

- [ ] **Step 1: Write failing tests**

```python
from paper_agent.ui.streamlit_helpers import (
    BROAD_RESEARCH_KEYWORDS,
    action_delta,
    build_initial_recommendation_query,
    format_authors,
    paper_id_from_payload,
    validate_interest_selection,
)


def test_broad_keywords_and_validation():
    assert "Large Language Models" in BROAD_RESEARCH_KEYWORDS
    assert "Long-Context Modeling" in BROAD_RESEARCH_KEYWORDS
    assert len(BROAD_RESEARCH_KEYWORDS) == 25
    assert validate_interest_selection(BROAD_RESEARCH_KEYWORDS[:5])[0] is True
    assert validate_interest_selection(BROAD_RESEARCH_KEYWORDS[:4])[0] is False
    assert validate_interest_selection(BROAD_RESEARCH_KEYWORDS[:6])[0] is False


def test_initial_query_and_paper_helpers():
    query = build_initial_recommendation_query(["LLM Agent", "RAG"])
    assert "LLM Agent" in query
    assert "RAG" in query
    assert paper_id_from_payload({"paper_id": "p1"}) == "p1"
    assert paper_id_from_payload({"url": "https://example.com/paper"}) == "https://example.com/paper"
    assert format_authors(["Ada", "Ben"]) == "Ada, Ben"
    assert action_delta("favorited") == 0.3
    assert action_delta("disliked") == -0.2
    assert action_delta("read") is None
```

- [ ] **Step 2: Verify red**

Run: `py -m pytest tests/test_streamlit_helpers.py -v`

Expected: FAIL because `paper_agent.ui.streamlit_helpers` does not exist.

- [ ] **Step 3: Implement helpers**

Add the exact keyword list from the phase 4 spec, strict count validation, stable paper id fallback, author formatting, and feedback deltas.

- [ ] **Step 4: Verify green**

Run: `py -m pytest tests/test_streamlit_helpers.py -v`

Expected: PASS.

### Task 2: Streamlit App Structure

**Files:**
- Modify: `app_streamlit.py`
- Test: `tests/test_streamlit_app_static.py`

**Interfaces:**
- App contains pages: `兴趣初始化 / Onboarding`, `科研雷达主页`, `文本查询`, `兼容旧功能`
- App contains exact `st.multiselect` label required by phase 4.

- [ ] **Step 1: Write failing static test**

```python
from pathlib import Path


def test_streamlit_app_contains_phase4_pages_and_legacy_entry():
    source = Path("app_streamlit.py").read_text(encoding="utf-8")

    assert "兴趣初始化 / Onboarding" in source
    assert "科研雷达主页" in source
    assert "文本查询" in source
    assert "兼容旧功能" in source
    assert 'st.multiselect("请选择 5 个你感兴趣的科研方向"' in source
    assert "PaperRadarWorkflow" in source
    assert "build_vision_provider" in source
```

- [ ] **Step 2: Verify red**

Run: `py -m pytest tests/test_streamlit_app_static.py -v`

Expected: FAIL because current app is single-page and lacks phase-4 pages.

- [ ] **Step 3: Implement app pages**

Render sidebar navigation, onboarding form, radar home, text query page, and legacy page. Use phase 1-3 agents and helpers.

- [ ] **Step 4: Verify green**

Run: `py -m pytest tests/test_streamlit_app_static.py -v`

Expected: PASS.

### Task 3: Regression and UI Verification

**Files:**
- Test: existing tests
- Runtime: `app_streamlit.py`

- [ ] **Step 1: Run phase-4 tests**

Run: `py -m pytest tests/test_streamlit_helpers.py tests/test_streamlit_app_static.py -v`

Expected: PASS.

- [ ] **Step 2: Run full tests**

Run: `py -m pytest`

Expected: all tests pass. `.pytest_cache` permission warning may appear and is not a phase-4 failure.

- [ ] **Step 3: Compile app and helpers**

Run: `py -m py_compile app_streamlit.py paper_agent/ui/streamlit_helpers.py`

Expected: exit code 0.

- [ ] **Step 4: Start Streamlit and verify browser loads**

Run Streamlit on a free local port and open it in the in-app browser. Verify visible page includes the phase-4 navigation and onboarding multiselect.
