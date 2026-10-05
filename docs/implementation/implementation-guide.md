# 系统实现指导方案（Implementation Guide）

> 版本 v0.1 · 用途：把选型与架构落成**可被 AI 逐步生成、可验收、可回归**的工程方案
> 关联：选型 `project/framework-selection.md` v0.5 · 架构 `design/architecture-overview.md` · 设计问题手册 `design/agent-design-decisions.md` · 自愈预想 `design/challenges-and-self-healing.md` · 评测方案 `implementation/evaluation-plan.md`
> 已定范围（v0.1 决策）：首版只做 **Web 三界面**（CLI 延后）· **代码直接放仓库根**（`src/`、`config/`、`tests/`、`web/` 与 `docs/` 平级；Phase 0 实验区为 `prototype/`）· 前端 **Vue3 + TS + Vite + Element Plus** · 工具层**内置工具为主、预留 MCP 接口** · 部署环境**全部参数化** · 工程规范按推荐默认
> 技术栈：Python 3.11+ · uv · FastAPI · SQLAlchemy 2.0 + Alembic · LangGraph(+SQLite checkpointer) · LiteLLM · Kuzu · Qdrant(local) · DeepEval · APScheduler · Vue3

---

## 0. 如何使用本方案驱动 AI 生成代码

### 0.1 角色与信息流
| 角色 | 职责 |
|---|---|
| 人（你） | 决策、评审、跑验收命令、提交；对"契约变更"签字 |
| 本方案（文档） | 唯一实现依据：契约 + 模块接口 + 验收标准 |
| AI（生成者） | 一次只做一个任务卡（附录 B），产物必须通过该任务的验收命令 |

**铁律**：§2 的"冻结契约"是接口真相；AI 不得擅自修改契约、增删依赖、改动提示词文本（需走 ADR + 回归）。

### 0.2 每个任务的标准流程
1. 取一张任务卡（含 ID、目标文件、依赖任务、验收命令）；
2. 读该任务涉及的契约章节（§2）与模块实现章节（§3–§12）；
3. 先写/补测试（`tests/`），再实现；
4. 本地跑验收命令：`uv run ruff check . && uv run ruff format --check . && uv run pytest -q`；
5. 通过后提交，提交信息格式：`<task-id>: <summary>`；
6. 若发现契约不足 → 停下，提 ADR 草稿（附录 C），不要"顺手改"。

### 0.3 Definition of Done（每个任务都必须满足）
- [ ] 契约中声明的接口签名/数据结构未被破坏；
- [ ] 新增逻辑有单测，关键路径有集成测试；
- [ ] 不新增未批准依赖；不写入密钥/路径硬编码；
- [ ] 日志与事件埋点符合 §1.4 / §2.2；
- [ ] 验收命令全绿；失败路径（超时/异常/空结果）有测试覆盖；
- [ ] 更新受影响文档（README / 模块文档），保持"文档即契约"。

### 0.4 验收门与回归
| 层级 | 命令 | 触发时机 |
|---|---|---|
| 静态 | `uv run ruff check .` / `ruff format --check .` | 每任务 |
| 单测 | `uv run pytest -q tests/unit` | 每任务 |
| 集成 | `uv run pytest -q tests/integration` | 每模块完成 |
| 端到端 | `uv run pytest -q tests/e2e -m "not slow"` | 每阶段（P1–P6） |
| 回归 | `uv run pytest -q tests/regression`（录制回放） | 提示词/模型/守卫阈值变更后 |

---

## 1. 仓库结构与工程规范

### 1.1 目录树（仓库根 = Python 项目根）
```
agent/                         # 仓库根（= 项目根；docs/ 与代码平级）
├─ docs/                       # 研究与设计文档（选型/架构/实现/评测/演示）
├─ prototype/                  # Phase 0 实验区（Phase 1 完成后删除）
├─ pyproject.toml            # uv 管理；依赖与工具配置
├─ uv.lock
├─ README.md                 # 启动、配置、最小可跑说明
├─ .env.example              # 密钥占位（真实 .env 不入库）
├─ config/
│  ├─ config.example.yaml
│  └─ config.yaml            # gitignored
├─ migrations/               # Alembic
├─ src/lit_agent/
│  ├─ config.py              # pydantic-settings：YAML + env 合并
│  ├─ logging.py             # 结构化 JSON 日志
│  ├─ errors.py              # 错误分类学（§1.5）
│  ├─ models/                # Pydantic：Paper/Author/Topic/Run/Event/Report/Chat/Verdict
│  ├─ db/{base,tables,repo/} # SQLAlchemy 2.0 + 仓储层
│  ├─ sources/               # SourceAdapter + openalex.py + arxiv.py + whitelist.py
│  ├─ parsing/               # pdf.py + chunking.py + pipeline.py
│  ├─ stores/{graph,vector,files}.py
│  ├─ gateway/{llm,policy,metering}.py
│  ├─ context/{budget,folding,slots}.py
│  ├─ agents/{base,retrieval,mapper,analyst,reporter,critic,chat}.py
│  ├─ graph/{state,pipeline,guards,edges}.py
│  ├─ runtime/{runner,jobs,watchdog,events}.py
│  ├─ api/{app.py,routes/,sse.py}
│  ├─ tools/{registry,builtin/,mcp_adapter}.py
│  └─ eval/{grounding,judge,metrics,faultinject,datasets,export}.py
├─ tests/{unit,integration,e2e,regression,fixtures}/
├─ eval_data/                # 评测数据集（§12.6）
└─ web/                      # Vue3 + TS + Vite + Element Plus
   ├─ package.json / vite.config.ts / tsconfig.json
   └─ src/{api,stores,views/{Topics,Report,Chat},components,router}
```

