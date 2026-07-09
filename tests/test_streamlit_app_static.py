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


def test_streamlit_app_contains_phase5_multimodal_page():
    source = Path("app_streamlit.py").read_text(encoding="utf-8")

    assert "PAGE_MULTIMODAL" in source
    assert "render_multimodal_query_page" in source
    assert "run_vision_query" in source
    assert "file_uploader" in source
    assert "png" in source
    assert "webp" in source


def test_streamlit_app_contains_phase6_profile_chart_page():
    source = Path("app_streamlit.py").read_text(encoding="utf-8")

    assert "PAGE_PROFILE_CHARTS" in source
    assert "画像分析 / Profile" in source
    assert "render_profile_charts_page" in source
    assert "build_profile_chart_rows" in source
    assert "build_profile_stat_cards" in source
    assert "st.bar_chart" in source


def test_streamlit_app_uses_explicit_demo_fallback_and_structured_results():
    source = Path("app_streamlit.py").read_text(encoding="utf-8")

    assert "allow_demo_fallback" in source
    assert "允许使用演示论文兜底" in source
    assert "render_query_result" in source
    assert "查看完整 Markdown 报告" in source
    assert "演示数据，无真实链接" in source


def test_streamlit_app_contains_reset_profile_memory_controls():
    source = Path("app_streamlit.py").read_text(encoding="utf-8")

    assert "reset_user_profile_memory" in source
    assert "我确认要清空当前 user_id 的画像和推荐记忆" in source
    assert "清空当前用户偏好记忆" in source


def test_streamlit_app_contains_black_white_research_theme():
    source = Path("app_streamlit.py").read_text(encoding="utf-8")

    assert "def render_global_styles" in source
    assert "radar-shell" in source
    assert "radar-page-header" in source
    assert "radar-paper-card" in source
    assert "radar-keyword-chip" in source
    assert "#050505" in source
    assert "#f5f5f5" in source
    assert "linear-gradient" not in source


def test_project_has_technical_handoff_document():
    doc = Path("docs/TECHNICAL_HANDOFF.md")

    assert doc.exists()
    source = doc.read_text(encoding="utf-8")
    assert "系统整体逻辑" in source
    assert "时间桶检索" in source
    assert "推荐排序公式" in source
    assert "新一轮对话修改入口" in source
