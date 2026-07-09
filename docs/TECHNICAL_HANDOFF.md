# 个人科研雷达技术交接文档

本文档用于在新一轮 Codex 对话或人工维护时快速理解项目逻辑。它描述当前系统的入口、数据层、智能体流程、推荐排序、UI 行为、降级策略和常见修改位置。

## 系统整体逻辑

本项目是一个“多模态多智能体个人科研雷达 Agent”。用户先初始化 5 个科研兴趣方向，系统保存用户画像；随后用户可以通过文本问题或图片上传触发论文检索、个性化排序、论文推荐、画像更新和推荐原因生成。

系统分两条主要路线：

1. 新版科研雷达路线：Streamlit 多页面 UI，核心是 `CoordinatorAgent` 编排多个 agent。
2. 兼容旧功能路线：保留原 `PaperRadarWorkflow`、FastAPI `/search`、FastAPI `/vision/analyze` 和旧 Streamlit 功能入口。

新版路线推荐优先维护；旧路线用于课程作业兼容和回归。

## 运行入口

### Streamlit

主入口：

```powershell
py -m streamlit run app_streamlit.py --server.headless true --server.port 8507 --server.runOnSave false
```

主要文件：

- `app_streamlit.py`
- `paper_agent/ui/streamlit_helpers.py`

页面：

- `兴趣初始化 / Onboarding`
- `科研雷达主页`
- `画像分析 / Profile`
- `文本查询`
- `多模态查询`
- `兼容旧功能`

### FastAPI

主入口：

```powershell
py -m uvicorn main:app --reload
```

接口：

- `GET /health`
- `POST /search`
- `POST /vision/analyze`
- `GET /tasks/{task_id}`

FastAPI 主要走旧工作流，不是新版科研雷达 UI 的主链路。

## 环境与配置

配置文件：

- `.env`
- `.env.example`
- `paper_agent/config.py`

关键变量：

- `DEEPSEEK_API_KEY`：文本 LLM，存在时使用 DeepSeek。
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`
- `ZHIPU_API_KEY`：视觉模型，存在时使用 Zhipu vision。
- `ZHIPU_BASE_URL`
- `ZHIPU_VISION_MODEL`
- `SEMANTIC_SCHOLAR_API_KEY`
- `PAPER_AGENT_DB_PATH`
- `PAPER_AGENT_TIMEOUT`
- `PAPER_AGENT_MAX_PDF_PAGES`

常见问题：如果 `HTTP_PROXY`、`HTTPS_PROXY` 或 `ALL_PROXY` 被设置为无效地址，例如 `http://127.0.0.1:9`，真实论文源会连接失败。启动前可清理：

```powershell
Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:ALL_PROXY -ErrorAction SilentlyContinue
```

## 数据库与记忆层

主要文件：

- `paper_agent/memory/db.py`
- `paper_agent/memory/repository.py`

SQLite 表：

- `papers`：全局论文缓存。
- `search_tasks`：旧工作流搜索任务记录。
- `user_memory`：旧版用户记忆。
- `users`：用户基础状态，包括 `onboarding_done`。
- `user_interests`：新版用户兴趣画像和权重。
- `user_actions`：用户行为，包括 `shown`、`read`、`favorited`、`disliked`。
- `recommendation_logs`：推荐展示日志。
- `image_interactions`：图片查询交互日志。

重要仓库方法：

- `create_initial_profile(user_id, interests)`：保存 5 个初始兴趣。
- `get_user_profile(user_id)`：读取画像、兴趣权重和统计。
- `update_profile_from_query(user_id, query, extracted_keywords)`：文本查询后更新画像。
- `update_profile_from_image(user_id, vision_result)`：图片查询后更新画像。
- `log_recommendations(user_id, task_id, papers)`：记录展示过的推荐。
- `log_user_action(user_id, paper_id, action_type)`：记录收藏、已读、不感兴趣等动作。
- `get_seen_paper_ids(user_id)`：返回用户已展示或操作过的论文 id。
- `reset_user_profile_memory(user_id)`：清空当前用户个性化记忆。

`reset_user_profile_memory` 清空内容：

- `user_interests`
- `user_actions`
- `recommendation_logs`
- `image_interactions`
- `user_memory`
- 将 `users.onboarding_done` 置为 `0`

它保留：

- `papers`
- `search_tasks`
- `.env` 和 API 配置

## 新版文本查询流程

入口：

- `app_streamlit.py`
- `CoordinatorAgent.run_text_query(...)`

主要链路：

