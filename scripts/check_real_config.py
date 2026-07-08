from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from paper_agent.config import get_settings, redact_secret


def main() -> None:
    settings = get_settings()
    print("Paper Radar Agent configuration")
    print(f"DeepSeek provider: {'deepseek' if settings.deepseek_api_key else 'mock'}")
    print(f"DeepSeek base URL: {settings.deepseek_base_url}")
    print(f"DeepSeek model: {settings.deepseek_model}")
    print(f"DeepSeek key: {redact_secret(settings.deepseek_api_key) or 'missing'}")
    print(f"Vision provider: {'zhipu' if settings.zhipu_api_key else 'mock'}")
    print(f"Zhipu base URL: {settings.zhipu_base_url}")
    print(f"Zhipu model: {settings.zhipu_vision_model}")
    print(f"Zhipu key: {redact_secret(settings.zhipu_api_key) or 'missing'}")


if __name__ == "__main__":
    main()
