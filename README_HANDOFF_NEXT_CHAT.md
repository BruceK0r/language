# 新对话交接说明：个人科研雷达阶段 1-6

本文件用于在新的 Codex 对话中快速衔接当前工作，尽量减少重新读取历史对话的成本。

## 本轮更新（2026-07-09）

- 已验收阶段 5：`tests/test_vision_agent.py`、`tests/test_coordinator_vision.py`、`tests/test_streamlit_app_static.py` 共 5 项通过。
- 已完成阶段 6：新增 Streamlit 页面 `画像分析 / Profile`，展示用户画像摘要、兴趣权重柱状图、兴趣明细表和画像统计指标。
- 阶段 6 主要改动：`app_streamlit.py`、`paper_agent/ui/streamlit_helpers.py`、`tests/test_streamlit_helpers.py`、`tests/test_streamlit_app_static.py`。
- 已运行全量回归：`py -m pytest` 结果为 `31 passed`，仅有既有 `.pytest_cache` 权限 warning。
- 已运行编译检查：`py -m py_compile app_streamlit.py paper_agent\ui\streamlit_helpers.py paper_agent\agents\vision_agent.py paper_agent\agents\coordinator_agent.py` 通过。
- 已用后台 Popen 模式启动 Streamlit：`http://localhost:8503` 返回 HTTP 200，PID 为 `25448`，日志为 `streamlit_phase6.out.log` / `streamlit_phase6.err.log`。

## 当前目标

- 用户要求“一次只跑一个阶段，每个阶段成功启动并自测后再进入下一阶段”。
- 阶段 1-4 是关键优先级，已完成实现与自测。
- 阶段 5-6 是加分完善，已完成实现与自测。
- 不要破坏原有 FastAPI `/search`、`/vision/analyze` 和旧 Streamlit 兼容功能。

## 工作目录与环境

- 工作目录：`E:\Document\Classroom\自然语言`
- Shell：PowerShell
- Python 启动命令优先使用：`py`
- Streamlit 不能用会占住当前 shell 的命令直接跑；可靠做法是用短 `py -c` 启动后台子进程并把日志写入文件。

可靠启动模式：

```powershell
py -c "import os, subprocess; out=open('streamlit_phase5.out.log','wb'); err=open('streamlit_phase5.err.log','wb'); p=subprocess.Popen(['py','-m','streamlit','run','app_streamlit.py','--server.headless','true','--server.port','8502','--server.runOnSave','false'], cwd=os.getcwd(), stdout=out, stderr=err, stdin=subprocess.DEVNULL); print(p.pid)"
```

之前确认阶段 4 的 Streamlit 服务已可访问：

- URL：`http://localhost:8501`
- 成功探测：`Invoke-WebRequest http://localhost:8501` 返回 `200`
- 当时后台 PID：`35160`

不要再用这些容易卡住或失败的方式：

- 前台执行 `py -m streamlit run app_streamlit.py ...`
- `Start-Process` 后等待交互输出
- `cmd /c start /B ...`
- `subprocess.Popen(sys.executable, ...)` 曾遇到 `_ssl` DLL 相关失败

## 阶段 1：用户画像与记忆层

主要文件：

- `paper_agent/memory/db.py`
- `paper_agent/memory/repository.py`
- `paper_agent/agents/profile_agent.py`
- `tests/test_profile_memory.py`
- `tests/test_profile_agent.py`

已实现能力：

- 用户表、兴趣表、用户行为表、推荐日志表、图片交互表。
- `create_initial_profile(user_id, interests)`：保存初始兴趣。
- `get_user_profile(user_id)`：返回画像、兴趣权重和统计。
- `update_profile_from_query(...)`：从文本查询更新兴趣。
- `update_profile_from_image(...)`：从视觉结果更新兴趣并记录图片交互。
- `log_user_action(...)`、`log_recommendations(...)`、`filter_unseen_papers(...)`。
- Onboarding 约束：用户在 UI 中选择 5 个兴趣方向。

