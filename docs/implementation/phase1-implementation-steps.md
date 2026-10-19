# Phase 1 实施步骤指导（完整系统搭建：全模块骨架 + 数据/接口/界面可用闭环）

> **文档定位**：本文件是 `implementation/implementation-guide.md` 的实施级指导，覆盖**项目 Phase 1**：
> 按 guide §1.1 的仓库布局，把**全部模块**（sources / parsing / db / stores / gateway / graph / agents /
> context / tools / runtime / api / eval / web）一次性建成**可运行、可测试、接口齐全的完整骨架**，
> 并把其中"数据层 → 三库 → 网关 → 运行时宿主 → 全量 API → 三界面"做到**真实可用**。
> 后续阶段在同一骨架上填深度，**不再改目录结构与契约**。
>
> **上游**：`implementation/implementation-guide.md`（冻结契约 §2、模块 §3–§12、阶段 §14、Wave §附录 A）、
> `design/state-machine-and-guards.md`（S0–S9 / E1–E13 / G1–G15）、`design/agent-design-decisions.md`、
> `implementation/phase0-implementation-steps.md` + `../prototype/RESULTS.md`（Phase 0 实测与 12 条静默错误）、
> `implementation/adr/0001`–`0003`。
> **下游**：`implementation/phase2-implementation-steps.md`（Harness 与多 Agent 深度；本文 §8 给交接与首张任务卡）。
> **引用约定**：文档引用相对 `docs/` 根；代码/路径相对**仓库根**。
> **版本**：v2.0（2026-10-19）。**v1.0 已废弃**——v1.0 把阶段目标定为"先给导师看 demo"（含 D0/D1 演示档、
> 静态页、录屏验收），与"直接搭建完整系统"的意图不符，本版已整体删除该路径；§0.2 记录全部变更。

---

## 0. 阶段定位与导读

### 0.1 一句话目标

> 一次性把**整个系统的骨架**按 guide §1.1 建起来：所有目录、所有模块、所有契约、所有接口都真实存在且可运行；
> 数据层（源→解析→去重→三库→重建对账）、网关层、运行时宿主、全量 REST/SSE、三界面**达到可用**；
> 其余模块（LangGraph 全边、守卫全集、多 Agent 深度、上下文折叠、周更、评测平台、MCP）以**真实接口 + 显式未实现**
> 的方式就位，后续阶段只填逻辑、不改结构。
>
> **这是"搭骨架"，不是"做演示"，也不是"做最小闭环"。** 判断标准是：新增一个模块时"文件该放哪、
> 接口长什么样、事件怎么发"都已经有答案，且答案在代码里而不在文档里。

### 0.2 相对 v1.0 的变更（差异登记）

| 变更 | v1.0（已废弃） | v2.0（本版） |
|---|---|---|
| 阶段目标 | 先跑通一条最窄的链路给导师看 | 全模块骨架一次建齐，结构冻结 |
| demo 路径 | D0 静态页 / D1 一键 demo / D2 周报 | **全部删除**（无 demo 档、无录屏验收、无静态页） |
| 模块范围 | 只到 sources/db/stores/gateway/runtime/api/web | **加 graph/agents/context/tools/eval 五层骨架** |
| 守卫与 Harness | 明确不做（全留 P2） | **state/pipeline/edges/guards/checkpoint 骨架就位**；判定全集留 Phase 2 |
| 三界面 | 只做 Topics + Report 两页 | **三界面骨架**（Topics/Report/Chat），Chat 以"未启用"态存在但路由/类型/组件齐全 |
| 调度 | 明确不做 | **APScheduler 装配但默认 disabled**，配置与接口就位 |
| 评测 | 明确不做 | **eval 地基**：5 项指标从事件算、数据集目录、回归基线机制；Judge 留 Phase 3 |
| 验收方式 | demo 录屏 + 手工清单 | **全自动**：单元/集成/契约/e2e + 指标快照 + 结构一致性检查 |
| 工期 | 16.5 d | **31.5 d（约 6–6.5 周，含并行与缓冲）** |

### 0.3 深度分层（本阶段最重要的概念）

每个模块在 Phase 1 交付四种深度之一，**禁止升级也禁止降级**（升级挤压后续阶段，降级破坏骨架完整性）：

| 标记 | 含义 | 验收要求 |
|---|---|---|
| **D-FULL** | 完整实现，功能可用 | 端到端跑通 + 集成测试 |
| **D-MIN** | 最小实现：功能存在、覆盖主路径、边界留后续 | 单测 + 至少 1 条真实路径集成测试 |
| **D-SKEL** | 骨架：契约/接口/注册位/测试齐全，核心逻辑 `NotImplementedError(code)` **显式**抛出 | 契约测试 + "未实现必须显式失败"测试 |
| **D-STUB** | 仅目录与 `__init__.py` 导出 | 导入测试 |

> **红线**：`D-SKEL` 不允许"返回空列表/悄悄跳过"（那是静默失败，Phase 0 的 12 条教训全是这一类）。
> 必须抛带错误码的异常，并由测试断言该异常确实抛出。

### 0.4 名义工期与关键路径

- **名义工期 31.5 个工作日**；前端（1.16）与运维/评测（1.17/1.18）并行时，日历约 **6 周**。
- **关键路径**：1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6/1.7 → 1.8 → 1.9 → 1.10 → 1.11 → 1.15 → 1.16。
- **可并行**：1.9（网关，依赖 1.2/1.3）可与 1.5–1.8 并行；1.12/1.13/1.14（agents/context/tools）与 1.10/1.11 并行；
  1.16（前端）在 1.15 的 `docs/api/openapi.json` 冻结后即可开工；1.18（评测）在 1.4 完成后即可开工。

### 0.5 开工前必须拍板的决策门（**DG-1/DG-2/DG-3 已定稿，完整清单见 §附录 E**）

| ID | 决策 | 状态 | 结论 | 阻塞 |
|---|---|---|---|---|
| **DG-1** | 向量来源与部署形态 | ✅ **已定**（ADR-0004） | Qdrant **local 嵌入式** + `BAAI/bge-m3`（**1024 维**，与 §2.6 契约一致）；备选 `bge-large-en-v1.5` 可热切换 | 1.5 |
| **DG-2** | 论文/作者/引文实体表 | ✅ **已定**（ADR-0005） | 新增 12 张表（含 `papers_raw`/`paper_chunks`/`embeddings`/`store_meta`），另有 12 张既有表做列修订（共 24 张）；`merged_ids_json` 与 `paper_merges` 并存 | 1.3 |
| **DG-3** | `run_events` 的 seq 与幂等键 | ✅ **已定**（ADR-0005 §5–§7） | `runs.next_seq` 事务内 `UPDATE ... RETURNING`；`(run_id,seq)` + 部分唯一 `(run_id,dedupe_key)`；幂等键总表逐资源定义 | 1.3/1.4 |
| **DG-4** | Chat 页在 Phase 1 的形态 | ⏳ 待定（1.15 前） | 页面+路由+类型+后端 501（`E_FEATURE_DISABLED`） | 1.15/1.16 |

---

## 1. 目标与出口标准

### 1.1 阶段目标（G1–G7）

| ID | 目标 | 可观测形式 |
|---|---|---|
| **G1 结构完整** | guide §1.1 的目录与文件**全部存在**，每模块有真实接口与测试入口 | `lit-agent doctor` 输出模块三态清单，无缺失；无空包 |
| **G2 数据闭环** | 源→解析→去重→三库→对账→重建全链路可用且幂等 | 同 fixture 重跑计数零增长；删库可重建且结果一致 |
| **G3 事件可回放** | 所有事实走事件，可整轮从 SQLite 回放 | `seq == 1..N`；回放序列 == 执行序列 |
| **G4 网关可信** | 单一出口 + 缓存可复现 + 敏感零出网 + 成本可见 | 缓存命中 $0；敏感零调用/零请求；`llm_calls` 与事件一致 |
| **G5 Harness 就位** | state/图构建器/边定义/守卫契约/checkpoint 全部可用（逻辑深度按矩阵） | 三节点冒烟图跑通；checkpoint 可读写；SKEL 有"显式失败"测试 |
| **G6 接口与界面完整** | guide §2.4 **全部路由**有契约与响应；三界面可运行 | OpenAPI 路径数 = 契约表行数；未启用功能 501 而非 404 |
| **G7 可评估** | 指标可从事件算，回归基线机制可跑 | `lit-agent eval metrics` 输出 5 项指标；`tests/regression` 可执行 |

### 1.2 出口标准（DoD，逐条可验）

| ID | 出口标准 | 判定方法（证据落点） |
|---|---|---|
| **D1** | **结构完整**：§3.1 目录树与职责表逐项存在 | `lit-agent doctor --strict` 退出码 0；`scripts/check_structure.py` |
| **D2** | 测试全绿：`pytest -q -m "not slow"` + ruff clean | 命令输出 + 用例数记录到 `RESULTS-P1.md` |
| **D3** | D-FULL/D-MIN 通过集成测试；**每个 D-SKEL 有"显式未实现"测试** | `tests/**/test_*_not_implemented.py` 断言 `NotImplementedError.code` |
| **D4** | 同 fixture 重跑**幂等**：三库计数零增长、报告字节一致 | `tests/integration/test_idempotency.py` + sha256 快照 |
| **D5** | 事件可回放：`seq` 连续无重号，回放序列 == 执行序列 | `tests/integration/test_events_replay.py` |
| **D6** | 三库可**全量重建**且对账一致 | `lit-agent stores rebuild --all --verify` |
| **D7** | **e2e 全链路**（自动化）：建 topic → run → 事件流 → 报告 → 三库可查 | `tests/e2e/test_full_system.py`（fake LLM，无网络） |
| **D8** | 成本与时长：单 run ≤ **$0.02**、≤ **5 min**（fixture 规模） | `llm_calls` 汇总 + run 起止 |
| **D9** | **失败可见**：源 4xx/429、坏 PDF、LLM 截断、预算超限、未实现模块调用 均有 `error` 事件与明确状态 | `tests/integration/test_failure_visibility.py`（6 类注入） |
| **D10** | 文档与交接：`RESULTS-P1.md`、guide 回写、Phase 2 首张任务卡 | 文档 review |

### 1.3 明确不做清单（**不实现逻辑**，但**必须有接口**）

1. LangGraph 的**全部条件边与回退策略**（只做主干的 builder + 边常量 + 路由表；重试/回退逻辑 Phase 2）。
2. 守卫**判定全集**与阈值标定（只实现 budget / no-progress 两个检测器）。
3. 看门狗的**主动取消**与协作式中断（只做超时检测与状态标记）。
4. 网关**熔断器**与复杂度分流（只留 `CircuitBreaker` Protocol + `NoopBreaker`）。
5. 多 Agent 的**真实协作拓扑**与角色间消息传递（只做 `Agent` Protocol + 6 角色类）。
6. 上下文**折叠策略全集**（只实现 `truncate`；`summarize`/`hierarchical` 抛未实现）。
7. 真实 **MCP 接入**（只做 `MCPAdapter` Protocol 与注册位）。
8. **Chat 问答**的检索与生成（页面/路由/类型就位，后端 501）。
9. **周更调度**的实际注册与执行（装配完成，`scheduler.enabled=false`）。
10. **评测**的 Judge/人工标注/gold 集（只做指标聚合与回归机制）。
11. 论文**删除/修订**语义、多用户鉴权、Docker/Redis/消息队列（guide 全局禁止）。
12. 非 OA 全文抓取与超大文件支持。

### 1.4 模块深度矩阵（本阶段的**范围合同**）

| 模块（guide §） | 深度 | Phase 1 交付内容 | 未实现部分如何显式存在 | 后续 |
|---|---|---|---|---|
| `config`（§1.3） | **D-FULL** | 全键配置、env 覆盖、`config_version`、目录准备 | — | — |
| `logging`（§1.4） | **D-FULL** | 结构化日志、脱敏、正文守卫、错误双写、轮转 | — | — |
| `errors`（§1.5） | **D-FULL** | 九段错误码 + `LitError` + 默认处置 + `E_FEATURE_DISABLED` | — | — |
| `models`（§2.3） | **D-FULL** | 全部契约（含 `merged_ids`、`GuardVerdict`、阶段 Result） | — | 新字段走 ADR |
| `db`（§2.1） | **D-FULL** | 全表 + Alembic + 仓储 + WAL/PRAGMA | — | — |
| `stores/*`（§2.5/2.6） | **D-FULL** | Kuzu + Qdrant + files + selftest + rebuild/verify | — | P4 加相似度边 |
| `sources`（§3） | **D-FULL** | OpenAlex + arXiv + 白名单 + 增量水位线 + 重试分类 | — | P4 加 cited_by |
| `parsing`（§3） | **D-FULL** | PDF 三级降级 + tiktoken 分块 + 稳定 chunk_id | — | P3 启 chunks 向量 |
| `gateway/llm+cache+metering`（§5） | **D-FULL** | 调用、缓存、截断检测、重试、计量、预算 | — | — |
| `gateway/policy`（§5） | **D-MIN** | 敏感度硬门 + `route_reason` + local 路线禁用 | 复杂度分流 → `E_FEATURE_DISABLED` | P2 |
| `gateway/breaker`（§5） | **D-SKEL** | `CircuitBreaker` Protocol + `NoopBreaker` + 注入点 | `NoopBreaker` 断言"不熔断" | P2 |
| `graph/state`（§6） | **D-FULL** | `AgentState` 冻结 + reducer + 大小约束 | — | 加字段走 ADR |
| `graph/pipeline`（§6） | **D-MIN** | builder + 节点注册 + checkpoint 接线 + 三节点冒烟 | 全边编排 → `E_FEATURE_DISABLED` | P2 |
| `graph/edges`（§6） | **D-SKEL** | E1–E13 常量 + 路由函数签名 + 主干路由 | 回退类路由抛未实现 | P2 |
| `graph/guards`（§6/§7） | **D-MIN** | `GuardVerdict` + `Guard` Protocol + budget/no-progress | 其余 4 类抛 `E_FEATURE_DISABLED` | P2 |
| `runtime/runner`（§13） | **D-MIN** | 单 run 生命周期 + 失败报告 + 锁 | 断点续跑 → `E_FEATURE_DISABLED` | P2 |
| `runtime/watchdog`（§13） | **D-SKEL** | 检测接口 + 超时标记 + 事件 | 主动取消 → 未实现 | P2 |
| `runtime/events`（§2.2） | **D-FULL** | 唯一入口 + 先落库后广播 + 回放 + JSONL 导出 | — | — |
| `runtime/scheduler`（§14） | **D-SKEL** | APScheduler 装配 + job 定义 + 默认 disabled | 实际注册执行 | P3 |
| `agents/*`（§7） | **D-SKEL**（reporter 为 D-MIN） | `Agent` Protocol + 6 角色 + 输入输出契约 | 各角色 `run()` 抛未实现（reporter 真实可用） | P3 |
| `context/budget`（§8） | **D-MIN** | token 预算 + 截断 | — | — |
| `context/folding`（§8） | **D-SKEL** | `FoldingStrategy` Protocol + `truncate` | `summarize`/`hierarchical` 未实现 | P3 |
| `context/slots`（§8） | **D-SKEL** | `CtxSlot` 契约 + 注册表 | 填充策略未实现 | P3 |
| `tools`（§9） | **D-SKEL**（3 builtin 为 D-MIN） | registry + `Tool` Protocol + 3 内置工具 | MCP 接入未实现 | P3 |
| `api`（§2.4） | **D-FULL** | 全部路由 + SSE + OpenAPI + 错误映射 | chat/graph 路由 501 | P3/P4 |
| `web`（§11） | **D-MIN** | 工程化 + 三页面 + 组件 + 类型生成 | Chat 页"未启用"态 | P3 |
| `eval`（§12） | **D-MIN** | 5 项指标从事件算 + 数据集目录 + 回归基线 | Judge/gold 集 | P3 |

