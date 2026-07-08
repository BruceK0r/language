from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _default_database_path() -> Path:
    base = Path(tempfile.gettempdir()) / "paper_radar_agent"
    return base / "paper_agent.db"


def _database_path_from_env() -> Path:
    configured = os.getenv("PAPER_AGENT_DB_PATH")
    if configured and configured.strip():
        return Path(configured)
    return _default_database_path()


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str | None = os.getenv("DEEPSEEK_API_KEY") or None
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    zhipu_api_key: str | None = os.getenv("ZHIPU_API_KEY") or None
    zhipu_base_url: str = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    zhipu_vision_model: str = os.getenv("ZHIPU_VISION_MODEL", "glm-4.6v")
    semantic_scholar_api_key: str | None = os.getenv("SEMANTIC_SCHOLAR_API_KEY") or None
    database_path: Path = _database_path_from_env()
    request_timeout_seconds: float = float(os.getenv("PAPER_AGENT_TIMEOUT", "30"))
    max_pdf_pages: int = int(os.getenv("PAPER_AGENT_MAX_PDF_PAGES", "4"))

    @property
    def use_mock_llm(self) -> bool:
        return not self.deepseek_api_key

    @property
    def use_mock_vision(self) -> bool:
        return not self.zhipu_api_key


def get_settings() -> Settings:
    return Settings()


def redact_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}***{value[-3:]}"
