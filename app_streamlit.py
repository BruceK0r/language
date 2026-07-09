from __future__ import annotations

from html import escape as escape_html
from typing import Any

import streamlit as st

from paper_agent.agent.workflow import PaperRadarWorkflow
from paper_agent.agents import CoordinatorAgent, ProfileAgent, RetrievalAgent
from paper_agent.config import get_settings
from paper_agent.memory.repository import MemoryRepository
from paper_agent.providers import build_vision_provider
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
    paper_profile_text,
    truncate_text,
    validate_interest_selection,
)


PAGE_ONBOARDING = "兴趣初始化 / Onboarding"
PAGE_RADAR = "科研雷达主页"
PAGE_PROFILE_CHARTS = "画像分析 / Profile"
PAGE_TEXT_QUERY = "文本查询"
PAGE_MULTIMODAL = "多模态查询"
PAGE_LEGACY = "兼容旧功能"
PAGE_OPTIONS = [PAGE_ONBOARDING, PAGE_RADAR, PAGE_PROFILE_CHARTS, PAGE_TEXT_QUERY, PAGE_MULTIMODAL, PAGE_LEGACY]


st.set_page_config(page_title="多模态多智能体个人科研雷达 Agent", layout="wide")
settings = get_settings()
memory = MemoryRepository(settings.database_path)
profile_agent = ProfileAgent(memory=memory)


PAGE_SUBTITLES = {
    PAGE_ONBOARDING: "建立当前用户的科研兴趣向量，作为后续检索和排序的个性化基线。",
    PAGE_RADAR: "聚合画像、真实论文源和多智能体排序结果的工作台。",
    PAGE_PROFILE_CHARTS: "查看兴趣权重、反馈记录和当前用户的长期偏好状态。",
    PAGE_TEXT_QUERY: "用自然语言发起一次可追踪的论文检索与推荐。",
    PAGE_MULTIMODAL: "从论文截图、架构图或实验图表出发，生成相关论文线索。",
    PAGE_LEGACY: "保留旧版检索、摘要和图片解释入口。",
}


