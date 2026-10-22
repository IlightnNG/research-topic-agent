# RESULTS — Phase 2.1（接线 · 门禁 · 契约）

> 口径：只记**实测**；数字由命令产出。
> 规范：`phase2.1-wiring-and-contracts.md` v1.2.0（M1–M6 × S1–S13，H1–H14）。

## 0. 一页摘要

| 指标 | 当前值 |
|---|---|
| 阶段 | **S1–S6 完成**（图/门禁/回边/指标口径/指标落库） |
| 测试 | `pytest` 收集 **371 例**（1 skip=浏览器 e2e；2 xfail=待 S7/S9） |
| 接线测试 | `tests/wiring` 6 条：4 绿（守卫/LLM/回边/指标）、2 xfail（S7 hybrid、S9 scheduler） |
| 门禁测试 | `tests/gates` 11 例全绿（6 类门禁 × 触发/不触发 + 监督者 3 例 + 集成 2 例） |
| Phase 2 基线 | `verify_phase2 --offline` **12/12**（未回归） |
| Phase 1 基线 | `verify_phase1 --online` **13/13** |
| 前端 | `playwright 8 passed`；`vue-tsc` 0 error |

---

## 1. S1 · 先写"会红"的接线测试（2026-10-22）

| 文件 | 断言 | 现状 |
|---|---|---|
| `tests/wiring/test_guards_wired.py` | 预算超限 → aborted + `guard_trigger` | ✅ 绿（S3） |
| `tests/wiring/test_transitions_wired.py` | 坏产物 → `analysis` attempt=2 + `recovery` | ⏳ xfail（S4 开回边） |
| `tests/wiring/test_metrics_wired.py` | 两 run 指标独立 + 落库 + API | ⏳ xfail（S5/S6） |
| `tests/wiring/test_llm_wired.py` | `analysis` 收到 `ctx.gateway` | ✅ 绿（S3 顺手接通） |
| `tests/wiring/test_hybrid_wired.py` | `retrieval` 走 `hybrid_search` | ⏳ xfail（S7） |
| `tests/wiring/test_scheduler_wired.py` | scheduler 只调 `run_graph` | ⏳ xfail（S9） |

**设计说明**：未实现的 4 条用 `xfail(strict=True)`——套件保持绿，但对应步骤完成后会 **XPASS→红**，强制回头删标记，避免"假绿"。

---

## 2. S2 · 契约骨架 + 门禁 + 两阶段提交（2026-10-22）

### 2.1 交付

| 产物 | 说明 |
|---|---|
| `contracts/nodeio.py` | `NodeOutput` / `GateResult` / `PendingWrite` / `Decision`（只约束边界） |
| `graph/gates.py` | 6 类门禁：schema / evidence / citation / support_ratio / budget / drift |
| `runtime/commit.py` | 执行 `pending_writes`（报告、指标），支持 `drop_claim_indexes` |
| `graph/nodes.py` | `report` / `evaluate` 改为**只声明写入**，由 commit 落库 |

### 2.2 实测

```
坏 claim（无引用）→ 门禁命中 → 落库的 claim 全部有引用（坏的那条被丢弃）
健康 run（1 篇论文）→ gate failures == 0
schema 门禁：9KB 产物 → 拒绝（claims_json 例外，由 MAX_CLAIMS 限长）
```

### 2.3 设计取舍

- `claims_json` 从"大字段"判定中排除：它由 `MAX_CLAIMS=50` 限长，且被引用门禁单独校验；
  否则 20+ 条 claim 的合法报告会被判"输出过大"。
- 报告降级时的占位 claim（"本轮未检索到可引用证据"）允许无引用——它不是证据结论。

---

## 3. S3 · 监督者 + 守卫接线 + 预算（2026-10-22）

### 3.1 交付

| 产物 | 说明 |
|---|---|
| `runtime/context.py` | `RunContext`（settings/run_id/budget/gateway/log/flags），节点不再 new 服务 |
| `graph/supervisor.py` | `Decision` + `decide()`：门禁 + 守卫取最重动作（abort > replan > degrade > repair > retry） |
| `runtime/budget.py` | `RunBudget.from_db()`：续跑从 `llm_calls` 重建已花预算 |
| `runtime/graph_runner.py` | 每阶段：attempt 记账 → 门禁 → 守卫 → 决策 → 两阶段提交 → 事件；`abort` 终止 |
| `graph/state.py` | 新增 `attempts`（合并）与 `decisions`（累积），`STATE_SCHEMA_VERSION=1.2` |