**验收规则**：每个模块的"未实现部分"必须有**可断言的显式失败**（`NotImplementedError(code=...)` 或
`E_FEATURE_DISABLED` 事件），且 `lit-agent doctor` 能列出"已实现 / 骨架 / 未启用"三态清单。
**禁止**用"返回空结果"伪装完成。

---

## 2. 全局约定

### 2.1 代码位置与单向依赖

- 正式代码 `src/lit_agent/`（可安装包）、测试 `tests/`、运维脚本 `scripts/`、前端 `web/`、迁移 `migrations/`。
- `prototype/` 为 Phase 0 实验区：**只读复用**，迁完即删（§3.5 映射表全绿后）。
- **依赖方向**：`models` ← 所有层；`db`/`stores`/`gateway`/`sources`/`parsing` 互不依赖；`graph` 可依赖以上；
  `agents`/`context`/`tools` 可依赖 `gateway`/`stores`；`runtime` 可依赖全部；`api` 只依赖 `runtime`/`db`/`stores`；
  `eval` 只读（db/stores/events）。**禁止反向依赖**，`lit-agent doctor` 检查循环导入。
- **不变量**：SQLite 是唯一真相源；Kuzu/Qdrant/files 是派生物，任何时刻可"删除并从 SQLite 重建"。

### 2.2 环境初始化

```powershell
uv sync
uv run lit-agent doctor            # 结构/依赖/路径/三库/配置/版本 六类自检
uv run lit-agent doctor --strict   # 结构缺项即失败（D1 用）
uv run pytest -q                   # 基线（Phase 0 迁移用例 + 新增）
```

- 密钥只从 env 读；`.env` 不入库；`DEEPSEEK_API_KEY` 缺失时除 LLM 相关外全部可跑。
- `data/` 必须纯 ASCII 绝对路径（Kuzu 约束，ADR-0003），启动即校验。
- Windows/pwsh：不依赖 `make`；长命令封装为 `scripts/*.ps1`。

### 2.3 每个任务的标准动作

1. 读 guide 对应 §，只改任务卡列出的文件（§附录 C）。
2. 先写测试后写实现；`D-SKEL` 的测试必须断言"显式失败"而不是"没崩"。
3. 不得改冻结契约、不得加 guide §1.2 之外的依赖；契约不足 → 出 ADR 草稿。
4. 完成后贴出：`ruff check` + `ruff format --check` + 相关 `pytest` + `lit-agent doctor`。
5. 回写本文 §5 与 `docs/implementation/RESULTS-P1.md`（实测值 + 证据路径）。

### 2.4 埋点要求（强制）

- **双写**：所有外部调用（源 API / LLM / DB 批量写 / PDF / 工具调用）→ 日志 + `run_events`，
  关联键 `run_id + stage + step_key`。
- **唯一入口** `runtime/events.py::emit_event()`；业务代码禁止用日志记录"事实"（Phase 0 #5/#6 的根因）。
- 事件必填：`run_id, seq, ts(UTC+tz), type, stage, severity, payload, schema_version`；`seq` 事务内单调。
- 类型白名单：`phase_change | tool_call | llm_call | guard_trigger | recovery | message | error | metric | report_written`。
- **先落库后广播**；SSE 只是通知。
- **指标事实必须是事件**（ADR-0002）：去重率、缓存命中、截断、预算、守卫触发、检索命中率、解析成功率一律先落事件。
- **未启用功能**也必须发事件（`error` + `E_FEATURE_DISABLED`），否则前端与评测看不到"为什么没有"。

### 2.5 记录模板

```markdown
### Step 1.x <标题>（YYYY-MM-DD，耗时 x.x d）
- 深度：<D-FULL / D-MIN / D-SKEL>
- 命令：`uv run pytest -q tests/integration/test_xxx.py -m "not slow"`
- 输出：<关键行>
- 实测值：<papers_new=0 / p95=155ms / cost=$0.006294 / 用例数=NN>
- 证据：`docs/implementation/RESULTS-P1.md#step-1x`、`logs/runs/<run_id>.jsonl`
- 偏差：<与预期不符；无则写"无">
- 结论：<是否达出口标准；条件通过时写明条件>
```

`docs/implementation/RESULTS-P1.md` 是 Phase 1 **唯一数字来源**；其他文档引用须注明其小节，禁止二次抄写。

### 2.6 提交粒度（git 操作由人工执行）

```
step1.<n>: <一句话>

