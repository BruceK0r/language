from paper_agent.ui.streamlit_helpers import (
    BROAD_RESEARCH_KEYWORDS,
    action_delta,
    build_profile_chart_rows,
    build_profile_stat_cards,
    build_initial_recommendation_query,
    format_authors,
    is_demo_paper,
    paper_id_from_payload,
    paper_source_label,
    truncate_text,
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
    assert paper_source_label({"source": "arxiv"}) == "arXiv"
    assert paper_source_label({"source": "semantic_scholar"}) == "Semantic Scholar"
    assert paper_source_label({"source": "mock"}) == "演示数据"
    assert is_demo_paper({"source": "mock", "url": "https://example.com/papers/demo"}) is True
    assert is_demo_paper({"source": "arxiv", "url": "https://arxiv.org/abs/2401.1"}) is False


def test_truncate_text_keeps_short_text_and_shortens_long_text():
    assert truncate_text("short text", max_length=20) == "short text"
    shortened = truncate_text("a" * 80, max_length=20)
    assert shortened == ("a" * 20) + "..."


def test_profile_chart_and_stat_helpers():
    profile = {
        "interests": [
            {"interest_name": "RAG", "weight": 2.3456, "percentage": 54.321, "source": "query"},
            {"interest_name": "Agent Memory", "weight": 1.2, "percentage": 27.0, "source": "image"},
        ],
        "stats": {
            "recommended": 9,
            "shown": 6,
            "favorited": 2,
            "disliked": 1,
            "read": 3,
            "image_interactions": 4,
        },
    }

    rows = build_profile_chart_rows(profile)
    assert rows == [
        {"兴趣方向": "RAG", "权重": 2.346, "占比": 54.32, "来源": "query"},
        {"兴趣方向": "Agent Memory", "权重": 1.2, "占比": 27.0, "来源": "image"},
    ]

    cards = build_profile_stat_cards(profile)
    assert cards == [
        {"label": "已展示论文", "value": 6},
        {"label": "推荐日志", "value": 9},
        {"label": "收藏", "value": 2},
        {"label": "不感兴趣", "value": 1},
        {"label": "已读", "value": 3},
        {"label": "图片交互", "value": 4},
    ]