1. `QueryPlannerAgent.plan(query, top_k)` 解析问题，抽取关键词。
2. `RetrievalAgent.retrieve(planned_query)` 检索候选论文。
3. `ProfileAgent.update_profile_from_query(...)` 更新用户画像。
4. `RecommenderAgent.recommend(...)` 按画像和查询进行综合排序。
5. `ReaderAgent.enrich_recommendation_reasons(...)` 调用 DeepSeek 生成简短推荐原因。
6. `ReaderAgent.summarize(...)` 生成结构化摘要字段。
7. `CriticAgent.review(...)` 做轻量审查。
8. `ReportAgent.build_text_query_report(...)` 生成完整 Markdown 报告。
9. Streamlit 用结构化卡片展示结果，完整报告放入折叠区。

## 新版多模态查询流程

入口：

- `app_streamlit.py`
- `CoordinatorAgent.run_vision_query(...)`

主要链路：

1. 用户上传图片，可选输入问题。
2. `VisionAgent.analyze(...)` 调用视觉 provider 或 mock vision。
3. 从视觉结果抽取：
   - `image_type`
   - `main_content`
   - `key_findings`
   - `possible_related_topics`
   - `recommendation_keywords`
4. `ProfileAgent.update_profile_from_image(...)` 写入画像和 `image_interactions`。
5. 用图片关键词构造检索 query。
6. `RetrievalAgent.retrieve(...)` 检索论文。
7. `RecommenderAgent.recommend(...)` 排序。
8. `ReaderAgent.enrich_recommendation_reasons(...)` 为图片相关论文和额外 3 篇生成推荐原因。
9. `ReportAgent.build_vision_query_report(...)` 生成完整报告。

视觉 provider 未配置或调用失败时，系统不崩溃，会返回友好说明。

## 时间桶检索

新版 `RetrievalAgent` 已迁移旧流程的时间桶检索逻辑。

文件：

- `paper_agent/agents/retrieval_agent.py`
- `paper_agent/tools/time_buckets.py`

时间桶：

```text
0-7d    limit 5
8-30d   limit 10
31-60d  limit 10
61-90d  limit 15
```

检索逻辑：

1. 以当天为 anchor date。
2. 根据 `last_90_days` 或更长窗口构造最多 4 个桶。
3. arXiv 按每个桶独立检索。
4. Semantic Scholar 在整体窗口内补充检索。
5. 合并、去重。
6. 调用 `select_papers_by_time_buckets(...)` 从各桶挑选候选，最多 40 篇。
7. 将这 40 篇传给 `RecommenderAgent` 统一综合排序。

桶内热度：

```text
0.75 * citation_heat
+ 0.15 * relevance
+ 0.10 * has_pdf
```

桶抽取只负责候选池均衡，不直接决定最终 Top-K。

## 推荐排序公式

文件：

- `paper_agent/agents/recommender_agent.py`

最终排序公式：

```text
final_score =
0.30 * profile_match_score
+ 0.20 * query_relevance_score
+ 0.20 * recency_score
+ 0.15 * citation_score
+ 0.05 * novelty_score
+ 0.05 * quality_score
+ 0.05 * diversity_score
```

分项说明：

- `profile_match_score`：标题和摘要与用户兴趣画像的匹配程度。
- `query_relevance_score`：标题和摘要与当前查询关键词的匹配程度。
- `recency_score`：越新的论文分越高。
- `citation_score`：引用数经 log 缩放后的热度。
- `novelty_score`：未展示过为 1，已展示过为 0。
- `quality_score`：有摘要、链接、PDF、作者信息会更高。
- `diversity_score`：当前固定为 0.5，保留给后续多样性策略。

## Top5 与额外 3 篇逻辑

文件：

- `paper_agent/agents/recommender_agent.py`

逻辑：

1. 候选池最多 40 篇。
2. 对所有候选按 `final_score` 降序排序。
3. 过滤出未展示过的论文。
4. 取前 `top_k` 篇作为主推荐，默认 5 篇。
5. 如果未读论文不足，会用已展示论文补齐，并标记 `used_seen_fallback = True`。
6. 从未读候选中排除主推荐，继续取前 3 篇作为 `follow_up_recommendations`。
7. 主推荐和额外 3 篇都会写入推荐日志和 `user_actions(shown)`。

额外 3 篇不是随机推荐，也不是重新搜索，而是同一批候选里主推荐之后的备选论文。

## DeepSeek 推荐原因

文件：

- `paper_agent/agents/reader_agent.py`
- `paper_agent/agents/coordinator_agent.py`

`ReaderAgent.enrich_recommendation_reasons(...)` 会对主推荐和额外推荐逐篇调用 LLM：

- 主推荐：`purpose="top"`
- 额外 3 篇：`purpose="follow_up"`

Prompt 要求：

- 只基于论文标题、摘要、匹配兴趣、匹配关键词和分数。
- 中文输出。
- 不超过约 80 字。
- 不编造论文不存在的信息。