## 阶段 2：推荐智能体

主要文件：

- `paper_agent/agents/recommender_agent.py`
- `paper_agent/agents/__init__.py`
- `tests/test_recommender_agent.py`

已实现能力：

- 基于用户画像、查询关键词、论文新近度、引用量和摘要匹配进行排序。
- 过滤已经展示或操作过的论文。
- 当未读论文不足时允许 fallback，并标记 `was_seen`。
- 返回 `recommendations` 和额外 3 篇 `follow_up_recommendations`。
- 将推荐展示写入 `recommendation_logs` 和 `user_actions(shown)`。

## 阶段 3：文本查询多智能体流程

主要文件：

- `paper_agent/agents/query_planner_agent.py`
- `paper_agent/agents/retrieval_agent.py`
- `paper_agent/agents/reader_agent.py`
- `paper_agent/agents/critic_agent.py`
- `paper_agent/agents/report_agent.py`
- `paper_agent/agents/coordinator_agent.py`
- `tests/test_text_agents.py`
- `tests/test_retrieval_agent.py`
- `tests/test_coordinator_agent.py`

已实现流程：

1. `CoordinatorAgent.run_text_query(user_id, query, top_k)`
2. `QueryPlannerAgent.plan(...)`
3. `RetrievalAgent.retrieve(...)`
4. `ProfileAgent.update_profile_from_query(...)`
5. `RecommenderAgent.recommend(...)`
6. `ReaderAgent.summarize(...)`
7. `CriticAgent.review(...)`
8. `ReportAgent.build_text_query_report(...)`

降级要求：

- 检索失败时不崩溃。
- 无候选论文时返回空推荐和带错误信息的 Markdown 报告。
- Mock 模式下可用样例论文保证 demo 可跑。

## 阶段 4：Streamlit 多页面 UI

主要文件：

- `app_streamlit.py`
- `paper_agent/ui/__init__.py`
- `paper_agent/ui/streamlit_helpers.py`
- `tests/test_streamlit_helpers.py`
- `tests/test_streamlit_app_static.py`

当前页面：

- `兴趣初始化 / Onboarding`
- `科研雷达主页`
- `文本查询`
- `兼容旧功能`

已实现 UI 行为：

- Onboarding 页面选择 5 个科研方向并生成初始推荐。
- 科研雷达主页显示画像摘要和刷新推荐。
- 文本查询页面调用 `CoordinatorAgent.run_text_query(...)`。
- 兼容旧功能页面保留原 `PaperRadarWorkflow` 和旧图片解释入口。

注意：

- PowerShell/工具输出中中文可能显示为乱码，但此前 `py_compile`、pytest 和浏览器页面文本验证均通过。
- 不要因为输出乱码大面积重写中文文案。

## 阶段 4 已做过的验证

曾完成：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; py -m pytest
py -m py_compile app_streamlit.py paper_agent\ui\streamlit_helpers.py
Invoke-WebRequest http://localhost:8501
```

当时结果：

- pytest：`25 passed`，只有 `.pytest_cache` 权限相关 warning。
- `py_compile`：通过。
- Streamlit HTTP：`200`。
- 浏览器验证看到标题和页面入口，包括 Onboarding、科研雷达主页、文本查询、兼容旧功能。

继续阶段 5 前仍应重新跑一次相关测试。

## 阶段 5 待完成：多模态查询

目标：

- 允许用户上传论文截图、架构图、实验图表、表格或 PDF 页面截图。
- 先由视觉智能体解释图片，再抽取推荐关键词。
- 用抽取出的关键词更新用户画像，并推荐相关论文。
- Streamlit 新增独立页面，不替代旧兼容页面的图片解释功能。

建议新增文件：

- `paper_agent/agents/vision_agent.py`
- `tests/test_vision_agent.py`
- `tests/test_coordinator_vision.py`

建议修改文件：

- `paper_agent/agents/__init__.py`
- `paper_agent/agents/coordinator_agent.py`
- `paper_agent/agents/report_agent.py`
- `app_streamlit.py`
- `tests/test_streamlit_app_static.py`

`VisionAgent` 期望输出：

```python
{
    "image_type": "model_architecture | experiment_chart | table | pdf_page | other",
    "main_content": "...",
    "key_findings": ["..."],
    "possible_related_topics": ["RAG", "Multi-Agent", "LLM Agent"],
    "recommendation_keywords": ["multi-agent", "retrieval", "agent memory"],
}
```

降级要求：

- 如果视觉 provider 未配置或调用失败，不崩溃。
- 返回友好说明，例如“当前未配置视觉模型，请配置 GLM / Zhipu vision provider 或对应 API key。”
- `recommendation_keywords` 可以为空；Coordinator 需要优雅返回无推荐或基于用户问题的弱推荐。

`CoordinatorAgent.run_vision_query(...)` 建议接口：

```python
def run_vision_query(
    self,
    user_id: str,
    image_file: Any,
    question: str = "",
    top_k: int = 3,
) -> dict[str, Any]:
    ...
