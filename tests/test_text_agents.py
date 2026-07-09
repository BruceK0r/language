from paper_agent.agents.critic_agent import CriticAgent
from paper_agent.agents.query_planner_agent import QueryPlannerAgent
from paper_agent.agents.reader_agent import ReaderAgent
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


def test_reader_uses_llm_to_enrich_recommendation_reasons():
    class ReasonLLM:
        def __init__(self):
            self.calls = []

        def chat(self, messages, temperature=0.2):
            self.calls.append(messages)
            return f"LLM 推荐原因 {len(self.calls)}：这篇论文与查询高度相关，适合作为拓展阅读。"

    llm = ReasonLLM()
    papers = [
        {
            "paper_id": "p1",
            "title": "RAG Agent Memory",
            "abstract": "RAG agent memory.",
            "reason": "推荐原因：rule",
        },
        {
            "paper_id": "p2",
            "title": "Multi-Agent Planning",
            "abstract": "Multi-agent planning.",
            "reason": "推荐原因：rule",
        },
    ]

    enriched = ReaderAgent(llm_provider=llm).enrich_recommendation_reasons(
        papers,
        query="agent memory",
        purpose="follow_up",
    )

    assert len(llm.calls) == 2
    assert enriched[0]["reason"].startswith("LLM 推荐原因 1")
    assert enriched[0]["llm_reason"] == enriched[0]["reason"]
    assert enriched[1]["reason"].startswith("LLM 推荐原因 2")