### 3.2 实测

```
预算超限 → state=aborted, error_code=E_BUDGET_EXCEEDED
事件：phase_change(end, ok=false) + guard_trigger(code=E_BUDGET_EXCEEDED)
报告：0 行（中止的 run 不写库）
```

### 3.3 偏差（已记录，S4 收口）

| 偏差 | 原因 | 处理 |
|---|---|---|
| `retry/repair/replan` 暂不建回边，降级继续 | S4 才实现回边执行器 | 事件里带 `deferred: true`，S4 打开后改为真回边 |
| LLM 接线提前通过 | `analysis` 已接收 `ctx.gateway`（无 key 时为 None） | S8 仍负责"有 key 真调用 + 成本归因"验收 |
| attempt 级幂等键 | `{stage}:start:{attempt}`，为回边预留 | S4 用同一套键验证"同 attempt 不重复" |

---

## 4. 下一步

**S4**：`transitions_enabled=True` + 图内条件回边（analysis↔critique、retrieval↔expand），
把 4 条 xfail 中的 `test_transitions_wired` 翻绿。

## 5. S4 · 有界回边（2026-10-22）

### 5.1 交付

| 产物 | 说明 |
|---|---|
| `graph/transitions.py` | `MAX_ATTEMPTS`（analysis/critique/retrieval=2、report=1）+ `next_stage()` 纯函数 |
| `graph/pipeline.py` | 线性边 → `add_conditional_edges`（图内环，每个 superstep 都 checkpoint） |
| `graph_runner.py` | 回边执行：attempt 未用尽 → 发 `guard_trigger` + `recovery` 并跳转；用尽 → `degrade` |
| `graph/gates.py` | `support_ratio` 改为 `repair`；`citation_integrity` 覆盖 critique + report |

### 5.2 实测

```
坏产物 → critique 门禁命中 → recovery(critique→analysis)
      → analysis attempt=2 → 仍坏 → 尝试用尽 → degrade → 落库时丢弃坏 claim
pytest tests/wiring/test_transitions_wired.py → 绿
```

### 5.3 本轮抓到的真 bug（守卫误报）

`NoProgressGuard` / `StagnationGuard` 在**非产出阶段**（parse/normalize/mapping）也收到 `produced/artifacts`，
而这两个阶段本来就不增长 → 误判"停滞" → 决策 `degrade`，把回边吃掉了。

修法：
- `RunContext.observation()` 只对 `retrieval/analysis/report` 提供 `produced/artifacts`；
- 两个守卫在缺键时返回 `None`（"不适用" ≠ "没问题"）。

> 这正是 Phase 2.1 文档 §12 第 4 条"零值/缺失要区分"的翻版。

---

## 6. S5 · 指标改 run 口径（2026-10-22）

### 6.1 交付

`compute_run_metrics()` 重写：claims / citations / llm_calls 全部按 `run_id` 过滤；
`grounding_rate` 改由判定器（`check_claim`）计算，DB 口径保留为 `claims_supported` / `supported_rate_db`。

### 6.2 实测

```
同话题、两篇不同论文、两次 run（focus_hint 不同）：
  m1.claims_total = 1，m2.claims_total = 1（旧实现会都是 2）
pytest tests/wiring/test_metrics_wired.py → 绿
```

### 6.3 口径变更（契约）

| 指标 | 旧 | 新 |
|---|---|---|
| `grounding_rate` | `claims.support` 自证 | 判定器 `check_claim` |
| `claims_supported` | 唯一口径 | 保留（= DB support），新增 `supported_rate_db` 名称 |
| `hallucination_rate` | `1 - support 比例` | `1 - grounding_rate` |

旧测试已按新口径调整，并在测试内注明原因。

---

## 7. S6 · 指标落库 + API（2026-10-22）

### 7.1 交付

| 产物 | 说明 |
|---|---|
| `GET /api/runs/{run_id}/metrics` | 优先读 `metrics`；缺行**按需计算**并标 `source="computed"`（不做回填迁移） |
| `commit` 中的 `metrics` 写入 | `evaluate` 节点声明写入 → 门禁通过后 `persist_run_metrics` 落库 |
| 分节回填 | `UPDATE ... WHERE report_id = :report_id`（不再按 run 批量覆盖） |

### 7.2 实测

```
metrics 表：scope='run' 每 run 一行集；scope_id=run_id
API：200 + 与库一致；未知 run → 404
分节：同一 report 行更新，不再影响历史行
```