### 1.2 依赖基线（`pyproject.toml`）
`fastapi, uvicorn[standard], sqlalchemy>=2, alembic, pydantic>=2, pydantic-settings, langgraph, langgraph-checkpoint-sqlite, litellm, httpx, pyalex, arxiv, pymupdf, pdfplumber, qdrant-client, kuzu, apscheduler, tiktoken, deepeval, structlog`（开发组：`pytest, pytest-asyncio, ruff, respx`）。
**禁止**：Redis/Celery/消息队列/Docker 依赖（P1–P6 不需要）。

### 1.3 配置管理
单一 `config.yaml` + 环境变量覆盖；所有键有安全默认；`llm.*.api_key` 只从 env 读。
```yaml
storage: {sqlite_path: data/app.db, kuzu_path: data/kuzu, qdrant_path: data/qdrant, papers_dir: data/papers}
sources: {openalex: {mailto: you@example.com}, arxiv: {categories: [cs.AI, cs.LG]}, venues: []}
providers:
  cloud: {name: deepseek, base_url: https://api.deepseek.com, model: deepseek-chat, api_key_env: DEEPSEEK_API_KEY}
  local: {engine: ollama, base_url: http://localhost:11434/v1, model: qwen2.5:7b, ctx_len: 8192}
routing: {sensitivity: strict, complexity_threshold: 0.5, run_cost_budget_usd: 2.0}
guards: {scope_cosine_min: 0.60, oos_share_max: 0.30, loop_k: 5, no_progress_steps: 2, max_retries: 2}
scheduler: {timezone: Asia/Singapore, default_cron: "0 3 * * 1", stagger_seconds: 300}
eval: {enabled: true, judge_provider: cloud, sample_rate: 0.2}
logging: {level: INFO, format: json}
```

### 1.4 日志规范（详规见 `logging-and-observability.md`）
- 结构化 JSON（structlog）写 `logs/app.jsonl` + 控制台：必填 `ts/level/event/logger/msg/app_version/config_version/host/pid/schema_version`；有上下文时带 `run_id/topic_id/stage/agent/attempt/tool/tool_call_id/event_seq`；
- **info 以上不得含论文正文/敏感原文**；正文与完整 prompt/response 仅在 debug 模式写 `logs/debug/<run_id>/`（7 天自动清理）；
- 每个外部调用（源 API、LLM、DB 写）**双写**：一条日志 + 一条事件（§2.2），并以 `run_id + stage + tool_call_id/event_seq` 三向关联；
- 错误日志必带 `error_code/retryable/action_taken`（§1.5）；
- 轮转与保留：按天 + 100 MB 上限轮转，`app.jsonl` 30 天、`errors.jsonl` 90 天（规范 §4）；
- 框架日志统一接管（LangGraph/LiteLLM/SQLAlchemy/httpx 等降为 WARNING），禁止 `print()`；慢点阈值与告警见规范 §8。

### 1.5 错误分类学（`errors.py`）
| 代码段 | 示例 | 默认处置 |
|---|---|---|
| `E_PROTO_*` | `E_PROTO_SCHEMA`、`E_PROTO_ISERROR` | 拒绝并重试 |
| `E_SRC_*` | `E_SRC_TIMEOUT`、`E_SRC_RATE`、`E_SRC_4XX`、`E_SRC_SCHEMA` | 退避重试 / 隔离告警 |
| `E_LLM_*` | `E_LLM_TIMEOUT`、`E_LLM_RATE`、`E_LLM_5XX`、`E_LLM_QUOTA` | 重试 → 熔断降级 |
| `E_SCHEMA_*` | `E_SCHEMA_STAGE_OUTPUT` | 重试 1 次 → 降档 |
| `E_GROUND_*` | `E_GROUND_UNRESOLVED_CITATION` | 标记/重写 |
| `E_GUARD_*` | `E_GUARD_DRIFT`、`E_GUARD_LOOP`、`E_GUARD_STAGNATION` | 条件边回退（§7） |
| `E_BUDGET_*` | `E_BUDGET_TOKENS`、`E_BUDGET_TIME`、`E_BUDGET_COST` | 降级或终止留痕 |
| `E_DATA_*` | `E_DATA_DUP`、`E_DATA_SYNC` | 幂等重放 |
| `E_LOCK_*` | `E_LOCK_HELD` | 排队或拒绝 |
每个错误对象含 `code, message, retryable, action_taken, context`。

