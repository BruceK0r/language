from __future__ import annotations

import base64
import logging
import time
from typing import Any

import requests

from paper_agent.config import redact_secret

logger = logging.getLogger(__name__)


class ZhipuVisionProvider:
    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout: float = 30,
        retries: int = 2,
    ) -> None:
        if not api_key:
            raise ValueError("ZHIPU_API_KEY is required for ZhipuVisionProvider")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.retries = retries

    def analyze_image(self, image_bytes: bytes, mime_type: str, prompt: str | None = None) -> str:
        if not image_bytes:
            raise ValueError("image_bytes is required; vision model is never called without an image")
        data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        user_prompt = prompt or "请解释这张论文截图、图表或 PDF 页面中的关键信息，并指出可用于论文摘要的证据。"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "temperature": 0.2,
        }
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
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
                    "Zhipu vision request failed on attempt %s/%s. model=%s key=%s error=%s",
                    attempt + 1,
                    self.retries + 1,
                    self.model,
                    redact_secret(self.api_key),
                    exc,
                )
                if attempt < self.retries:
                    time.sleep(0.8 * (attempt + 1))
        raise RuntimeError(f"Zhipu vision request failed after retries: {last_error}")

