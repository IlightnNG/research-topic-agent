# Phase 2.1 —— 接线、门禁与契约（Wiring · Gates · Contracts）

> **文档性质**：**规范性文件（冻结契约）**。Phase 2.1 的"做什么 / 什么算做完 / 按什么顺序"以本文件为唯一判据。
> **版本**：**1.3.0**（2026-10-22，S1–S6 已落地）
> **前序**：`phase2-implementation-steps.md` v3.0.0（已收尾）、`phase1.1-scope-and-acceptance.md`、`phase1.2-frontend-spec.md` v1.3.0、**ADR-0006（事件格式冻结）**、本阶段新增 **ADR-0007（NodeIO 与配置冻结）**。
> **入口基线**：`verify_phase2 12/12`、`verify_phase1 13/13`、`pytest 354 例`、`e2e 8 passed`、`vue-tsc 0 error`、迁移 head `0003_reports_sections`。

---

## 0. 目标、"完成"定义与四条硬规则

### 0.1 一句话目标

把 Phase 2 **"已实现但没接进主链路"** 的能力真正接线：门禁在每个节点出口执行、条件边真的重试/重写/降级、指标按 run 口径落库、检索与 LLM 进入生产路径；同时立起 **NodeIO 契约 + 验证器 + 冻结 gold**，为 Phase 5 自进化留出**可验证**的接口。

> **Phase 2 造零件，Phase 2.1 装机器，并装上检测线。**

### 0.2 四条硬规则

| 规则 | 内容 | 违反后果 |
|---|---|---|
| **R1 范围冻结** | 只做 §7 的 S1–S13；新想法进 §6 | 范围蔓延、判据失效 |
| **R2 只接线不重画** | 不新增节点、不改图拓扑（除两条受控回边）、不换框架 | 变成 Phase 3 |
| **R3 单步可逆** | 每步有**特性开关**与回滚点；收尾：`pytest` 全绿 + `ruff` clean + 本阶段断言绿 + 文档更新 | 不可回退 |
| **R4 零迁移** | 本阶段**不新增表/列/迁移**；确需改 schema 必须停止并重写计划 | 迁移返工 |

### 0.3 反向定义（何时结束）

> **Phase 2.1 结束 ⇔ §11 的 H1–H14 全绿，且 §5 中 P0 清零。**
> 此后新问题：登记 → 分级 → 排 2.2 / 3 / 5，**不重开 2.1**。
> "没实现"是 backlog；**"实现了但没生效"是 P0 缺陷**。

### 0.4 为什么是 2.1 而不是 Phase 3

| 判据 | 现状 | 继续盖楼的后果 |
|---|---|---|
| 守卫是否在生产链路 | ❌ 只在旧 `run_topic` | 错误不拦，且无人发现 |
| 条件边是否改变行为 | ❌ 12/13 只写事件 | "重试/降级"是文案 |
| 指标是否可信 | ❌ topic 口径 + 不落库 | 论文实验表填不出来 |
| LLM 是否进分析 | ❌ 没传 gateway | 成本/多角色空转 |
| 是否单流水线 | ❌ scheduler 走四阶段 | 双口径，排查翻倍 |

**Phase 3（Chat + ReAct）复用同一套图/事件/守卫/指标；底座不真，上面全假。**

---

## 1. 入口条件

| # | 条件 | 验证 |
|---|---|---|
| E1 | Phase 2 已收尾 | `phase2-implementation-steps.md` §12 = COMPLETE |
| E2 | 基线全绿 | `pytest -q`、`verify_phase2`、`verify_phase1 --online`、`npm run test:e2e` |
| E3 | 可回退 | `git tag phase2-rc1`（负责人执行） |
| E4 | 缺口册已冻结 | `phase1.1-known-gaps.md` 无"未定级" |
| E5 | gold/bench 可规范化哈希 | 见 §10.1 |

---

## 2. 现状盘点（本阶段全部输入）

### 2.1 十二处"实现了但没生效"

| # | 现象 | 证据（文件:行） | 级别 | 修于 |
|---|---|---|---|---|
| 1 | 15 类守卫未进十节点图 | `graph/guards.py:414` 仅 `runtime/runner.py:268` 使用 | P0 | S3 |
| 2 | 混合检索未接线 | `graph/nodes.py:106` 用 `select_cards` | P0 | S7 |
| 3 | 单 run 指标实为 topic 聚合 | `eval/metrics.py:116-128` | P0 | S5 |
| 4 | 指标从不落库 | `graph/nodes.py:276`；`persist_run_metrics` 无调用 | P0 | S6 |
| 5 | 条件边只有 abort 生效 | `runtime/graph_runner.py:152-170` | P0 | S4 |
| 6 | critic 判决不拦报告 | `graph/nodes.py:236-250` | P1 | S2 |
| 7 | 分析节点不走 LLM | `graph/nodes.py:166` | P1 | S8 |
| 8 | 定时任务走旧四阶段 | `runtime/scheduler.py:52` | P1 | S9 |
| 9 | PDF 工具未注册 | `tools/builtin/paper_pdf.py:98` | P2 | S10 |
| 10 | 漂移检测无产出者 | `drift_warn/drift_block` 无写入 | P2 | 2.2 |
| 11 | 预算未进图 | `RunBudget` 只进 state | P2 | S3（门禁） |
| 12 | 分节回填不限行 | `runner.py` `UPDATE ... WHERE run_id` | P2 | S6（带主键） |

