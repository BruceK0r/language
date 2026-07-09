# Streamlit UI Redesign Design

## Goal

Optimize the Streamlit research radar UI into a restrained black-and-white research workstation: high contrast, readable, technical, and not decorative or cheap-looking.

## Design Direction

- Use a near-black background, white and neutral gray text, subtle gray borders, and a very small amount of silver highlight.
- Avoid bright gradients, decorative blobs, oversized marketing hero sections, and loud color alerts.
- Keep the first screen functional: navigation, current runtime state, inputs, and research results remain immediately usable.
- Improve scanability for repeated research workflows: compact page headers, status metrics, keyword chips, paper cards, and calm reading areas.

## UI Units

- `render_global_styles()` injects the global CSS theme.
- `render_page_header(title, subtitle)` creates consistent page hierarchy.
- `render_query_result(...)` presents status metrics, keywords, recommended papers, follow-up papers, errors, and full reports.
- `_render_paper_list(...)` keeps each paper readable with title, score, metadata, reason, abstract, links, and feedback actions.
- Sidebar remains the main navigation surface and displays model mode state.

## Constraints

- Do not change retrieval, recommendation, memory, provider, or database behavior.
- Do not introduce a new frontend framework or dependency.
- Do not make a landing page.
- Preserve all existing Streamlit pages and legacy entry points.
- Add tests that confirm the theme and core UI markers stay present.

## Validation

- Add a static test for `render_global_styles`, black-and-white CSS tokens, and custom card classes.
- Run the Streamlit static tests.
- Run the full pytest suite.
- Start a fresh Streamlit server after implementation and verify it returns HTTP 200.
