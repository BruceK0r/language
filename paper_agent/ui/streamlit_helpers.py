from __future__ import annotations

from typing import Any


BROAD_RESEARCH_KEYWORDS = [
    "Large Language Models",
    "LLM Agent",
    "Multi-Agent Systems",
    "Retrieval-Augmented Generation",
    "Prompt Engineering",
    "Natural Language Processing",
    "Multimodal Learning",
    "Computer Vision",
    "Recommendation Systems",
    "Information Retrieval",
    "Knowledge Graphs",
    "AI for Education",
    "AI for Science",
    "Robotics",
    "Reinforcement Learning",
    "Machine Learning Theory",
    "Graph Neural Networks",
    "Human-Computer Interaction",
    "Speech Processing",
    "Data Mining",
    "Trustworthy AI",
    "AI Safety",
    "Medical AI",
    "Efficient AI",
    "Long-Context Modeling",
]


def validate_interest_selection(interests: list[str]) -> tuple[bool, str]:
    count = len(interests)
    if count == 5:
        return True, "已选择 5 个科研方向。"
    return False, f"请恰好选择 5 个科研方向，当前选择了 {count} 个。"


def build_initial_recommendation_query(interests: list[str]) -> str:
    joined = ", ".join(interests)
    return f"Recommend recent important research papers about {joined}."


def paper_id_from_payload(paper: dict[str, Any]) -> str:
    return str(paper.get("paper_id") or paper.get("id") or paper.get("url") or paper.get("title") or "")


def format_authors(authors: object) -> str:
    if isinstance(authors, list):
        return ", ".join(str(author) for author in authors if str(author).strip()) or "检索结果未提供"
    if authors:
        return str(authors)
    return "检索结果未提供"


def paper_source_label(paper: dict[str, Any]) -> str:
    source = str(paper.get("source") or "").strip().lower()
    labels = {
        "arxiv": "arXiv",
        "semantic_scholar": "Semantic Scholar",
        "mock": "演示数据",
    }
    return labels.get(source, source or "未知来源")


def is_demo_paper(paper: dict[str, Any]) -> bool:
    source = str(paper.get("source") or "").strip().lower()
    url = str(paper.get("url") or "")
    pdf_url = str(paper.get("pdf_url") or "")
    return source == "mock" or "example.com" in url or "example.com" in pdf_url


def truncate_text(text: str, max_length: int = 420) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[:max_length].rstrip()}..."


def action_delta(action_type: str) -> float | None:
    if action_type == "favorited":
        return 0.3
    if action_type == "disliked":
        return -0.2
    return None


def build_profile_chart_rows(profile: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in profile.get("interests", [])[:limit]:
        rows.append(
            {
                "兴趣方向": str(item.get("interest_name") or ""),
                "权重": round(float(item.get("weight") or 0.0), 3),
                "占比": round(float(item.get("percentage") or 0.0), 2),
                "来源": str(item.get("source") or "unknown"),
            }
        )
    return rows


def build_profile_stat_cards(profile: dict[str, Any]) -> list[dict[str, Any]]:
    stats = profile.get("stats", {})
    return [
        {"label": "已展示论文", "value": int(stats.get("shown") or 0)},
        {"label": "推荐日志", "value": int(stats.get("recommended") or 0)},
        {"label": "收藏", "value": int(stats.get("favorited") or 0)},
        {"label": "不感兴趣", "value": int(stats.get("disliked") or 0)},
        {"label": "已读", "value": int(stats.get("read") or 0)},
        {"label": "图片交互", "value": int(stats.get("image_interactions") or 0)},
    ]


def paper_profile_text(paper: dict[str, Any]) -> str:
    return " ".join(str(paper.get(key) or "") for key in ("title", "abstract"))