### 2.2 为什么现有测试没抓到

12 条能力探针验的是 **"函数/类存在且行为正确"**，不是 **"生产路径调用了它"**。
→ 2.1 的验收一律**接线级**：从 API 触发 run，检查**事件流 / 指标表 / DB 行 / API 响应**里是否有该能力的痕迹。

---

## 3. 目标架构（含四个必须先定死的机制）

```
请求线程: prepare_run(建 run + 锁) → 202
     │
后台线程: run_graph
     │  构造 RunContext(settings, run_id, budget_from_db, gateway, log, checkpointer)
     ▼
  ┌────────────────────────── 每个节点（两阶段执行）──────────────────────────┐
  │ 1. abort/pause 检查（阶段边界）                                            │
  │ 2. attempt = state.attempts[stage] + 1；发 phase_change(start, attempt)   │
  │ 3. patch = node(ctx, state)          ← 只计算，返回 outputs + pending_writes│
  │ 4. gates = run_gates(stage, patch, state)                                 │
  │ 5. decision = supervisor.decide(gates, observation, attempt, budget)      │
  │ 6. continue/degrade → commit(pending_writes, 幂等) → 发 end(ok)           │
  │    retry/repair/replan → 发 guard_trigger + recovery → **不提交** → 回边   │
  │    abort → 发 guard_trigger → 失败报告 → 终止                              │
  └───────────────────────────────────────────────────────────────────────────┘
     │
  条件边（纯函数）：读 state.decisions[-1] → 下一节点 / 回边 / END
     │
  evaluate: 指标落库（run 口径）
```

### 3.1 机制一：两阶段执行（compute → gate → commit）

**为什么必须**：若节点里直接写库，门禁失败时坏数据已进库，回滚困难（Phase 2 的 `report` 就是直接写）。
**做法**：节点返回 `pending_writes`（声明式），由 `commit()` 执行，且 **commit 必须在门禁通过之后**。
**代价**：只有 `report`（写报告+claims）与 `evaluate`（写指标）需要改造，其余节点只读。

### 3.2 机制二：RunContext 注入（不在节点里 new 服务）

```python
# runtime/context.py
@dataclass(frozen=True)
class RunContext:
    settings: Settings
    run_id: str
    topic_id: str
    budget: RunBudget          # **活对象**，不是 state 里的快照
    gateway: LLMGateway | None # 无 key 时为 None
    log: SqliteEventLog
    registry: ToolRegistry
```
- 通过 LangGraph `config["configurable"]["ctx"]` 传入；节点签名 `node(ctx, state)`。
- **禁止**在节点内 `make_engine()` 反复建引擎（现有实现每阶段新建，属性能与一致性隐患），统一用 `ctx.engine`（懒建、单次释放）。

### 3.3 机制三：决策物化（supervisor 只产出，边只读）

```python
# graph/supervisor.py
class Decision(BaseModel):
    action: Literal["continue","retry","repair","degrade","replan","abort"]
    target: str | None          # 回边目标节点（retry/repair/replan 必填）
    code: str                   # 来自 errors.py 码表
    reasons: list[str]
    source: Literal["gate","guard","llm"]   # 便于审计
    attempt: int
```
- `state.decisions: list[Decision]`（`_concat` 累积）；`state.attempts: dict[str,int]`（`_merge_dicts`）。
- 条件边函数**纯读** `state.decisions[-1]`，不重新计算（避免"两处各判一次"漂移）。

### 3.4 机制四：有界回边 + 预算

| 回边 | 触发 | 上限 | 回落 |
|---|---|---|---|
| `analysis → analysis`（repair） | 引用缺失 / 坏 claim | `max_attempts.analysis = 2` | `degrade` |
| `critique → analysis`（repair） | critic 判 BLOCK | 同上 | `degrade` |
| `retrieval → retrieval`（expand） | 证据不足 | `max_attempts.retrieval = 2` | `degrade` |
| 任意 → `abort` | 预算 / E2 漂移阻断 | 1 | —— |

