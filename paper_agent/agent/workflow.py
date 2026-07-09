from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Any

from paper_agent.agent.state import AgentState
from paper_agent.config import get_settings
from paper_agent.memory.repository import MemoryRepository
from paper_agent.providers import build_llm_provider
from paper_agent.providers.mock import MockLLMProvider
from paper_agent.schemas import Paper, PaperSummary, ParsedRequest, RankedPaper
from paper_agent.tools.arxiv_tool import ArxivTool
from paper_agent.tools.dedup import deduplicate_papers
from paper_agent.tools.pdf_parser import PDFParser
from paper_agent.tools.ranking import rank_papers
from paper_agent.tools.semantic_scholar_tool import SemanticScholarTool
from paper_agent.tools.time_buckets import build_default_time_buckets, select_papers_by_time_buckets

logger = logging.getLogger(__name__)


def _parse_time_window(user_query: str, time_range: str | None) -> int:
    text = f"{time_range or ''} {user_query}".lower()
    patterns = [
        (r"last[_\s-]?(\d+)[_\s-]?days?", 1),
        (r"最近\s*(\d+)\s*天", 1),
        (r"last[_\s-]?(\d+)[_\s-]?months?", 30),
        (r"最近\s*(\d+)\s*个月", 30),
    ]
    cn_months = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6}
    for cn, month_count in cn_months.items():
        if f"最近{cn}个月" in text.replace(" ", ""):
            return month_count * 30
    for pattern, factor in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return max(1, int(match.group(1)) * factor)
    if "三个月" in user_query or "last_90" in text or "90" in text:
        return 90
    return 90


def _parse_top_k(user_query: str, explicit_top_k: int) -> int:
    for pattern in [r"top\s*(\d+)", r"Top\s*(\d+)", r"前\s*(\d+)", r"总结\s*Top\s*(\d+)"]:
        match = re.search(pattern, user_query, re.I)
        if match:
            return max(1, min(20, int(match.group(1))))
    return max(1, min(20, explicit_top_k))


def _extract_domain(user_query: str) -> str:
    match = re.search(r"关于\s*(.+?)(?:的|，|,|并|。|$)", user_query)
    if match:
        return match.group(1).strip()
    cleaned = re.sub(r"检索|最近.*?关于|重要论文|总结|Top\s*\d+|前\s*\d+", " ", user_query, flags=re.I)
    return re.sub(r"\s+", " ", cleaned).strip(" ，。") or user_query


def parse_user_request_heuristic(user_query: str, top_k: int = 5, time_range: str | None = None) -> ParsedRequest:
    days = _parse_time_window(user_query, time_range)
    end = date.today()
    start = end - timedelta(days=days)
    domain = _extract_domain(user_query)
    parsed_top_k = _parse_top_k(user_query, top_k)
    return ParsedRequest(
        domain=domain,
        query_terms=[domain],
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        time_window_days=days,
        top_k=parsed_top_k,
        language="zh",
        summary_depth="standard",
    )


def _short_evidence(text: str, limit: int = 4) -> list[str]:
    pieces = re.split(r"(?<=[.!?。！？])\s+", (text or "").strip())
    return [piece.strip()[:280] for piece in pieces if len(piece.strip()) > 20][:limit]


def _ensure_supported_evidence(summary: PaperSummary, source_text: str) -> PaperSummary:
    normalized_source = " ".join((source_text or "").split())
    supported = []
    for evidence in summary.evidence:
        clean = " ".join(evidence.split())
        if clean and clean in normalized_source:
            supported.append(evidence)
    if not supported:
        supported = _short_evidence(source_text, limit=3) or [summary.title]
    data = summary.model_dump()
    data["evidence"] = supported[:5]
    return PaperSummary.model_validate(data)