def render_global_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --radar-bg: #050505;
            --radar-panel: #0d0d0d;
            --radar-panel-soft: #141414;
            --radar-border: #2a2a2a;
            --radar-border-soft: #1d1d1d;
            --radar-text: #f5f5f5;
            --radar-muted: #a6a6a6;
            --radar-dim: #737373;
            --radar-silver: #d8d8d8;
            --radar-radius: 8px;
        }

        .stApp, [data-testid="stAppViewContainer"] {
            background: #050505;
            color: #f5f5f5;
        }

        [data-testid="stHeader"] {
            background: rgba(5, 5, 5, 0.88);
            border-bottom: 1px solid var(--radar-border-soft);
        }

        [data-testid="stSidebar"] {
            background: #090909;
            border-right: 1px solid var(--radar-border);
        }

        [data-testid="stSidebar"] * {
            color: var(--radar-text);
        }

        .main .block-container {
            max-width: 1280px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        h1, h2, h3, h4, h5, h6, p, label, span, div {
            letter-spacing: 0;
        }

        h1, h2, h3 {
            color: var(--radar-text);
            font-weight: 650;
        }

        .radar-shell {
            color: var(--radar-text);
        }

        .radar-page-header {
            border: 1px solid var(--radar-border);
            background: var(--radar-panel);
            border-radius: var(--radar-radius);
            padding: 22px 24px 20px;
            margin: 0 0 22px;
        }

        .radar-eyebrow {
            color: var(--radar-dim);
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }

        .radar-page-header h1 {
            margin: 0;
            font-size: clamp(1.65rem, 2.1vw, 2.35rem);
            line-height: 1.15;
        }

        .radar-page-header p {
            margin: 10px 0 0;
            max-width: 820px;
            color: var(--radar-muted);
            line-height: 1.68;
        }

        .radar-sidebar-title {
            border: 1px solid var(--radar-border);
            border-radius: var(--radar-radius);
            padding: 13px 14px;
            margin: 0 0 14px;
            color: var(--radar-text);
            font-size: 0.88rem;
            font-weight: 700;
            letter-spacing: 0.08em;
        }

        .radar-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 8px 0 18px;
        }

        .radar-keyword-chip {
            display: inline-flex;
            align-items: center;
            min-height: 28px;
            border: 1px solid var(--radar-border);
            border-radius: 999px;
            padding: 3px 11px;
            background: #111111;
            color: var(--radar-silver);
            font-size: 0.82rem;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--radar-border) !important;
            background: var(--radar-panel) !important;
            border-radius: var(--radar-radius) !important;
            box-shadow: none !important;
        }

        .radar-paper-card {
            border-bottom: 1px solid var(--radar-border-soft);
            padding-bottom: 12px;
            margin-bottom: 12px;
        }

        .radar-paper-topline {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 18px;
        }

        .radar-paper-title {
            color: var(--radar-text);
            font-size: 1.04rem;
            font-weight: 680;
            line-height: 1.45;
            margin: 0;
        }

        .radar-score-pill {
            flex: 0 0 auto;
            border: 1px solid var(--radar-border);
            border-radius: 999px;
            padding: 4px 10px;
            color: var(--radar-text);
            background: #161616;
            font-variant-numeric: tabular-nums;
            font-size: 0.82rem;
        }

        .radar-paper-meta {
            color: var(--radar-muted);
            font-size: 0.84rem;
            line-height: 1.55;
            margin-top: 8px;
        }

        .radar-reason, .radar-abstract, .radar-vision-panel, .radar-report-panel {
            border: 1px solid var(--radar-border-soft);
            border-radius: var(--radar-radius);
            background: #101010;
            padding: 12px 14px;
            margin: 10px 0;
            color: var(--radar-text);
            line-height: 1.68;
        }

        .radar-vision-panel {
            white-space: pre-wrap;
        }

        .radar-reason span, .radar-abstract span {
            display: block;
            color: var(--radar-dim);
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 5px;
        }

        .radar-reason p, .radar-abstract p {
            margin: 0;
            color: var(--radar-silver);
        }

        .stButton > button, .stDownloadButton > button, div[data-testid="stLinkButton"] a {
            border-radius: var(--radar-radius) !important;
            border: 1px solid var(--radar-border) !important;
            background: #f5f5f5 !important;
            color: #050505 !important;
            font-weight: 650 !important;
            box-shadow: none !important;
        }

        .stButton > button[kind="secondary"] {
            background: #121212 !important;
            color: var(--radar-text) !important;
        }

        input, textarea, [data-baseweb="select"] > div {
            background: #101010 !important;
            border-color: var(--radar-border) !important;
            color: var(--radar-text) !important;
            border-radius: var(--radar-radius) !important;
        }

        input[type="radio"], input[type="checkbox"] {
            accent-color: #f5f5f5 !important;
        }

        [data-testid="stRadioOption"] > div > div > div:first-child {
            background: #262626 !important;
        }

        [data-testid="stRadioOption"] > div > div > div:first-child > div {
            background: #111111 !important;
        }

        [data-testid="stRadioOption"][data-selected="true"] > div > div > div:first-child {
            background: #f5f5f5 !important;
        }

        [data-testid="stRadioOption"][data-selected="true"] > div > div > div:first-child > div {
            background: #050505 !important;
        }

        [data-testid="stMetric"] {
            border: 1px solid var(--radar-border);
            border-radius: var(--radar-radius);
            background: var(--radar-panel-soft);
            padding: 12px 14px;
        }

        [data-testid="stMetricLabel"] p {
            color: var(--radar-muted);
        }

        [data-testid="stMetricValue"] {
            color: var(--radar-text);
        }

        [data-testid="stAlert"], [data-testid="stAlertContainer"], details {
            border-radius: var(--radar-radius) !important;
            border: 1px solid var(--radar-border) !important;
            background: #111111 !important;
            color: var(--radar-text) !important;
        }

        [data-testid="stAlertContainer"] *,
        [data-testid^="stAlertContent"] {
            background: transparent !important;
            color: var(--radar-text) !important;
            border-color: var(--radar-border) !important;
        }
        </style>
        <div class="radar-shell"></div>
        """,
        unsafe_allow_html=True,
    )


def _html(value: object) -> str:
    return escape_html(str(value or ""), quote=True)


def render_page_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <section class="radar-page-header">
            <div class="radar-eyebrow">Personal Research Radar</div>
            <h1>{_html(title)}</h1>
            <p>{_html(subtitle)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_keyword_chips(keywords: list[Any]) -> None:
    if not keywords:
        return
    chips = "".join(
        f'<span class="radar-keyword-chip">{_html(keyword)}</span>'
        for keyword in keywords[:12]
    )
    st.markdown(f'<div class="radar-chip-row">{chips}</div>', unsafe_allow_html=True)


render_global_styles()


def _coordinator() -> CoordinatorAgent:
    return CoordinatorAgent(
        memory=memory,
        profile_agent=profile_agent,
        retrieval_agent=RetrievalAgent(
            use_mock_search=bool(st.session_state.get("allow_demo_fallback", False)),
        ),
    )


def _current_user_id(default: str = "demo_user") -> str:
    return st.session_state.get("radar_user_id", default)


def _profile_ready(user_id: str) -> bool:
    profile = profile_agent.get_profile(user_id)
    return bool(profile.get("user", {}).get("onboarding_done"))


def _render_profile_summary(user_id: str) -> None:
    profile = profile_agent.get_profile(user_id)
    st.markdown(profile_agent.summarize_profile(user_id))
    interests = profile.get("interests", [])
    if interests:
        st.dataframe(
            [
                {
                    "兴趣方向": item["interest_name"],
                    "权重": round(item["weight"], 3),
                    "占比": f"{item['percentage']:.1f}%",
                    "来源": item["source"],
                }
                for item in interests
            ],
            use_container_width=True,
            hide_index=True,
        )


def _record_action(user_id: str, paper: dict[str, Any], action_type: str) -> None:
    paper_id = paper_id_from_payload(paper)
    if not paper_id:
        st.warning("该论文缺少可记录的 paper_id 或 url。")
        return
    profile_agent.log_user_action(user_id, paper_id, action_type)
    delta = action_delta(action_type)
    if delta is not None:
        keywords = profile_agent.extract_keywords_from_query(paper_profile_text(paper))
        profile_agent.memory.update_interest_weights(user_id, keywords, delta=delta, source=action_type)
    st.success("已记录反馈。")


def _render_paper_list(
    papers: list[dict[str, Any]],
    user_id: str,
    key_prefix: str,
    enable_actions: bool = True,
) -> None:
    if not papers:
        st.info("暂无可展示论文。")
        return
    for index, paper in enumerate(papers, start=1):
        paper_id = paper_id_from_payload(paper) or str(index)
        demo_paper = is_demo_paper(paper)
        source_label = paper_source_label(paper)
        with st.container(border=True):
            score_html = ""
            if paper.get("score") is not None:
                score_html = f'<div class="radar-score-pill">score {float(paper.get("score", 0.0)):.3f}</div>'
            st.markdown(
                f"""
                <div class="radar-paper-card">
                    <div class="radar-paper-topline">
                        <h3 class="radar-paper-title">{index}. {_html(paper.get("title", "Untitled"))}</h3>
                        {score_html}
                    </div>
                    <div class="radar-paper-meta">
                        来源：{_html(source_label)} · 作者：{_html(format_authors(paper.get("authors")))}
                        · 时间：{_html(paper.get("published_date") or paper.get("published") or "未知")}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if demo_paper:
                st.warning("演示数据，无真实链接。请关闭演示兜底并修复网络后重新检索真实论文。")
            if paper.get("reason"):
                st.markdown(
                    f"""
                    <div class="radar-reason">
                        <span>Reason</span>
                        <p>{_html(paper["reason"])}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            if paper.get("abstract"):
                st.markdown(
                    f"""
                    <div class="radar-abstract">
                        <span>Abstract</span>
                        <p>{_html(truncate_text(paper["abstract"], max_length=560))}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            if not demo_paper:
                link_col, pdf_col = st.columns(2)
                if paper.get("url"):
                    link_col.link_button("打开论文页面", paper["url"], use_container_width=True)
                if paper.get("pdf_url"):
                    pdf_col.link_button("打开 PDF", paper["pdf_url"], use_container_width=True)
            if enable_actions:
                col1, col2, col3 = st.columns(3)
                if col1.button("收藏", key=f"{key_prefix}-fav-{paper_id}"):
                    _record_action(user_id, paper, "favorited")
                if col2.button("不感兴趣", key=f"{key_prefix}-dislike-{paper_id}"):
                    _record_action(user_id, paper, "disliked")
                if col3.button("已读", key=f"{key_prefix}-read-{paper_id}"):
                    _record_action(user_id, paper, "read")


def render_query_result(
    result: dict[str, Any],
    user_id: str,
    key_prefix: str,
    recommendations_key: str = "recommendations",
    primary_title: str = "Top-K 推荐论文",
    follow_up_title: str = "额外 3 篇未出现论文",
) -> None:
    planned_query = result.get("planned_query", {})
    recommendations = result.get(recommendations_key, [])
    follow_up = result.get("follow_up_recommendations", [])
    errors = result.get("errors") or []
    uses_demo = any(is_demo_paper(paper) for paper in [*recommendations, *follow_up])

    status_cols = st.columns(3)
    status_cols[0].metric("推荐论文", len(recommendations))
    status_cols[1].metric("额外候选", len(follow_up))
    status_cols[2].metric("检索模式", "演示兜底" if uses_demo else "真实论文源")

    keywords = planned_query.get("keywords") or []
    _render_keyword_chips(keywords)

    if uses_demo:
        st.warning("当前结果包含演示论文，不代表真实论文库结果。关闭“允许使用演示论文兜底”并修复网络后可重新检索真实论文。")
    elif errors and not recommendations:
        st.error("真实论文源暂不可用或没有返回候选论文。请检查代理/网络后重试。")
    elif recommendations:
        st.success("已返回真实论文推荐。")

    st.subheader(primary_title)
    _render_paper_list(recommendations, user_id, f"{key_prefix}-primary", enable_actions=True)

    st.subheader(follow_up_title)
    _render_paper_list(follow_up, user_id, f"{key_prefix}-follow", enable_actions=False)

    profile_summary = result.get("profile_update", {}).get("summary")
    if profile_summary:
        with st.expander("画像更新摘要", expanded=False):
            st.write(profile_summary)

    if errors:
        with st.expander("运行降级与错误", expanded=not recommendations):
            for error in errors:
                st.write(f"- {error}")

    if result.get("answer"):
        with st.expander("查看完整 Markdown 报告", expanded=False):
            st.markdown(result["answer"])


def render_onboarding_page() -> None:
    render_page_header(PAGE_ONBOARDING, PAGE_SUBTITLES[PAGE_ONBOARDING])
    user_id = st.text_input("user_id", value=_current_user_id())
    try:
        interests = st.multiselect(
            "请选择 5 个你感兴趣的科研方向",
            BROAD_RESEARCH_KEYWORDS,
            max_selections=5,
        )
    except TypeError:
        interests = st.multiselect("请选择 5 个你感兴趣的科研方向", BROAD_RESEARCH_KEYWORDS)
    ok, message = validate_interest_selection(interests)
    if ok:
        st.success(message)
    else:
        st.warning(message)
    if st.button("生成我的科研雷达", type="primary", disabled=not ok):
        st.session_state["radar_user_id"] = user_id
        profile_agent.create_initial_profile(user_id, interests)
        query = build_initial_recommendation_query(interests)
        with st.spinner("正在生成初始推荐..."):
            result = _coordinator().run_text_query(user_id, query, top_k=5)
        st.session_state["radar_home_result"] = result
        st.success("科研雷达已生成。")
        render_query_result(result, user_id, "onboarding")


def render_radar_home_page() -> None:
    render_page_header(PAGE_RADAR, PAGE_SUBTITLES[PAGE_RADAR])
    user_id = st.text_input("当前 user_id", value=_current_user_id())
    st.session_state["radar_user_id"] = user_id
    if not _profile_ready(user_id):
        st.warning("请先到兴趣初始化页面选择 5 个科研方向。")
        return
    _render_profile_summary(user_id)
    profile = profile_agent.get_profile(user_id)
    top_interests = [item["interest_name"] for item in profile.get("interests", [])[:5]]
    if st.button("刷新推荐", type="primary"):
        query = build_initial_recommendation_query(top_interests)
        with st.spinner("正在刷新个性化推荐..."):
            st.session_state["radar_home_result"] = _coordinator().run_text_query(user_id, query, top_k=5)
    result = st.session_state.get("radar_home_result")
    if result:
        render_query_result(
            result,
            user_id,
            "radar-home",
            primary_title="个性化推荐论文",
            follow_up_title="额外 3 篇未出现论文",
        )
    else:
        st.info("点击刷新推荐获取当前用户的个性化论文列表。")


def render_profile_charts_page() -> None:
    render_page_header(PAGE_PROFILE_CHARTS, PAGE_SUBTITLES[PAGE_PROFILE_CHARTS])
    user_id = st.text_input("user_id", value=_current_user_id())
    st.session_state["radar_user_id"] = user_id
    if not _profile_ready(user_id):
        st.warning("请先到兴趣初始化页面选择 5 个科研方向。")
        return

    reset_confirmed = st.checkbox("我确认要清空当前 user_id 的画像和推荐记忆")
    if st.button("清空当前用户偏好记忆", type="secondary", disabled=not reset_confirmed):
        reset_summary = memory.reset_user_profile_memory(user_id)
        for key in ["radar_home_result", "text_query_result", "vision_query_result"]:
            st.session_state.pop(key, None)
        st.success("已清空当前用户偏好记忆。请回到兴趣初始化页面重新选择 5 个科研方向。")
        with st.expander("清空明细", expanded=False):
            st.json(reset_summary)
        return

    profile = profile_agent.get_profile(user_id)
    st.markdown(profile_agent.summarize_profile(user_id))

    stat_cards = build_profile_stat_cards(profile)
    metric_cols = st.columns(3)
    for index, card in enumerate(stat_cards):
        metric_cols[index % 3].metric(card["label"], card["value"])

    chart_rows = build_profile_chart_rows(profile)
    if not chart_rows:
        st.info("暂无兴趣画像数据。")
        return

    st.subheader("兴趣权重分布")
    st.bar_chart(chart_rows, x="兴趣方向", y="权重", use_container_width=True)
    st.subheader("兴趣明细")
    st.dataframe(chart_rows, use_container_width=True, hide_index=True)


def render_text_query_page() -> None:
    render_page_header(PAGE_TEXT_QUERY, PAGE_SUBTITLES[PAGE_TEXT_QUERY])
    user_id = st.text_input("user_id", value=_current_user_id())
    st.session_state["radar_user_id"] = user_id
    if not _profile_ready(user_id):
        st.warning("请先到兴趣初始化页面选择 5 个科研方向。")
        return
    query = st.text_area("科研问题", value="请推荐 multi-agent RAG 和 agent memory 相关论文。", height=120)
    top_k = st.slider("top_k", min_value=1, max_value=10, value=5)
    if st.button("开始查询", type="primary"):
        with st.spinner("正在执行多智能体文本查询..."):
            st.session_state["text_query_result"] = _coordinator().run_text_query(user_id, query, top_k=top_k)
    result = st.session_state.get("text_query_result")
    if result:
        render_query_result(
            result,
            user_id,
            "text",
            primary_title="Top-K 推荐论文",
            follow_up_title="请求结束后的 3 篇未出现论文",
        )


def render_multimodal_query_page() -> None:
    render_page_header(PAGE_MULTIMODAL, PAGE_SUBTITLES[PAGE_MULTIMODAL])
    user_id = st.text_input("user_id", value=_current_user_id())
    st.session_state["radar_user_id"] = user_id
    if not _profile_ready(user_id):
        st.warning("请先到兴趣初始化页面选择 5 个科研方向。")
        return

    uploaded = st.file_uploader("上传图片", type=["png", "jpg", "jpeg", "webp"])
    if uploaded is not None:
        try:
            st.image(uploaded, caption="图片预览", use_container_width=True)
        except TypeError:
            st.image(uploaded, caption="图片预览", use_column_width=True)

    question = st.text_area(
        "可选问题",
        value="",
        placeholder="例如：这张架构图和哪些 RAG / Multi-Agent 论文相关？",
        height=90,
    )
    top_k = st.slider("top_k", min_value=1, max_value=10, value=3)
    if st.button("分析图片并推荐论文", type="primary", disabled=uploaded is None):
        with st.spinner("正在理解图片并检索相关论文..."):
            st.session_state["vision_query_result"] = _coordinator().run_vision_query(
                user_id,
                uploaded,
                question=question,
                top_k=top_k,
            )

    result = st.session_state.get("vision_query_result")
    if not result:
        st.info("上传论文截图、模型架构图、实验图表或表格截图后即可生成相关论文推荐。")
        return

    vision_result = result.get("vision_result", {})
    if not vision_result.get("provider_available", True):
        st.warning(vision_result.get("main_content", "当前未配置视觉模型。"))
    st.markdown("### 图片理解")
    st.markdown(
        f'<div class="radar-vision-panel">{_html(vision_result.get("main_content") or "暂无图片解释。")}</div>',
        unsafe_allow_html=True,
    )
    with st.expander("结构化视觉结果"):
        st.json(vision_result)
    render_query_result(
        result,
        user_id,
        "vision",
        recommendations_key="related_recommendations",
        primary_title="图片相关论文",
        follow_up_title="额外 3 篇未出现论文",
    )


def render_legacy_page() -> None:
    render_page_header(PAGE_LEGACY, PAGE_SUBTITLES[PAGE_LEGACY])
    with st.sidebar:
        top_k = st.slider("旧检索 Top K", min_value=1, max_value=10, value=5)
        time_range = st.selectbox("旧检索时间范围", ["last_90_days", "last_30_days", "last_6_months", "last_12_months"])
        user_id = st.text_input("旧检索 user_id", value=_current_user_id())
    query = st.text_area(
        "研究领域或自然语言问题",
        value="检索最近三个月关于 LLM Agent Memory 的重要论文，并总结 Top 5。",
        height=110,
    )
    if st.button("开始旧检索", type="primary"):
        with st.spinner("正在检索、排序并生成中文简报..."):
            workflow = PaperRadarWorkflow(enable_pdf_download=not settings.use_mock_llm)
            state = workflow.run(user_query=query, top_k=top_k, time_range=time_range, user_id=user_id)
        st.session_state["legacy_state"] = state
    state = st.session_state.get("legacy_state")
    if state:
        st.subheader("扩展关键词")
        st.write(state.expanded_keywords)
        st.subheader("Top 论文")
        rows = [
            {
                "title": item.paper.title,
                "date": item.paper.published_date,
                "source": item.paper.source,
                "score": round(item.scores.final_score, 3),
                "url": item.paper.url,
            }
            for item in state.ranked_papers[:top_k]
        ]
        st.dataframe(rows, use_container_width=True)
        st.subheader("论文简报")
        st.markdown(state.final_report)
        if state.errors:
            with st.expander("运行降级与错误"):
                for error in state.errors:
                    st.write(f"- {error}")
    st.divider()
    st.subheader("图片 / 图表 / PDF 页面截图解释")
    uploaded = st.file_uploader("上传图片", type=["png", "jpg", "jpeg", "webp"])
    vision_note = st.text_input("可选说明", value="")
    if uploaded is not None and st.button("解释图片"):
        provider = build_vision_provider(settings)
        with st.spinner("正在分析图片..."):
            explanation = provider.analyze_image(
                uploaded.getvalue(),
                mime_type=uploaded.type or "image/png",
                prompt=vision_note or None,
            )
        st.markdown(explanation)


with st.sidebar:
    st.markdown('<div class="radar-sidebar-title">PAPER RADAR</div>', unsafe_allow_html=True)
    st.caption("运行模式")
    st.write(f"LLM：{'Mock' if settings.use_mock_llm else 'DeepSeek'}")
    st.write(f"Vision：{'Mock' if settings.use_mock_vision else 'Zhipu GLM-4.6V'}")
    st.session_state["allow_demo_fallback"] = st.checkbox(
        "允许使用演示论文兜底",
        value=bool(st.session_state.get("allow_demo_fallback", False)),
        help="真实论文源失败时才返回演示论文；演示论文没有真实链接。",
    )
    page = st.radio("页面", PAGE_OPTIONS, index=0)

if page == PAGE_ONBOARDING:
    render_onboarding_page()
elif page == PAGE_RADAR:
    render_radar_home_page()
elif page == PAGE_PROFILE_CHARTS:
    render_profile_charts_page()
elif page == PAGE_TEXT_QUERY:
    render_text_query_page()
elif page == PAGE_MULTIMODAL:
    render_multimodal_query_page()
else:
    render_legacy_page()
