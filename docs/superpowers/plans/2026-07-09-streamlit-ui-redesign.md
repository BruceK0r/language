# Streamlit UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply a restrained black-and-white research workstation visual system to the existing Streamlit paper radar app.

**Architecture:** Keep all business logic in place. Add global CSS and small rendering helpers in `app_streamlit.py`, then update existing page and result rendering functions to use those helpers.

**Tech Stack:** Python, Streamlit, pytest static source tests.

## Global Constraints

- Do not change retrieval, recommendation, memory, provider, or database behavior.
- Do not add frontend dependencies.
- Preserve existing page names and legacy entry points.
- Use TDD: add static UI tests before implementation.

---

### Task 1: Theme Regression Test

**Files:**
- Modify: `tests/test_streamlit_app_static.py`

**Interfaces:**
- Consumes: existing `app_streamlit.py` source.
- Produces: static assertions for `render_global_styles`, theme tokens, and custom UI class names.

- [ ] **Step 1: Write failing test**

Add `test_streamlit_app_contains_black_white_research_theme`.

- [ ] **Step 2: Run focused test**

Run: `py -m pytest tests/test_streamlit_app_static.py::test_streamlit_app_contains_black_white_research_theme -v`

Expected: fail before implementation because the theme helper and class names do not exist.

### Task 2: Global Theme And Helpers

**Files:**
- Modify: `app_streamlit.py`

**Interfaces:**
- Produces: `render_global_styles()`, `render_page_header(...)`, `_render_keyword_chips(...)`, and custom CSS classes.

- [ ] **Step 1: Implement global CSS**

Add a restrained black-and-white theme using Streamlit-safe CSS selectors and `.radar-*` custom classes.

- [ ] **Step 2: Add page headers**

Replace bare `st.title(...)` calls in main pages with `render_page_header(...)`.

- [ ] **Step 3: Improve result cards**

Update `_render_paper_list(...)` and `render_query_result(...)` to use clearer card header, metadata, reason, abstract, and chip layout.

- [ ] **Step 4: Run focused tests**

Run: `py -m pytest tests/test_streamlit_app_static.py -v`

Expected: pass.

### Task 3: Full Verification

**Files:**
- Modify: none unless tests reveal issues.

- [ ] **Step 1: Run full test suite**

Run: `py -m pytest`

Expected: all tests pass.

- [ ] **Step 2: Syntax check without pyc writes**

Run: `py -c "import ast, pathlib; ast.parse(pathlib.Path('app_streamlit.py').read_text(encoding='utf-8'))"`

Expected: exit code 0.

- [ ] **Step 3: Start fresh Streamlit service**

Start a new port and verify HTTP 200.
