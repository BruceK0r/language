from __future__ import annotations

import streamlit as st

from paper_agent.agent.workflow import PaperRadarWorkflow
from paper_agent.config import get_settings
from paper_agent.providers import build_vision_provider


st.set_page_config(page_title="Paper Radar Agent", layout="wide")
st.title("领域论文检索与摘要 Agent")

settings = get_settings()

with st.sidebar:
    st.caption("运行模式")
    st.write(f"LLM：{'Mock' if settings.use_mock_llm else 'DeepSeek'}")
    st.write(f"Vision：{'Mock' if settings.use_mock_vision else 'Zhipu GLM-4.6V'}")
    top_k = st.slider("Top K", min_value=1, max_value=10, value=5)
    time_range = st.selectbox("时间范围", ["last_90_days", "last_30_days", "last_6_months", "last_12_months"])
    user_id = st.text_input("user_id", value="demo-user")

query = st.text_area(
    "研究领域或自然语言问题",
    value="检索最近三个月关于 LLM Agent Memory 的重要论文，并总结 Top 5。",
    height=110,
)

if st.button("开始检索", type="primary"):
    with st.spinner("正在检索、排序并生成中文简报..."):
        workflow = PaperRadarWorkflow(enable_pdf_download=not settings.use_mock_llm)
        state = workflow.run(user_query=query, top_k=top_k, time_range=time_range, user_id=user_id)
    st.session_state["last_state"] = state

state = st.session_state.get("last_state")
if state:
    st.subheader("扩展关键词")
    st.write(state.expanded_keywords)

    st.subheader("Top 论文")
    rows = []
    for item in state.ranked_papers[:top_k]:
        rows.append(
            {
                "title": item.paper.title,
                "date": item.paper.published_date,
                "source": item.paper.source,
                "score": round(item.scores.final_score, 3),
                "url": item.paper.url,
            }
        )
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

