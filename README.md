# Paper Radar Agent

一个可运行的“领域论文检索与摘要 Agent”MVP。用户输入研究领域、关键词、时间范围和输出偏好后，系统会检索论文、去重、按固定公式排序、读取摘要或 PDF 片段，并输出中文结构化论文简报。

## 功能

- FastAPI：`GET /health`、`POST /search`、`POST /vision/analyze`、`GET /tasks/{task_id}`
- Streamlit Demo：自然语言检索、Top K、时间范围、论文表格、Markdown 简报、图片上传解释
- 检索源：arXiv API 必选实现，Semantic Scholar API 尽力调用并自动降级
- Agent 工作流：请求解析、关键词扩展、检索、去重、排序、读取 Top 论文、摘要、审查、报告、记忆更新
- 模型封装：`DeepSeekLLMProvider`、`ZhipuVisionProvider`、`MockLLMProvider`
- 无 API Key 时自动使用 Mock provider，测试和 Demo 不会阻塞
- SQLite 记忆：`papers`、`search_tasks`、`user_memory`
- 轻量本地向量相似度模块：用于 MVP 级记忆/文本匹配扩展

## 安装与运行

```bash
pip install -r requirements.txt
cp .env.example .env
pytest
uvicorn main:app --reload
streamlit run app_streamlit.py
```

Windows PowerShell 可用：

```powershell
Copy-Item .env.example .env
py -m pytest
py -m uvicorn main:app --reload
streamlit run app_streamlit.py
```

## 环境变量

`.env.example` 已列出所有配置。真实模型调用至少需要：

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`，默认 `https://api.deepseek.com`
- `DEEPSEEK_MODEL`，默认 `deepseek-v4-flash`
- `ZHIPU_API_KEY`
- `ZHIPU_BASE_URL`，默认 `https://open.bigmodel.cn/api/paas/v4`
- `ZHIPU_VISION_MODEL`，默认 `glm-4.6v`
- `PAPER_AGENT_DB_PATH`，留空时默认使用系统临时目录下的 `paper_radar_agent/paper_agent.db`

不要把 API Key 写入代码、日志或前端页面。

配置真实 API 后可运行：

```bash
python scripts/check_real_config.py
```

如果输出中显示 `DeepSeek provider: deepseek`，`Vision provider: zhipu`，说明后端会使用真实模型。密钥只会以脱敏形式显示。

## 示例请求

```bash
curl -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d "{\"user_query\":\"检索最近三个月关于 LLM Agent Memory 的重要论文，并总结 Top 5。\",\"top_k\":5,\"time_range\":\"last_90_days\",\"user_id\":\"demo-user\"}"
```

响应包含：

- `final_report`
- `expanded_keywords`
- `candidate_count`
- `ranked_papers`
- `paper_summaries`
- `errors`

## 排序公式

```text
score =
0.35 * semantic_relevance
+ 0.20 * recency_score
+ 0.15 * citation_score
+ 0.15 * source_quality_score
+ 0.10 * has_pdf_score
+ 0.05 * user_memory_match_score
```

每个分项都限制在 0 到 1，并随结果保存排序理由。引用数缺失时按 0 处理。

## 当前限制

- arXiv API 不提供稳定引用数，引用分主要来自 Semantic Scholar。
- PDF 解析默认只读前 `PAPER_AGENT_MAX_PDF_PAGES` 页，避免下载和上下文过大。
- 没有 API Key 或外部检索失败时会使用 Mock 数据，便于演示，不代表真实论文库。
- 本地向量检索是轻量依赖版实现；生产环境可替换为 Chroma、FAISS 或 Qdrant。

## 下一步扩展

- 接入 OpenAlex 和 Crossref 补充 DOI、引用、机构和 venue 信息。
- 使用 Chroma/FAISS 建立论文全文向量库。
- 为摘要审查增加更严格的 evidence-span 对齐。
- 加入异步任务队列，支持长 PDF 批量解析和缓存。
- 为 Streamlit 增加历史任务浏览和论文收藏。