- 图内 `recursion_limit = 60`；超限必须映射为 `E_GUARD_LOOP` 失败报告，**不能**把 `GraphRecursionError` 抛给用户。
- 单 run LLM 调用硬顶 `max_total_llm_calls = 12`（预算门禁 + 网关计数器双保险）。
- **预算从 DB 重建**：`RunBudget.from_db(settings, run_id)`（`SUM(llm_calls.cost)`），续跑不会"预算清零"。

---

## 4. 模块与验收判据（M1–M6）

> 每模块：目标 / 增量 / **可执行判据** / 重难点 / 禁止项 / OOS / 依赖。

### M1 门禁与监督者

| 项 | 内容 |
|---|---|
| **目标** | 节点出口统一过门禁；supervisor 依门禁+守卫做**分层决策**，决策可审计 |
| **增量** | `gates.py`（6 类门禁 + `GateResult`）、`supervisor.py`（`Decision`）、`graph/pipeline.py` 接两阶段提交 |
| **完成判据** | ① 10 个节点全部声明 `gates`（缺一个→契约测试红）；② 坏 claim → `E_GROUND_UNRESOLVED_CITATION` 且 `reports` 无新行；③ 预算超限 → `aborted` + `guard_trigger`；④ **健康 run 的 `gate failures == 0`**（防过严）；⑤ `pytest -q tests/gates` 绿 |
| **重难点** | 门禁判"产物对不对"，守卫判"过程偏没偏"；两者结果进**同一决策器**，取最重动作（复用 `PRIORITY`） |
| **禁止** | 节点内直接 abort；门禁写库；健康 run 出现门禁误报 |
| **OOS** | 学习型阈值（P5） |
| **依赖** | 无（第一步） |

**门禁清单（6 类，冻结）**

| 门禁 | 判什么 | 失败动作 | 错误码（已存在） |
|---|---|---|---|
| `schema` | 输出符合 `NodeOutput` | retry(1) → abort | `E_SCHEMA_STAGE_OUTPUT` |
| `evidence_sufficiency` | `len(paper_ids) ≥ evidence_min_cards` | repair→`retrieval` | `E_GROUND_NO_EVIDENCE` |
| `citation_integrity` | 每条 claim ≥1 citation 且 paper_id 存在 | repair→`analysis` | `E_GROUND_UNRESOLVED_CITATION` |
| `support_ratio` | supported/total ≥ 0.6 | **repair→analysis**（用尽后 degrade） | `E_GROUND_UNSUPPORTED_RATIO` |
| `budget` | 已花 ≤ 硬顶 且 LLM 调用数 ≤ 12 | abort | `E_BUDGET_EXCEEDED` |
| `drift` | `drift_block/drift_warn` 计数 | abort / annotate | `E_GUARD_DRIFT` |

> **2.1 新增错误码数 = 0**（全部复用现有码表，避免契约变更）。

### M2 条件边执行器

| 项 | 内容 |
|---|---|
| **目标** | `retry / repair / degrade / replan / abort` **真的发生**，有次数/预算上限，可续跑 |
| **增量** | `edges.route_from_decision()`、`graph/pipeline.py` 加 3 条条件回边、`graph_runner` 执行 `Decision` |
| **完成判据** | ① retry 后 `phase_change start` 的 `attempt=2`，且 `attempts ≤ max_attempts`；② repair 只重跑 `analysis`（retrieval 事件数不变）；③ 超限 → `degrade` + 报告 `degraded=true`；④ 中断续跑不产生"同一 attempt 两次 start"；⑤ `pytest -q tests/transitions` 绿 |
| **重难点** | attempt 计数必须在**节点真正执行时**递增；checkpoint 重放时同 attempt 的 dedupe 必须命中 |
| **禁止** | runner 里 `for` 循环模拟回边；无上限；回边不消耗预算 |
| **OOS** | 并行分支（P4） |
| **依赖** | M1 |

### M3 指标口径与落库

| 项 | 内容 |
|---|---|
| **目标** | 指标只算本 run、落库、可被 API 读取、与报告一致 |
| **增量** | `compute_run_metrics` 全 SQL 加 `r.id = :run`；`commit` 内 `persist_run_metrics`；`GET /api/runs/{id}/metrics` |
| **完成判据** | ① 同话题跑 2 次：`metrics.claims_total == 该 run 报告 n_claims` 且两次不同；② `metrics` 表有 `scope='run'` 行；③ API 与库一致（逐字段）；④ 无 LLM 时 `cost_usd=0.0`（不是 `None`）；⑤ 历史 run 无指标行时 API **按需计算**并标 `source="computed"`，不要求回填迁移 |
| **重难点** | `grounding_rate` 必须由**引用判定器**算（`check_claim`），不能拿 `claims.support` 自证；两个数要分开命名 |
| **禁止** | topic 聚合冒充 run；`None` 写成 0；回填迁移 |
| **OOS** | 跨 run 趋势（2.2） |
| **依赖** | M1/M2 |