### 1.6 测试基线
- `tests/unit`：纯逻辑，无网络（守卫阈值、校验器、幂等、折叠、路由策略）；
- `tests/integration`：SQLite + Kuzu + Qdrant(local) 真库，源 API 用 `respx` 录制响应；
- `tests/fixtures/`：源响应样本、MCP/工具返回样本、注入样本、录制 LLM 交互；
- `tests/regression`：golden run 回放（提示词/模型/阈值变更后必跑）。

---

## 2. 冻结契约（Freeze List，v0.1）

### 2.1 SQLite schema（表 = 真相源）
```sql
topics(id PK, name, description, scope_statement, status, config_json, schedule_cron,
       created_at, updated_at)
topic_sources(topic_id FK, source, selector_json)          -- arXiv category / OpenAlex venue id
runs(id PK, topic_id FK, trigger, state, error_code, started_at, finished_at, config_snapshot_json)
run_events(id PK, run_id FK, seq, ts, type, stage, agent, severity, payload_json, schema_version)
reports(id PK, topic_id FK, run_id FK, period, title, content_md, claims_json,
        metrics_snapshot_json, degraded, created_at)
chat_sessions(id PK, topic_id FK, created_at)
chat_messages(id PK, session_id FK, role, content, citations_json, run_id_ref, ts)
llm_calls(id PK, ts, run_id FK, agent, provider, model, route_reason,
          req_tokens, resp_tokens, latency_ms, cost, degraded)
metrics(id PK, scope, scope_id, metric, value, meta_json, ts)
sync_state(source, last_cursor, last_success_at, status, error_code)
job_locks(topic_id PK, owner, acquired_at, heartbeat_at)
eval_judgments(id PK, target_type, target_id, metric, score, judge_model, human, ts)
```
索引：`run_events(run_id, seq)`、`metrics(scope, scope_id, metric)`、`llm_calls(run_id)`、`chat_messages(session_id, ts)`。
写入规则：事件**只追加**；`reports`/`metrics` 提交后不可改（修订走新行）。

### 2.2 事件 schema
```json
{"id": 1, "run_id": 7, "seq": 42, "ts": "2026-01-01T03:00:00Z", "type": "tool_call",
 "stage": "retrieval", "agent": "retrieval_agent", "severity": "info",
 "payload": {"tool": "openalex_search", "args_hash": "…", "ok": true, "latency_ms": 812},
 "schema_version": "1.0"}
```
类型：`phase_change | tool_call | llm_call | guard_trigger | recovery | message | error | metric | report_written`
幂等键：`(run_id, stage, step_key)`；广播与落库顺序：**先落库，后广播**。

### 2.3 Pydantic 模型清单（`models/`）
`Author{author_id,name,name_norm}` · `Paper{paper_id,title,abstract,authors,venue,year,published_at,updated_at,source,references,oa_pdf_url}` · `SourceRecord{raw_json, fetched_at}` · `ParsedDoc{paper_id,text_path,page_count,quality}` · `Chunk{paper_id,idx,text,tokens}` · `EvidenceCard{paper_id,title,year,snippet,source,score}` · `Claim{text,citations[],support}` · `Verdict{ok,severity,action,reasons[]}` · 阶段产物 `RetrievalResult / MappingResult / AnalysisResult / ReportDraft` · `EvalRecord`。
规则：所有跨模块传递都用这些模型；**不用裸 dict**。

### 2.4 API 契约（REST + SSE）
| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/api/topics` | 列表 / 新建 |
| GET/PATCH/DELETE | `/api/topics/{id}` | 详情 / 修改（含 scope、源白名单、调度）/ 删除 |
| POST | `/api/topics/{id}/run` | 手动触发（返回 run_id；已有运行 → 409 `E_LOCK_HELD`） |
| GET | `/api/topics/{id}/runs` | 运行历史 |
| GET | `/api/runs/{id}` | 运行详情（状态、错误码、降级标记） |
| GET | `/api/runs/{id}/events` | 事件分页（回放） |
| GET | `/api/runs/{id}/stream` | **SSE**：实时事件流（`text/event-stream`） |
| GET | `/api/topics/{id}/reports` | 报告历史 |
| GET/POST | `/api/topics/{id}/chat` | 会话历史 / 发消息（**SSE 流式回答**） |
| GET | `/api/graph/authors/{id}` | 作者动向（近 N 年、合作者、方向位移） |
| GET | `/api/graph/topics/{id}/network` | topic 子图（节点/边，供可视化） |
| GET | `/api/metrics/summary` | 指标汇总（评测/看板） |
| GET | `/api/sources` / POST `/api/sources/sync` | 源状态 / 手动同步 |

### 2.5 图 schema（Kuzu DDL 摘要）
```cypher
CREATE NODE TABLE Paper(paper_id STRING PRIMARY KEY, title STRING, year INT64,
                        source STRING, discovered_at TIMESTAMP);