如果 DeepSeek 不可用或调用失败，会保留 `RecommenderAgent` 生成的规则推荐原因。

## 演示兜底与真实论文

Streamlit 侧边栏有 `允许使用演示论文兜底`。

默认不勾选：

- 外部论文源失败时，页面提示真实论文源不可用。
- 不会返回 mock 假论文。

勾选后：

- 真实论文源失败且没有候选时，使用 mock 演示论文。
- 页面会明确提示“演示数据，无真实链接”。

这个开关适合录屏演示，不适合真实论文检索。

## UI 展示逻辑

文件：

- `app_streamlit.py`
- `paper_agent/ui/streamlit_helpers.py`

新版结果展示函数：

- `render_query_result(...)`
- `_render_paper_list(...)`

页面展示结构：

- 顶部指标：推荐论文数量、额外候选数量、检索模式。
- 关键词短标签。
- 主推荐论文卡片。
- 额外 3 篇论文卡片。
- 画像更新摘要折叠区。
- 运行错误折叠区。
- 完整 Markdown 报告折叠区。

论文卡片会识别 mock 数据：

- `is_demo_paper(...)`
- `paper_source_label(...)`

如果是演示论文或 `example.com` 链接，不显示“打开论文页面”按钮。

## 用户偏好清空按钮

位置：

- `画像分析 / Profile`

控件：

- `我确认要清空当前 user_id 的画像和推荐记忆`
- `清空当前用户偏好记忆`

清空后：

- 当前 user_id 的画像、行为、推荐日志、图片交互和旧版 user_memory 被删除。
- onboarding 状态重置。
- 页面提示回到 `兴趣初始化 / Onboarding` 重新选择 5 个方向。

## 测试结构

重要测试：

- `tests/test_profile_memory.py`：用户画像、记忆清空。
- `tests/test_retrieval_agent.py`：时间桶检索、真实源失败、演示兜底。
- `tests/test_recommender_agent.py`：排序公式、额外推荐、已展示过滤。
- `tests/test_text_agents.py`：QueryPlanner、Reader LLM 推荐原因、Report。
- `tests/test_coordinator_agent.py`：文本查询编排。
- `tests/test_coordinator_vision.py`：多模态查询编排。
- `tests/test_streamlit_app_static.py`：Streamlit 页面静态入口和关键控件。
- `tests/test_streamlit_helpers.py`：UI helper。

推荐验证命令：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; py -m pytest
py -m py_compile app_streamlit.py paper_agent\agents\retrieval_agent.py paper_agent\agents\recommender_agent.py paper_agent\agents\reader_agent.py paper_agent\agents\coordinator_agent.py paper_agent\memory\repository.py
```

`.pytest_cache` 权限 warning 目前可忽略，不影响测试结果。

## 新一轮对话修改入口

常见需求和对应文件：

- 改 Streamlit 页面或按钮：`app_streamlit.py`
- 改 UI 数据格式化：`paper_agent/ui/streamlit_helpers.py`
- 改用户画像和记忆：`paper_agent/memory/repository.py`
- 改数据库表：`paper_agent/memory/db.py`
- 改文本查询编排：`paper_agent/agents/coordinator_agent.py`
- 改查询规划：`paper_agent/agents/query_planner_agent.py`
- 改真实论文检索：`paper_agent/agents/retrieval_agent.py`
- 改 arXiv 请求：`paper_agent/tools/arxiv_tool.py`
- 改 Semantic Scholar 请求：`paper_agent/tools/semantic_scholar_tool.py`
- 改时间桶：`paper_agent/tools/time_buckets.py`
- 改推荐排序公式：`paper_agent/agents/recommender_agent.py`
- 改推荐原因或摘要：`paper_agent/agents/reader_agent.py`
- 改报告 Markdown：`paper_agent/agents/report_agent.py`
- 改图片理解：`paper_agent/agents/vision_agent.py`
- 改 DeepSeek 调用：`paper_agent/providers/deepseek.py`
- 改 Zhipu vision 调用：`paper_agent/providers/zhipu_vision.py`
- 改 mock 演示数据：`paper_agent/providers/mock.py`
- 改 FastAPI：`main.py`
- 改旧工作流：`paper_agent/agent/workflow.py`

## 当前维护建议

1. 保持新版科研雷达和旧兼容流程分离，避免为旧接口重构新版 UI。
2. 推荐排序改动必须同步更新 `tests/test_recommender_agent.py`。
3. 时间桶改动必须同步更新 `tests/test_retrieval_agent.py`。
4. 用户记忆写入或清空必须同步更新 `tests/test_profile_memory.py`。
5. UI 新控件至少补 `tests/test_streamlit_app_static.py`。
6. 不要把 API key 写入代码、测试或文档。
7. 外部网络失败时优先报告真实错误，不默认伪造论文。
