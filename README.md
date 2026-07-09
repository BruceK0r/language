# Paper Radar Agent

多模态多智能体个人科研雷达 Agent。系统面向“科研人员难以及时跟踪近期论文”的实际场景，支持从自然语言问题或论文相关图片出发，自动完成任务规划、论文检索、个性化排序、摘要生成、结果审查、中文简报输出和用户画像更新。

本仓库是《自然语言处理》课程大作业项目，同时也是一个可运行的论文推荐与科研简报 Demo。

## 核心能力

- 文本论文检索：输入自然语言科研问题，系统自动解析意图、扩展关键词并检索近期论文。
- 多源论文检索：支持 arXiv API 与 Semantic Scholar API，外部源失败时可降级到演示数据。
- 多智能体协作：由 CoordinatorAgent 调度 Planner、Retrieval、Profile、Recommender、Reader、Critic、Report、Vision 等专职智能体。
- 个性化记忆：通过 SQLite 保存用户兴趣、展示历史、推荐日志和图片交互记录，并影响后续排序。
- 可解释推荐：推荐结果包含分项得分、匹配兴趣、匹配关键词和中文推荐理由。
- 中文结构化简报：自动生成包含查询理解、Top-K 推荐、摘要、额外论文、画像更新和错误降级信息的报告。
- 多模态查询：支持上传论文截图、模型架构图、实验图表或表格截图，由 VisionAgent 提取研究主题和推荐关键词。
- 双入口运行：提供 Streamlit 交互页面和 FastAPI 服务接口。
- Mock fallback：未配置 API Key 或外部服务不可用时，测试和演示流程仍可运行。

## 快速开始

建议使用 Python 3.11 或更高版本。

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

检查模型配置：

```powershell
py scripts\check_real_config.py
```

运行自动化测试：

```powershell
py -m pytest tests
```

注意：如果工作区存在文档渲染临时目录，直接运行 `py -m pytest` 可能会误收集 `tmp/` 下的临时文件；推荐固定使用 `py -m pytest tests`。

启动 Streamlit 页面：

```powershell
py -m streamlit run app_streamlit.py --server.headless true --server.port 8501 --server.runOnSave false
```

启动 FastAPI 服务：

```powershell
py -m uvicorn main:app --reload
```

## 环境变量

`.env.example` 提供了完整配置模板。

```env
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash

ZHIPU_API_KEY=
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4
ZHIPU_VISION_MODEL=glm-4.6v

SEMANTIC_SCHOLAR_API_KEY=
PAPER_AGENT_DB_PATH=
PAPER_AGENT_TIMEOUT=30
PAPER_AGENT_MAX_PDF_PAGES=4
```

配置说明：

- `DEEPSEEK_API_KEY`：文本 LLM。未配置时使用 `MockLLMProvider`。
- `ZHIPU_API_KEY`：视觉模型。未配置时使用 Mock Vision 降级逻辑。
- `SEMANTIC_SCHOLAR_API_KEY`：Semantic Scholar 可选密钥。
- `PAPER_AGENT_DB_PATH`：SQLite 数据库路径。留空时使用系统临时目录下的 `paper_radar_agent/paper_agent.db`。
- `PAPER_AGENT_MAX_PDF_PAGES`：PDF 解析最大页数，避免上下文过大。

不要把真实 API Key 写入代码、报告、日志或前端页面。

## Streamlit 页面

主入口文件：`app_streamlit.py`

当前页面包括：

- `兴趣初始化 / Onboarding`：选择 5 个科研兴趣方向，建立初始用户画像。
- `科研雷达主页`：展示画像摘要和推荐结果入口。
- `画像分析 / Profile`：展示兴趣权重、画像统计和偏好清空入口。
- `文本查询`：输入自然语言问题，执行完整多智能体论文推荐流程。
- `多模态查询`：上传图片并输入补充问题，从图片中提取研究线索并推荐论文。
- `兼容旧功能`：保留早期 `PaperRadarWorkflow` 和图片解释入口。

## FastAPI 接口

主入口文件：`main.py`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 查看服务状态和模型 provider 类型 |
| `POST` | `/search` | 执行论文检索、排序、摘要和中文报告生成 |
| `POST` | `/vision/analyze` | 上传图片并调用视觉模型生成解释 |
| `GET` | `/tasks/{task_id}` | 查询历史任务记录 |

示例请求：

```powershell
curl -X POST http://127.0.0.1:8000/search `
  -H "Content-Type: application/json" `
  -d "{\"user_query\":\"检索最近三个月关于 LLM Agent Memory 的重要论文，并总结 Top 5。\",\"top_k\":5,\"time_range\":\"last_90_days\",\"user_id\":\"demo-user\"}"
```

响应核心字段：

- `final_report`
- `expanded_keywords`
- `candidate_count`
- `ranked_papers`
- `paper_summaries`
- `errors`

## 系统架构

系统按六层组织：

1. 交互层：Streamlit 页面和 FastAPI 接口。
2. 调度层：`CoordinatorAgent` 统一编排文本查询和多模态查询。
3. 智能体层：规划、检索、画像、推荐、阅读、审查、报告和视觉理解。
4. 工具层：arXiv、Semantic Scholar、时间桶检索、去重、PDF 解析等。
5. 数据层：SQLite 保存论文缓存、任务记录、用户画像、推荐日志和图片交互。
6. 输出层：论文卡片、推荐理由、中文 Markdown 简报、多模态推荐结果。