**指标定义（冻结）**

| 指标 | 公式 / 来源 |
|---|---|
| `claims_total` | `count(claims where run_id=:run)` |
| `claims_supported_db` | 同上 + `support='supported'`（仅供调试） |
| `grounding_rate` | `count(check_claim ok) / claims_total`（判定器口径） |
| `cost_usd` | `sum(llm_calls.cost where run_id=:run)` |
| `cost_by_agent` | 同表 `group by agent` |
| `n_claims(report)` | 报告 `claims` 长度；必须 == `claims_total` |

### M4 检索与 LLM 接线

| 项 | 内容 |
|---|---|
| **目标** | `retrieval` 用 hybrid；`analysis` 有 key 走 LLM、无 key 显式降级 |
| **增量** | `ctx.retrieval.hybrid`；`nodes.analysis(ctx, ...)` 用 `ctx.gateway`；`llm_calls.agent` 非空 |
| **完成判据** | ① 事件 `selected` 与 `hybrid_search` 同输入结果一致；② 有 key：`llm_calls` 出现 `analyst`、`cost_usd>0`、`calls_by_agent` 非空；③ 无 key：报告标注"确定性抽取"且不 failed；④ 检索基准 `hybrid_recall ≥ 0.90`（不下降） |
| **重难点** | gateway 单例（避免每节点新建导致缓存失效/预算分裂）；LLM JSON 解析失败只回落该条，不整轮失败 |
| **禁止** | 改 benchmark 拿分；绕过预算直接调 SDK |
| **OOS** | 真实向量模型（P3）、rerank（P3） |
| **依赖** | M3 |

### M5 单流水线与工具协议

| 项 | 内容 |
|---|---|
| **目标** | 生产只有一条流水线；工具协议最小闭环 |
| **增量** | `scheduler` → `run_graph`；`run_topic` 标 deprecated 且加运行期 warning；`tools.registry.default_registry()` + `call()`（超时/事件/`ToolResult`）；`paper_pdf` 注册；`parse` 在 `tools.pdf.enabled` 时调用 |
| **完成判据** | ① 静态断言：生产代码只有 `run_graph` 被调用（契约测试扫 import）；② 定时 run 有 10 阶段事件；③ `tools.call("paper_pdf", text=...)` 发 `tool_call` 且 `ok=true`；④ 同 PDF 两次 `new_chunks=0`；⑤ 工具超时返回 `E_TOOL_TIMEOUT` 而非抛穿 |
| **重难点** | 弃用不能删（测试还用），但要**唯一生产入口**；工具失败必须结构化 |
| **禁止** | 双生产路径；工具内写业务表 |
| **OOS** | MCP（P4）、PDF 真实下载（P4） |
| **依赖** | M2（parse 位置） |

### M6 契约、验证器、冻结 gold

| 项 | 内容 |
|---|---|
| **目标** | 节点有可校验契约；验证器自动发现"接线断了"；gold 防篡改 |
| **增量** | `contracts/{nodeio,specs}.py`；`tests/contracts/`（参数化自动生成）；`scripts/verify_phase2_1.py`；`GOLD_SHA256`/`BENCH_SHA256` |
| **完成判据** | ① 10 节点 spec 齐全（缺→红）；② 每个 spec 过 6 条通用契约；③ `verify_phase2_1 --contracts` = `10/10`；④ 改 gold 任一字段 → `--frozen` 红；⑤ `pytest -q tests/contracts` 绿 |
| **重难点** | 契约只约束**边界**（输入/输出/门禁/副作用），不约束内部推理；否则 ReAct 写不出来 |
| **禁止** | 改 gold 过测；正文进 state；契约绑实现细节 |
| **OOS** | 自动生成节点（P5） |
| **依赖** | M1–M5 |

**通用契约六条（每个节点都必须过）**

| # | 契约 | 判定 |
|---|---|---|
| C1 | schema 往返 | `NodeOutput.model_validate(out.model_dump())` 相等 |
| C2 | 无大字段 | `outputs` 序列化 ≤ 8 KB（正文只放引用） |
| C3 | 副作用声明 | `side_effects ⊆ {"reports","claims","metrics","events"}` 且与实际写表一致 |
| C4 | 幂等键稳定 | 同 `(run_id, stage, attempt)` 生成同键 |
| C5 | 错误码合法 | 所有 `GateResult.code ∈ errors.py` |
| C6 | 门禁非空 | `len(spec.gates) ≥ 1`，且 `schema` 必含 |

---

## 5. 缺陷分级与处置

| 级别 | 定义 | 处置 |
|---|---|---|
| **P0** | 出口断言红 / **接线未生效** / 指标口径错 / 指标造假 | 本阶段关闭 |
| **P1** | 影响体验/可解释性 | 本阶段尽量 |
| **P2** | 未实现功能、性能、美化 | §6 backlog |