CREATE NODE TABLE Author(author_id STRING PRIMARY KEY, name STRING, name_norm STRING);
CREATE NODE TABLE Venue(venue_id STRING PRIMARY KEY, name STRING);
CREATE NODE TABLE Topic(topic_id STRING PRIMARY KEY, name STRING);
CREATE REL TABLE PAPER_AUTHOR(FROM Paper TO Author, year INT64);
CREATE REL TABLE CITES(FROM Paper TO Paper, first_seen TIMESTAMP);
CREATE REL TABLE PUBLISHED_IN(FROM Paper TO Venue);
CREATE REL TABLE BELONGS_TO(FROM Paper TO Topic, added_at TIMESTAMP);
CREATE REL TABLE SIMILAR_TO(FROM Paper TO Paper, score DOUBLE, computed_at TIMESTAMP);
```
写入一律 `MERGE`（幂等）；节点只存查询/展示必需字段（完整元数据在 SQLite）。

### 2.6 向量 collection（Qdrant）
`papers`：size=1024（bge-m3）、distance=Cosine、payload=`{paper_id,title,year,source,topic_ids,published_at,discovered_at}`；
`chunks`（阶段 P3 启用）：payload=`{paper_id,chunk_idx,tokens}`，正文放文件系统。

### 2.7 契约变更流程
任何契约变更 → 写 ADR（`docs/implementation/adr/NNNN-*.md`）：动机 / 影响面 / 迁移步骤 / 回归范围；未记录不得合并。

---

## 3. 模块 1：源适配与解析（`sources/`, `parsing/`）

**目标**：OpenAlex 主 + arXiv 辅 + 白名单 → 统一 `Paper`；增量、去重、幂等；OA 全文抽取与分块。
**接口**
```python
class SourceAdapter(Protocol):
    name: str
    def fetch_updated(self, since: datetime, selector: dict) -> AsyncIterator[SourceRecord]: ...
    def to_paper(self, rec: SourceRecord) -> Paper: ...
def canonical_id(doi: str | None, openalex_id: str | None, arxiv_id: str | None) -> str  # DOI→W→arxiv:
def fingerprint(paper: Paper) -> str          # sha1(canonical_id)
async def sync_topic(topic, adapters, repos, stores) -> SyncReport
```
**实现步骤**：① pyalex/arxiv 分页拉取（带 mailto、礼貌限速、退避）；② `to_paper` 字段映射 + 作者 `name_norm`；③ 指纹去重与 `sync_state` 游标更新；④ 写 SQLite（真相源）→ 投影 Kuzu（MERGE）→ Qdrant（upsert）；⑤ 解析管道：OA 定位 → 下载 → PyMuPDF → pdfplumber 兜底 → 清洗 → 递归分块（token 预算）→ chunk 向量；⑥ 失败隔离（`E_SRC_*`）+ 可重跑。
**配置**：`sources.*`、`storage.papers_dir`、解析并发与超时。
**单测清单**：canonical_id 优先级、指纹幂等、字段映射（缺字段/多作者/无 DOI）、坏 PDF fallback、分块 token 预算边界、限流退避（respx fixture）。
**验收标准**：同一 fixture 连续跑两次，三库记录数不增（幂等）；断源字段样本不崩、错误入库为告警事件；分块 token 数与配置一致（±5%）。

---

## 4. 模块 2：存储层（`db/`, `stores/`）

**目标**：SQLite 为真相源；Kuzu/Qdrant 为可重建索引；薄仓储层屏蔽 SQL。
**接口**：`TopicRepo / RunRepo / EventRepo / ReportRepo / ChatRepo / MetricRepo / SyncStateRepo`（方法按 §2.1 表）；`GraphStore.upsert_paper/upsert_edges/recent_papers_by_author/novelty_candidates`；`VectorStore.upsert_papers/search(filter,...)`；`FileStore.write_text/read_chunk`。
**实现步骤**：① `engine` 用 SQLite + `PRAGMA journal_mode=WAL`、单写者封装（事件顺序写）；② Alembic 初始迁移；③ 图/向量服务启动时自检 schema（缺则建）；④ 投影任务表状态（pending/done/failed）与重试；⑤ 重建命令 `python -m lit_agent.tools.rebuild_indexes`。
**单测清单**：WAL 并发写、事件 seq 单调、MERGE 幂等、Qdrant filter（topic/year/source）、重建后计数对账。
**验收标准**：删 Kuzu/Qdrant 后由 SQLite+源重建，图查询与检索结果与重建前一致；注入单库写失败 → 系统仍可查询（回退真相源）。

---

## 5. 模块 3：LLM 网关（`gateway/`）

**目标**：统一 OpenAI 协议调用；敏感度强制路由；熔断降级；全量计量。
**接口**
```python
class LLMGateway:
    async def chat(self, *, agent: str, messages: list[Message], task_class: TaskClass,
                   sensitivity: Sensitivity, schema: type[BaseModel] | None = None) -> LLMResult: ...