主要 Agent：

| Agent | 职责 |
| --- | --- |
| `CoordinatorAgent` | 统一调度完整任务流程 |
| `QueryPlannerAgent` | 解析意图、抽取关键词、识别时间范围 |
| `RetrievalAgent` | 调用 arXiv 与 Semantic Scholar，构造候选论文池 |
| `ProfileAgent` | 读取和更新用户画像 |
| `RecommenderAgent` | 根据画像、查询相关性、时效性等进行排序 |
| `ReaderAgent` | 生成推荐理由和结构化摘要 |
| `CriticAgent` | 对摘要进行保守审查，降低幻觉风险 |
| `ReportAgent` | 生成中文结构化报告 |
| `VisionAgent` | 理解图片内容并提取推荐关键词 |

## 工作流

### 文本查询

```text
用户问题
  -> QueryPlannerAgent 解析意图与关键词
  -> RetrievalAgent 检索近期论文
  -> ProfileAgent 更新画像
  -> RecommenderAgent 个性化排序
  -> ReaderAgent 生成摘要和推荐理由
  -> CriticAgent 审查摘要
  -> ReportAgent 输出中文简报
  -> MemoryRepository 保存记录
```

### 多模态查询

```text
图片上传 + 补充问题
  -> VisionAgent 图片理解
  -> 提取图片类型、主要内容、研究主题和关键词
  -> ProfileAgent 更新图片交互和兴趣权重
  -> RetrievalAgent 检索相关论文
  -> RecommenderAgent 推荐
  -> ReportAgent 生成多模态查询报告
```

## 推荐排序

新版 `RecommenderAgent` 使用可解释加权公式：

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

分项含义：

- `profile_match_score`：论文标题和摘要与用户兴趣画像的匹配程度。
- `query_relevance_score`：论文与当前查询关键词的匹配程度。
- `recency_score`：越新的论文得分越高。
- `citation_score`：引用数经过 log 缩放后的热度。
- `novelty_score`：未展示过的论文得分更高。
- `quality_score`：摘要、URL、PDF、作者信息越完整越高。
- `diversity_score`：当前作为后续多样性策略的预留项。

推荐结果会返回 `score_breakdown`，便于解释每篇论文为什么被推荐。

## 数据库与记忆

SQLite 表结构由 `paper_agent/memory/db.py` 初始化，主要包括：

- `papers`：论文缓存。
- `search_tasks`：旧工作流检索任务记录。
- `user_memory`：兼容旧版用户记忆。
- `users`：用户基础状态和 onboarding 状态。
- `user_interests`：用户兴趣画像和权重。
- `user_actions`：展示、已读、收藏、不感兴趣等行为。
- `recommendation_logs`：推荐展示日志。
- `image_interactions`：图片查询交互记录。

核心仓库封装在 `paper_agent/memory/repository.py`。

## 工程结构

```text
.
├── app_streamlit.py                 # Streamlit 多页面 UI
├── main.py                          # FastAPI 服务入口
├── paper_agent/
│   ├── agents/                      # 多智能体实现
│   ├── agent/                       # 兼容旧工作流
│   ├── memory/                      # SQLite 与用户记忆
│   ├── providers/                   # DeepSeek、Zhipu Vision、Mock provider
│   ├── tools/                       # arXiv、Semantic Scholar、去重、时间桶等
│   ├── ui/                          # Streamlit 展示辅助函数
│   ├── config.py                    # 配置读取
│   └── schemas.py                   # Pydantic 数据结构
├── tests/                           # 自动化测试
├── reports/                         # 课程报告与图片素材
├── docs/                            # 设计文档与技术交接
└── requirements.txt
```

## 测试结果

当前推荐验证命令：

```powershell
py -m pytest tests
```

最近一次验证结果：

```text
44 passed
```

测试覆盖：

- API 接口
- 旧版工作流
- 文本查询多智能体编排
- 多模态查询编排
- 用户画像和记忆更新
- 推荐排序与额外推荐
- 时间桶检索与去重
- Streamlit 静态页面入口
- VisionAgent 降级与关键词提取

## 课程报告材料

课程实验报告位于：

```text
reports/自然语言处理大作业-姓名-学号-实验报告.docx
```

报告图片素材位于：

```text
reports/pics/
```

报告中使用了系统架构图、多智能体协作流程图、文本查询截图、用户画像截图、多模态查询截图、测试通过截图、API 接口图和排序公式可视化图。

## 当前限制

- arXiv API 不提供稳定引用数，引用热度主要依赖 Semantic Scholar。
- 外部论文源受网络、代理和限流影响，可能出现检索失败。
- PDF 解析默认限制页数，避免下载成本和上下文过大。
- CriticAgent 当前为轻量保守审查，尚未实现严格 evidence-span 对齐。
- 本地向量检索是 MVP 级轻量实现，生产环境可替换为 Chroma、FAISS 或 Qdrant。
- 用户画像初期数据少，个性化效果依赖 onboarding 和后续反馈积累。
- 视觉模型对复杂图表中的精确数值理解仍可能不稳定。

## 后续方向

- 接入 OpenAlex、Crossref 等更多论文源。
- 建立全文向量库，增强论文级 RAG。
- 为摘要审查增加 evidence-span 对齐。
- 引入长期反馈学习和学习排序。
- 增强 OCR、表格解析和图表理解。
- 增加历史任务浏览、论文收藏和对话式追问。