**新增两条纪律**

1. **"接线类缺陷"一律 P0**（实现了没被生产调用 = 缺陷）。
2. **门禁/回边/指标改动必须附"负例"**：不触发、不越限、不重复。

---

## 6. 缺口登记（2.1 起点）

| ID | 项 | 级别 | 归属 |
|---|---|---|---|
| G-17 | F5/F7/F8/F9 手动验证 | P2 | 2.2 |
| G-20 | 部署 `try_files` | P2 | 部署清单 |
| G-21 | `agents.chat` | P2 | P3 |
| G-23 | 真实语义向量 | P2 | P3 |
| G-24 | 分节固定 5 条分组 | P2 | P5 |
| 2.1-01…12 | §2.1 十二项 | 见上表 | 本阶段 |

---

## 7. 实施步骤 S1–S13

> 每步：**前置 / 产物 / 门禁 / 回滚点**。每轮只做一个 S；收尾输出三件套（门禁结果 / 文件清单 / 英文 commit）。

### 7.1 步骤表

| 步 | 模块 | 目标 | 产物 | 关键门禁 | 回滚点 | 预估 |
|---|---|---|---|---|---|---|
| **S1** ✅ | M0 | 先写**会红**的接线测试 | `tests/wiring/` 6 文件；4 条 `xfail(strict)`、2 条已绿 | 套件保绿 + 4 条待翻绿 | 删除新测试 | 0.5 h |
| **S2** ✅ | M1 | 契约骨架 + 门禁框架 + 两阶段提交 | `contracts/nodeio.py`、`graph/gates.py`、`runtime/commit.py`、report/evaluate 改 pending_writes | 坏 claim 不落库；健康 run 零门禁失败 | `gates.enabled=false` | 4 h |
| **S3** ✅ | M1 | supervisor + 守卫接线 + 预算门禁 | `supervisor.py`、`context.py`、`RunBudget.from_db`、attempt/decision 入 state | 预算超限→aborted + `guard_trigger`；中止 run 零写入 | 同上 + `guards.enabled=false` | 4 h |
| **S4** ✅ | M2 | 有界回边 | `graph/transitions.py`、`add_conditional_edges`、attempt 上限、`recovery` 事件 | 坏产物 → analysis attempt=2 → 用尽后 degrade；续跑不重复 | `transitions=false` | 4 h |
| **S5** ✅ | M3 | 指标 run 口径 | `compute_run_metrics` 全部按 `run_id` 取数；grounding 改判定器口径 | 两 run 指标独立（m1=1, m2=1） | 保留旧函数别名 | 2 h |
| **S6** ✅ | M3 | 指标落库 + API + 分节回填带主键 | `evaluate` commit 落库、`GET /runs/{id}/metrics`（缺行按需计算）、回填按 `report_id` | 库/接口/报告一致；旧 run 不回填 | `metrics.persist=false` | 2.5 h |
| **S7** | M4 | hybrid 进节点 | `nodes.retrieval` 用 `ctx.retrieval` | `selected` 与基准一致 | `retrieval.hybrid=false` | 1.5 h |
| **S8** | M4 | LLM 进分析 | `nodes.analysis(ctx)` + 回落 + `llm_calls` | 有 key 有行、无 key 降级 | `llm.enabled=false` | 2.5 h |
| **S9** | M5 | 单流水线 | scheduler→`run_graph`；`run_topic` 弃用警告 | 定时 run 十阶段 | 恢复 scheduler 旧调用 | 1.5 h |
| **S10** | M5 | 工具协议闭环 | `default_registry`、`tools.call`、PDF 注册 | `tool_call` + 幂等 | `tools.pdf.enabled=false` | 2.5 h |
| **S11** | M6 | NodeIO 契约 + 自动测试 | `contracts/specs.py`、10 节点 spec | 10/10 通过 | 关闭参数化用例 | 3 h |
| **S12** | M6 | 验证器 + 冻结哈希 | `verify_phase2_1.py`（12 断言）、哈希常量 | `--contracts` 10/10；`--frozen` PASS | 保留脚本但不算门禁 | 2.5 h |
| **S13** | M0 | 收尾 | H1–H14 全跑、`RESULTS-P2.1.md`、前端成本展示 | 全绿 + 文档 | —— | 2 h |

**合计 ≈ 32 人时（约 2 个工作日）**

### 7.2 每步 Definition of Done（防止"以为做完了"）

每步必须同时满足：

