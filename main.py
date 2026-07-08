from __future__ import annotations

import logging

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from paper_agent.agent.workflow import PaperRadarWorkflow
from paper_agent.config import get_settings
from paper_agent.memory.repository import MemoryRepository
from paper_agent.providers import build_vision_provider
from paper_agent.schemas import SearchRequest, SearchResponse, VisionResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

settings = get_settings()
memory = MemoryRepository(settings.database_path)
workflow = PaperRadarWorkflow(memory=memory)
app = FastAPI(title="Paper Radar Agent", version="0.1.0")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <title>Paper Radar Agent</title>
        <style>
          body { font-family: system-ui, sans-serif; margin: 48px; line-height: 1.6; }
          a { color: #0f766e; }
          code { background: #f3f4f6; padding: 2px 5px; border-radius: 4px; }
        </style>
      </head>
      <body>
        <h1>Paper Radar Agent</h1>
        <p>FastAPI 服务已启动。常用入口：</p>
        <ul>
          <li><a href="/docs">API 文档 /docs</a></li>
          <li><a href="/health">健康检查 /health</a></li>
          <li>Streamlit Demo：<a href="http://127.0.0.1:8501">http://127.0.0.1:8501</a></li>
        </ul>
        <p>论文检索接口请使用 <code>POST /search</code>，或在 Streamlit 页面里直接操作。</p>
      </body>
    </html>
    """


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "llm_provider": "mock" if settings.use_mock_llm else "deepseek",
        "vision_provider": "mock" if settings.use_mock_vision else "zhipu",
    }


@app.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    state = workflow.run(
        user_query=request.user_query or request.query or "",
        top_k=request.top_k,
        time_range=request.time_range,
        user_id=request.user_id,
    )
    return SearchResponse(
        task_id=state.memory_updates.get("task_id", ""),
        final_report=state.final_report,
        expanded_keywords=state.expanded_keywords,
        candidate_count=len(state.candidate_papers),
        ranked_papers=state.ranked_papers[: request.top_k],
        paper_summaries=state.paper_summaries,
        errors=state.errors,
    )


@app.post("/vision/analyze", response_model=VisionResponse)
async def analyze_vision(
    file: UploadFile = File(...),
    note: str | None = Form(default=None),
    paper_id: str | None = Form(default=None),
) -> VisionResponse:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported")
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")
    provider = build_vision_provider(settings)
    try:
        explanation = provider.analyze_image(image_bytes, mime_type=file.content_type, prompt=note)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Vision provider failed: {exc}") from exc
    return VisionResponse(
        explanation=explanation,
        model=getattr(provider, "model", "unknown"),
        used_mock=settings.use_mock_vision,
        paper_id=paper_id,
    )


@app.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    task = memory.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
