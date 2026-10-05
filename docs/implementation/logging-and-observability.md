# 日志与可观测性规范（Logging & Observability Spec）

> 版本 v0.1 · 定位：**可观测性的唯一规范**——字段、级别、脱敏、落盘轮转、调试开关、debug bundle、框架日志接管、慢点告警、运维反馈闭环
> 关联：`implementation-guide.md` §1.4/§2.2/§13（落地位置）· `phase0-implementation-steps.md` Step 0.3（最小基线）· `../design/architecture-overview.md` §3.7（事件溯源）· `../design/agent-design-decisions.md` H4/I 类（问题与解法）· `../design/state-machine-and-guards.md`（守卫事件）
> 原则：**日志＝过程可读；事件＝事实真相；指标＝聚合优化**。三者可互相关联，但**不重复造真相**。

---

## 1. 三层模型与职责边界

| 层 | 目的 | 存储 | 写入者 | 读取者 | 保留 |
|---|---|---|---|---|---|
| **日志 log** | 人排障：上下文、时序、异常栈、性能 | `logs/*.jsonl`（可轮转） | 所有模块 | 开发者 / 运维 | 30 天（错误 90 天） |
| **事件 event** | 机器事实：回放、评测、审计、状态恢复 | SQLite `run_events`（Phase 0 为 `out/events.jsonl`） | 编排/守卫/工具/网关 | 评测、回放、UI | 长期（按 run 归档） |
| **指标 metric** | 聚合优化：趋势、告警、论文数据 | SQLite `metrics`（由事件聚合 + 少量直写） | 聚合器 | 看板/评测/告警 | 长期 |

**边界规则（强制）**
1. **任何外部调用**（源 API / LLM / DB / 工具）→ **双写**：1 条日志 + 1 条事件；
2. **事件只追加不可改**，是回放的唯一真相源；日志可以被轮转/压缩/删除；
3. **指标优先由事件聚合**得出，只有无法从事件推导的（如进程内存水位、磁盘水位）才直写 `metrics`；
4. 绝不用日志替代事件做状态判断，也绝不用事件替代日志做逐行排障（事件是结构化事实，日志是叙述）。

---

## 2. 字段字典

### 2.1 日志字段（JSON 行）
| 字段 | 必填 | 说明 | 示例 |
|---|---|---|---|
| `ts` | ✅ | UTC ISO8601 | `2026-01-01T03:00:00.123Z` |
| `level` | ✅ | `debug/info/warning/error/critical` | `info` |
| `event` | ✅ | 语义事件名（snake_case） | `tool_call_finished` |
| `logger` | ✅ | 模块名 | `lit_agent.sources.openalex` |
| `msg` | ✅ | 一行中文/英文叙述（**不含正文**） | `openalex page fetched` |
| `run_id` | ⭕ | 有 run 上下文时必填 | `p0-s5-001` |
| `topic_id` | ⭕ | topic 上下文 | `T1` |
| `stage` | ⭕ | 流水线阶段 | `S2_retrieve` |
| `agent` | ⭕ | 角色 | `retrieval_agent` |
| `attempt` | ⭕ | 第几次尝试（重试/回退） | `2` |
| `tool` / `tool_call_id` | ⭕ | 工具名 / 本次调用唯一 ID（ULID） | `openalex_search` / `01J...` |
| `event_seq` | ⭕ | 关联的 `run_events.seq`（三向跳转用） | `42` |
| `provider` / `model` | ⭕ | LLM 调用 | `deepseek` / `deepseek-chat` |
| `req_tokens` / `resp_tokens` / `cost_usd` | ⭕ | 计量 | `1203` / `455` / `0.0012` |
| `latency_ms` | ⭕ | 本次操作耗时 | `812` |
| `error_code` | ⭕（error 级必填） | 见 `implementation-guide.md` §1.5 | `E_SRC_TIMEOUT` |
| `retryable` / `action_taken` | ⭕ | 错误处置 | `true` / `retry_backoff` |
| `degraded` | ⭕ | 是否走了降级路径 | `false` |
| `app_version` / `config_version` | ✅ | 代码与配置版本（复现必需） | `0.1.0` / `cfg-a13f` |
| `host` / `pid` | ✅ | 运行环境 | `zhu-nb` / `23412` |
| `schema_version` | ✅ | 日志 schema 版本 | `1.0` |

