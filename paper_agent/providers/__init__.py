from __future__ import annotations

from paper_agent.config import Settings
from paper_agent.providers.deepseek import DeepSeekLLMProvider
from paper_agent.providers.mock import MockLLMProvider, MockVisionProvider
from paper_agent.providers.zhipu_vision import ZhipuVisionProvider


def build_llm_provider(settings: Settings):
    if settings.use_mock_llm:
        return MockLLMProvider()
    return DeepSeekLLMProvider(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        timeout=settings.request_timeout_seconds,
    )


def build_vision_provider(settings: Settings):
    if settings.use_mock_vision:
        return MockVisionProvider(model=settings.zhipu_vision_model)
    return ZhipuVisionProvider(
        api_key=settings.zhipu_api_key,
        base_url=settings.zhipu_base_url,
        model=settings.zhipu_vision_model,
        timeout=settings.request_timeout_seconds,
    )