# policy.decide(task_class, sensitivity, health) -> RouteDecision{provider, model, reason, allow}
# metering.on_success/on_failure -> 写 llm_calls + 事件
```
**实现步骤**：① LiteLLM Router 注册 `cloud/local`（OpenAI 兼容 base_url）；② policy 层：`sensitivity=secret` → 只允许 local（拦截非本地，写入 deny 事件）；复杂度/成本 → 选择 deployment；③ 熔断器（按 provider，closed/open/half-open，阈值配置）；④ 重试退避 + jitter；⑤ 计量 callback 落库；⑥ 内置 `judge`/`embedding` 用途走同一接口。
**单测清单**：敏感度 deny（不产生网络调用）、熔断状态迁移、降级链顺序、计量字段完整、超时重试次数上限。
**验收标准**：拔掉云 key 后自动切本地继续跑；敏感样本零出网（审计事件可证）；每次调用都有 `llm_calls` 行且字段齐全。

---

## 6. 模块 4：编排与多 Agent（`graph/`, `agents/`）

**目标**：LangGraph 显式状态图跑周更；角色 agent 只产出结构化产物。
**状态**：`RunState{topic_id, run_id, stage, scope, evidence: list[EvidenceCard], open_questions, counters{budget,retries,loop}, artifacts{...}}`（只存结构化摘要 + 指针）。
**节点**：`scope_check → plan → retrieve(retrieval_agent) → ingest(解析/入库) → map(mapper) → novelty → analyze(analyst) → draft(reporter) → critique(critic) → finalize`。
**条件边**：见 §7 守卫映射；所有回退有次数上限（`guards.max_retries`）。
**接口**：`build_pipeline(services) -> CompiledGraph`；每个 agent 实现 `async def run(state, ctx) -> StageOutput`；`thread_id = run_id` 绑定 `SqliteSaver`。
**实现步骤**：① 定义 state 与各阶段 Pydantic 产物；② 节点包装（计时/事件/预算扣减）；③ 条件边（守卫判决 → 路由）；④ checkpoint 配置（节点边界）；⑤ `astream_events` → 事件 sink（§9）；⑥ 对话图 `chat_graph`（ReAct + 领域工具）。
**单测清单**：图可达性（每条边有测试）、状态更新正确、预算扣减与超限终止、checkpoint 恢复后续跑、对话工具选择。
**验收标准**：注入"空检索/坏产物/超时"三类故障，图按预期走降级路径且事件完整；同一输入两次运行的状态轨迹一致（除 LLM 采样差异）。

---

## 7. 模块 5：守卫与自愈（`graph/guards.py`, `runtime/watchdog.py`）

**目标**：把 `design/agent-design-decisions.md` A1–A8 落成可测代码。
**接口**
```python
@dataclass
class GuardVerdict: ok: bool; action: Literal["continue","retry","degrade","replan","abort"]; code: str; reasons: list[str]