```

建议返回：

```python
{
    "vision_result": {...},
    "answer": "...markdown...",
    "related_recommendations": [...],
    "follow_up_recommendations": [...],
    "profile_update": {...},
    "planned_query": {...},
    "errors": [...],
}
```

阶段 5 推荐流程：

1. Streamlit 上传图片并输入可选问题。
2. `VisionAgent.analyze(...)` 调用 `build_vision_provider(settings)` 或测试注入的 fake provider。
3. 视觉结果经 `ProfileAgent.update_profile_from_image(...)` 写入画像和 `image_interactions`。
4. 使用 `recommendation_keywords` / `possible_related_topics` 组成检索 query。
5. `RetrievalAgent.retrieve(...)` 检索候选论文。
6. `RecommenderAgent.recommend(...)` 个性化排序。
7. `ReportAgent` 生成 Markdown 报告。

Streamlit 阶段 5 页面建议：

- 页面名：`多模态查询`
- 控件：
  - `user_id`
  - `st.file_uploader("上传图片", type=["png", "jpg", "jpeg", "webp"])`
  - 图片预览
  - 可选问题输入
  - `top_k` 默认 3
  - 按钮：`分析图片并推荐论文`
- 若用户未完成 Onboarding，先提示去初始化兴趣。
- 展示视觉解释、关键信息、推荐关键词、相关论文、额外论文和画像更新摘要。

## 当前 git 状态提示

此仓库已有较多未提交变更和未跟踪文件。不要回滚用户或前序阶段变更。

已知会出现的状态：

- `M app_streamlit.py`
- `M paper_agent/agent/workflow.py`
- `M paper_agent/memory/db.py`
- `M paper_agent/memory/repository.py`
- `M paper_agent/tools/arxiv_tool.py`
- `?? docs/`
- `?? paper_agent/agents/`
- `?? paper_agent/tools/time_buckets.py`
- `?? paper_agent/ui/`
- `?? tests/test_*.py`
- `?? streamlit_phase4.*.log`
- `?? pytest-cache-files-*`

`paper_agent/agent/workflow.py`、`paper_agent/tools/arxiv_tool.py` 和 `paper_agent/tools/time_buckets.py` 包含更早的时间范围/去重相关工作，不属于阶段 5，不要无故改回。

## 推荐下一步

1. 先写阶段 5 的失败测试：`VisionAgent`、`CoordinatorAgent.run_vision_query(...)`、Streamlit 静态页面入口。
2. 运行这些测试并确认失败原因是功能缺失。
3. 实现最小代码让测试通过。
4. 跑全量 `py -m pytest`。
5. 用后台 Popen 模式启动 Streamlit 到新端口，例如 `8502`，用 `Invoke-WebRequest` 验证 HTTP 200。
6. 若要浏览器人工验证，打开 `http://localhost:8502`，确认侧边栏出现 `多模态查询`。