1. 新增/修改代码有**测试**，且测试**先红后绿**（S1 的红测即基线）；
2. `uv run pytest -q` 全绿、`uv run ruff check .` clean；
3. 对应门禁命令有输出，并粘贴到 `RESULTS-P2.1.md`；
4. 该步的特性开关**默认值已定**（生产默认开/关写进文档）；
5. 回滚方式已验证（能用一个开关关掉，且关掉后老测试全绿）。

### 7.3 实现逻辑不变量（评审逐条对照代码）

| # | 不变量 | 为什么 |
|---|---|---|
| I1 | 门禁在 **commit 之前**、`phase_change end` 之后不得再有写操作 | 否则"完成"事件撒谎 |
| I2 | `(run_id, stage, attempt)` 唯一；同 attempt 不重复 start | 续跑/重试不重复记账 |
| I3 | 回边次数 ≤ `max_attempts`，每次消耗预算；总 LLM 调用 ≤ 12 | 防失控/烧钱 |
| I4 | 指标只统计本 run（`r.id = :run`） | 口径失真会让实验作废 |
| I5 | 同 run `report.n_claims == metrics.claims_total` | 防口径分裂 |
| I6 | 门禁失败**零写入**（无报告、无 claims、无 metrics 行） | 避免"坏数据进库再回滚" |
| I7 | 生产只有一条流水线 | 双路径必然漂移 |
| I8 | 工具失败返回 `ok=false`，不抛穿 | 异常穿透杀死整轮 |
| I9 | LLM 不可用 → 显式降级，不 failed | 可用性优先 |
| I10 | gold/bench 内容哈希不变（除非升版本 + ADR） | 防改测试集刷分 |
| I11 | 预算从 DB 重建，不用 checkpoint 快照 | 续跑不清零 |
| I12 | 所有"写"都是幂等 upsert（含重试重放） | at-least-once 安全 |

### 7.4 顺序的因果约束（不可颠倒）

1. **S1 先写红测**：否则"接通了"无法证明。
2. **M1 先于 M2**：执行器消费决策，决策来自门禁。
3. **S5 先于 S6**：口径错了，落库只是存错数据。
4. **S3 先于 S4**：无守卫判决，回边没有触发条件。
5. **S2 先于 S6**：两阶段提交是"零写入"的前提。
6. **M6 最后**：spec 要覆盖真实门禁/副作用，先写必错。

### 7.5 返工风险登记（本阶段重点规避）

| # | 返工风险 | 规避手段 |
|---|---|---|
| 1 | 事后加字段导致契约大改 | **S2 前冻结** NodeIO + 事件 payload + 配置名（ADR-0007） |
| 2 | 门禁与写库顺序错，坏数据入库 | 两阶段提交 + I6 |
| 3 | 回边与 checkpoint 冲突（重放/重复） | 回边建在图内 + attempts 入 state + 幂等 upsert |
| 4 | 预算快照过期，续跑后无限花钱 | 门禁读 `ctx.budget`（DB 重建），I11 |
| 5 | 指标口径再改，实验重做 | 公式与源表**冻结**（§4 M3 表） |
| 6 | 前端跟着后端字段改动反复改 | 只消费 `GET /runs/{id}/metrics`，字段**只增不改** |
| 7 | 迁移返工 | R4 零迁移；历史 run 用"按需计算" |
| 8 | 双流水线漂移 | S9 静态断言 + 弃用警告 |
| 9 | 测试写不出"接线"证据 | S1 先定义 6 条红测，作为验收模板 |
| 10 | gold 被"顺手优化" | 哈希 + 版本记录 + 禁止清单 |

### 7.6 每步禁止项

1. 不得把失败分支改成 `pass`；
2. 不得调松阈值/改 gold 变绿；
3. 不得在节点/守卫里重复取数（单一取数入口）；
4. 不得跨步提交（一步一 commit）；
5. 不得为"看起来绿"删测试；
6. 不得在节点内 new 服务（必须用 `ctx`）。

---

## 8. 分批计划

| 批次 | 步骤 | 轮次 | 交付后的系统状态 |
|---|---|---|---|
| **批 1（先红后绿）** | S1 → S2 → S3 | 3 | 有门禁、有监督者；坏数据进不了库 |
| **批 2（会动）** | S4 → S5 → S6 | 3 | 能自我纠正；指标可信、可查 |
| **批 3（有脑）** | S7 → S8 → S9 | 3 | hybrid + LLM 进生产；单流水线 |
| **批 4（契约）** | S10 → S11 → S12 → S13 | 4 | 工具协议、NodeIO、验证器、收尾 |

---

## 9. 标准化设计（落地最小集）

### 9.1 标准什么、不标准什么