### 2.2 事件字段
沿用 `implementation-guide.md` §2.2（`id, run_id, seq, ts, type, stage, agent, severity, payload, schema_version`），**新增约定**：`payload.tool_call_id` 与 `payload.attempt` 与日志同名字段一致，用于三向定位。

### 2.3 三向关联
```
日志行 ──(run_id + stage + tool_call_id / event_seq)──► 事件（回放时间线）
   │                                                        │
   └──────────(run_id + attempt)──► debug 快照 / bundle ◄────┘
```
**验收**：给定任一 `run_id`，能 ① 取完整事件时间线；② 从任一事件找到对应日志行；③ 从任一错误日志跳到对应事件与上下文快照。

---

## 3. 级别策略与脱敏

| 级别 | 使用场景 | 内容限制 |
|---|---|---|
| `debug` | 逐步骤细节、原始响应结构、折叠前后 token 数 | 可含正文/原始 payload，**但只在受控目录**（`logs/debug/`） |
| `info` | 阶段进出、工具调用摘要、计量、状态迁移 | **不得含论文正文/用户原文/密钥** |
| `warning` | 可恢复异常、阈值触发（慢点、重试、降级） | 摘要 + 关键字段 |
| `error` | 操作失败（必带 `error_code`） | 摘要 + 错误码 + 是否可重试 |
| `critical` | 进程级故障、数据损坏风险 | 摘要 + 建议动作 |

**脱敏规则（统一由 logger processor 实现，禁止各模块自行拼字符串）**
| 目标 | 规则 |
|---|---|
| 密钥/令牌 | 键名匹配 `(?i)(api[_-]?key\|token\|secret\|password\|authorization)` → `"***"` |
| 邮箱（含 OpenAlex `mailto`） | 保留域名、本地部分打码：`z***@nus.edu.sg` |
| 本地路径 | 家目录替换为 `~`（避免泄露真实用户名/目录结构） |
| 论文正文/用户输入 | 默认不写；必须写时替换为 `{sha1, chars}` 摘要 |
| Prompt / Response | INFO 只记 `prompt_template_version + prompt_hash + resp_hash`；全文仅 debug 模式（§5） |

**禁止清单**：密钥明文、`.env` 内容、完整 prompt/response（默认）、原始 PDF 文本、用户聊天全文（INFO 及以上）。

**测试**：脱敏单测覆盖上表每一项；CI 扫描 info 日志不得出现长度 > 500 的文本字段。

---

## 4. 落盘、轮转、保留与容量

```
logs/
├─ app.jsonl                  # 全量日志（JSON 行）
├─ errors.jsonl               # 仅 error/critical（便于快速排障）
├─ llm/2026-01-01.jsonl       # LLM 调用记录（与 llm_calls 表对应，摘要级）
├─ debug/<run_id>/            # 调试模式产物（默认不生成，见 §5）
│  ├─ llm_calls.jsonl         # 脱敏后的完整 prompt/response
│  ├─ context_snapshots.jsonl # 折叠前后上下文
│  └─ tool_io.jsonl           # 工具入参/原始返回
├─ bundles/                   # debug bundle 导出的 zip（§6）
└─ archives/                  # 轮转归档（gz）
```
| 项 | 默认值 | 配置键 |
|---|---|---|
| 单文件上限 | 100 MB | `logging.max_file_mb` |
| 轮转 | 按天 + 超限即轮转 | `logging.rotate` |
| `app.jsonl` 保留 | 30 天（压缩归档） | `logging.retain_days` |
| `errors.jsonl` 保留 | 90 天 | `logging.retain_error_days` |
| `debug/` 保留 | 7 天（自动清理） | `logging.debug_retain_days` |
| 磁盘水位告警 | `logs/` > 2 GB 或磁盘 > 80% | `logging.disk_alert` |
| 写入开销 | < 3% run 墙钟时间（debug 模式 < 10%） | 验收指标 |

