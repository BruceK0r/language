from __future__ import annotations

import logging
from io import BytesIO

import requests

logger = logging.getLogger(__name__)


class PDFParser:
    def __init__(self, timeout: float = 30, max_pages: int = 4, max_bytes: int = 20_000_000) -> None:
        self.timeout = timeout
        self.max_pages = max_pages
        self.max_bytes = max_bytes

    def extract_text_from_url(self, pdf_url: str) -> str:
        response = requests.get(pdf_url, timeout=self.timeout)
        response.raise_for_status()
        content = response.content[: self.max_bytes]
        return self.extract_text_from_bytes(content)

    def extract_text_from_bytes(self, content: bytes) -> str:
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:  # pragma: no cover - dependency is installed in normal runs
            raise RuntimeError("PyMuPDF is required for PDF parsing") from exc

        text_parts: list[str] = []
        with fitz.open(stream=BytesIO(content), filetype="pdf") as doc:
            for page_index in range(min(self.max_pages, doc.page_count)):
                text_parts.append(doc.load_page(page_index).get_text("text"))
        return "\n".join(part.strip() for part in text_parts if part.strip())