- 深度：<D-FULL/D-MIN/D-SKEL>
- 交付：<文件/表/接口>
- 验收：ruff clean; pytest -q -m "not slow" (<n> passed); lit-agent doctor
- 实测：<关键数字>
- 关联：implementation/phase1-implementation-steps.md §Step 1.<n>
```

### 2.7 命名与编码约定

| 对象 | 约定 |
|---|---|
| 表/列 | `snake_case`，复数表名（`run_events.seq`） |
| 事件 `type` | 只用 §2.4 白名单 |
| 阶段名 `stage` | 与 design 阶段表一致：`intake/scope/retrieval/parse/normalize/mapping/analysis/report/persist/evaluate` |
| 时间 | UTC 存储，`Asia/Singapore` 展示 |
| 幂等键 | `(run_id, stage, step_key)` |
| 未实现错误码 | `E_FEATURE_DISABLED`（附 `feature=<模块名>`，禁止空 message） |
| 模型/枚举 | 跨模块只用 `models/` 类型，禁止裸 dict |
| 文件路径 | `data/` 纯 ASCII；`data/papers/<canonical_id>.pdf` |

### 2.8 红线（guide §15.5 十条 + Phase 1 追加四条）

1–10 沿用 guide §15.5（裸 dict / 提示词塞业务约束 / LLM 做确定性校验 / 先广播后落库 / 图向量不 MERGE /
漏埋点 / 未批准依赖 / 改契约不提 ADR / 日志事件含密钥或敏感原文 / 失败静默）。

Phase 1 追加：
11. **禁止** `D-SKEL` 返回空值/空列表冒充完成；必须抛 `NotImplementedError(code=...)` 且有测试断言。
12. **禁止**用 `shutil.rmtree()` 清理 Kuzu 路径（它是文件；Phase 0 曾因 `ignore_errors=True` 静默失败，ADR-0003）。
13. **禁止**把 Kuzu/Qdrant 当真相源（先写图再写 SQLite = 返工）。
14. **禁止**新增未在 guide §1.1 的顶层目录（如需要 → 记入 §8.4 差异登记 + ADR）。

---

## 3. 文件结构与职责

### 3.1 Phase 1 结束时的完整目录树

> 标记：`[F]` D-FULL、`[M]` D-MIN、`[S]` D-SKEL、`[·]` 仅导出。
> **本树即 Phase 1 的结构冻结基线**：后续阶段只在标注位置的实现内填逻辑，不改结构。

```
agent/
├─ pyproject.toml  uv.lock  .env.example  README.md  .gitignore  .python-version
├─ alembic.ini
├─ config/
│  ├─ config.example.yaml          # 全键（guide §1.3 + topics/seeds）
│  ├─ seeds/topics.yaml            # 示例 topic
│  └─ config.yaml                  # gitignored
├─ migrations/{env.py, versions/0001_initial.py}
├─ src/lit_agent/
│  ├─ __init__.py  __main__.py  _version.py  py.typed  cli.py  doctor.py
│  ├─ config.py [F]   logging.py [F]   errors.py [F]   selftest.py [M]
│  ├─ models/
│  │  ├─ __init__.py
│  │  ├─ paper.py [F]  author.py [F]  topic.py [F]  run.py [F]  event.py [F]
│  │  ├─ claim.py [F]  evidence.py [F]  report.py [F]  verdict.py [F]
│  │  └─ results.py [F]        # StageResult / RetrievalResult / MappingResult / AnalysisResult / ReportDraft
│  ├─ db/
│  │  ├─ base.py [F]  session.py [F]  tables.py [F]
│  │  └─ repo/{papers,authors,citations,topics,runs,events,reports,claims,chunks,sync,llm_calls,locks}.py [F]
│  ├─ stores/{files.py,graph.py,vector.py,selftest.py,rebuild.py} [F]
│  ├─ sources/{base.py,openalex.py,arxiv.py,whitelist.py,normalize.py,dedup.py,sync.py} [F]
│  ├─ parsing/{pdf.py,chunking.py,pipeline.py} [F]
│  ├─ gateway/{llm.py,cache.py,metering.py} [F] + {policy.py} [M] + {breaker.py} [S]
│  ├─ graph/{state.py [F], pipeline.py [M], edges.py [S], guards.py [M], checkpoint.py [M]}
│  ├─ agents/{base.py [S], retrieval.py [S], mapper.py [S], analyst.py [S],
│  │          reporter.py [M], critic.py [S], chat.py [S]}
│  ├─ context/{budget.py [M], folding.py [S], slots.py [S]}
│  ├─ tools/{registry.py [M], mcp_adapter.py [S], builtin/{openalex_search.py,paper_pdf.py,kv_cache.py} [M]}
│  ├─ runtime/{events.py [F], runner.py [M], jobs.py [M], budget.py [M], watchdog.py [S], scheduler.py [S]}
│  ├─ api/{app.py, schemas.py, sse.py, dependencies.py} [F]
│  ├─ api/routes/{topics,runs,reports,chat,graph,metrics,sources,health}.py [F]（chat/graph 返回 501）
│  └─ eval/{metrics.py [M], export.py [M], datasets.py [S], grounding.py [S], judge.py [S], faultinject.py [S]}
├─ tests/
│  ├─ unit/  integration/  e2e/  regression/  contract/
│  └─ fixtures/{openalex,pdf,llm,tools}/
├─ scripts/{doctor.ps1, selfcheck.ps1, check_structure.py, seed_topics.py, rebuild_stores.py, run_topic.py}
├─ web/
│  ├─ package.json  vite.config.ts  tsconfig.json  index.html  .env.example
│  └─ src/
│     ├─ main.ts  App.vue  router/index.ts
│     ├─ api/{client.ts, types.gen.ts, sse.ts}
│     ├─ stores/{topics.ts, run.ts, report.ts}
│     ├─ layouts/DefaultLayout.vue
│     ├─ views/{Topics.vue, Report.vue, Chat.vue}
│     └─ components/{EventStream.vue, StageProgress.vue, ClaimEvidence.vue, ReportBody.vue,
│                   TopicForm.vue, RunList.vue, FeatureDisabled.vue}
├─ docs/
│  ├─ implementation/phase1-implementation-steps.md      # 本文件
│  ├─ implementation/RESULTS-P1.md
│  ├─ implementation/adr/{0004-*.md, 0005-*.md}
│  └─ api/openapi.json
├─ data/    # gitignored
├─ logs/    # gitignored
└─ prototype/   # Phase 0；迁完删除
```

### 3.2 文件职责表

> 列义：**功能责任 / 关键接口或内容 / 输入→输出 / 依赖 / 归属步骤 / 下一阶段归属**。
> 「下一阶段归属」是 Phase 2 起判断"保留 / 升级 / 丢弃"的依据。

**A. 工程基座与配置**

| 路径 | 功能责任 | 关键接口或内容 | 输入 → 输出 | 依赖 | 归属 | 下一阶段 |
|---|---|---|---|---|---|---|
| `pyproject.toml` | 依赖与工具 | guide §1.2 依赖；`[project.scripts] lit-agent`；ruff/pytest；`pythonpath=["src"]` | — | uv | 1.1 | 沿用 |
| `cli.py` | 单一 CLI 入口 | `doctor/db/stores/sources/run-topic/llm/api/eval/schedule` | argv → 退出码 | 全 | 1.1 | 升级（P2 注入命令） |
| `doctor.py` | 自检编排 | `run_doctor(strict, json)`：结构/依赖/路径/三库/配置/版本；模块三态清单 | — → 报告 | 1.1 | 1.1 | 沿用（加守卫自检） |
| `config.py` | 配置加载 | `load_settings()`、`Settings`（冻结）、`config_version`、`ensure_dirs()` | YAML+env → `Settings` | pydantic-settings | 1.1 | 升级（guards 实参） |
| `logging.py` | 结构化日志 | `setup_logging()`、`bind_context()`、`validate_no_bodies()`、轮转/保留 | 调用 → `logs/app.jsonl` | structlog | 1.1 | 沿用 |
| `errors.py` | 错误分类学 | 九段常量 + `LitError` + `DEFAULT_ACTION` + `E_FEATURE_DISABLED` | 异常 → 结构对象 | — | 1.1 | 升级（`E_GUARD_*` 处置） |
| `scripts/check_structure.py` | 结构一致性（D1） | 比对 §3.1 清单 → 缺失/多余 | 仓库 → 报告 | — | 1.1 | 沿用 |
| `scripts/{doctor,selfcheck}.ps1` | 一键自检 | 包装 `lit-agent doctor` | — | 1.1 | 1.1 | 沿用 |

**B. 契约模型（`models/`）**

| 路径 | 功能责任 | 关键接口或内容 | 输入 → 输出 | 依赖 | 归属 | 下一阶段 |
|---|---|---|---|---|---|---|
| `models/paper.py` | `Paper` | `paper_id,title,abstract,authors,venue,year,published_at,updated_at,source,references,oa_pdf_url,merged_ids`；主记录排序键 | dict → `Paper` | pydantic | 1.2 | 沿用 |
| `models/author.py` `evidence.py` `claim.py` | `Author/EvidenceCard/Claim` | `Claim{text,citations[],support}` + 证据规则 | dict → 模型 | pydantic | 1.2 | 沿用 |
| `models/topic.py` | `Topic` | `scope_statement`（唯一来源）、`scope_keywords`、`seed_queries`、`sources[]`、`status` | dict → `Topic` | pydantic | 1.2 | P4 加调度字段 |
| `models/run.py` `event.py` | `Run` + `Event` | `RunState`；`EventType` 白名单；`Event.seq` | dict → 模型 | pydantic | 1.2 | 加守卫事件 |
| `models/verdict.py` | `GuardVerdict`（冻结） | `ok,severity,action,code,reasons[]`；`GuardSeverity=info/warn/block`；`GuardAction=continue/retry/degrade/replan/abort/annotate` | 观测 → 判决 | pydantic | 1.2 | P2 用满 |
| `models/report.py` `results.py` | `Report` + 阶段产物 | `RetrievalResult/MappingResult/AnalysisResult/ReportDraft/StageResult/RunContext` | 模型 → 模型 | pydantic | 1.2 | 沿用 |

**C. 数据库（`db/`、`migrations/`）**

| 路径 | 功能责任 | 关键接口或内容 | 输入 → 输出 | 依赖 | 归属 | 下一阶段 |
|---|---|---|---|---|---|---|
| `db/base.py` `db/session.py` | engine/session/PRAGMA | WAL、`foreign_keys=ON`、`busy_timeout`、`session_scope()` | 路径 → engine | SQLAlchemy 2 | 1.3 | 沿用 |
| `db/tables.py` | 全表 DDL | §2.1 全表 + `paper_merges`(ADR-0001) + 实体表(ADR-0005) + `llm_cache` + `papers_raw` + `paper_chunks`(P3 启) | — | SQLAlchemy | 1.3 | P3 启 chunks |
| `db/repo/*.py` | 幂等仓储（唯一写入口） | `upsert_many()`、`counts()`、`next_seq()`、`append_event()`、`read_events()`、`set_cursor()` | 模型 → 行 | 1.3 | 1.3 | 沿用 |
| `migrations/versions/0001_initial.py` | 初始迁移 | 全表 + 索引 | — → schema | alembic | 1.3 | 每阶段加版本 |

**D. 存储（`stores/`）**

| 路径 | 功能责任 | 关键接口或内容 | 输入 → 输出 | 依赖 | 归属 | 下一阶段 |
|---|---|---|---|---|---|---|
| `stores/files.py` | 论文文件管理 | `paper_path()`、`save_pdf()`（大小/ASCII/限速）、`prune()` | 字节 → `data/papers/*` | 1.3 | 1.5 | P3 加 chunk 正文 |
| `stores/graph.py` | Kuzu 图（MERGE） | `upsert_papers/authors/venues/topics/citations()`、`counts()`、`neighbors()`、`close()` | 模型 → 图 | kuzu | 1.5 | P4 加 `SIMILAR_TO` |
| `stores/vector.py` | Qdrant collection | `ensure_collections()`（`papers` 1024/Cosine/§2.6 payload）、`upsert()`、`search(filters)` | 向量 → 点 | qdrant-client | 1.5 | P3 加 `chunks` |
| `stores/selftest.py` | 存储自检（ADR-0003） | `assert_ascii_path()`、`store_is_empty()`（`E_STORE_NOT_EMPTY`）、`check_columns()`（`E_STORE_SCHEMA_MISMATCH`）、`path_size_mb()`（close 后）、`reset_store_path()` | 路径 → 通过/错误码 | 1.3 | 1.5 | 沿用 |
| `stores/rebuild.py` | 重建与对账 | `rebuild_graph/vector()`、`verify_counts()`、差异样例、`E_DATA_SYNC` | SQLite → 派生物 | 1.5 | 1.5/1.8 | 沿用（P5 复现） |

**E. 采集与解析（`sources/`、`parsing/`）**

| 路径 | 功能责任 | 关键接口或内容 | 输入 → 输出 | 依赖 | 归属 | 下一阶段 |
|---|---|---|---|---|---|---|
| `sources/base.py` | `SourceAdapter` 协议 | `fetch(since, selector)`、`health()`、`SourceRecord` | 游标 → 记录流 | httpx | 1.6 | P4 加 cited_by |
| `sources/openalex.py` | OpenAlex 适配 | 礼貌池、`cursor=*` 深分页、`from_publication_date` 水位线、429/5xx 退避、日期过滤 | 游标 → 记录 | httpx | 1.6 | 沿用 |
| `sources/arxiv.py` | arXiv 补充源 | 按 `sources.arxiv.categories` | 配置 → 记录 | arxiv | 1.6 | 沿用 |
| `sources/whitelist.py` | 白名单（**source.id**） | `resolve_venues()`、`is_whitelisted()`、离线缓存 | 配置 → 判定 | 1.6 | 1.6 | 沿用 |
| `sources/normalize.py` | 归一化/id 规范化 | `canonical_id()`（DOI→W→arXiv→指纹）、`openalex_work_to_paper()`、`_w_to_canonical()` | 记录 → `Paper` | pydantic | 1.6 | 沿用 |
| `sources/dedup.py` | 三段式去重 | `dedup_papers()`、`merge_relations()`、确定性主记录 | `Paper[]` → 主记录+合并对 | 1.6 | 1.8 | P4 加相似度去重 |
| `parsing/pdf.py` | PDF 抽取 | `download_oa()`、`extract_text()`（PyMuPDF→pdfplumber→failed） | URL → 文本+质量 | pymupdf/pdfplumber | 1.7 | 沿用 |
| `parsing/chunking.py` | 分块 | `count_tokens()`(tiktoken)、`chunk_text()`（预算+句界+overlap）、稳定 `chunk_id` | 文本 → `Chunk[]` | tiktoken | 1.7 | P3 用于向量 |
| `parsing/pipeline.py` | 解析编排 | `parse_papers()` + `parse_status` + 事件 | id 列表 → `ParsedDoc[]` | 1.7 | 1.7 | 沿用 |

**F. 网关（`gateway/`）**

| 路径 | 功能责任 | 关键接口或内容 | 输入 → 输出 | 依赖 | 归属 | 下一阶段 |
|---|---|---|---|---|---|---|
| `gateway/llm.py` | LLM 调用 | `chat()`、`chat_json()`、超时/退避、截断检测、JSON 校验 | 消息 → `LLMCall` | litellm | 1.9 | P2 接熔断 |
| `gateway/cache.py` | 内容寻址缓存 | 键=sha256(model+messages+temp+max_tokens+schema_ver) → `llm_cache` | 请求 → 命中/未命中 | 1.3 | 1.9 | 沿用 |
| `gateway/metering.py` | 计量 | `llm_calls` 写入、run 成本累计、80/100 预算事件、usage 缺失估算 | 调用 → 行+事件 | 1.3 | 1.9 | P3 接指标 |
| `gateway/policy.py` | 路由与敏感硬门 | `decide()`：strict 敏感→拒绝零出网；`route_reason`；local→`E_FEATURE_DISABLED` | 请求 → 决策 | 1.9 | 1.9 | P2 加分流 |
| `gateway/breaker.py` | 熔断接口 | `CircuitBreaker` Protocol、`NoopBreaker`、调用注入点 | 调用 → 结果 | 1.9 | 1.9 | **P2 真熔断** |

**G. Harness（`graph/`、`runtime/`）**

| 路径 | 功能责任 | 关键接口或内容 | 输入 → 输出 | 依赖 | 归属 | 下一阶段 |
|---|---|---|---|---|---|---|
| `graph/state.py` | 状态契约（冻结） | `AgentState`（TypedDict + reducer）、`STATE_SCHEMA_VERSION`、大小上限、不可序列化隔离 | — → state | langgraph | 1.10 | 加字段走 ADR |
| `graph/pipeline.py` | 图构建器 | `build_graph()`、`register_node()`、`smoke_graph()`（intake→retrieve→draft）；全边编排抛 `E_FEATURE_DISABLED` | state → 图 | langgraph | 1.10 | **P2 全边** |
| `graph/edges.py` | 边定义 | `E1–E13` 常量、`EdgeCondition`、主干路由表 | state → 下一节点 | 1.10 | 1.10 | **P2 回退逻辑** |
| `graph/checkpoint.py` | checkpoint 接线 | `open_checkpointer()`（sqlite）、`thread_id=run_id`、`resume(None)` 包装 | 配置 → saver | checkpoint-sqlite | 1.10 | P2 续跑 |
| `graph/guards.py` | 守卫 | `GuardVerdict`、`Guard` Protocol、`BudgetGuard`、`NoProgressGuard`、`GuardRail.run()` | 观测 → 判决 | 1.2 | 1.11 | **P2 六类全集** |
| `runtime/events.py` | 事件唯一入口 | `emit_event()`、`replay()`、JSONL 导出、`EventSink` 协议 | 事实 → 行+日志+广播 | 1.3 | 1.4 | 沿用 |
| `runtime/runner.py` | run 编排 | `start_run()`（线性）+ 预算检查 + 失败报告；`resume()` 抛未实现 | topic → run | 1.10/1.11 | 1.11 | **P2 换图执行** |
| `runtime/jobs.py` | 生命周期与锁 | `job_locks` 互斥、状态流转、`cleanup_orphans()`、`fail_with_report()` | 请求 → 状态 | 1.3 | 1.11 | P2 看门狗联动 |
| `runtime/budget.py` | 预算 | tokens/cost/时长 80/100 两档 | 用量 → verdict | 1.9 | 1.11 | P2 并入 guards |
| `runtime/watchdog.py` | 看门狗 | `scan()`（无事件超时→`guard_trigger`）；取消接口留空 | 时间 → 事件 | 1.11 | 1.11 | **P2 主动取消** |
| `runtime/scheduler.py` | 调度装配 | `build_scheduler()`、`weekly_job()`、`enabled=false` 默认不注册 | 配置 → scheduler | apscheduler | 1.17 | **P3 实跑** |

**H. Agent / 上下文 / 工具**

| 路径 | 功能责任 | 关键接口或内容 | 输入 → 输出 | 依赖 | 归属 | 下一阶段 |
|---|---|---|---|---|---|---|
| `agents/base.py` | Agent 协议 | `Agent` Protocol（`name/inputs/outputs/run(ctx)`）、`AgentResult` | ctx → 结果 | 1.2 | 1.12 | P3 扩展协作 |
| `agents/{retrieval,mapper,analyst,critic,chat}.py` | 角色骨架 | 声明 inputs/outputs；`run()` 抛 `E_FEATURE_DISABLED` | ctx → 结果 | 1.12 | 1.12 | **P3 实现** |
| `agents/reporter.py` | 报告生成（可用） | 证据卡 → claims（必带 citations，回查校验）→ 确定性 Markdown | 证据 → `Report` | 1.9 | 1.12 | P3 升级 |
| `context/budget.py` | 上下文预算 | `TokenBudget.fit()`、截断、超限事件 | 文本+预算 → 文本 | tiktoken | 1.13 | 沿用 |
| `context/folding.py` | 折叠策略 | `FoldingStrategy` Protocol + `TruncateFolding` | 文本 → 文本 | 1.13 | 1.13 | **P3 多策略** |
| `context/slots.py` | 上下文槽 | `CtxSlot` 契约 + `SlotRegistry` | 注册 → 槽 | 1.13 | 1.13 | **P3 填充** |
| `tools/registry.py` | 工具注册表 | `Tool` Protocol（`name/params_schema/run/validate`）、`Registry` | 工具 → 注册 | 1.2 | 1.14 | P3 加权限 |
| `tools/builtin/*.py` | 内置工具 | `openalex_search`、`paper_pdf`、`kv_cache`（真实可用） | 参数 → 结果 | 1.6/1.5 | 1.14 | P3 扩展 |
| `tools/mcp_adapter.py` | MCP 适配 | `MCPAdapter` Protocol + 注册位 | — | 1.14 | 1.14 | **P3 接 MCP** |

**I. 接口（`api/`）**

| 路径 | 功能责任 | 关键接口或内容 | 输入 → 输出 | 依赖 | 归属 | 下一阶段 |
|---|---|---|---|---|---|---|
| `api/app.py` | 应用装配 | 路由挂载、异常→HTTP、启动钩子、CORS | — | 1.15 | 1.15 | 沿用 |
| `api/schemas.py` | API 契约 | 复用 `models/`（不重复定义）+ 分页/错误包 | 模型 → JSON | 1.2 | 1.15 | 沿用 |
| `api/dependencies.py` | 依赖注入 | `get_session/get_settings/get_runner` | — | 1.15 | 1.15 | 沿用 |
| `api/routes/topics.py` | topic CRUD + 触发 | §2.4 topic 全路由；并发→409 `E_LOCK_HELD` | 请求 → JSON | 1.11 | 1.15 | 沿用 |
| `api/routes/runs.py` | run 与事件 | 详情/历史/事件分页（`after_seq`）/报告/claims | 请求 → JSON | 1.4 | 1.15 | 沿用 |
| `api/routes/{reports,sources,metrics,health}.py` | 报告/源/指标/健康 | §2.4 对应路由 | 请求 → JSON | 1.5/1.18 | 1.15 | 升级（P5 指标） |
| `api/routes/{chat,graph}.py` | 未启用功能 | 契约完整，返回 501 + `E_FEATURE_DISABLED` | 请求 → 501 | 1.15 | 1.15 | **P3/P4 实现** |
| `api/sse.py` | SSE | `stream(run_id, after_seq)`、`Last-Event-ID`、心跳 15s、结束事件 | 订阅 → `text/event-stream` | 1.4 | 1.15 | P3 复用于 Chat |
| `docs/api/openapi.json` | 契约快照 | `lit-agent api export-openapi` | app → JSON | 1.15 | 1.15 | 沿用 |

**J. 前端（`web/`）**

| 路径 | 功能责任 | 关键接口或内容 | 输入 → 输出 | 依赖 | 归属 | 下一阶段 |
|---|---|---|---|---|---|---|
| `web/{package.json,vite.config.ts,tsconfig.json}` | 工程化 | Vue3+TS+Vite+Element Plus；`/api` 代理；`vue-tsc` 类型检查 | — | node | 1.16 | 沿用 |
| `web/src/api/client.ts` | API 客户端 | §2.4 全路由封装 + 错误码提示 + 分页 | 请求 → 数据 | 1.15 | 1.16 | 沿用 |
| `web/src/api/types.gen.ts` | 类型（生成） | 由 `docs/api/openapi.json` 生成（`openapi-typescript`） | openapi → TS | 1.15 | 1.16 | 沿用 |
| `web/src/api/sse.ts` | SSE 客户端 | `EventSource` + `after_seq` 续传 + 重连退避 | — → 事件回调 | 1.15 | 1.16 | 沿用 |
| `web/src/router/index.ts` `layouts/DefaultLayout.vue` | 路由与布局 | `/topics`、`/report/:runId`、`/chat` | — | 1.16 | 1.16 | P3 加会话路由 |
| `web/src/views/Topics.vue` | topic 管理 | 列表/新建/触发/运行历史 + 阶段进度 | 操作 → run | 1.16 | 1.16 | P4 加调度 |
| `web/src/views/Report.vue` | 报告页 | 报告渲染 + claims 表 + 证据卡 + run 元信息 | run → 页面 | 1.16 | 1.16 | P4 加网络图 |
| `web/src/views/Chat.vue` | Chat 页（未启用） | 布局与输入就位，显示 `FeatureDisabled` + 后端 501 说明 | — | 1.16 | 1.16 | **P3 实现** |
| `web/src/components/*.vue` | 复用组件 | `EventStream/StageProgress/ClaimEvidence/ReportBody/TopicForm/RunList/FeatureDisabled` | props → UI | 1.16 | 1.16 | 沿用 |
| `web/src/stores/*.ts` | 状态 | pinia：topics/run/report | — | 1.16 | 1.16 | 沿用 |

**K. 评测（`eval/`）**

| 路径 | 功能责任 | 关键接口或内容 | 输入 → 输出 | 依赖 | 归属 | 下一阶段 |
|---|---|---|---|---|---|---|
| `eval/metrics.py` | 指标聚合 | 5 项（grounding/幻觉/引用覆盖/去重率/成本）+ TPR/FPR + campaign 作用域 | 事件 → 指标 | 1.4 | 1.18 | P3 扩指标 |
| `eval/export.py` | 导出 | CSV/JSON/汇总 md | 指标 → 文件 | 1.18 | 1.18 | 沿用 |
| `eval/datasets.py` | 数据集骨架 | `eval_data/<topic>/` 约定 + 加载器 | 目录 → 样本 | 1.18 | 1.18 | **P3 gold 集** |
| `eval/{grounding,judge}.py` | 判分骨架 | `GroundingChecker`/`Judge` Protocol | — | 1.18 | 1.18 | **P3 实现** |
| `eval/faultinject.py` | 注入骨架 | 6 类注入定义（未实现） | — | 1.18 | 1.18 | **P2 实现** |

**L. 测试、脚本与文档**

| 路径 | 功能责任 | 关键接口或内容 | 输入 → 输出 | 依赖 | 归属 | 下一阶段 |
|---|---|---|---|---|---|---|
| `tests/unit/*` | 离线逻辑测试 | Phase 0 迁移的 112 例 + 各层新增 | — | — | 全程 | 沿用 |
| `tests/integration/*` | 真库集成 | migrations/repo/events/graph/vector/projection/openalex/gateway/runner/idempotency/api/sse | — | 1.3–1.15 | 全程 | 沿用 |
| `tests/contract/*` | 契约一致性 | 模型↔表↔OpenAPI 三方一致；E1–E13 与 design 一致 | — | 1.2/1.10/1.15 | 1.15 | 沿用 |
| `tests/e2e/test_full_system.py` | 全链路（D7） | fake LLM + 真三库：建 topic→run→事件→报告→查询 | — | 1.16 | 1.16 | 沿用 |
| `tests/regression/*` | 回归机制 | golden run 快照；提示词/阈值变更必跑 | — | 1.18 | 1.18 | P3 扩 |
| `tests/fixtures/*` | 离线样本 | 源响应/坏 PDF/录制 LLM/工具返回 | — | — | 1.5–1.16 | 沿用 |
| `scripts/{run_topic,seed_topics,rebuild_stores}.py` | 运维脚本 | 命令行包装（不承载业务逻辑） | — | 1.11 | 1.11 | 沿用 |
| `docs/implementation/RESULTS-P1.md` | **唯一数字来源** | 摘要/各步实测/静默错误/决策门 | — | 全程 | 全程 | 升级为 Phase 2 输入 |
| `docs/implementation/adr/{0004,0005}-*.md` | 决策产物 | 向量来源 / 实体表+事件键 | — | — | 1.5/1.3 | 冻结 |

### 3.3 文件边界与命名约定

1. **单文件单责任**：仓储不含业务判定；阶段/节点函数不写 SQL；`stores/` 不 import `runtime/`。
2. **写路径唯一**：SQLite→`db/repo/*`；Kuzu→`stores/graph.py`；Qdrant→`stores/vector.py`；事件→`runtime/events.py`。
3. **契约即类型**：跨模块参数/返回只用 `models/` 类型（`payload` 除外）。
4. **节点函数签名统一**：`(ctx: RunContext) -> StageResult`；编排（重试/跳转/回退）只能写在 `graph/` 与 `runtime/`。
5. **未实现必须自证**：`D-SKEL` 文件顶部 `# SKELETON: Phase 2 实现 <feature>`，并导出 `FEATURE = "<name>"` 供测试断言。
6. **命名**：`stage_*`/`node_*`（执行）、`upsert_*/count_*/get_*/list_*`（仓储）、`ensure_*/assert_*/verify_*`（自检）、
   `*Guard/*Strategy/*Adapter/*Protocol`（扩展点）。

### 3.4 结构冻结与扩展规则

- §3.1 在 Phase 1 收口时**冻结**：后续新增文件必须在 §8.4 差异登记，不得新增顶层目录。
- 职责表的「下一阶段」列决定后续动作：`沿用`（不动）、`升级`（改内部不改接口）、`P2/P3 实现`（填 SKELETON）。

### 3.5 `prototype/` → `src/` 搬迁映射

| prototype 资产 | 迁往 | 处置 |
|---|---|---|
| `config.py` | `config.py` | 扩展全键 |
| `models.py` | `models/*`（拆 9 文件） | + `merged_ids`/`GuardVerdict`/`results` |
| `logging.py` | `logging.py` | 原样 |
| `eventlog.py` | `runtime/events.py` + `db/repo/events.py` | JSONL → SQLite（保留导出） |
| `stores.py` | `db/repo/*` + `stores/*` | 拆分 |
| `normalize.py` | `sources/normalize.py` | 原样（含 `_w_to_canonical`） |
| `chunking.py` | `parsing/{chunking,pdf}.py` | 拆分；换 tiktoken |
| `llm.py` | `gateway/{llm,cache,metering}.py` | 拆分 |
| `scoring.py` | `eval/metrics.py`（或 `eval/scoring.py`） | 原样；阈值 Phase 2 重标定 |
| `guards.py` | `graph/guards.py` | **契约迁入，判定全集留 Phase 2** |
| `topics.py` | `models/topic.py` + `config/seeds/topics.yaml` | 拆模型/数据 |
| `report.py` | `agents/reporter.py` | 并入 |
| `steps/s3_storage_spike.py` | `stores/*` + `tests/integration/test_graph_store.py` | 逻辑并入 |
| `steps/s3b_vector_latency_probe.py` | — | 不迁（一次性归因） |
| `steps/s4_checkpoint_spike.py` | `graph/checkpoint.py` + `tests/integration/test_checkpoint.py` | 结论迁入（`invoke(None)`/幂等） |
| `steps/s5_walking_skeleton.py` | `runtime/runner.py` + `agents/reporter.py` | 逻辑并入 |
| `steps/s6_guards_demo.py` | `graph/guards.py` + `eval/faultinject.py` | 场景迁入（注入集 P2 实现） |
| `steps/s7_metrics.py` | `eval/metrics.py` | 逻辑并入 |
| `tests/test_*.py`（10 个） | `tests/unit` 或 `tests/integration` | 按 §3.2 L 组归类 |
| `FILEMAP.md` / `RESULTS.md` | 本文 §3.2 / `RESULTS-P1.md` | 取代/承接 |

### 3.6 本阶段的 ADR 状态

| 缺口 | 状态 | 结论 | 落点 |
|---|---|---|---|
| 论文/作者/引文实体表（guide §2.1 未列） | ✅ **`adr/0005` 已定稿** | 12 张新表（含 `store_meta`）+ 12 张既有表列修订（共 24 张）+ `merged_ids_json` 与 `paper_merges` 并存 + DDL/索引/外键 | 1.3 实现 |
| 事件 seq 生成与幂等键冲突策略 | ✅ **`adr/0005` §5–§7 已定稿** | `runs.next_seq` 事务内自增；双唯一约束；**幂等键总表**（覆盖/忽略/拒绝逐资源定义） | 1.3/1.4 实现 |
| 向量部署形态与嵌入模型 | ✅ **`adr/0004` 已定稿** | Qdrant local + `bge-m3` 1024 维（备选 `bge-large-en-v1.5`）；新增 `sentence-transformers` 依赖；维度/模型身份校验；换模型走"新 collection + 全量重嵌入 + 指针切换" | 1.5 实现 |
| 顶层 `scripts/` + `doctor` 子命令 | ⏳ 待 1.19 回写 | 记入 §8.4 | 1.19 |

**附带补充（登记即可）**：`errors.py` 在 guide §1.5 九段外补 `E_STORE_*`（`E_STORE_NOT_EMPTY`/`E_STORE_SCHEMA_MISMATCH`
来自 ADR-0003；`E_STORE_PATH_NONASCII` 为新增）、`E_POLICY_SENSITIVE`、`E_FEATURE_DISABLED`，随 1.19 回写 guide §1.5。

---

## 4. Step 明细

> 固定字段：**目标 / 深度 / 内容要求 / 交付物 / 关键契约 / 执行命令 / 期望输出 / 验收标准与方法 / 时间盒 / 重难点 / 失败应对**。

### Step 1.1 工程基座：全模块骨架、配置、日志、错误、CLI、doctor（2.5 d）

- **深度**：`config/logging/errors` D-FULL；`doctor/selftest` D-MIN；其余模块建 SKELETON 文件。
- **内容要求**：
  1. `pyproject.toml`（guide §1.2 依赖 + `[project.scripts] lit-agent` + ruff/pytest + `pythonpath=["src"]`）。
  2. §3.1 的目录与文件**全部创建**（每模块至少 `__init__.py` 导出；D-SKEL 文件写 `# SKELETON:` 与 `FEATURE = "..."`）。
  3. `config.py`（全键 + env 覆盖 + `config_version` + `ensure_dirs`）、`logging.py`（迁入 + 脱敏 + 轮转）、
     `errors.py`（九段 + `E_FEATURE_DISABLED`）。
  4. `doctor.py`：六类检查（结构/依赖/路径/三库/配置/版本）+ 模块三态清单（FULL/MIN/SKEL），支持 `--strict`/`--json`。
  5. `cli.py`：子命令树（`doctor/db/stores/sources/run-topic/llm/api/eval/schedule`），未实现子命令给
     `E_FEATURE_DISABLED` 并退出码 60。
  6. `scripts/check_structure.py`：比对 §3.1 清单 → 缺失/多余。
  7. Phase 0 测试全部迁入（**改 import 不改断言**）。
- **交付物**：全目录骨架、`cli.py`、`doctor.py`、`config.py`、`logging.py`、`errors.py`、
  `scripts/{doctor,selfcheck}.ps1`、`scripts/check_structure.py`、迁移后的 `tests/**`。
- **关键契约**：目录结构 = §3.1；`E_FEATURE_DISABLED(feature=...)`；`doctor` 退出码与三态计数语义。
- **执行命令 / 期望输出**：
  ```powershell
  uv sync
  uv run lit-agent doctor                  # 6/6 通过；"modules: 16 present（13 包 + 3 顶层模块）, FULL/MIN/SKEL 计数"
  uv run lit-agent doctor --strict --json   # 机器可读，退出码 0
  uv run python scripts/check_structure.py  # missing=0, extra=0
  uv run pytest -q                          # ≥112 passed
  ```
- **验收标准与方法**：①六项全过且输出三态计数；②`--strict` 在缺任一文件时退出码非 0（临时改名验证后还原）；
  ③非 ASCII 数据路径 → `E_STORE_PATH_NONASCII`；④`check_structure.py` 删除一个模块文件即报缺失；
  ⑤`tests/unit/test_package_surface.py` 断言 16 个模块（13 包 + config/logging/errors 三文件）可导入且导出非空；⑥`pytest` 计数 ≥112。
- **时间盒**：2.5 d（超时 → 砍 `--json` 与 `schedule` 子命令，保留结构检查）。
- **重难点**：①一次建 16 模块骨架易漏导出 → 用 surface 测试锁死；②skeleton 文件必须可导入且**导入期无副作用**
  （否则 `doctor` 自身崩溃）。
- **失败应对**：Phase 0 测试因拆分失败 → 先保 112 全绿再继续；无法一次迁移的登记 §5 阻塞列，禁止删用例。

### Step 1.2 契约模型全集冻结（1.5 d）

- **深度**：D-FULL。
- **内容要求**：`Paper`（含 `merged_ids`）、`Author`、`Topic`、`Run/RunState`、`Event/EventType`、`Claim/Support`、
  `EvidenceCard`、`Report`；`GuardVerdict/Action`（对齐 design §7）；`results.py`（`RetrievalResult/MappingResult/
  AnalysisResult/ReportDraft/StageResult/RunContext`）。全部 `extra="forbid"`（`payload`/`config_json` 除外）；
  `ts` 带时区；`Event.type` 白名单校验；`RunContext` 只放可序列化字段，不可序列化资源进 `ctx.resources`（标注 non-persistent）。
- **交付物**：`models/*.py`（9 文件）、`tests/unit/{test_contracts,test_models_surface}.py`、
  `tests/contract/test_models_vs_guide.py`（清单比对）。
- **关键契约**：guide §2.3；design §7；`RunContext` 可序列化约束。
- **执行命令 / 期望输出**：
  ```powershell
  uv run pytest -q tests/unit -k "contract or models"   # 全绿
  uv run pytest -q tests/contract -k models             # 清单零缺项
  ```
- **验收标准与方法**：①参数化遍历全部模型做 JSON 往返；②未知字段被拒；③`Event(type='bogus')` 报错并列出合法值；
  ④`GuardVerdict.action` 只能取 6 值、`severity` 只能取 info/warn/block；⑤`RunContext.model_dump_json()` 成功且不含 session；⑥dump 与日志无密钥明文。
- **时间盒**：1.5 d。
- **重难点**：①`RunContext` 混入不可序列化对象会炸 Phase 2 的 checkpoint —— 现在用测试锁死；②`extra="forbid"`
  与历史事件解析冲突 → `payload` 用宽松类型；③模型名与 guide §2.3 逐字一致（contract 清单比对，不靠人眼）。
- **失败应对**：与 guide 有出入 → **以 guide 为准**；guide 缺字段 → 出 ADR 草稿，禁止静默加字段。

### Step 1.3 SQLite 真相源 + Alembic + 仓储层（2.0 d）

- **深度**：D-FULL。
- **内容要求**：**前置条件已满足**——`adr/0005` 已定稿，本步**照抄其 §3 的 DDL**（12 张新表 + 索引，另修订 12 张既有表），不重新设计表结构。
  `db/tables.py` = guide §2.1 全表 + ADR-0001 `paper_merges` + ADR-0005 的实体表/缓存表/`store_meta`；
  `db/session.py`（WAL/`foreign_keys=ON`/`busy_timeout`/`synchronous=NORMAL`）；11 个仓储（`upsert_many`/`counts`/
  `next_seq` 事务内 `UPDATE ... RETURNING`/`set_cursor`）；Alembic `0001_initial`（建表顺序按 ADR-0005 §3）；
  `lit-agent db upgrade/reset`；`doctor` 增加 SQLite ≥3.35 与表清单比对。
- **交付物**：`db/**`、`migrations/**`、`alembic.ini`、`tests/integration/{test_migrations,test_repo_sqlite}.py`。
- **关键契约**：guide §2.1；ADR-0001/0005；"事件只追加、报告与指标提交后不可改"。
- **执行命令 / 期望输出**：
  ```powershell
  uv run lit-agent db upgrade     # 0001_initial applied
  uv run pytest -q tests/integration -k "migrat or repo" -m "not slow"
  ```
- **验收标准与方法**：①升→降→升 schema 快照一致；②`journal_mode=wal`；③重复 upsert 零增长；
  ④手工删列 → `E_STORE_SCHEMA_MISMATCH` 且列出差异列；⑤1000 行单事务批量写 < 1 s；⑥崩溃回滚不留半行。
- **时间盒**：2.0 d（超时 → 先把 `claims/reports/metrics` 表推到 1.12，核心十表先上）。
- **重难点**：①`next_seq` 竞态 → `UPDATE ... RETURNING`；②WAL 下 `downgrade base` 需先关连接；
  ③SQLite 单写者 → 批量事务 + `job_locks` 兜底；④实体表命名与 guide 风格一致，不自创前缀。
- **失败应对**：seq 竞态修不动 → 降级为单写者并登记 §5 阻塞，禁止"大概不会并发"。

### Step 1.4 事件总线与回放（1.5 d）

- **深度**：D-FULL。
- **内容要求**：`db/repo/events.py`（append/read/paginate）；`runtime/events.py`（唯一入口、事务内 seq、
  **先落库→日志→广播**、`EventSink` 协议）；JSONL 导出 `logs/runs/<run_id>.jsonl`；`replay(run_id)` 回放器。
- **交付物**：`runtime/events.py`、`db/repo/events.py`、`tests/integration/{test_events_replay,test_events_idempotent}.py`。
- **关键契约**：guide §2.2；`(run_id,seq)` + `(run_id,stage,step_key)` 双唯一；冲突→忽略并记 `E_DATA_DUP`。
- **执行命令 / 期望输出**：
  ```powershell
  uv run pytest -q tests/integration -k events -m "not slow"
  ```
- **验收标准与方法**：①`seq == 1..N` 连续；②重复 emit 行数不变 + `E_DATA_DUP`+1；③`after_seq` 分页不重不漏；
  ④回放序列 == 执行序列（比对 `phase_change`）；⑤广播回调抛异常不影响已落库事实。
- **时间盒**：1.5 d。
- **重难点**：①"日志与事件双写必须一处完成"；②广播失败不能回滚事实；③同 run 重跑必须**续号**，seq 重置会破坏回放。
- **失败应对**：双写难统一 → 改为"日志由事件派生"（emit 后分流），并把该设计写入 RESULTS-P1。

### Step 1.5 三库、自检与重建对账（2.0 d）

- **深度**：D-FULL。
- **内容要求**：**DG-1 已定**（`adr/0004`：Qdrant local 嵌入式 + `BAAI/bge-m3` 1024 维 + `sentence-transformers`）。
  `stores/graph.py`（§2.5 DDL + MERGE + `UNWIND` 批量 + `CITES` 双向查询 + `close()` 落盘）；
  `stores/vector.py`（`get_client()` 单例、`ensure_collection('papers_v1',1024,Cosine)`、**encoder 依赖注入**、
  `normalize_embeddings=True`、幂等 upsert、filter 检索、§7 的三重维度/模型身份校验）；
  `stores/files.py`；`stores/selftest.py`（ASCII/`store_meta` 哨兵/列级 schema/close 后测盘/`reset_store_path`）；
  `stores/rebuild.py` 接口（`rebuild_vector` 走 `embeddings` 缓存）。
- **交付物**：`stores/*.py`、`adr/0004-*.md`、`scripts/rebuild_stores.py`、
  `tests/integration/{test_graph_store,test_vector_store,test_store_selftest}.py`。
- **关键契约**：guide §2.5/§2.6；ADR-0003/0004。
- **执行命令 / 期望输出**：
  ```powershell
  uv run pytest -q tests/integration -k "graph_store or vector_store or store_selftest" -m "not slow"
  uv run lit-agent stores verify     # 三库 + 哨兵 + 磁盘
  ```
- **验收标准与方法**：①MERGE 幂等（写两次零增长）；②filter 检索生效；③`reset_store_path` 文件/目录都对且幂等；
  ④close 前后磁盘读数差异（锁死"close 后测量"）；⑤非空库 → `E_STORE_NOT_EMPTY`；⑥5k 写入耗时/磁盘记录 RESULTS-P1。
- **时间盒**：2.0 d（DG-1 已定，原先用于决策的 0.5 d 改用于 `stores bench-embedding` 实测）。
- **重难点**：①Kuzu 单文件 + 独占打开；②逐条 MERGE 慢一个量级；③Qdrant local 无 ANN（0.038 ms/点，5k p95 155 ms）
  → Phase 1 不引入 server/ANN，触发条件写进 ADR-0004；④键口径统一 `canonical_id`（merged 记录不进图/向量）。
- **失败应对**：DG-1 选 A 但模型不可用 → 切 C 并更新 ADR（schema 不变，不影响其他步骤）。

### Step 1.6 源适配与增量（1.5 d）

- **深度**：D-FULL。
- **内容要求**：`SourceAdapter` 协议；OpenAlex 礼貌池/深分页/429/5xx 退避/`E_SRC_*`/`from_publication_date` 水位线
  （写 `sync_state`）/日期合理性过滤/`papers_raw` 原样入库；arXiv 按 categories；
  **白名单解析器** `resolve_venues(venue_names) -> venue_ids`（把 ADR-0005 §8.2 的候选名称解析成 OpenAlex `source.id`
  并回写 `config/seeds/topics.yaml`，**代码里禁止名称匹配**）；空 selector → `E_SRC_NO_SELECTOR`（不许退化为全量抓取）；
  四域种子 topic 落库；`normalize.py`（`canonical_id`/`_w_to_canonical`）。
- **交付物**：`sources/{base,openalex,arxiv,whitelist,normalize}.py`、`tests/fixtures/openalex/*`、
  `tests/integration/test_openalex_adapter.py`。
- **关键契约**：guide §3；增量语义（`since` + 游标）。
- **执行命令 / 期望输出**：
  ```powershell
  uv run pytest -q tests/integration -k openalex -m "not slow"
  uv run lit-agent sources sync --topic llm-agents --limit 200
  uv run lit-agent sources sync --topic llm-agents --limit 200   # papers_new=0
  ```
- **验收标准与方法**：①respx 重放分页 + 429 + 500；②连续两次第二次 `new=0/updated=0`；③水位线前移一天只补该天；
  ④白名单按名称匹配的负例**必须不命中**；⑤`_w_to_canonical` 映射用例（Phase 0 #8 防护）。
- **时间盒**：1.5 d。
- **重难点**：①回溯更新盲区（水位线回溯 7 天 + 抽样全量核对）；②深分页游标与 `per-page` 上限；
  ③源 schema 漂移 → fixture 失效要显式失败而非跳过。
- **失败应对**：源 API 变更 → 重录 fixture 并记录响应版本日期；禁止为迁就旧断言改测试。

### Step 1.7 解析与分块（1.5 d）

- **深度**：D-FULL。
- **内容要求**：`download_oa()`（限速/大小上限/ASCII 文件名）；`extract_text()`（PyMuPDF→pdfplumber→`failed`）；
  `count_tokens()`（tiktoken，`TIKTOKEN_CACHE_DIR` 指向仓库内缓存，离线可复现）；`chunk_text()`（预算+句界+overlap）；
  `chunk_id = <canonical_id>#<section>#<idx>` + 内容哈希；`parse_papers()` 编排 + 事件。
- **交付物**：`parsing/*.py`、`tests/fixtures/pdf/*`（含截断/加密）、`tests/unit/test_chunking.py`。
- **验收标准与方法**：①token ≤ 预算且利用率 ≥0.9；②坏 PDF → `failed` 不中断；③同文本两次 `chunk_id` 相同；
  ④断网可跑（tiktoken 缓存）。
- **执行命令 / 期望输出**：
  ```powershell
  uv run pytest -q tests/unit/test_chunking.py
  ```
- **时间盒**：1.5 d。
- **重难点**：tiktoken 首次联网；PDF 体积与并发；分块边界影响后续 snippet 定位。
- **失败应对**：tiktoken 离线不可行 → 用确定性估算器并记录（契约字段不变）。

### Step 1.8 去重与三库投影（2.0 d）

- **深度**：D-FULL。
- **内容要求**：`dedup_papers()`（精确 id→指纹→模糊）；`merge_relations()` 写 `paper_merges`；确定性主记录
  （有摘要>DOI>作者多>id 序）；**只记录不物理合并**；投影 `stage_normalize`/`stage_project`；`verify_counts()`
  对账 + 差异样例 + `E_DATA_SYNC` + 自动重投影。
- **交付物**：`sources/dedup.py`、`stores/rebuild.py`（投影部分）、`tests/unit/test_dedup.py`、
  `tests/integration/test_projection.py`。
- **验收标准与方法**：①同 DOI 多版本合并 + 可回查；②同名不同文不误合并；③两次跑主记录集合相同；
  ④手工删边 → 对账报错 → 重投影恢复；⑤去重率 19.3–19.8% ±3pp。
- **时间盒**：2.0 d。
- **重难点**：误合并不可逆（故只记录）；模糊阈值边界；merged 记录**不进**图/向量（只写属性）。
- **失败应对**：模糊段误判多 → 关闭模糊段（`exact+fingerprint`）并记录降级理由。

### Step 1.9 LLM 网关（2.0 d）

- **深度**：`llm/cache/metering` D-FULL；`policy` D-MIN；`breaker` D-SKEL。
- **内容要求**：litellm 调用 + 超时退避 + **截断检测**（`finish_reason=='length'` 或空正文 → 失败 → `max_tokens`
  翻倍重试 1 次）+ `chat_json` 围栏剥离/JSON 校验；内容寻址缓存；`llm_calls` 计量 + usage 缺失估算
  `cost_estimated`；预算 80/100 事件；敏感硬门（零出网）+ `route_reason`；`NoopBreaker` 注入点。
- **交付物**：`gateway/*.py`、`tests/unit/test_policy.py`、`tests/integration/test_gateway.py`、`tests/fixtures/llm/*`。
- **关键契约**：guide §2.1 `llm_calls`；§2.2；ADR-0002。
- **执行命令 / 期望输出**：
  ```powershell
  uv run pytest -q tests/unit/test_policy.py tests/integration/test_gateway.py -m "not slow"
  uv run lit-agent llm probe --budget 0.01   # 真实 1 次，打印 tokens/cost/route_reason
  ```
- **验收标准与方法**：①敏感样本 `litellm.completion` 调用 0 + respx 0 请求；②同请求二次 `cost=0` 且输出逐字节一致；
  ③截断重试 `max_tokens` 翻倍；④预算 warn/stop 事件；⑤`llm_calls` 行数 == 事件数；⑥`NoopBreaker` 连续失败仍不打开。
- **时间盒**：2.0 d。
- **重难点**：①缓存键漏 `max_tokens` 会让截断重试命中旧缓存；②预算必须**调用前**判；③reasoning 空正文不当成功。
- **失败应对**：usage 长期缺失 → 20 次抽样校准估算系数并标注。

### Step 1.10 Harness 骨架：state / pipeline / edges / checkpoint（2.0 d）

- **深度**：`state` D-FULL；`pipeline` D-MIN；`edges` D-SKEL；`checkpoint` D-MIN。
- **内容要求**：
  1. `state.py`：`AgentState`（TypedDict + `Annotated[list, operator.add]`）、`STATE_SCHEMA_VERSION`、
     大小上限（>256 KB 产物只存引用）、`resources` 隔离。
  2. `pipeline.py`：`build_graph(nodes, entry, exit)`、`register_node()`、`smoke_graph()`（intake→retrieve→draft 用真实 stage 函数）。
  3. `edges.py`：`E1–E13` 常量（引用 design）、`EdgeCondition`、主干路由表；**回退类路由抛 `E_FEATURE_DISABLED`**。
  4. `checkpoint.py`：`open_checkpointer(path)`（`SqliteSaver`）、`thread_id=run_id`、`resume(None)` 包装（禁止带输入重放）。
- **交付物**：`graph/{state,pipeline,edges,checkpoint}.py`、`tests/unit/test_state_contract.py`、
  `tests/integration/test_smoke_graph.py`、`tests/contract/test_edges_vs_design.py`。
- **验收标准与方法**：①冒烟链跑通且事件按阶段发；②三节点可达 END；③checkpoint 写入可读回同状态；
  ④`resume` 只接受 `None`（传 state 抛错）；⑤`edges` 常量与 design 文档 E1–E13 一一对应（contract 解析 md 表格）；
  ⑥回退路由 → `E_FEATURE_DISABLED` 有测试。
- **时间盒**：2.0 d。
- **重难点**：①state 不可序列化对象；②LangGraph 1.x 中断语义（`invoke(None)`）；③骨架里**不得顺手实现**回退逻辑。
- **失败应对**：LangGraph API 不匹配 → 锁版本 + ADR 记录；冒烟链可退化为"裸函数链 + 事件"，但 state 契约不变。

### Step 1.11 守卫契约与运行时（1.5 d）

- **深度**：`guards` D-MIN（2 检测器）；`runner/jobs/budget` D-MIN；`watchdog` D-SKEL。
- **内容要求**：`Guards`：`Guard` Protocol、`GuardRail.run()`（按严重度取最重：abort>replan>degrade>warn）、
  `BudgetGuard`（80/100）、`NoProgressGuard`；其余 4 类抛 `E_FEATURE_DISABLED`。`runner.start_run()` 线性执行 +
  每阶段 `phase_change` + 异常→`fail_with_report()`；`resume()` 抛未实现。`jobs`：`job_locks` 互斥/状态流转/
  `cleanup_orphans()`/失败报告四要素。`budget`：三维（tokens/cost/时长）。`watchdog.scan()`：无事件超时→`guard_trigger`。
- **交付物**：`graph/guards.py`、`runtime/{runner,jobs,budget,watchdog}.py`、`scripts/{run_topic,seed_topics}.py`、
  `tests/integration/{test_runner,test_locks,test_guard_contract}.py`。
- **验收标准与方法**：①并发触发同 topic → 409 `E_LOCK_HELD`；②孤儿锁重启清理；③`BudgetGuard` 80/100 两侧正确；
  ④`NoProgressGuard` 连续 2 步无新增触发；⑤4 类未实现守卫 → `E_FEATURE_DISABLED`；⑥失败报告四要素断言。
- **时间盒**：1.5 d。
- **重难点**：①守卫"纯判定不写事件"（事件由 runner 发）；②多守卫合并顺序；③锁心跳与孤儿判定。
- **失败应对**：合并语义不清 → 冻结为"最重动作胜出 + reasons 聚合"，写 docstring + 测试。

> **1.11 补充纪律（来自 DSH 对照，见 `design/harness-reference-comparison.md` P0-2）**：
> 阶段函数里的**副作用必须与事件同事务**——抓取/PDF 落盘/DB 批量写之后，用
> `emit_event(..., conn=conn)` 在同一事务内写事件；崩溃时"要么都成功、要么都回滚"。
> LLM 调用前先落一条 `llm_call` 事实（含 `request_sha`），避免"发出去了但没记录"。

### Step 1.12 Agent 层骨架与 reporter（1.5 d）

- **深度**：`base` + 5 角色 D-SKEL；`reporter` D-MIN。
- **内容要求**：`Agent` Protocol（`name/inputs/outputs/run(ctx)->AgentResult`）；5 角色声明 inputs/outputs 且
  `run()` 抛 `E_FEATURE_DISABLED`；`reporter.py`：证据卡 → claims（每条必带 citations，**回查强制校验**）→
  确定性 Markdown → `report_written` 事件；不可落地 claim 标 `unsupported` 且仍入库。
- **交付物**：`agents/*.py`、`tests/unit/test_agents_contract.py`、`tests/integration/test_reporter.py`。
- **验收标准与方法**：①每个 agent 的 inputs/outputs 与 design 一致；②未实现角色显式失败；③reporter ≥8 claims 且
  100% 可回查；④同输入两次渲染字节一致；⑤生成 claims 数 == 入库 claims 数（Phase 0 #6 防护）。
- **时间盒**：1.5 d。
- **重难点**：①inputs/outputs 声明要真实（Phase 3 靠它编排与分配上下文）；②确定性渲染（禁时间戳/随机序）；
  ③claim 丢弃会伪造 grounding。
- **失败应对**：reporter 无法稳定 ≥8 claims → 降阈值并记录，但**不得**丢弃 claim。

### Step 1.13 上下文层骨架（1.5 d）

- **深度**：`budget` D-MIN；`folding/slots` D-SKEL。
- **内容要求**：`TokenBudget.fit(texts, budget)`（超限截断 + 事件，保 citation 锚点）；`FoldingStrategy` Protocol +
  `TruncateFolding`（保头尾可配）；`summarize/hierarchical` 抛未实现；`CtxSlot` 契约 + `SlotRegistry`（重名报错）。
- **交付物**：`context/*.py`、`tests/unit/{test_budget,test_folding_contract}.py`。
- **验收标准与方法**：①预算内不变、超限必截且记事件；②truncate 保头尾；③未实现策略显式失败；④重名槽位报错。
- **时间盒**：1.5 d。
- **重难点**：预算单位与分块单位一致；截断不能截掉 citation 锚点。
- **失败应对**：截断导致 claim 无法回查 → 改为"按证据卡粒度裁剪"并记录。

### Step 1.14 工具注册表骨架（1.0 d）

- **深度**：`registry` + 3 builtin D-MIN；`mcp_adapter` D-SKEL。
- **内容要求**：`Tool` Protocol（`name/params_schema/run/validate`）；`Registry`（注册/获取/列举/重名报错）；
  `openalex_search`/`paper_pdf`/`kv_cache`（真实调用 1.6/1.5/1.3）；`tool_call` 事件（`args_hash`，不落敏感参数）；
  `MCPAdapter` Protocol + 注册位。
- **交付物**：`tools/*.py`、`tests/unit/test_tool_registry.py`、`tests/integration/test_builtin_tools.py`。
- **验收标准与方法**：①重名报错；②参数校验结构化错误；③3 内置工具各有集成用例（kv 真落库/openalex fixture/paper_pdf
  好坏样本）；④MCP 调用显式未实现。
- **时间盒**：1.0 d。
- **重难点**：工具"原子能力"与 agent"编排策略"的边界；返回大小上限。
- **失败应对**：职责重叠 → 保持边界并记录到 docstring。

### Step 1.15 全量 API + SSE + OpenAPI（2.0 d）

- **深度**：D-FULL（chat/graph 501）。
- **内容要求**：8 个路由文件覆盖 guide §2.4 **全部行**；`api/sse.py`（`Last-Event-ID`/`after_seq` **从库**补发、
  心跳 15s、结束事件）；错误码→HTTP 映射（409/404/422/501）；`export-openapi`；`tests/contract/test_openapi_vs_guide.py`
  解析 guide 表格比对路径集合。
- **交付物**：`api/**`、`docs/api/openapi.json`、`tests/integration/{test_api,test_sse}.py`、
  `tests/contract/test_openapi_vs_guide.py`。
- **验收标准与方法**：①§2.4 每行都有路由与测试；②200/404/409/422/501 分支；③SSE 断线续传不重不漏；
  ④run 期间 `/health` < 200 ms；⑤未启用路由 501 + `E_FEATURE_DISABLED`（不是 404）。
- **时间盒**：2.0 d。
- **重难点**：①长任务不得阻塞事件循环（`asyncio.to_thread` 或子进程）；②SSE 真相源在库；③契约表解析失败要显式报错。
- **失败应对**：SSE 浏览器端不稳 → 保留 `/events` 分页兜底，但在 RESULTS 标为已知限制，不得静默降级。

> **1.15 补充纪律（DSH 对照 P0-1）**：SSE 的**流式 token 帧不进 `run_events`**（那是瞬态信号，
> 只走内存通道）；`run_events` 只落**结算事件**（一条 `llm_call` 带 usage/cost）。否则事件表会被
> 流式帧撑爆、且回放语义被破坏（D5）。前端"打字机"效果用独立通道，断线只从库补发结算事件。

### Step 1.16 前端工程化 + 三界面骨架（2.5 d）

- **深度**：D-MIN。
- **内容要求**：Vite+Vue3+TS+Element Plus；`client.ts`（全路由封装 + 错误码提示）、`types.gen.ts`（生成）、
  `sse.ts`（续传/重连）、router 三路由 + `DefaultLayout`、三页面 + 7 组件、pinia stores；`npm run build` 与
  `vue-tsc --noEmit` 通过。
- **交付物**：`web/**`、`tests/e2e/test_full_system.py`。
- **验收标准与方法**：①`npm run build` + `vue-tsc --noEmit` 通过；②`types.gen.ts` 重新生成后 diff 为空；
  ③三路由可导航；④Topics 页建 topic + 触发 + 事件流 + 阶段进度真实工作；⑤Report 页 claims 可点开证据；
  ⑥Chat 页显示"未启用"并展示后端 501 的 code；⑦e2e 通过（D7）。
- **时间盒**：2.5 d。
- **重难点**：类型漂移（生成而非手写）；`EventSource` 自动重连带 `Last-Event-ID`；刷新后从历史恢复。
- **失败应对**：node 环境不可用 → 交付 `web/dist` + API 静态托管并登记阻塞；但**类型生成**必须完成。

### Step 1.17 调度与运维骨架（1.0 d）

- **深度**：D-SKEL。
- **内容要求**：`runtime/scheduler.py`（`build_scheduler()`、`weekly_job(topic_id)` 调 `start_run(trigger='schedule')`、
  `enabled=false` 时**不注册**）；`/api/health` 含三库状态与最近 run；日志轮转与 7 天 debug 清理；
  `lit-agent schedule list/run-once`（`run-once` 可用，注册留 Phase 3）。
- **交付物**：`runtime/scheduler.py`、`tests/unit/test_scheduler_wiring.py`、`tests/integration/test_health.py`。
- **验收标准与方法**：①`enabled=false` 时 scheduler 为空（断言无 job）；②`enabled=true` job 定义正确（cron/stagger）；
  ③`run-once` 等价 `run-topic`；④health 输出三库状态；⑤debug 清理按 mtime。
- **时间盒**：1.0 d。
- **重难点**：disabled 必须"不注册"而非"注册后跳过"；时区 `Asia/Singapore`；单进程内调度与 API 并发。
- **失败应对**：APScheduler 与 asyncio 冲突 → `BackgroundScheduler` + 线程执行，记录到 RESULTS。

### Step 1.18 评测地基（1.5 d）

- **深度**：`metrics/export` D-MIN；`datasets/grounding/judge/faultinject` D-SKEL。
- **内容要求**：`eval/metrics.py`（grounding、幻觉率、引用覆盖率、去重率、成本；TPR/FPR **campaign 作用域**）；
  `export.py`（CSV/JSON/md）；`datasets.py`（`eval_data/<topic>/` 约定 + 加载器）；`grounding/judge` Protocol；
  `faultinject` 6 类定义；`lit-agent eval metrics --runs <ids> --out`；`tests/regression` 机制（golden 快照）。
- **交付物**：`eval/*.py`、`eval_data/README.md`、`tests/unit/test_metrics.py`、`tests/regression/README.md`。
- **验收标准与方法**：①5 指标对构造事件集正确（空集/单 run/多 run campaign）；②分母口径含 `unsupported`；
  ③只读事件（不查业务表）；④未实现 judge 显式失败；⑤回归脚本可对比两次 golden 快照。
- **时间盒**：1.5 d。
- **重难点**：campaign 口径（Phase 0 的 FPR/TPR 假象）；字段缺失必须报错（不许回退成 0）。
- **失败应对**：事件字段不足 → 指标计算直接报错并登记契约缺口。

### Step 1.19 阶段收口（0.5 d）

- **深度**：—
- **内容要求**：`RESULTS-P1.md`（摘要/环境/各步实测/被证伪假设/静默错误/决策门）；回写本文 §5 与各步实测；
  `doctor` 三态清单快照；回写 guide（§8.4 差异登记 10 项）；删除 `prototype/`；起草 Phase 2 首张任务卡。
- **交付物**：`RESULTS-P1.md`、本文 v2.1、guide 补丁、Phase 2 任务卡、结构清单快照。
- **执行命令 / 期望输出**：
  ```powershell
  uv run ruff check . ; uv run ruff format --check .
  uv run pytest -q -m "not slow"
  uv run lit-agent doctor --strict
  uv run python scripts/check_structure.py
  ```
- **验收标准与方法**：①§7 出口清单逐条有证据；②`RESULTS-P1.md` 数字抽查 5 个有出处；③结构快照与 §3.1 完全一致；
  ④深度矩阵与实际交付一致（SKEL 不得写成已实现）；⑤Phase 2 任务卡字段完整。
- **时间盒**：0.5 d。
- **重难点**：如实记录"哪些是壳"。
- **失败应对**：未达标项不改标准，改结论并写进 Phase 2 任务卡。

---

## 5. 进度跟踪表

> 状态：`未开始 / 进行中 / 完成 / 阻塞`；完成后填实测值与证据（模板见 §2.5）。

| Step | 目标 | 深度 | 验收命令 | 状态 | 日期 | 实测值 / 证据 | 阻塞 |
|---|---|---|---|---|---|---|---|
| 1.1 | 全模块骨架 + doctor + 测试迁移 | F/M/S | `lit-agent doctor --strict`；`pytest -q` | ✅ 完成 | 2026-10-19 | 结构 127/127；doctor 6/6；未实现子命令退出码 60（`RESULTS-P1` §2-1.1） | — |
| 1.2 | 契约模型全集冻结 | F | `pytest -q tests/unit -k contract`；`tests/contract -k models` | ✅ 完成 | 2026-10-19 | 33 个导出；guide §2.3 清单全比对通过；20 例契约测试 | — |
| 1.3 | SQLite + 迁移 + 仓储 | F | `pytest -k "migrat or repo"` | ✅ 完成 | 2026-10-19 | 24 表；升/降/升三轮一致；WAL+FK 生效；字段边界与幂等 15 例 | 已解除（ADR-0005） |
| 1.4 | 事件总线 + 回放 | F | `pytest -k events` | ✅ 完成 | 2026-10-19 | seq 连续；去重命中不跳号；并发 60×2 各连续；广播在 commit 后 | — |
| 1.5 | 三库 + 自检 + 重建 | F | `stores verify`；`pytest -k "graph_store or vector_store"` | ✅ 完成 | 2026-10-19 | Kuzu MERGE 幂等；Qdrant payload 六字段；bge-m3 已就位（D:\lit-agent-store\hf）；三方对账可发现漂移 | 已解除（ADR-0004） |
| 1.6 | 源适配 + 增量 | F | `pytest -k openalex`；`sources sync`×2 | ✅ 完成 | 2026-10-19 | 首次 new=2、第二次 new=0；空 selector → `E_SRC_NO_SELECTOR`；白名单按 source.id | — |
| 1.7 | 解析 + 分块 | F | `pytest -q tests/unit -k chunking` | ✅ 完成 | 2026-10-19 | tiktoken 预算 ≤；坏 PDF → failed 不中断；`paper_chunks` 整体替换 | — |
| 1.8 | 去重 + 投影 + 对账 | F | `pytest -k "dedup or projection"` | ✅ 完成 | 2026-10-19 | 版本副本合并；`paper_merges`/`merged_ids` 落库；图只含主记录；引用只收语料内（重跑不增） | — |
| 1.9 | 网关 + 策略 + 计量 | F/M/S | `pytest -k "policy or gateway"` | ✅ 完成 | 2026-10-19 | 敏感零出网；缓存命中 $0 且同内容；截断 64→128 重试；预算调用前拦截；`llm_calls` 落库 | — |
| 1.10 | Harness 骨架 + checkpoint | F/M/S | `pytest -k "smoke_graph or state_contract or edges"` | ✅ 完成 | 2026-10-19 | 三节点冒烟；`invoke(None)` 不重放；E1–E13 常量；**修复 MERGE 时间戳导致重复建边** | — |
| 1.11 | 守卫契约 + 运行时 | M/S | `pytest -k "runner or locks or guard_contract"` | ✅ 完成 | 2026-10-19 | run 成功/失败两条路径；`E_LOCK_HELD`；失败报告四要素；预算中止；停滞告警；孤儿清理；`run-topic` 已接通 | — |
| 1.12 | Agent 骨架 + reporter | S/M | `pytest -k "agents_contract or reporter"` | ✅ 完成 | 2026-10-19 | 确定性渲染（正/逆序逐字节一致）；每条 claim 带引用；空证据 → unsupported | — |
| 1.13 | 上下文骨架 | M/S | `pytest -k "budget or folding"` | ✅ 完成 | 2026-10-19 | `fit_*` 不超预算；`truncate` 可用；`summarize` 显式未实现；槽位重名/未知报错 | — |
| 1.14 | 工具注册表 | M/S | `pytest -k "tool_registry or builtin_tools"` | ✅ 完成 | 2026-10-19 | 重名/未知保护；工具异常转 `ToolResult`；kv_cache 往返；openalex_search 工具声明 | — |
| 1.15 | 全量 API + SSE + OpenAPI | F | `pytest -k "api or sse"`；`tests/contract -k openapi` | ✅ 完成 | 2026-10-19 | 8 组路由可用；409/501/404 映射；事件分页 `1..N`；SSE 补发 + `event: end`；chat/graph 501 | — |
| 1.16 | 前端 + 三界面 + e2e | M | `npm run build`；`pytest -q tests/e2e` | 🟡 部分 | 2026-10-19 | 三页签可构建（JS 72 kB / gzip 28 kB）；TS/Element Plus/独立页面/e2e 未做 | — |
| 1.17 | 调度 + 运维骨架 | S | `pytest -k "scheduler or health"` | ✅ 完成 | 2026-10-19 | disabled 不注册 job；enabled 恰好 1 个 weekly；cron 解析；`run_once` trigger=schedule | — |
| 1.18 | 评测地基 | M/S | `pytest -k metrics`；`lit-agent eval metrics` | ✅ 完成 | 2026-10-19 | 5 项指标可算；分母 0 → None；持久化可复算；json/csv/md 导出 | — |
| 1.19 | 收口 + guide 回写 | — | §7 全部 | 🟡 部分 | 2026-10-19 | RESULTS/openapi/进度表已更新；guide 回写、prototype 删除、结构快照、Phase 2 文档未做 | — |

**基线数字（Phase 0，出处 `../prototype/RESULTS.md`）**：白名单 3 年 386 篇（≈129/年）、arXiv 收录率 91.7%、
去重副本 19.3–19.8%、白名单引用完整率 1.5%/14.3%、图 2-hop p95 4.42 ms、磁盘 64.9 MB/5k、
向量 top-10 p95 155 ms（0.038 ms/点，local 无 ANN）、checkpoint 28–37 KB、
报告 8.9k–10.8k 字符 / 16–23 claims / 100% 可引用、冷启动 $0.0036–0.0126、缓存重跑 $0、
守卫注入 15/15 检出 0/3 误报、grounding 0.7949、单 run $0.006294（max $0.012589）、112 测试。

---

## 6. 常见失败与应对

### 6.1 症状 → 处置

| 症状 | 可能原因 | 定位方法 | 处置 | 预防 |
|---|---|---|---|---|
| `table has no column` | 旧库 schema 漂移（Phase 0 #1） | `PRAGMA table_info` 对照 `tables.py` | `lit-agent db reset --yes` | 列级 schema 守卫（1.3/1.5） |
| Kuzu 打不开 / 异常 | 非 ASCII 路径；把文件当目录 | `repr(path)`、`is_file()` | 迁 ASCII；`unlink` | `assert_ascii_path`（1.5） |
| 磁盘/计数与实际不符 | 未 `close()` 就测/拷（#2/#3） | close 前后各测 | `close_all()` 后测 | close 前回归测（1.5） |
| 节点数偏多且只按 id 定位 | 旧库残留 + reset 静默失败（#4） | id 集合差集 | 空库哨兵 + 重建 | `E_STORE_NOT_EMPTY` |
| citations = 0 | W-id 未映射 canonical（#8） | 抽 1 条打印映射 | 补 `_w_to_canonical` | 1.6 集成断言 |
| 失败没有指标 | 只写日志没写事件（#5） | 查该 run `error` 事件数 | 统一 `emit_event()` | §2.4 纪律 |
| grounding 恒 100% | 不可落地 claim 被丢弃（#6） | 生成数 vs 入库数 | 标 `unsupported` 入库 | 1.12 断言两数相等 |
| FPR/TPR 失真 | 全历史聚合（#9） | 按 run/campaign 重算 | 指标作用域化 | 1.18 campaign 测试 |
| LLM 空正文"成功" | reasoning 截断（#10） | 打印 `finish_reason`/`usage` | 判失败 + 翻倍重试 | 1.9 截断检测 |
| 成本恒 0 | usage 缺失被当 0 | 抽样对比 | 估算兜底 + 标记 | 1.9 计量 |
| **骨架模块"没报错但没做事"** | D-SKEL 返回空值 | 看返回值是否为空 | 改抛 `E_FEATURE_DISABLED` + 补测试 | §1.4 规则 + 1.1 |
| **未启用路由返回 404** | 未实现=没挂载 | 查 OpenAPI 路径数 | 挂载并返回 501 | 1.15 contract 测试 |
| 前端类型与后端不符 | 手写类型 | 重新生成 diff | 用 `types.gen.ts` | 1.16 生成校验 |
| 页面刷新进度丢失 | 依赖内存态 | 断网只看历史接口 | 进页面先拉历史再订阅 | 1.16 |
| `database is locked` | 逐行 commit / 多进程写 | 看 WAL 与堆栈 | 批量事务 + 锁 | 1.3 |
| 结构检查/契约测试"通过"但漏项 | 清单硬编码或解析失败被吞 | 打印比对条目数 | 解析失败必须报错 | 1.1/1.15 |

### 6.2 处置优先级

**真相源正确 → 事件完整 → 派生物一致 → 接口契约 → 前端呈现**。顺序颠倒会造成"看起来完整、实际不可信"。

### 6.3 静默错误登记义务

任何"没报错但结果不对"必须当天写入 `RESULTS-P1.md` §4，并注明"哪条测试/守卫以后挡住它"；写不进测试的，
在 §7 留人工检查项。**Phase 1 额外要求**：每个 SKEL 都要有"未实现必须失败"的测试，否则视为静默失败。

---

## 7. 出口检查清单

**A. 结构与基座（D1）**
- [ ] `lit-agent doctor --strict` 退出码 0，模块三态清单已存档
- [ ] `scripts/check_structure.py` 输出 `missing=0 extra=0`
- [ ] 16 个模块（13 包 + config/logging/errors）可 `import`，无空包、无导入期副作用
- [ ] `data/` 纯 ASCII；非 ASCII 路径能报错；仓库无密钥明文

**B. 契约（D2/D3）**
- [ ] guide §2.3 模型清单 100% 落地（`tests/contract` 通过）
- [ ] 模型 ↔ 表 ↔ OpenAPI 三方一致；E1–E13 与 design 一致
- [ ] `ruff check`/`ruff format --check` 无输出；`pytest -q -m "not slow"` 全绿
- [ ] **每个 D-SKEL 有显式未实现测试**（数量 = SKEL 文件数）

**C. 数据与三库（D4/D6）**
- [ ] 同 fixture 重跑：三库计数零增长、报告 sha256 相同
- [ ] 删 Kuzu/Qdrant → `stores rebuild --all --verify` 通过
- [ ] `verify_counts()` 连续 3 次运行对账一致
- [ ] 去重率 19.3–19.8%±3pp；主记录两次跑相同
- [ ] 坏 PDF → `failed` + 事件 + 报告脚注披露

**D. 事件（D5）**
- [ ] `seq == 1..N` 无缺号；重复 emit 行数不变
- [ ] 回放序列 == 执行序列
- [ ] 每个外部调用均有事件（源/LLM/PDF/工具/DB 批量写各抽 1 条）
- [ ] 无裸 `logger.info` 记录事实（代码审查）

**E. 网关（D8）**
- [ ] 敏感样本：调用 0 + HTTP 0
- [ ] 缓存命中 `cost=0` 且逐字节一致
- [ ] 截断重试 `max_tokens` 翻倍；单 run ≤ $0.02
- [ ] `NoopBreaker` 断言"不熔断"（熔断接口就位）
- [ ] `llm_calls` 行数 == 事件数

**F. Harness 与运行时**
- [ ] 冒烟图三节点跑通、可达 END、checkpoint 可读写
- [ ] `edges` E1–E13 常量与 design 一致
- [ ] 4 类未实现守卫 / 回退路由 / 续跑 均显式失败
- [ ] 并发触发 409；孤儿锁重启清理；失败报告四要素

**G. 接口与前端（D7）**
- [ ] §2.4 全部路由存在，路径数 == 契约表行数
- [ ] 未启用功能 501 + `E_FEATURE_DISABLED`（chat/graph）
- [ ] SSE 断线续传不重不漏；run 期间 `/health` < 200 ms
- [ ] `web`：`npm run build` + `vue-tsc --noEmit` 通过
- [ ] `types.gen.ts` 重新生成后 diff 为空
- [ ] 三页面可导航；Topics/Report 真实可用；Chat 显示未启用态
- [ ] `tests/e2e/test_full_system.py` 通过

**H. 调度与评测**
- [ ] `scheduler.enabled=false` 时不注册任何 job
- [ ] `lit-agent schedule run-once` 等价 `run-topic`
- [ ] 5 项指标对构造事件集正确；campaign 作用域有测试
- [ ] `tests/regression` 可执行并对比 golden 快照

**I. 文档与交接（D10）**
- [ ] `RESULTS-P1.md` 完成（含被证伪假设、静默错误、决策门结论）
- [ ] 本文 §5 全绿并回写实测值
- [ ] ADR-0004/0005 定稿；guide §8.4 差异登记已回写
- [ ] `prototype/` 已删除且历史数字已引用
- [ ] Phase 2 首张任务卡已写入 §8.5

---

## 8. 与下一阶段的衔接

### 8.1 保留（禁止重写）

| 资产 | 说明 |
|---|---|
| 目录结构与 `models/` 契约 | 结构已冻结；新增字段走 ADR |
| `db/**` + `runtime/events.py` | 唯一写路径与事件契约 |
| `stores/**` + `rebuild.py` + `selftest.py` | 对账与重建是守卫与复现的基础 |
| `gateway/{llm,cache,metering}` | Phase 2 只加 `breaker` 实现，不改调用面 |
| `graph/state.py` + `checkpoint.py` | 状态契约与续跑接线 |
| `api/**` + `web/**` | Phase 2 只在事件流/守卫面板上扩展 |
| `eval/metrics.py` | Phase 3 的指标基线 |

### 8.2 升级（在骨架上填逻辑）

| 现状 | Phase 2/3 动作 |
|---|---|
| `graph/pipeline.py` 三节点冒烟 | 铺满 S0–S9 + 全边编排 |
| `graph/edges.py` 主干路由 | E1–E13 回退逻辑 + 预算 |
| `graph/guards.py` 2 个检测器 | 六类全集 + 阈值按真实分布重标定（F9 教训） |
| `gateway/breaker.py` Noop | 真熔断（连续失败→打开→半开）+ 复杂度分流 |
| `agents/*` 骨架 | 角色协作拓扑与消息契约 |
| `context/folding.py` truncate | summarize/hierarchical + 对照评测 |
| `tools/mcp_adapter.py` Protocol | 真实 MCP 接入 |
| `api/routes/chat.py` 501 | Chat 问答 + 引用回溯 |
| `runtime/scheduler.py` disabled | 周更实跑 + 两周期验收 |
| `eval/{grounding,judge}.py` Protocol | gold 集 + 跨厂商 Judge + 指标平台 |

### 8.3 丢弃

| 项 | 原因 |
|---|---|
| `prototype/` | Phase 0 实验区（1.19 删除） |
| 旧阈值常量（`eval/scoring`） | 换 embedding 后需重标定（Phase 2） |
| `scripts/` 一次性探针 | 只保留 doctor/check_structure/seed/rebuild/run_topic |

### 8.4 与 guide 的差异登记（1.19 回写 `implementation-guide.md`）

| # | 差异 | 回写位置 |
|---|---|---|
| 1 | 新增顶层 `scripts/`（doctor/check_structure/seed/rebuild/run_topic） | §1.1 |
| 2 | 新增 `doctor.py` 与 `lit-agent doctor`（结构 + 模块三态自检） | §1.1/§15 |
| 3 | guide §2.1 缺实体表 → ADR-0005 补齐 | §2.1 |
| 4 | 新增 `llm_cache`、`papers_raw`、`paper_chunks`（P3 启用） | §2.1 |
| 5 | `Paper.merged_ids` 入契约 | §2.3 |
| 6 | 新增 `GuardVerdict/Action`（design §7 的落地） | §2.3 |
| 7 | 新增 `E_FEATURE_DISABLED` 与 `E_STORE_*` | §1.5 |
| 8 | P1 的 `graph/guards.py` 为 D-MIN（2 检测器）、其余 D-SKEL | §14 P1 行加注 |
| 9 | 向量来源与降级 → ADR-0004 | §2.6 |
| 10 | 事件 seq/幂等键落库 → ADR-0005/0006 | §2.2 |

### 8.5 Phase 2 第一张任务卡

```
Task ID: P2-GRAPH-02
Goal: 把 graph/pipeline.py 的三节点冒烟图扩展为完整 S0–S9 状态机，接通 E1–E13 全部条件边与 checkpoint 续跑
Files: src/lit_agent/graph/{pipeline,edges,checkpoint}.py,
       tests/integration/test_graph_resume.py, tests/contract/test_edges_vs_design.py
Depends: Phase 1 出口清单 §7 全绿（尤其 A/B/F 组）；graph/state.py 契约冻结
Contracts: design/state-machine-and-guards.md 阶段表 + E1–E13；guide §2.2；ADR-0002；STATE_SCHEMA_VERSION
Acceptance:
  - uv run pytest -q tests/integration/test_graph_resume.py -m "not slow"
  - 可达性：每个 stage 可触达 END，无孤立节点；E1–E13 每条边至少 1 个用例
  - 续跑：第 k 节点 os._exit(9) 后 invoke(None) → 报告与不中断对照逐字节一致
  - 重复 invoke(None) 幂等：产物与事件（去重后）不变
  - 带输入 invoke(state) 在 API 层被禁止（只暴露 resume）
Forbidden: 改 §2 冻结契约；新增依赖；改 agents/* 骨架；把 SQLite 降级为派生视图
```

**Phase 2 任务卡队列（预告）**：`P2-GUARD-01`（六类守卫全集）、`P2-GUARD-02`（阈值重标定）、
`P2-WATCH-01`（主动取消）、`P2-GW-01`（熔断 + 分流）、`P2-INJECT-01`（故障注入 hook + 恢复包）、
`P2-UPD-01`（守卫事件可视化）。

---

## 附录 A：验收总表

| Step | 验收命令 | 通过判据 | 方法 | 证据 |
|---|---|---|---|---|
| 1.1 | `doctor --strict`；`pytest -q`；`check_structure.py` | 6/6；≥112；missing=0 | 删文件负例；模块 surface 测试 | doctor 输出、结构快照 |
| 1.2 | `pytest -q tests/unit -k contract`；`tests/contract -k models` | 全绿；零缺项 | 参数化往返；清单比对 | 测试输出 |
| 1.3 | `pytest -k "migrat or repo"` | 升降级一致；WAL；幂等 | schema 快照 diff；手工删列 | schema dump |
| 1.4 | `pytest -k events` | `seq==1..N`；重复零增长 | 分页 / 重复投递 | 事件 dump |
| 1.5 | `stores verify`；`pytest -k "graph_store or vector_store"` | MERGE 幂等；重建一致 | 双写零增长；删库重建 | 对账表 |
| 1.6 | `pytest -k openalex`；`sources sync`×2 | 第二次 new=0 | respx；水位线前移 | fixture / sync 输出 |
| 1.7 | `pytest -q tests/unit/test_chunking.py` | 预算/利用率；坏 PDF | 边界样本 | 单测输出 |
| 1.8 | `pytest -k "dedup or projection"` | 不误合并；对账发现漂移 | 歧义样本；手工删边 | `paper_merges`/对账 |
| 1.9 | `pytest -k "policy or gateway"` | 零出网；$0 缓存；截断重试 | mock + respx 双保险 | 测试/`llm_calls` |
| 1.10 | `pytest -k "smoke_graph or state_contract or edges"` | 三节点通；E 常量一致 | 可达性；contract 解析 | 测试输出 |
| 1.11 | `pytest -k "runner or locks or guard_contract"` | 锁互斥；守卫两档；SKEL 失败 | 并发；预算两侧 | 事件流 |
| 1.12 | `pytest -k "agents_contract or reporter"` | 契约一致；≥8 claims 可回查 | 契约比对；同输入两次 | 报告/claims |
| 1.13 | `pytest -k "budget or folding"` | 超限必截；SKEL 失败 | 边界预算 | 单测输出 |
| 1.14 | `pytest -k "tool_registry or builtin_tools"` | 重名报错；3 工具可用 | 真调用（fixture） | 测试输出 |
| 1.15 | `pytest -k "api or sse"`；`tests/contract -k openapi` | 路由全覆盖；501；续传 | contract 解析 guide 表 | openapi.json |
| 1.16 | `npm run build`；`vue-tsc`；`pytest -q tests/e2e` | 构建/类型/e2e 全过 | 生成校验 diff | dist / e2e 输出 |
| 1.17 | `pytest -k "scheduler or health"` | disabled 不注册；run-once 等价 | 断言 scheduler 空 | 测试输出 |
| 1.18 | `pytest -k metrics`；`lit-agent eval metrics` | 5 指标正确；campaign | 构造事件集 | 指标输出 |
| 1.19 | §7 全部 | 全绿 + 证据 | 逐条勾选 + 抽查 | `RESULTS-P1.md` |

## 附录 B：重难点汇总

| # | 重难点 | 为什么难 | 应对 | 证据 |
|---|---|---|---|---|
| 1 | **结构一次建齐不返工** | 16 模块 × 契约 × 接口，漏一个破坏骨架完整 | `check_structure.py` + `doctor` 三态 + 结构冻结 | 结构快照 |
| 2 | **SKEL 不静默** | 骨架最易写成"返回空" | 规则 + `FEATURE` 常量 + 未实现测试 | 每 SKEL 测试 |
| 3 | **契约三方一致** | 模型/表/OpenAPI 各写一份必漂移 | `tests/contract` 三方比对 | contract 测试 |
| 4 | **幂等三来源** | 游标/主记录/渲染任一不确定 → D4 失败 | 逐项测 + 确定性渲染 + 缓存 | `test_idempotency` |
| 5 | **事件不重不漏** | seq 竞态、双写遗漏、广播先于落库 | 唯一入口 + 事务内 seq + 双唯一约束 | `test_events_replay` |
| 6 | **三库一致** | 派生物易被当真相源；Kuzu 需 close 落盘 | 只从 SQLite 重建 + 对账 + close 后测 | `rebuild --verify` |
| 7 | **向量来源（DG-1）** | 契约锁 1024 维，但本地模型成本/约束冲突 | schema 不变、来源可换、ADR-0004 | ADR-0004 |
| 8 | **敏感零出网可证** | "没发出去"难证明 | 调用层 + HTTP 层双计数 | `test_gateway` |
| 9 | **reasoning 截断伪装成功** | 空正文像正常 | 判失败 + 翻倍重试 | 截断用例 |
| 10 | **Harness 骨架边界** | 写少返工，写多挤压 Phase 2 | 深度矩阵 + 显式未实现 | §1.4 与测试 |
| 11 | **前端类型漂移** | 手写类型必错 | 生成 + diff 校验 | `types.gen.ts` |
| 12 | **成本静默为 0** | usage 缺失 | 估算兜底 + 标记 | `llm_calls` 抽样 |
| 13 | **Windows/编码** | 路径非 ASCII、控制台编码 | ASCII + pwsh + UTF-8 | doctor |

## 附录 C：任务卡清单

> guide §15.1 模板；`[并行]` 可同时开工。所有卡的 `Forbidden` 均含："改冻结契约、新增依赖、
> 把 D-SKEL 写成返回空值、在 `src/` 内 import `prototype/`"。

```
Task ID: P1-SKEL-01                     [1.1]
Goal: 建 §3.1 全目录骨架 + CLI + doctor（六类自检、--strict/--json）+ check_structure
Files: pyproject.toml, src/lit_agent/{__init__,__main__,cli,doctor,config,logging,errors,selftest}.py,
       全部模块 __init__.py 与 SKELETON 文件, scripts/{doctor,selfcheck}.ps1, scripts/check_structure.py
Depends: —
Contracts: guide §1.1/§1.2/§1.3/§1.5；本文 §1.4 深度矩阵
Acceptance: doctor --strict 退出码 0（6/6 + 三态计数）；check_structure missing=0；删任一文件后 --strict 失败；
            非 ASCII 路径报 E_STORE_PATH_NONASCII
```

```
Task ID: P1-MODEL-01                    [1.2]
Goal: guide §2.3 模型 + GuardVerdict/Action + results 全部落地并冻结
Files: src/lit_agent/models/*.py, tests/unit/{test_contracts,test_models_surface}.py,
       tests/contract/test_models_vs_guide.py
Depends: P1-SKEL-01
Contracts: guide §2.3；design §7
Acceptance: 参数化 JSON 往返；未知字段被拒；Event 白名单；RunContext 可序列化（不含 session）；无密钥明文
```

```
Task ID: P1-DB-01 [并行]                [1.3]
Goal: SQLite 全表 + Alembic + 仓储层（唯一写入口）
Files: src/lit_agent/db/**, migrations/**, alembic.ini,
       tests/integration/{test_migrations,test_repo_sqlite}.py
Depends: ADR-0005（前置）；P1-MODEL-01
Contracts: guide §2.1；ADR-0001/0005
Acceptance: 升→降→升快照一致；journal_mode=wal；重复 upsert 零增长；手工删列→E_STORE_SCHEMA_MISMATCH；
            1000 行批量写 < 1 s
```

```
Task ID: P1-EVENTS-01 [并行]            [1.4]
Goal: 事件总线：事务内 seq、双唯一约束、先落库后广播、JSONL 导出、回放器
Files: src/lit_agent/runtime/events.py, src/lit_agent/db/repo/events.py,
       tests/integration/{test_events_replay,test_events_idempotent}.py
Depends: P1-DB-01
Contracts: guide §2.2；ADR-0002
Acceptance: seq==1..N；重复 emit 行数不变且 E_DATA_DUP+1；after_seq 分页不重不漏；回放==执行；
            广播异常不回滚事实
```

```
Task ID: P1-STORE-01 [并行]             [1.5]
Goal: Kuzu + Qdrant + files + selftest + rebuild 接口
Files: src/lit_agent/stores/*.py, docs/implementation/adr/0004-*.md,
       tests/integration/{test_graph_store,test_vector_store,test_store_selftest}.py
Depends: ADR-0004（DG-1）；P1-DB-01
Contracts: guide §2.5/§2.6；ADR-0003/0004
Acceptance: MERGE 幂等；filter 检索生效；reset 对文件/目录均正确且幂等；close 前后磁盘差异；
            非空库→E_STORE_NOT_EMPTY；记录 5k 耗时与磁盘
```

```
Task ID: P1-SRC-01                      [1.6]
Goal: OpenAlex/arXiv + 白名单(source.id) + 增量水位线 + E_SRC_* 分类
Files: src/lit_agent/sources/{base,openalex,arxiv,whitelist,normalize}.py,
       tests/fixtures/openalex/*, tests/integration/test_openalex_adapter.py
Depends: P1-DB-01
Contracts: guide §3
Acceptance: respx 分页/429/500；连续两次 sync 第二次 new=0；水位线前移只补当天；
            按名称匹配的负例不命中；_w_to_canonical 用例
```

```
Task ID: P1-PARSE-01 [并行]             [1.7]
Goal: OA PDF 三级降级 + tiktoken 分块 + 稳定 chunk_id + 文件存储
Files: src/lit_agent/parsing/*.py, tests/fixtures/pdf/*, tests/unit/test_chunking.py
Depends: P1-SRC-01（下载接口）
Contracts: guide §2.3 Chunk；Phase 0 chunking 口径
Acceptance: token ≤ 预算且利用率 ≥0.9；坏 PDF→failed 不中断；同文本两次 chunk_id 相同；断网可跑
```

```
Task ID: P1-DEDUP-01 [并行]             [1.8]
Goal: 三段式去重 + paper_merges + 确定性主记录 + 投影对账
Files: src/lit_agent/sources/dedup.py, src/lit_agent/stores/rebuild.py,
       tests/unit/test_dedup.py, tests/integration/test_projection.py
Depends: P1-STORE-01
Contracts: ADR-0001
Acceptance: 同 DOI 多版本合并且可回查；同名不同文不误合并；两次跑主记录相同；
            手工删边→E_DATA_SYNC→重投影恢复；去重率 19.3–19.8%±3pp
```

```
Task ID: P1-GW-01 [并行]                [1.9]
Goal: 网关（cache/llm/metering）+ 敏感硬门 + 预算 + NoopBreaker
Files: src/lit_agent/gateway/*.py, tests/{unit/test_policy.py,integration/test_gateway.py},
       tests/fixtures/llm/*
Depends: P1-DB-01
Contracts: guide §2.1 llm_calls；§2.2；ADR-0002
Acceptance: 敏感零调用零请求；缓存 $0 且逐字节一致；截断重试翻倍；预算 80/100；llm_calls==事件数；
            NoopBreaker 断言不熔断
```

```
Task ID: P1-HARNESS-01                  [1.10]
Goal: state 冻结 + pipeline builder + 三节点冒烟 + edges 常量 + checkpoint 接线
Files: src/lit_agent/graph/{state,pipeline,edges,checkpoint}.py,
       tests/unit/test_state_contract.py, tests/integration/test_smoke_graph.py,
       tests/contract/test_edges_vs_design.py
Depends: P1-MODEL-01
Contracts: design 阶段表 + E1–E13；guide §2.2
Acceptance: 冒烟链跑通且按阶段发事件；可达 END；checkpoint 读写；resume 只接受 None；
            E 常量与 design 一致；回退路由→E_FEATURE_DISABLED
```

```
Task ID: P1-RUNTIME-01 [并行]           [1.11]
Goal: 守卫契约 + Budget/NoProgress + runner/jobs/budget/watchdog 骨架
Files: src/lit_agent/graph/guards.py, src/lit_agent/runtime/{runner,jobs,budget,watchdog}.py,
       scripts/{run_topic,seed_topics}.py,
       tests/integration/{test_runner,test_locks,test_guard_contract}.py
Depends: P1-EVENTS-01, P1-HARNESS-01
Contracts: guide §13；design §7；Phase 0 guards 语义
Acceptance: 并发 409；孤儿锁清理；预算 80/100 两侧；NoProgress 触发；4 类守卫显式未实现；
            失败报告四要素
```

```
Task ID: P1-AGENT-01 [并行]             [1.12]
Goal: Agent Protocol + 5 角色骨架 + reporter（真实报告闭环）
Files: src/lit_agent/agents/*.py, tests/unit/test_agents_contract.py,
       tests/integration/test_reporter.py
Depends: P1-GW-01
Contracts: guide §7；design agent 决策
Acceptance: inputs/outputs 契约一致；未实现角色显式失败；reporter ≥8 claims 100% 可回查；
            同输入两次字节一致；不可落地 claim 标 unsupported 且入库
```

```
Task ID: P1-CTX-01 [并行]               [1.13]
Goal: TokenBudget 真实 + FoldingStrategy(truncate) + CtxSlot 契约
Files: src/lit_agent/context/*.py, tests/unit/{test_budget,test_folding_contract}.py
Depends: P1-MODEL-01
Contracts: guide §8
Acceptance: 预算内不变、超限必截且记事件；truncate 保头尾可配；未实现策略显式失败；槽位重名报错
```

```
Task ID: P1-TOOL-01 [并行]              [1.14]
Goal: Tool Registry + 3 内置工具 + MCPAdapter 协议
Files: src/lit_agent/tools/*.py, tests/unit/test_tool_registry.py,
       tests/integration/test_builtin_tools.py
Depends: P1-DB-01, P1-SRC-01
Contracts: guide §9
Acceptance: 重名报错；参数校验结构化；3 工具各有集成用例；tool_call 事件（args_hash 不含敏感）；
            MCP 调用显式未实现
```

```
Task ID: P1-API-01                      [1.15]
Goal: guide §2.4 全量路由 + 错误映射 + 501 语义 + OpenAPI 导出
Files: src/lit_agent/api/**, docs/api/openapi.json, tests/integration/{test_api,test_sse}.py,
       tests/contract/test_openapi_vs_guide.py
Depends: P1-RUNTIME-01
Contracts: guide §2.4
Acceptance: 契约表每行都有路由与测试；200/404/409/422/501 分支；SSE 续传不重不漏；/health < 200 ms；
            501 带 E_FEATURE_DISABLED
```

```
Task ID: P1-WEB-01                      [1.16]
Goal: web 工程化 + 三页面 + 7 组件 + 类型生成 + e2e
Files: web/**, tests/e2e/test_full_system.py
Depends: P1-API-01, docs/api/openapi.json
Contracts: OpenAPI 生成的 types.gen.ts（禁手写）
Acceptance: npm run build + vue-tsc --noEmit 通过；types 重生成 diff 为空；三路由可导航；
            Topics 真实可用；Report claim 可溯源；Chat 显示未启用；e2e 通过
```

```
Task ID: P1-OPS-01 [并行]               [1.17]
Goal: APScheduler 装配 + 周更 job 定义 + 默认 disabled + health + 日志运维
Files: src/lit_agent/runtime/scheduler.py, tests/unit/test_scheduler_wiring.py,
       tests/integration/test_health.py
Depends: P1-RUNTIME-01
Contracts: guide §14
Acceptance: enabled=false 不注册任何 job；enabled=true job 定义正确；run-once 等价 run-topic；
            health 输出三库状态；debug 清理按 mtime
```

```
Task ID: P1-EVAL-01 [并行]              [1.18]
Goal: 5 项指标从事件算 + campaign 作用域 + 数据集目录 + 回归基线机制
Files: src/lit_agent/eval/*.py, eval_data/README.md, tests/unit/test_metrics.py,
       tests/regression/README.md
Depends: P1-EVENTS-01
Contracts: guide §12；ADR-0002
Acceptance: 5 指标对构造事件集正确（空集/单 run/多 run）；分母口径含 unsupported；只读事件；
            字段缺失报错而非回退 0；未实现 judge 显式失败；回归脚本可对比快照
```

```
Task ID: P1-WRAP-01                     [1.19]
Goal: RESULTS-P1 + 出口清单 + guide 回写 + 结构冻结快照 + Phase 2 任务卡
Files: docs/implementation/RESULTS-P1.md, docs/implementation/phase1-implementation-steps.md,
       docs/implementation/implementation-guide.md
Depends: 其余全部
Contracts: guide §15.6
Acceptance: §7 全绿且每项有证据路径；数字抽查 5 个有出处；结构快照与 §3.1 一致；
            深度矩阵与实际交付一致（SKEL 不得写成已实现）
```

## 附录 D：命令速查

```powershell
# 环境与自检
uv sync
uv run lit-agent doctor [--strict] [--json]
uv run python scripts/check_structure.py

# 数据库与存储
uv run lit-agent db upgrade | db reset --yes
uv run lit-agent stores verify
uv run lit-agent stores rebuild --all --verify

# 数据与运行
uv run lit-agent sources sync --topic <slug> --limit 200
uv run lit-agent run-topic --topic <slug> [--run-id <id>] [--max-usd 0.02] [--no-cache]
uv run lit-agent llm probe --budget 0.01

# 接口 / 前端
uv run lit-agent api export-openapi --out docs/api/openapi.json
uv run uvicorn lit_agent.api.app:app --port 8000
cd web; npm install; npm run dev; npm run build; npx vue-tsc --noEmit

# 调度与评测
uv run lit-agent schedule list | run-once --topic <slug>
uv run lit-agent eval metrics --runs <id,id> --out out/metrics

# 验收
uv run ruff check . ; uv run ruff format --check .
uv run pytest -q tests/unit
uv run pytest -q tests/contract
uv run pytest -q tests/integration -m "not slow"
uv run pytest -q tests/e2e -m "not slow"
uv run pytest -q -m "not slow"
```

## 附录 E：决策门清单

| ID | 决策 | 状态 | 截止 | 记录 | 结论 |
|---|---|---|---|---|---|
| **DG-1** | 向量部署形态与嵌入模型 | ✅ **已定** | 1.5 前 | `adr/0004` | Qdrant local 嵌入式 + `BAAI/bge-m3`（1024 维，MIT，8192 ctx）；备选 `bge-large-en-v1.5` 同维度热切换；新增 `sentence-transformers` 依赖；复评触发：>50k 点或 p95>500 ms |
| **DG-2** | 实体表契约 | ✅ **已定** | 1.3 前 | `adr/0005` | 12 张新表（`papers/papers_raw/authors/paper_authors/citations/paper_merges/paper_chunks/claims/claim_citations/llm_cache/embeddings/store_meta`）+ 12 张既有表列修订（共 24 张）+ 索引/外键 |
| **DG-3** | seq 分配与幂等键 | ✅ **已定** | 1.3 前 | `adr/0005 §5–7` | `BEGIN IMMEDIATE` + `UPDATE runs SET next_seq=next_seq+1 RETURNING`；双唯一约束；幂等键总表；`E_DATA_DUP` 的 `dedupe_key` 必须为 NULL |
| **DG-4** | Chat 页 Phase 1 形态 | ⏳ 待定 | 1.15 | `RESULTS-P1.md §5` | 默认：页面+路由+类型+后端 501 |
| **DG-5** | 前端若不便本地构建 | ⏳ 待定 | 1.16 | `RESULTS-P1.md §5` | 默认：交付 `web/dist` + API 托管；类型生成必须完成 |

---

> **执行方式**：按附录 C 的 `Depends` 顺序派卡，一卡一会话/一提交；每卡完成后要求：①跑验收命令贴输出；
> ②回写 §5 与 `RESULTS-P1.md`；③若触碰契约先出 ADR。
> **修订纪律**：结构（§3.1）在 1.19 后冻结；深度（§1.4）不得事后放宽；任何偏离走 §8.4 差异登记 + ADR。