**容量估算**：单 run ≈ 1–3 MB 日志（info）+ 0.5 MB 事件；若 10 topic × 每周 = 每周 ≈ 40 MB → 30 天滚动足够（≈ 170 MB）。事件表同样按 run 归档（`run_events` > 50 万行时按季度分表/导出归档）。

---

## 5. 调试开关（per-run / per-topic）

**配置与触发**
```yaml
logging:
  level: INFO
  debug_runs: []            # 例：["p0-s5-001"] 或 ["T1:*"]（topic 全程）
```
```bash
uv run python -m lit_agent.runtime.run --topic T1 --run-id p0-s5-001 --debug-run
# 或 API：POST /api/topics/{id}/run {"debug": true}
```
**开启后的行为**
1. 该 run 的日志级别降为 `debug`（只影响该 run，其他 run 保持 info）；
2. 记录**脱敏后**的完整 prompt/response、上下文折叠前后快照、工具原始入参/返回 → `logs/debug/<run_id>/`；
3. 写入一条事件 `metric{debug_mode: true}`（**审计**：谁在何时开了调试）；
4. 保留 7 天后自动清理；bundle 导出后建议手动归档。

**默认关闭**；禁止在生产配置中长期开启（启动自检会告警）。

---

## 6. debug bundle（一键导出证据包）

```bash
uv run python -m lit_agent.tools.debug_bundle --run-id p0-s5-001 --out logs/bundles/
```
**内容清单（固定顺序，缺项要显式标注 "N/A"）**
| # | 文件 | 内容 |
|---|---|---|
| 1 | `README.md` | 现象描述模板 + 复现命令 + 环境版本 |
| 2 | `run.json` | run 元数据（topic、触发方式、状态、起止、降级标记） |
| 3 | `events.jsonl` | 该 run 的完整事件时间线 |
| 4 | `llm_calls.jsonl` | 调用明细（provider/model/token/成本/时延/route_reason） |
| 5 | `guards.jsonl` | 守卫判决与恢复包 |
| 6 | `logs.jsonl` | 该 run 的日志（已脱敏） |
| 7 | `config.snapshot.yaml` | 配置快照（脱敏，仅 guards/routing/logging 等） |
| 8 | `prompts.json` | 提示词模板版本 + hash |
| 9 | `env.json` | Python/依赖版本、OS、模型版本、采样参数 |

**约束**：单包 ≤ 50 MB；打包前自动跑脱敏检查（发现疑似密钥即失败）；**不含**原始 PDF、完整语料、用户全量聊天。
**用途**：① 组会/求助时提交；② 运维反馈闭环（§10）；③ 作为回归测试 fixture 的输入。

---

## 7. 框架与第三方日志接管

| 来源 | 级别 | 去向 |
|---|---|---|
| 自有 logger（`lit_agent.*`） | 按 §3 | `app.jsonl` + 控制台 |
| LangGraph / langchain-core | `WARNING` | `app.jsonl`（加 `logger` 字段区分） |
| LiteLLM | `WARNING`（调用失败时 INFO 记录摘要） | `app.jsonl` |
| SQLAlchemy / Alembic | `WARNING`（`echo=False`） | `app.jsonl` |
| httpx / httpcore | `WARNING` | `app.jsonl` |
| uvicorn / FastAPI | `INFO`（access 摘要） | `app.jsonl`（单独 `logger=uvicorn.access`） |
| APScheduler | `INFO` | `app.jsonl` |
| Kuzu / Qdrant client | `WARNING` | `app.jsonl` |
| 根 logger | `WARNING` | `app.jsonl` |