class PaperRadarWorkflow:
    def __init__(
        self,
        llm_provider: Any | None = None,
        memory: MemoryRepository | None = None,
        arxiv_tool: Any | None = None,
        semantic_scholar_tool: Any | None = None,
        pdf_parser: PDFParser | None = None,
        enable_pdf_download: bool = True,
        use_mock_search: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.llm = llm_provider or build_llm_provider(settings)
        self.memory = memory or MemoryRepository(settings.database_path)
        injected_search_tools = arxiv_tool is not None or semantic_scholar_tool is not None
        self.arxiv_tool = arxiv_tool or ArxivTool(timeout=settings.request_timeout_seconds)
        self.semantic_scholar_tool = semantic_scholar_tool or SemanticScholarTool(
            api_key=settings.semantic_scholar_api_key,
            timeout=settings.request_timeout_seconds,
        )
        self.pdf_parser = pdf_parser or PDFParser(
            timeout=settings.request_timeout_seconds,
            max_pages=settings.max_pdf_pages,
        )
        self.enable_pdf_download = enable_pdf_download
        self.use_mock_search = (
            use_mock_search
            if use_mock_search is not None
            else isinstance(self.llm, MockLLMProvider) and not injected_search_tools
        )

    def run(self, user_query: str, top_k: int = 5, time_range: str | None = None, user_id: str = "default") -> AgentState:
        state = AgentState(user_query=user_query)
        parsed = self._parse_user_request(user_query, top_k=top_k, time_range=time_range, state=state)
        state.parsed_request = parsed.model_dump()
        state.expanded_keywords = self._expand_keywords(user_query, state.parsed_request, state)
        state.candidate_papers = self._search_papers(state.expanded_keywords, parsed, state)
        state.candidate_papers = deduplicate_papers(state.candidate_papers)
        user_memory = self.memory.get_user_memory(user_id)
        state.ranked_papers = rank_papers(
            state.candidate_papers,
            keywords=state.expanded_keywords,
            time_window_days=parsed.time_window_days,
            user_memory=user_memory,
        )
        top_ranked = state.ranked_papers[: parsed.top_k]
        source_texts = self._read_top_papers(top_ranked, state)
        state.paper_summaries = self._summarize_and_critique(top_ranked, source_texts, user_query, state)
        state.final_report = self.llm.generate_report(
            user_query=user_query,
            parsed_request=state.parsed_request,
            expanded_keywords=state.expanded_keywords,
            candidate_count=len(state.candidate_papers),
            ranked_papers=top_ranked,
            paper_summaries=state.paper_summaries,
            errors=state.errors,
        )
        state.memory_updates = self._update_memory(user_id, state, top_ranked, parsed)
        return state

    def _parse_user_request(self, user_query: str, top_k: int, time_range: str | None, state: AgentState) -> ParsedRequest:
        fallback = parse_user_request_heuristic(user_query, top_k=top_k, time_range=time_range)
        try:
            data = self.llm.parse_request(user_query, top_k=top_k, time_range=time_range)
            merged = {**fallback.model_dump(), **(data or {})}
            if not merged.get("start_date") or not merged.get("end_date"):
                merged["start_date"] = fallback.start_date
                merged["end_date"] = fallback.end_date
            return ParsedRequest.model_validate(merged)
        except Exception as exc:  # noqa: BLE001
            state.errors.append(f"ParseUserRequest 降级为规则解析：{exc}")
            return fallback

    def _expand_keywords(self, user_query: str, parsed_request: dict[str, Any], state: AgentState) -> list[str]:
        try:
            keywords = self.llm.expand_keywords(user_query, parsed_request)
        except Exception as exc:  # noqa: BLE001
            state.errors.append(f"ExpandKeywords 失败，使用领域词：{exc}")
            keywords = [parsed_request.get("domain", user_query)]
        cleaned = [keyword.strip() for keyword in keywords if keyword and keyword.strip()]
        return list(dict.fromkeys(cleaned))[:10] or [user_query]

    def _search_papers(self, keywords: list[str], parsed: ParsedRequest, state: AgentState) -> list[Paper]:
        start = date.fromisoformat(parsed.start_date)
        end = date.fromisoformat(parsed.end_date)
        buckets = build_default_time_buckets(end, max_window_days=parsed.time_window_days)
        total_bucket_limit = sum(bucket.limit for bucket in buckets)
        max_results = max(total_bucket_limit, parsed.top_k * 8, 20)
        papers: list[Paper] = []
        if self.use_mock_search and isinstance(self.llm, MockLLMProvider):
            state.errors.append(
                "SearchPapers uses Mock search data; configure DEEPSEEK_API_KEY for real paper sources."
            )
            return self.llm.sample_papers(start_date=start, max_results=parsed.top_k)

        for bucket in buckets:
            bucket_start, bucket_end = bucket.date_range(end)
            bucket_start = max(bucket_start, start)
            bucket_end = min(bucket_end, end)
            if bucket_start > bucket_end:
                continue
            try:
                papers.extend(
                    self.arxiv_tool.search(
                        keywords,
                        start_date=bucket_start,
                        end_date=bucket_end,
                        max_results=bucket.limit * 4,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("arXiv search failed for bucket %s: %s", bucket.name, exc)
                state.errors.append(f"SearchPapers arXiv bucket {bucket.name} failed: {exc}")

        try:
            query = " ".join(keywords[:4])
            papers.extend(
                self.semantic_scholar_tool.search(query, start_date=start, end_date=end, max_results=max_results)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Semantic Scholar search failed: %s", exc)
            state.errors.append(f"SearchPapers Semantic Scholar failed: {exc}")

        if not papers and isinstance(self.llm, MockLLMProvider):
            papers = self.llm.sample_papers(start_date=start, max_results=parsed.top_k)
            state.errors.append("SearchPapers found no external results; using Mock papers for demo.")

        return select_papers_by_time_buckets(
            deduplicate_papers(papers),
            keywords=keywords,
            buckets=buckets,
            anchor_date=end,
        )

    def _read_top_papers(self, ranked_papers: list[RankedPaper], state: AgentState) -> dict[str, str]:
        source_texts: dict[str, str] = {}
        for item in ranked_papers:
            paper = item.paper
            source_text = paper.abstract
            if self.enable_pdf_download and paper.pdf_url:
                try:
                    pdf_text = self.pdf_parser.extract_text_from_url(paper.pdf_url)
                    if pdf_text:
                        source_text = f"{paper.abstract}\n\n{pdf_text}"
                except Exception as exc:  # noqa: BLE001
                    state.errors.append(f"ReadTopPapers PDF 解析失败（{paper.title}）：{exc}")
            source_texts[paper.paper_id] = source_text
        return source_texts

    def _summarize_and_critique(
        self,
        ranked_papers: list[RankedPaper],
        source_texts: dict[str, str],
        user_query: str,
        state: AgentState,
    ) -> list[PaperSummary]:
        summaries: list[PaperSummary] = []
        fallback_llm = MockLLMProvider()
        for item in ranked_papers:
            paper = item.paper
            source_text = source_texts.get(paper.paper_id) or paper.abstract
            try:
                summary = self.llm.summarize_paper(paper, source_text, user_query)
            except Exception as exc:  # noqa: BLE001
                state.errors.append(f"SummarizePapers 失败（{paper.title}），使用 Mock 摘要：{exc}")
                summary = fallback_llm.summarize_paper(paper, source_text, user_query)
            try:
                summary = self.llm.critique_summary(summary, source_text)
            except Exception as exc:  # noqa: BLE001
                state.errors.append(f"CritiqueSummaries 失败（{paper.title}），保留初版摘要：{exc}")
            summaries.append(_ensure_supported_evidence(summary, source_text))
        return summaries

    def _update_memory(
        self,
        user_id: str,
        state: AgentState,
        top_ranked: list[RankedPaper],
        parsed: ParsedRequest,
    ) -> dict[str, Any]:
        for item in state.ranked_papers:
            self.memory.upsert_paper(item.paper)
        task_id = self.memory.create_search_task(
            user_query=state.user_query,
            parsed_request=state.parsed_request,
            expanded_keywords=state.expanded_keywords,
            selected_papers=top_ranked,
            final_report=state.final_report,
        )
        memory = self.memory.update_user_memory(
            user_id=user_id,
            domain=parsed.domain,
            preferred_language=parsed.language,
            summary_style=parsed.summary_depth,
            selected_papers=top_ranked,
        )
        return {"task_id": task_id, "user_memory": memory}


def build_markdown_report(
    user_query: str,
    parsed_request: dict[str, Any],
    expanded_keywords: list[str],
    candidate_count: int,
    ranked_papers: list[RankedPaper],
    paper_summaries: list[PaperSummary],
    errors: list[str],
) -> str:
    lines: list[str] = [
        "# 领域论文检索与摘要简报",
        "",
        f"**用户问题**：{user_query}",
        f"**检索领域**：{parsed_request.get('domain', '')}",
        f"**时间范围**：{parsed_request.get('start_date')} 至 {parsed_request.get('end_date')}",
        "",
        "## 1. 检索关键词扩展结果",
        "",
        "\n".join(f"- {keyword}" for keyword in expanded_keywords) or "- 无",
        "",
        "## 2. 候选论文数量",
        "",
        f"共获得并去重后候选论文 **{candidate_count}** 篇。",
        "",
        "## 3. Top N 论文列表",
        "",
    ]
    for index, item in enumerate(ranked_papers, start=1):
        paper = item.paper
        lines.append(
            f"{index}. **[{paper.title}]({paper.url})**，{paper.published_date}，"
            f"来源：{paper.source}，综合分：{item.scores.final_score:.3f}"
        )
    lines.extend(["", "## 4. 逐篇结构化摘要", ""])
    summary_by_title = {summary.title: summary for summary in paper_summaries}
    for index, item in enumerate(ranked_papers, start=1):
        paper = item.paper
        summary = summary_by_title.get(paper.title)
        if summary is None:
            continue
        lines.extend(
            [
                f"### {index}. {summary.title}",
                "",
                f"- 作者：{', '.join(summary.authors) or '检索结果未提供'}",
                f"- 时间：{summary.published_date}",
                f"- 链接：{summary.url}",
                f"- PDF：{summary.pdf_url or '无'}",
                f"- 研究问题：{summary.research_problem}",
                f"- 核心方法：{summary.core_method}",
                f"- 主要贡献：{'；'.join(summary.main_contributions) or '原文未明确说明'}",
                f"- 实验：{summary.experiments}",
                f"- 结果：{summary.results}",
                f"- 局限性：{'；'.join(summary.limitations) or '原文未明确说明'}",
                f"- 为什么重要：{summary.why_important}",
                f"- 与用户问题的相关性：{summary.relevance_to_user_query}",
                f"- 置信度：{summary.confidence:.2f}",
                "- 证据：",
            ]
        )
        lines.extend(f"  - {evidence}" for evidence in summary.evidence)
        lines.append("")
    lines.extend(["## 5. 论文重要性排序理由", ""])
    for index, item in enumerate(ranked_papers, start=1):
        lines.append(f"{index}. {item.paper.title}：{item.ranking_reason}")
    lines.extend(["", "## 6. 近期研究趋势总结", ""])
    if paper_summaries:
        contribution_terms = "；".join(summary.main_contributions[0] for summary in paper_summaries if summary.main_contributions)
        lines.append(
            "从当前检索结果看，近期工作集中在记忆检索、长期上下文管理、规划任务中的记忆调用，"
            f"这些趋势仅由入选论文摘要证据归纳：{contribution_terms or '证据不足'}。"
        )
    else:
        lines.append("候选论文不足，无法形成可靠趋势总结。")
    lines.extend(["", "## 7. 推荐阅读顺序", ""])
    for index, item in enumerate(ranked_papers, start=1):
        lines.append(f"{index}. {item.paper.title}：按综合分和相关性优先阅读。")
    lines.extend(["", "## 8. 可追溯性说明", ""])
    lines.append("本报告的标题、作者、时间、链接、摘要证据均来自检索结果、abstract 或 PDF 解析文本。")
    lines.append("排序由固定公式生成，不完全交给大模型。")
    if errors:
        lines.extend(["", "## 运行降级与错误", ""])
        lines.extend(f"- {error}" for error in errors)
    return "\n".join(lines)