| 标准化（边界，冻结） | 不标准化（内部，自由） |
|---|---|
| `NodeInput / NodeOutput / GateResult / NodeSpec` | 节点内部是否 ReAct、调几次模型 |
| 6 类门禁与动作阶梯 | 阈值取值（可配，ADR 记录） |
| 事件四类 + payload 字段（**只增不改**） | 日志格式 |
| 副作用声明集合 | 实现库 |
| 幂等键 `{run_id}:{stage}:{attempt}` | —— |
| 错误码（必须在码表） | —— |
| 配置项名与默认值 | —— |

### 9.2 文件布局（新增，避免后期挪文件）

```
src/lit_agent/
├── contracts/
│   ├── __init__.py
│   ├── nodeio.py          # NodeInput/NodeOutput/GateResult/NodeSpec
│   └── specs.py           # 十节点 spec 注册表
├── graph/
│   ├── gates.py           # 6 类门禁 + run_gates()
│   ├── supervisor.py      # Decision + decide()
│   └── transitions.py     # 回边目标表 + 上限
├── runtime/
│   ├── context.py         # RunContext
│   └── commit.py          # pending_writes → 幂等 upsert
scripts/verify_phase2_1.py
tests/{wiring,gates,transitions,contracts,metrics,tools}/
```

### 9.3 配置模型（冻结名与默认值）

```python
class GateSettings(BaseModel):
    enabled: bool = True
    evidence_min_cards: int = 3
    support_ratio_min: float = 0.6
    citation_required: bool = True

class LimitSettings(BaseModel):
    max_attempts: dict[str, int] = {"analysis": 2, "retrieval": 2, "report": 1}
    max_total_llm_calls: int = 12
    recursion_limit: int = 60

class PipelineSettings(BaseModel):
    gates: GateSettings = GateSettings()
    limits: LimitSettings = LimitSettings()
    transitions: bool = True
    hybrid: bool = True
    hybrid_alpha: float = 0.6
    llm: Literal["auto", "on", "off"] = "auto"
    pdf_enabled: bool = False
```

### 9.4 事件 payload 冻结（复用 EventType，不新增类型）

| 事件 | 字段（类型） |
|---|---|
| `phase_change` | `phase: "start"\|"end"`、`attempt:int`、`ok:bool`（end 才有）、`gates:list[str]`（失败的） |
| `guard_trigger` | `gate:str`、`code:str`、`action:str`、`reasons:list[str]`、`attempt:int`、`source:"gate"\|"guard"\|"llm"` |
| `recovery` | `from_stage:str`、`to_stage:str`、`attempt:int`、`reason:str` |
| `tool_call` | `tool:str`、`ok:bool`、`duration_ms:int` |
| `report_written` | `report_id:str`、`claims:int`、`degraded:bool` |
| `error` | `code:str`、`message:str`、`failure_report:object` |

> 消费者必须忽略未知字段（前端已按此实现）；**禁止重命名已有字段**。

---

## 10. 契约 + 验证器 + 冻结 gold

### 10.1 冻结与哈希（含规范化算法）

| 对象 | 规范化 | 哈希 |
|---|---|---|
| gold | `json.dumps([asdict(i) for i in load_gold()], sort_keys=True, ensure_ascii=False)` | `GOLD_SHA256`（hex） |
| 检索基准 | `CORPUS` 按 key 排序 + `QUERIES` 原序，`sort_keys=True` | `BENCH_SHA256` |
| 事件/契约 | ADR-0006 + ADR-0007 | 版本号 |

**更新流程**：改内容 → 升本文档版本 → 记录 §13/§14 → 在 ADR 写理由 → 重跑全量评测 → 用 `--update-hashes --i-know-what-i-am-doing` 更新常量。**任何绕过都视为作弊。**

### 10.2 验证器契约（`scripts/verify_phase2_1.py`）

| 约束 | 规定 |
|---|---|
| 隔离 | 只用临时 store（`D:/lit-agent-store/temp/verify-2.1-*`），不碰 dev 库 |
| 离线 | 默认不联网；`--online` 才跑真实源 |
| 输出 | 控制台红绿表 + `--json` 报告（路径默认 `docs/implementation/phase2.1-report.json`） |
| 退出码 | 全绿 0；有红 1；`SKIP` 不计红但打标记 |
| 断言 | 12 条（见 §11 对应 H） |
| 幂等 | 可重复运行，不残留数据（结束时删临时库） |

### 10.3 自进化（Phase 5）——本阶段只留接口，不实现

```
提议 → 契约测试 → gold/bench 评估 → 成本/延迟检查 → 影子运行(A/B) → 人工批准 → 转正(可回滚)
```

**红线（写进验证器）**

1. 候选不得修改 gold/bench（哈希）；
2. 候选不得放宽门禁阈值（阈值来自配置 + ADR）；
3. 候选必须声明预算与副作用；
4. 只有"gold 不降 + 成本不超 + 契约全过"才允许进入影子；
5. 转正必须可一键回滚。