**规则**：统一在 `lit_agent/logging.py` 用一次配置完成（dictConfig/structlog 配置 + 处理器），**禁止模块内 `print()` 与自行 `basicConfig`**；第三方日志默认降级，避免噪声淹没自有日志。

---

## 8. 优化用度量与慢点告警

**必埋指标**（写入 `metrics` + 超阈时附带 WARNING 日志）
| 指标 | 采集点 | 慢阈值（默认） |
|---|---|---|
| `stage_duration_ms` | 每 stage 进出 | > 60 s |
| `node_duration_ms` | 图节点 | > 45 s |
| `tool_duration_ms` | 工具调用 | > 30 s |
| `llm_latency_ms` / `llm_ttft_ms` | 网关 | > 30 s / > 10 s |
| `db_query_ms` | 仓储层 | > 500 ms |
| `vector_search_ms` | Qdrant | > 2 s |
| `graph_query_ms` | Kuzu | > 1 s |
| `context_fold_count` | Context 层 | > 10 次/run |
| `cache_hit_ratio` | 工具网关 | < 0.2（异常低） |
| `token_rate` / `cost_rate` | 计量 | 偏离基线 z-score > 3 |

**采样策略**：指标全量（轻量）；DEBUG 明细默认关闭，或按 `logging.debug_sampling: 0.1` 抽样；**慢点强制记录明细**（即使未开 debug）。
**告警（本地，无外部服务）**：`logs/errors.jsonl` 追加 `alert` 事件 + 事件表写 `metric{alert=...}`；UI 顶部提示（P4）；告警类型：连续失败 ≥3、成本超预算 80%/100%、磁盘水位、日志写入失败（自身健康）。

---

## 9. 查看与检索手册（日常调试命令）

```bash
# 1) 某 run 的完整时间线（日志）
jq -c 'select(.run_id=="p0-s5-001")' logs/app.jsonl | sort_by(.ts)

# 2) 只看错误（跨 run）
jq -c 'select(.level=="error") | {ts,run_id,stage,error_code,msg,retryable}' logs/errors.jsonl

# 3) 某错误码发生次数 Top
jq -r 'select(.error_code!=null) | .error_code' logs/app.jsonl | sort | uniq -c | sort -rn

# 4) 慢调用 Top10
jq -c 'select(.latency_ms!=null)' logs/app.jsonl | jq -s 'sort_by(-.latency_ms)[:10] | .[] | {ts,event,stage,tool,latency_ms}'

# 5) 每个 stage 耗时合计 / 次数
jq -r 'select(.event=="stage_finished") | "\(.stage) \(.latency_ms)"' logs/app.jsonl | awk '{s[$1]+=$2;c[$1]++} END{for(k in s) printf "%s avg=%.0fms n=%d\n",k,s[k]/c[k],c[k]}'

# 6) LLM 成本按模型汇总
jq -r 'select(.event=="llm_call_finished") | "\(.model) \(.cost_usd)"' logs/llm/*.jsonl | awk '{s[$1]+=$2} END{for(k in s) printf "%s %.4f USD\n",k,s[k]}'

# 7) 从事件跳到日志（拿 event_seq 再查）
jq -c 'select(.seq==42)' out/events.jsonl          # 或 SQLite: WHERE run_id=? AND seq=42
```
**调试标准动作**：① 看 `errors.jsonl` 定位错误码；② 按 `run_id` 拉时间线；③ 找该 `stage` 的守卫判决与恢复包；④ 需要细节 → 开 debug 模式重跑并导出 bundle（§6）。

---

## 10. 运维与用户反馈闭环