async def guard_scope_drift(stage_output, scope, cfg) -> GuardVerdict
async def guard_retrieval_oos(cards, scope, cfg) -> GuardVerdict
async def guard_loop(tool_signatures, state_hashes, cfg) -> GuardVerdict
async def guard_no_progress(evidence_delta, cfg) -> GuardVerdict
async def guard_schema(stage_output) -> GuardVerdict
async def guard_citations(claims, corpus) -> GuardVerdict
async def guard_budget(counters, cfg) -> GuardVerdict
def recovery_packet(verdict, state) -> Message      # 失败类型+可信状态+下一步约束
```
**实现步骤**：① 检测器纯函数化（可单测、无 IO）；② 阈值全部来自 `guards.*` 配置；③ 判决映射条件边（`replan → plan`、`retry → 同节点`、`degrade → 换 provider`、`abort → finalize(annotated)`）；④ 恢复包注入 system 槽；⑤ 每次触发写 `guard_trigger` + `recovery` 事件；⑥ 看门狗：节点超时、run 预算、停滞检测，独立协程。
**单测清单**：每个检测器的边界值（阈值 ±ε）、动作映射、误报基线（正常样本不触发）、恢复包内容结构。
**验收标准**：故障注入集（漂移/循环/停滞/超时/幻觉诱导）能产出"检出→处置→恢复"完整事件链；正常 run 的守卫触发率低于配置基线（无误报）。

---

## 8. 模块 6：上下文工程（`context/`）

**目标**：把窗口当预算管理；记忆在窗外、引用进窗内。
**接口**：`estimate_tokens(messages)`；`budget_for(agent, state) -> Budget`；`fold(state, budget) -> FoldedContext`（阈值触发摘要节点）；`build_slots(scope, task, cards) -> Messages`（固定 system/user/tools 槽）；`kv_estimate(tokens, provider) -> bool`（是否触发折叠或切云）。
**实现步骤**：① token 计数（tiktoken/模型映射）；② 折叠策略：检索历史 → 要点+引用、旧对话 → 摘要、长文永不整篇；③ 超预算先折叠、再路由云；④ 折叠前后写 `metric` 事件（token 与质量对照）。
**单测清单**：预算计算、折叠触发点、槽位固定结构、KV 估算阈值、折叠后引用不丢失。
**验收标准**：构造超长输入，窗口不超限且引用完整；折叠与非折叠两组回答质量在评测中可对比（§12）。

---

## 9. 模块 7：调度与长任务（`runtime/`）

**目标**：每周自动触发、job 生命周期、看门狗、崩溃可恢复。
**接口**：`Scheduler.start()`（APScheduler，每 topic cron + 错峰）；`JobRegistry.enqueue/claim/heartbeat/complete/fail/cancel`；`Runner.run(run_id)`；`EventBus.publish(event)` + `EventSink.persist_then_broadcast`；`recover_interrupted()`。
**实现步骤**：① DB 锁（`job_locks` + 心跳）保证 per-topic 串行；② 手动触发与定时同队列；③ 启动扫描 `running` → 心跳过期 → `interrupted`（可续跑/待重跑，策略配置）；④ 事件先落库后广播；⑤ 取消信号（协作式，节点边界检查）。
**单测清单**：锁竞争（同 topic 409）、心跳过期判定、崩溃恢复状态机、取消路径、事件顺序。
**验收标准**：并发触发同 topic 只跑一个；kill -9 后重启状态正确；事件无缺失、无重复广播。

---

## 10. 模块 8：后端 API 与 SSE（`api/`）

**目标**：实现 §2.4 契约；SSE 推送运行事件与聊天流。
**接口**：`create_app(services) -> FastAPI`；依赖注入（repos/stores/gateway/runner）；`/api/runs/{id}/stream` 用 `StreamingResponse`（`text/event-stream`，禁缓冲，带 heartbeat 注释帧）；`POST /api/topics/{id}/chat` 流式返回 token + 最终 citations。
**实现步骤**：① Pydantic 模型直接复用 `models/`（agent 协议 = API schema）；② 事件订阅：内存 pub/sub 按 run_id 分发，断线用 `Last-Event-ID` 从事件表续传；③ 阻塞工作（解析/embedding）进线程池；④ 错误统一映射为 §1.5 错误码 + HTTP 状态；⑤ OpenAPI 导出供前端生成类型。
**单测清单**：路由契约测试（FastAPI TestClient）、SSE 帧格式、断线续传、409 锁、错误码映射。
**验收标准**：前端能实时看到完整事件序列；断线重连不丢事件；OpenAPI 生成的前端类型可编译。

---

## 11. 模块 9：前端三界面（`web/`，Vue3 + TS + Vite + Element Plus）

**目标**：Topic 管理 / Report（过程回放 + 报告历史 + 关系网络图）/ Chat（流式 + 引用）。
**结构**：`api/`（openapi-typescript 生成 + fetch 封装）· `stores/`（Pinia：topics、runs、chat）· `views/{Topics,Report,Chat}` · `components/{EventTimeline,ReportViewer,GraphNetwork,AuthorPanel,SourceConfig}` · `composables/useSse.ts`。
**实现步骤**：① 生成 API 类型；② `useSse` 用 EventSource 订阅并追加事件；③ EventTimeline 按 `phase/tool/thinking/guard/error` 分类过滤 + 折叠；④ GraphNetwork 用 ECharts graph 渲染 topic 子图，点作者 → AuthorPanel（近 N 年发文/合作者/方向关键词）；⑤ Chat 流式渲染 + citation 点击回溯到论文卡片；⑥ 顶部展示降级/失败标记。
**单测清单**：SSE 事件归并、过滤逻辑、图表数据转换、错误态/空态渲染（Vitest）。
**验收标准**：三个页面可用且能完成"创建 topic → 触发运行 → 观看过程 → 阅读报告 → 追问作者"的完整演示路径；图谱万级节点下按 topic 子图裁剪不卡顿。

---

## 12. 模块 10：评测与可观测（`eval/`）

**目标**：实现 `implementation/evaluation-plan.md` 的数据集、指标与执行协议。
**接口**：`extract_claims(md) -> list[Claim]`；`ground(claims, snapshot) -> GroundingReport`；`judge(target, rubric) -> Score`（DeepEval 外壳）；`faultinject.inject(run, scenario)`；`aggregate(...) -> MetricsFrame`；`export_charts(...)`。
**实现步骤**：① 数据集管理（`eval_data/topics/`、`chat_sets/`、`fault_scenarios/`、`snapshots/` 版本化）；② grounding：claim → citation → 快照回查 → 三类判定（支持/矛盾/无支撑）；③ 指标：grounding 支持率、幻觉率、对话准确率与召回（对 gold 事实）、漂移与自愈指标（检出/处置/恢复/越界）、双引擎配对对比；④ 故障注入 hook（生产同路径、仅测试副本）；⑤ 导出论文图表数据。
**单测清单**：claim 抽取、三类判定边界、召回计算、fault injector 不影响生产数据、指标聚合口径。
**验收标准**：固定测试集重复跑结果稳定（快照锁定）；"守卫开/关"两组对照可产出统计差异；评测命令一键可跑。

---

## 13. 重难点实现指引（与设计手册映射）

| 设计问题（`design/agent-design-decisions.md`） | 实现位置 |
|---|---|
| A1 防走偏 · A2 循环停滞 · A3 恢复注入 | `graph/guards.py`、`graph/edges.py` |
| A4 预算看门狗 · A7 失败留痕 | `runtime/watchdog.py`、`runtime/jobs.py` |
| A5 checkpoint 一致性 · G3 崩溃恢复 | `runtime/runner.py`、`db/repo/events.py` |
| A6 跨周漂移 · F4 快照 | `eval/metrics.py`、`eval/datasets.py` |
| A8 降级标注 | `reports.degraded`、`llm_calls.degraded` |
| B1 工具结果校验管线（L0–L5） | `tools/registry.py` + `validators/`（每工具绑定 schema 与策略） |
| B2 注入投毒 · H3 沙箱 | `tools/`、`parsing/clean.py` |
| B3 错误重试 · B4 幂等 | `gateway/`、`tools/` |
| C1–C6 上下文工程 | `context/` |
| D1–D6 事实性控制 | `eval/grounding.py`、`agents/reporter.py` |
| E1–E5 多 Agent 协作 | `agents/`、`graph/pipeline.py` |
| F1–F5 数据一致性 | `db/`、`stores/` |
| G1–G5 调度 | `runtime/jobs.py`、`runtime/runner.py` |
| H1–H2/H4 安全与密钥 | `gateway/policy.py`、`config.py` |
| I1–I4 可观测 | `runtime/events.py`、`logging.py`、`errors.py` |
| J1–J5 评测闭环 | `eval/` |
| K1–K4 工程化 | `pyproject.toml`、`tests/regression/` |

---

## 14. 分阶段验收（P1–P6）

| 阶段 | 交付物 | 验收门（DoD） | 演示脚本 |
|---|---|---|---|
| **P1 最小闭环** | 源适配+解析+SQLite/Kuzu/Qdrant 写库；手动触发单 topic run；事件表 + 基础 API/SSE | 同一 fixture 幂等；事件可按 run 回放；`pytest -m "not slow"` 全绿 | 建 topic → 手动跑 → 页面上看到事件与一份报告 |
| **P2 Harness** | LangGraph 流水线 + 守卫/看门狗 + 网关熔断 + 故障注入 hook | 注入漂移/循环/停滞/超时均能检出并处置；恢复包注入生效 | 现场注入故障，展示自愈事件链 |
| **P3 多 Agent + 上下文** | 角色拆分、折叠策略、Chat 页、chunks 向量 | 折叠后质量不劣化（对照评测）；对话带 citation | 对报告追问作者动向，引用可回溯 |
| **P4 周更与关系图** | APScheduler 周更、novelty、作者动向查询、Report 页网络图 | 连续 2 周无人值守自动出报；图谱可交互 | 展示两周报告 + 作者方向变化面板 |
| **P5 评测** | 测试 topic 集、gold 事实、对话问题集、故障注入集、指标表 | ≥4 周数据；守卫开/关对照；local vs cloud 对比 | 展示指标图表与结论 |
| **P6 文档与收尾** | 上下文/配置规范文档、迁移说明、论文素材 | 文档与代码一致；复现实验脚本可跑 | 一键复现评测结果 |

---

## 15. AI 生成工作流

### 15.1 任务卡模板（附录 B 同）
```
Task ID: P2-GUARD-03
Goal: 实现 guard_loop 检测器与其条件边路由
Files: src/lit_agent/graph/guards.py, tests/unit/test_guard_loop.py
Depends: P1-EVENTS-01, P2-STATE-01
Contracts: §2.2 事件 schema, §7 GuardVerdict 接口
Acceptance: uv run pytest -q tests/unit/test_guard_loop.py；正常样本零触发
Forbidden: 修改 §2 契约；新增依赖；改动提示词文本
```

### 15.2 提示词模板（给 AI 生成者）
> 读取 `docs/implementation/implementation-guide.md` 的 §{模块} 与 §2 契约；只实现任务卡列出的文件；先写测试再实现；不得修改冻结契约/新增依赖；完成后运行验收命令并贴出输出；若契约不足，输出 ADR 草稿而不是自行决定。

### 15.3 每任务验收命令
```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest -q tests/unit -k "<task keyword>"
uv run pytest -q tests/integration -m "not slow"     # 涉及 DB/存储时
```

### 15.4 回归与变更管控
- 提示词/模型/阈值变更 → 必跑 `tests/regression`（golden run 回放）+ 评测固定集子集；
- 契约变更 → ADR + 迁移脚本 + 全量集成测试；
- 依赖变更 → 仅允许 §1.2 列表内；新增需 ADR。

### 15.5 常见错误（AI 生成时的红线）
1. 用裸 `dict` 替代 Pydantic 契约；2. 在提示词里塞业务约束（应放代码/守卫）；3. 用 LLM 做可确定性判定的校验（如数值范围）；4. 事件"先广播后落库"；5. 图/向量写入不做 MERGE 幂等；6. 忘记写 `llm_calls`/事件埋点；7. 引入未批准依赖（Redis/Celery 等）；8. 修改冻结契约而不提 ADR；9. 在日志/事件中写入密钥或敏感原文；10. 失败静默（不写错误事件）。

### 15.6 文档结构要求（所有 step/phase 类文档必备章节，v0.2 起强制）

后续每一份"阶段/步骤"文档（Phase N、Step 清单、Wave 计划等）必须包含以下 8 个章节，缺一不可：

| # | 必备章节 | 说明 |
|---|---|---|
| 1 | 目标与出口标准 | 含"明确不做清单"与可勾选的出口检查项 |
| 2 | 全局约定 | 代码位置、环境初始化、埋点要求、记录模板 |
| 3 | **文件结构与职责** | 目录树 **+ 文件职责表**（路径 / 功能责任 / 关键接口或内容 / 输入→输出 / 依赖 / 归属步骤 / 下一阶段归属）**+ 文件边界与命名约定** |
| 4 | Step 明细 | 每步：内容要求 / 交付物 / 执行命令 / 期望输出 / 验收标准 / 时间盒 / 失败应对 |
| 5 | 进度跟踪表 | 状态（☐◐☑⛔）+ 结论数字列 + 依赖 |
| 6 | 常见失败与应对 | 含"结论为负"的处理原则 |
| 7 | 出口检查清单 | 逐项勾选，作为进入下一阶段的门 |
| 8 | 与下一阶段的衔接 | 哪些文件保留/升级/丢弃 + 下一阶段第一张任务卡 |

**理由**：文件职责表让后续优化能**定位到具体文件**（避免重复实现与职责漂移），也是 AI 生成代码时的文件边界依据；范式模板见 `implementation/phase0-implementation-steps.md` §1.1–§1.1.2。

---

## 附录 A：文件级生成顺序（Wave）

| Wave | 内容 | 依赖 |
|---|---|---|
| 1 | `pyproject.toml`、`config.py`、`logging.py`、`errors.py`、`models/` | — |
| 2 | `db/`（表 + 仓储 + Alembic 初始迁移）、`stores/files.py` | W1 |
| 3 | `stores/{graph,vector}.py` + 幂等测试 | W2 |
| 4 | `sources/` + `parsing/` + 三库投影 | W2, W3 |
| 5 | `gateway/`（LiteLLM + policy + metering） | W1 |
| 6 | `graph/{state,pipeline,edges}.py` + `agents/` 骨架 | W4, W5 |
| 7 | `graph/guards.py` + `runtime/{runner,jobs,watchdog,events}.py` | W6 |
| 8 | `api/`（REST + SSE）+ OpenAPI 导出 | W7 |
| 9 | `web/`（三界面，按 §11） | W8 |
| 10 | `eval/` + `eval_data/` 种子数据 + 回归基线 | W7 |
| 11 | 周更调度接入 + 文档收尾 | W9, W10 |

## 附录 B：任务卡清单（首批示例）
| Task ID | 目标 | 验收 |
|---|---|---|
| W1-CFG-01 | 配置加载（YAML+env，含安全默认） | 空配置启动自检通过 |
| W1-MODEL-01 | Pydantic 契约模型全部落地 | schema 单测 + JSON 往返 |
| W2-DB-01 | SQLite 表 + Alembic 初始迁移 | 迁移可升可降；WAL 生效 |
| W3-GRAPH-01 | Kuzu 服务 + MERGE 幂等 | 重复写入不增节点 |
| W3-VEC-01 | Qdrant local + filter 检索 | 过滤/幂等测试 |
| W4-SRC-01 | OpenAlex 适配器（增量游标） | respx fixture + 幂等 |
| W4-PARSE-01 | PyMuPDF + pdfplumber fallback + 分块 | token 预算 ±5% |
| W5-GW-01 | LiteLLM 路由 + 敏感度拦截 | 敏感样本零出网 |
| W6-GRAPH-01 | LangGraph 流水线骨架 | 可达性 + checkpoint |
| W7-GUARD-01 | 六类守卫 + 条件边 | 注入集全通过 |
| W8-API-01 | REST 契约 + SSE 流 | 断线续传测试 |
| W9-WEB-01 | 三界面可用 | 演示路径走通 |
| W10-EVAL-01 | grounding + 指标聚合 | 固定集结果稳定 |

## 附录 C：契约变更 ADR 模板
```
# ADR NNNN: <title>
Status: proposed | accepted | rejected
Context: 现状与动机
Decision: 变更内容（接口/表/事件/schema）
Impact: 受影响模块与测试
Migration: 迁移步骤（含数据）
Verification: 回归与验收命令
```

> 下一步建议：按附录 A 的 Wave 1 起**在仓库根**生成正式代码骨架（`src/` 等，见 §1.1）；Phase 0 的 `prototype/` 按 FILEMAP 的"下一阶段归属"列搬运完成后删除。每完成一个 Wave 跑一次验收门并更新本方案（v0.2 起在文末追加"实现进度"小节）。
