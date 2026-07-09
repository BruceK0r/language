from __future__ import annotations

import re
from typing import Any

from paper_agent.config import Settings, get_settings
from paper_agent.providers import build_vision_provider


UNCONFIGURED_VISION_MESSAGE = "当前未配置视觉模型，请配置 GLM / Zhipu vision provider 或对应 API key。"


KEYWORD_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("rag", ("retrieval-augmented generation", "retrieval augmented generation", "rag")),
    ("multi-agent", ("multi-agent", "multi agent", "multi-agent systems")),
    ("agent memory", ("agent memory", "memory module", "episodic memory", "long-term memory")),
    ("llm agent", ("llm agent", "language agent", "agent planner")),
    ("information retrieval", ("information retrieval", "retrieval module", "retriever")),
    ("recommendation systems", ("recommendation system", "recommendation systems", "recommender")),
    ("knowledge graphs", ("knowledge graph", "knowledge graphs")),
    ("computer vision", ("computer vision", "vision model", "image encoder")),
    ("multimodal learning", ("multimodal", "multi-modal")),
    ("transformer", ("transformer", "attention")),
    ("evaluation", ("evaluation", "benchmark", "experiment")),
]


def _clean_keywords(keywords: list[str], limit: int = 10) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        value = " ".join(str(keyword or "").strip().split())
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        cleaned.append(value)
        seen.add(key)
    return cleaned[:limit]


def _extract_keywords(text: str) -> list[str]:
    lowered = (text or "").lower()
    keywords: list[str] = []
    for canonical, variants in KEYWORD_PATTERNS:
        if any(variant in lowered for variant in variants):
            keywords.append(canonical)
    return _clean_keywords(keywords)


def _classify_image_type(text: str) -> str:
    lowered = (text or "").lower()
    if any(token in lowered for token in ("architecture", "diagram", "pipeline", "framework", "module")):
        return "model_architecture"
    if any(token in lowered for token in ("chart", "plot", "curve", "graph", "experiment", "benchmark")):
        return "experiment_chart"
    if "table" in lowered or "matrix" in lowered:
        return "table"
    if any(token in lowered for token in ("pdf", "page", "paper screenshot", "document")):
        return "pdf_page"
    return "other"


def _split_findings(text: str, limit: int = 3) -> list[str]:
    chunks = re.split(r"(?<=[.!?。！？])\s+", (text or "").strip())
    findings = [chunk.strip()[:280] for chunk in chunks if chunk.strip()]
    return findings[:limit]


def _looks_unconfigured(provider: Any, explanation: str) -> bool:
    model = str(getattr(provider, "model", "")).lower()
    normalized = " ".join((explanation or "").split()).lower()
    return (
        model.startswith("mock-")
        or normalized == UNCONFIGURED_VISION_MESSAGE.lower()
        or normalized.startswith("zhipu_api_key is required")
        or normalized.startswith("vision provider is not configured")
    )


class VisionAgent:
    def __init__(self, provider: Any | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.provider = provider
        self.provider_error: Exception | None = None
        if self.provider is None:
            try:
                self.provider = build_vision_provider(self.settings)
            except Exception as exc:  # noqa: BLE001
                self.provider_error = exc

    def analyze(self, image_bytes: bytes, mime_type: str = "image/png", question: str = "") -> dict[str, Any]:
        if not image_bytes:
            return self._fallback("image_bytes is required")
        if self.provider is None:
            return self._fallback(str(self.provider_error or "vision provider is unavailable"))

        prompt = self._build_prompt(question)
        try:
            raw_explanation = self.provider.analyze_image(image_bytes, mime_type=mime_type, prompt=prompt)
        except Exception as exc:  # noqa: BLE001
            return self._fallback(str(exc))

        if _looks_unconfigured(self.provider, raw_explanation):
            return self._fallback("vision provider is not configured", raw_explanation=raw_explanation)

        combined_text = f"{raw_explanation}\n{question}"
        keywords = _extract_keywords(combined_text)
        findings = _split_findings(raw_explanation)
        return {
            "image_type": _classify_image_type(combined_text),
            "main_content": raw_explanation.strip(),
            "key_findings": findings,
            "possible_related_topics": [keyword.upper() if keyword == "rag" else keyword.title() for keyword in keywords],
            "recommendation_keywords": keywords,
            "provider_available": True,
            "raw_explanation": raw_explanation,
            "provider_model": str(getattr(self.provider, "model", "")),
            "error": "",
        }

    def _build_prompt(self, question: str = "") -> str:
        base = (
            "请解释这张科研论文相关图片，判断它是模型架构、实验图表、表格、PDF 页面截图还是其他内容。"
            "请提炼主要内容、关键发现、可能相关研究主题，以及可用于论文推荐的英文关键词。"
        )
        if question:
            return f"{base}\n用户问题：{question}"
        return base

    def _fallback(self, error: str, raw_explanation: str = "") -> dict[str, Any]:
        return {
            "image_type": "other",
            "main_content": UNCONFIGURED_VISION_MESSAGE,
            "key_findings": [],
            "possible_related_topics": [],
            "recommendation_keywords": [],
            "provider_available": False,
            "raw_explanation": raw_explanation,
            "provider_model": str(getattr(self.provider, "model", "")) if self.provider is not None else "",
            "error": error,
        }