```
用户/自己报告问题
  → 导出 bundle（§6）
  → 归档到 bundles/<run_id>-<date>.zip 并登记（问题清单）
  → 三向定位：日志 → 事件 → 快照；确认根因分类（配置/数据/模型/守卫/框架）
  → 修复 + 新增回归用例（tests/regression，见 evaluation-plan J5）
  → 若属守卫阈值问题 → 走阈值标定流程（state-machine-and-guards §12）并写 ADR
```
**反馈条目模板**
```
[Problem] 现象：周报漏掉 X 方向的近期论文
[Run] run_id=p4-T1-2026w07, topic=T1
[Evidence] bundle: logs/bundles/p4-T1-2026w07-20260214.zip
[Root cause] 检索查询未包含新术语（scope 未更新）
[Fix] 更新 retrieve 提示词查询扩展 + 新术语进白名单
[Regression] tests/regression/test_t1_query_expansion.py
```
**规则**：每个修复必须留下"回归用例 + 对应文档更新"，避免同类问题复发。

---

## 11. 测试与验收

**单元测试**
- 字段完整性：必填字段缺失即测试失败；`error` 级日志必带 `error_code`；
- 脱敏：密钥/邮箱/路径/正文 四类样例全部被正确处理；
- 级别策略：info 不含正文字段（自动扫描长度阈值）；
- 轮转：写满阈值即生成归档；保留期删除逻辑正确；
- 关联：`event_seq`/`tool_call_id` 与事件表一致。

**集成测试**
- 一次 run 后：`logs/app.jsonl` 与 `out/events.jsonl` 可用 `run_id` 三向定位；
- 开 debug 模式跑：生成 `logs/debug/<run_id>/` 三文件且已脱敏，事件里出现 `debug_mode` 审计记录；
- bundle 导出：内容清单齐全、体积 ≤ 50 MB、打包前脱敏检查通过；
- 第三方日志：级别符合 §7（无 INFO 噪声）。

**验收指标（Phase 1 起纳入 DoD）**
- 100% 错误日志带 `error_code`；100% 外部调用双写（日志+事件）；
- info 及以上 0 处正文/密钥（CI 扫描）；
- 日志开销 < 3%（debug < 10%）；
- 任一历史 run 可在 5 分钟内完成"日志→事件→快照"定位。

---

## 12. 落地阶段与任务

| 阶段 | 内容 | 任务卡（建议） |
|---|---|---|
| **Phase 0** | 最小日志基线：`logging.py`、`logs/app.jsonl` 双写、字段照 §2.1、查看命令入 README ✅ **已交付（2026-10-05）** | `P0-LOG-01`（见 `phase0-implementation-steps.md` Step 0.3） |
| **P1** | 轮转/保留/容量、`errors.jsonl`、脱敏 processor、bundle 基础版、字段完整性测试 | `P1-LOG-01..03` |
| **P2** | 框架日志接管、慢点告警、debug 开关 + LLM 全量录制、日志健康自检 | `P2-LOG-01..03` |
| **P3** | 度量扩展（缓存命中/折叠次数/图查询）、性能基线对比 | `P3-LOG-01` |
| **P4** | 运维反馈闭环、归档与容量治理、UI 告警提示 | `P4-LOG-01..02` |
| P6 | 论文：可观测性设计章节 + 图表（延迟分布、错误分类统计） | — |

---

## 13. 关联文档

- 契约与落地位置：`implementation-guide.md` §1.4（日志规范）、§2.2（事件 schema）、§1.5（错误分类）、§13（I1–I4 映射）、§15.6（step 文档必备章节）；
- 最小基线步骤：`phase0-implementation-steps.md` Step 0.3；
- 事件与回放：`../design/architecture-overview.md` §3.7；
- 问题与解法：`../design/agent-design-decisions.md` H4（敏感信息）、I1–I4（可观测）；
- 守卫事件与阈值：`../design/state-machine-and-guards.md` §7/§12；
- 评测数据来源：`evaluation-plan.md` §5/§6。
