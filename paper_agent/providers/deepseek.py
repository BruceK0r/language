from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import requests

from paper_agent.config import redact_secret
from paper_agent.providers.mock import MockLLMProvider
from paper_agent.schemas import Paper, PaperSummary

logger = logging.getLogger(__name__)


def extract_json_object(text: str) -> dict[str, Any] | list[Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
    if not match:
        raise
    return json.loads(match.group(1))


class DeepSeekLLMProvider:
    name = "deepseek"

    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout: float = 30,
        retries: int = 2,
    ) -> None:
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for DeepSeekLLMProvider")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.retries = retries
        self._fallback = MockLLMProvider()

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        response_format: dict[str, str] | None = None,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "DeepSeek request failed on attempt %s/%s. model=%s base_url=%s key=%s error=%s",
                    attempt + 1,
                    self.retries + 1,
                    self.model,
                    self.base_url,
                    redact_secret(self.api_key),
                    exc,
                )
                if attempt < self.retries:
                    time.sleep(0.8 * (attempt + 1))
        raise RuntimeError(f"DeepSeek request failed after retries: {last_error}")

    def generate_json(self, messages: list[dict[str, str]], fallback: Any) -> Any:
        try:
            raw = self.chat(messages, response_format={"type": "json_object"})
            return extract_json_object(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("DeepSeek JSON generation failed, attempting repair: %s", exc)
        try:
            raw = self.chat(
                messages
                + [
                    {
                        "role": "user",
                        "content": "上一次输出不是合法 JSON。请只输出一个合法 JSON 对象或数组，不要包含解释。",
                    }
                ],
                response_format={"type": "json_object"},
            )
            return extract_json_object(raw)
        except Exception as exc:  # noqa: BLE001
            logger.error("DeepSeek JSON repair failed; using fallback. error=%s", exc)
            return fallback

    def parse_request(self, user_query: str, top_k: int = 5, time_range: str | None = None) -> dict[str, Any]:
        fallback = self._fallback.parse_request(user_query, top_k=top_k, time_range=time_range)
        messages = [
            {"role": "system", "content": "你是论文检索 Agent 的请求解析器，只输出 JSON。"},
            {
                "role": "user",
                "content": (
                    "解析用户论文检索请求，字段：domain, query_terms(list), time_window_days(int), "
                    "top_k(int), language, summary_depth。不要编造日期。"
                    f"\n用户请求：{user_query}\n显式 top_k：{top_k}\n显式 time_range：{time_range}"
                ),
            },
        ]
        data = self.generate_json(messages, fallback=fallback)
        if isinstance(data, dict):
            fallback.update({k: v for k, v in data.items() if v is not None})
        return fallback

    def expand_keywords(self, user_query: str, parsed_request: dict[str, Any]) -> list[str]:
        fallback = self._fallback.expand_keywords(user_query, parsed_request)
        messages = [
            {"role": "system", "content": "你是学术搜索关键词扩展器，只输出 JSON。"},
            {
                "role": "user",
                "content": (
                    "请把中文或自然语言检索请求扩展为 6-10 个英文论文检索关键词/短语。"
                    "输出格式：{\"keywords\": [\"...\"]}。"
                    f"\n请求：{user_query}\n解析结果：{json.dumps(parsed_request, ensure_ascii=False)}"
                ),
            },
        ]
        data = self.generate_json(messages, fallback={"keywords": fallback})
        if isinstance(data, dict) and isinstance(data.get("keywords"), list):
            return [str(item) for item in data["keywords"] if str(item).strip()]
        return fallback

    def summarize_paper(self, paper: Paper, source_text: str, user_query: str) -> PaperSummary:
        fallback = self._fallback.summarize_paper(paper, source_text, user_query).model_dump()
        clipped_text = source_text[:12000]
        messages = [
            {
                "role": "system",
                "content": (
                    "你是严谨的论文摘要助手。只允许基于给定 abstract/PDF 文本总结；"
                    "evidence 必须是原文短句，不得写模型常识。只输出 JSON。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请按字段生成结构化中文摘要：title, authors, published_date, url, pdf_url, "
                    "research_problem, core_method, main_contributions(list), experiments, results, "
                    "limitations(list), why_important, relevance_to_user_query, confidence(0-1), evidence(list)。"
                    f"\n用户问题：{user_query}\n论文元数据：{paper.model_dump_json(ensure_ascii=False)}"
                    f"\n可用原文：\n{clipped_text}"
                ),
            },
        ]
        data = self.generate_json(messages, fallback=fallback)
        if not isinstance(data, dict):
            data = fallback
        merged = {**fallback, **data}
        return PaperSummary.model_validate(merged)

    def critique_summary(self, summary: PaperSummary, source_text: str) -> PaperSummary:
        fallback = summary.model_dump()
        messages = [
            {
                "role": "system",
                "content": "你是事实审查器。删除没有证据支撑的过度推断，只输出同结构 JSON。",
            },
            {
                "role": "user",
                "content": (
                    "检查摘要是否仅由 evidence 和原文支持。无法支撑的内容改为“原文未明确说明”。"
                    f"\n摘要：{summary.model_dump_json(ensure_ascii=False)}\n原文：{source_text[:10000]}"
                ),
            },
        ]
        data = self.generate_json(messages, fallback=fallback)
        if not isinstance(data, dict):
            data = fallback
        return PaperSummary.model_validate({**fallback, **data})

    def generate_report(
        self,
        user_query: str,
        parsed_request: dict[str, Any],
        expanded_keywords: list[str],
        candidate_count: int,
        ranked_papers: list[Any],
        paper_summaries: list[PaperSummary],
        errors: list[str],
    ) -> str:
        from paper_agent.agent.workflow import build_markdown_report

        fallback = build_markdown_report(
            user_query,
            parsed_request,
            expanded_keywords,
            candidate_count,
            ranked_papers,
            paper_summaries,
            errors,
        )
        payload = {
            "user_query": user_query,
            "parsed_request": parsed_request,
            "expanded_keywords": expanded_keywords,
            "candidate_count": candidate_count,
            "ranked_papers": [item.model_dump() for item in ranked_papers],
            "paper_summaries": [item.model_dump() for item in paper_summaries],
            "errors": errors,
        }
        try:
            text = self.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是中文论文简报撰写助手。必须只使用输入 JSON 的事实，"
                            "保留来源链接、排序分数和 evidence，不得新增论文或结论。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "基于以下 JSON 生成中文 Markdown 简报，必须包含：关键词扩展、候选数量、"
                            "Top 论文、每篇结构化摘要、重要性排序理由、趋势总结、推荐阅读顺序、"
                            "可追溯证据说明。\n"
                            f"{json.dumps(payload, ensure_ascii=False)[:22000]}"
                        ),
                    },
                ]
            )
            return text.strip() or fallback
        except Exception as exc:  # noqa: BLE001
            logger.error("DeepSeek report generation failed; using deterministic report. error=%s", exc)
            return fallback