> 2.1 交付：spec、验证器、哈希、影子运行所需的**只读接口**（`--candidate <path>` 预留参数，本期仅校验契约）。**不交付生成器。**

---

## 11. 出口标准 H1–H14

| # | 判据 | 命令 | 期望 |
|---|---|---|---|
| H1 | 守卫进图 | `pytest -q tests/wiring -k guards` | 预算超限 → aborted + `guard_trigger` |
| H2 | 门禁挡坏数据 | `pytest -q tests/gates` | 坏 claim 零写入 |
| H3 | **健康 run 零误报** | 同上 `-k healthy` | `gate failures == 0` |
| H4 | 回边生效 | `pytest -q tests/transitions` | attempt 单调、≤上限、repair 只重跑 analysis |
| H5 | 续跑幂等 | `pytest -q tests/graph -k resume` | 同 attempt 不重复 start |
| H6 | 指标 run 口径 | `verify_phase2_1 --metrics` | 两 run 指标独立 |
| H7 | 指标落库 + API | `pytest -q tests/metrics` | 库/接口/报告一致 |
| H8 | hybrid 接线 | `verify_phase2_1 --retrieval` | hybrid_recall ≥ 0.90 且节点在用 |
| H9 | LLM 接线/回落 | `verify_phase2_1 --llm` | 有 key 有 `llm_calls`；无 key 降级 |
| H10 | 单流水线 | `verify_phase2_1 --pipeline` | 生产只调 `run_graph` |
| H11 | 工具闭环 | `verify_phase2_1 --tools` | `tool_call` + PDF 幂等 |
| H12 | 契约 | `verify_phase2_1 --contracts` | 10/10 |
| H13 | 冻结 | `verify_phase2_1 --frozen` | 哈希匹配 |
| H14 | 基线不回归 | `verify_phase2`；`verify_phase1 --online`；`pytest -q` | 12/12；13/13；全绿 |

---

## 12. 经验教训适配（2.x 真实踩坑 → 本阶段约束）

| # | 教训 | 约束 |
|---|---|---|
| 1 | 能力探针全绿但生产没用上 | 验收一律接线级（事件/DB/API 痕迹） |
| 2 | `artifacts` 无 reducer 被覆盖 | 只放引用；`_merge_dicts` 合并 |
| 3 | 条件边单值被覆盖 | 决策用列表累积，逐条落事件 |
| 4 | 零值型守卫空状态误报 | 门禁/守卫区分"没跑"与"跑了但为 0" |
| 5 | 指标 topic 聚合冒充 run | 口径写进契约测试（H6） |
| 6 | dedupe 返回旧事件导致幂等误判 | 一律 `has_dedupe()` 预探测 |
| 7 | timeout 在入口抛导致图没跑 | 注入点与真实故障点一致 |
| 8 | 双流水线 | H10 静态锁死 |
| 9 | UPDATE 不限行 | 写操作带主键/唯一键 |
| 10 | e2e 与自动切视图竞争 | 前端相关串行 + 用已有 run |

---

## 13. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| 1.0.0 | 2026-10-22 | 首版：12 项接线缺陷、M1–M6、S1–S13、10 不变量、H1–H12 |
| **1.1.0** | 2026-10-22 | **工程化重构**：新增两阶段提交（compute→gate→commit）、RunContext 注入、决策物化、预算从 DB 重建、attempt 幂等规则；补 6 类门禁表、指标公式表、配置模型、文件布局、事件 payload 冻结；新增 **C1–C6 通用契约**、**I1–I12 不变量**、**§7.5 返工风险登记**、**每步 DoD 与回滚点**；H 扩到 14 条（新增"健康 run 零误报""冻结"）；验证器补隔离/离线/JSON/退出码契约；明确 **2.1 零迁移、零新增错误码、零新增事件类型** |

---

## 附录 A · 命令速查

```powershell
. .\scripts\env.ps1
uv run pytest -q
uv run ruff check .
uv run python scripts/verify_phase2_1.py
uv run python scripts/verify_phase2_1.py --online
uv run python scripts/verify_phase2.py --offline
uv run python scripts/verify_phase1.py --online
cd web; npm run typecheck; npm run build; npm run test:e2e
```

## 附录 B · 与相邻阶段的边界

| 阶段 | 交付 | 不交付 |
|---|---|---|
| Phase 2.1 | 接线、门禁、回边、指标口径、契约、验证器 | 新节点、ReAct、自进化生成器、迁移 |
| Phase 2.2 | 节点合并（10→7）、`plan` 节点、前端打磨、G-17 | Chat |
| Phase 3 | `agents.chat` + ReAct + 多轮评测 | 并行、MCP |
| Phase 4 | 并行分支、MCP、PDF 真实链路 | 自进化 |
| Phase 5 | 契约内自进化（参数 → 配置 → 候选节点） | —— |
