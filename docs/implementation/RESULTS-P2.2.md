# RESULTS — Phase 2.2（收尾 · 可观测 · 前端质量）

> 口径：只记**实测**；数字由命令产出。
> 规范：`phase2.2-closeout-and-observability.md`（M1–M5 × S1–S8，H1–H8）。

## 0. 一页摘要

| 指标 | 当前值 |
|---|---|
| 阶段 | **S1–S8 完成（Phase 2.2 已收尾）** |
| 测试 | `pytest` 收集 **467 例**（1 skip）；e2e **13 passed** |
| Phase 2.1 验证器 | `verify_phase2_1 --all` **13/13 PASS** |
| Phase 2.2 验证器 | `verify_phase2_2 --all` **8/8 PASS** |
| Phase 2 基线 | `verify_phase2 --offline` **12/12** |
| Phase 1 基线 | `verify_phase1 --online` **13/13** |
| 前端 | `playwright 8 passed`；`ruff clean` |

---

## 1. S1 · pipeline 配置体系（2026-10-23）

### 1.1 交付

| 产物 | 说明 |
|---|---|
| `config.py` | `GateSettings / LimitSettings / PipelineSettings`，`Settings.pipeline` |
| `runtime/context.py` | `RunContext.pipeline` + `gates_cfg/limits_cfg`（默认从 settings 取） |
| `graph/gates.py` | 证据阈值、支持率阈值读配置；新增 `gate_llm_calls` |
| `graph/nodes.py` | hybrid 的 `alpha/min_score` 读配置 |
| `graph/transitions.py` | `next_stage(..., limits=)`；pipeline 构建时注入 `limits.max_attempts` |
| `runtime/graph_runner.py` | `recursion_limit`、`max_run_usd`、`pdf_enabled`、`llm` 模式、`gates.enabled` 全部读配置；pdf 开启时自动装配默认工具集 |
| `tests/config/test_pipeline_settings.py` | 6 例：默认快照、env 覆盖、非法值、门禁开关、attempt 上限、pdf 开关 |

### 1.2 实测

```
默认值 = 2.1 行为（快照测试逐项相等）
LIT_AGENT_PIPELINE__GATES__EVIDENCE_MIN_CARDS=3 → 生效
LIT_AGENT_PIPELINE__LLM=always → E_CONFIG_INVALID
gates.enabled=false → end 事件里 gates 为空（守卫仍独立报警）
limits.max_attempts.analysis=1 → 坏产物不产生 recovery
pipeline.pdf_enabled=true → parse 阶段出现 tool_call
```

### 1.3 设计取舍

- 环境变量前缀是 `LIT_AGENT_`（沿用现有机制），因此实际写法是
  `LIT_AGENT_PIPELINE__GATES__EVIDENCE_MIN_CARDS`（文档 2.2 §4 的示例已按此为准）。
- **门禁关闭 ≠ 守卫关闭**：门禁判"产物对不对"，守卫判"过程偏没偏"；关掉门禁后 G9 仍会报警，测试据此断言"无门禁结果"而不是"无任何告警"。
- `evidence_min_cards` 默认 **1**（与 2.1 行为等价），生产建议 3；ADR-0007 的默认值随本阶段更新。

---

## 2. S2 · LLM 调用数硬顶（2026-10-23）

### 2.1 交付

| 产物 | 说明 |
|---|---|
| `gates.gate_llm_calls` | `SELECT COUNT(*) FROM llm_calls WHERE run_id` ≥ 上限 → `abort E_BUDGET_EXCEEDED` |
| 事件 | `guard_trigger.gate="llm_calls"`、`details.llm_calls_used/limit`；`phase_change end` 的 `gates` 带 details |
| `tests/gates/test_llm_cap.py` | 3 例：12 条即中止（零写入）、11 条可完成、上限可配（2 条即中止） |

### 2.2 实测

```
预插 12 条 llm_calls → state=aborted, error_code=E_BUDGET_EXCEEDED, reports=0
预插 11 条          → succeeded（未额外产生调用）
max_total_llm_calls=2 + 2 条 → aborted（证明读配置）
```

### 2.3 设计取舍

- 计数以 **DB 为准**，不用内存计数器：进程重启/续跑不会丢。
- 超标动作是 `abort`（不是 degrade）：调用数失控属于"安全阀"，应显式中止并留失败原因。
- 与金额预算并存：谁先触发谁生效，错误码统一 `E_BUDGET_EXCEEDED`。

---

## 3. 下一步

**S3**：证据阈值语义收口（`selected < evidence_min_cards` 的完整行为矩阵 + 夹具显式设 1）。
**S4**：漂移产出者（`eval/scope_drift.py`）→ **S5–S7** 观测/前端/测试 → **S8** 收尾。

---

## 4. S3 · 证据阈值收口（2026-10-23）

### 4.1 交付

| 产物 | 说明 |
|---|---|
| `gates.gate_evidence_sufficiency` | 判 `selected < evidence_min_cards`，details 带 `selected/min_cards/repair_target` |
| `tests/wiring/__init__.prepare()` | **显式**设 `evidence_min_cards=1`（小夹具只有 1 篇论文） |
| `tests/gates/test_evidence_threshold.py` | 7 例：矩阵 0/1/3 × 阈值 1/3、缺键不误报、回边一次后降级、阈值 1 不回边 |

### 4.2 实测

```
矩阵：selected=1,min=1 通过；selected=1,min=3 失败；selected=3,min=3 通过
集成：min=3 + 1 篇论文 → retrieval attempt=[1,2] → 仍不足 → degrade（succeeded）
集成：min=1 + 1 篇论文 → retrieval attempt=[1]（不回边）
缺 "selected" 键（阶段未跑）→ 不触发
```

### 4.3 设计取舍

- **默认 1 = 2.1 行为**，生产建议 3；阈值只从配置读，测试显式声明，避免"阈值测试污染其他用例"。
- 失败动作是 `repair→retrieval`（可回边），次数用尽后由 runner 降级，不会中止整轮。

---

## 5. S4 · 漂移产出者（2026-10-23）

### 5.1 交付

| 产物 | 说明 |
|---|---|
| `eval/scope_drift.py` | `drift_for(scope, claims, warn_below, block_below)`；短 scope（<2 token）不判定 |
| `nodes.analysis` | 抽取后计算覆盖率，写 `drift_warn/drift_block` 计数 + artifacts `drift_verdict/coverage` |
| 门禁 | 复用 2.1 的 `gate_drift`（block→abort / warn→annotate） |
| 测试 | `tests/eval/test_scope_drift.py` 9 例（ok/warn/block/短 scope/空产出/阈值可配/集成 abort/健康零误报） |

### 5.2 实测

```
scope="protein folding cryo microscopy thermodynamics" + agent 论文
  → drift_verdict=block → run aborted, error_code=E_GUARD_DRIFT
scope="tool use agents" + 匹配论文
  → drift_verdict=ok → 零告警（健康 run）
```

### 5.3 设计取舍

- **确定性词面覆盖**，不引入 LLM 成本；语义漂移判定留 Phase 3 作为可选工具。
- **"没有证据" ≠ "跑题"**：空 claims 直接判 ok（证据不足由别的门禁负责）。
- **尽力而为**：scope 读不到（如单测无库）时跳过检测，不阻断分析。
- 阈值来自配置 `drift_warn_below / drift_block_below`，改配置即改行为。

### 5.4 本轮修掉的边界问题

`analysis` 新增 scope 查询后，一个只测"节点传 gateway"的单元测试没有建库 → 查询抛错。
修法：`_scope_text()` 失败返回空串（漂移是辅助判定，不该让主流程失败）。

---

## 6. S5 · 阶段耗时与指标（2026-10-26）

### 6.1 交付

| 产物 | 说明 |
|---|---|
| `graph_runner` | 每个 `phase_change end` 带 `duration_ms`（含 abort/回边/正常三条路径） |
| `compute_run_metrics` | 汇总 `duration_by_stage`、`duration_ms_total`、`slowest_stage`，并落 `duration_ms_<stage>` 指标行 |
| `persist_run_metrics` | 图跑完后补一次幂等汇总，使 `evaluate` 自身耗时也进入指标 |
| `GET /runs/{id}/metrics` | 从 `duration_ms_*` 行还原 `duration_by_stage` 与 `slowest_stage`；旧 run 缺失时不影响 |
| 测试 | `tests/observability/test_stage_duration.py`（3 例） |

### 6.2 实测

```
10 个阶段 end 事件均带 duration_ms（0ms 也合法）
metrics 表有 10 个 duration_ms_<stage> + duration_ms_total
API：duration_by_stage 10 项；slowest_stage ∈ 阶段集；Σstage ≈ total
未知 run → 404
```

### 6.3 设计说明（一个必要的小偏差）

`evaluate` 的耗时在它自己提交指标时还不可知（提交发生在 end 事件之前）。
处理：图跑完后在 `run_graph` 里**再补一次幂等 `persist_run_metrics`**，让指标覆盖全部十阶段。
副作用：指标多一次写入（可忽略），但"总耗时=各阶段之和"成立。

---

## 7. S6 · 前端展示（2026-10-26）

### 7.1 交付

| 产物 | 说明 |
|---|---|
| `RunWorkspace.vue` | 头部显示 `$cost` + `最慢 <stage> <ms>`（来自 metrics API） |
| `TrajectoryTimeline.vue` | 每条 `phase_change end` 显示 `· <ms>ms` |
| `runs` store | `metrics` 状态 + `loadMetrics()`（失败不阻塞主流程） |
| `useRunSession` | run 进入终态后加载一次指标 |
| `types / endpoints` | `RunMetrics` 类型 + `getRunMetrics()` |

### 7.2 实测

```
npm run typecheck → 0 error
npm run build     → ✓ built in 7.10s
playwright        → 8 passed（未回归）
新 run 头部截图：$0.0000 · 最慢 normalize 32ms（web/screens/run-header.png）
```

### 7.3 下一步

S7：把"成本/最慢阶段"的断言并入正式 e2e，并补连点 409、SSE 断线两条用例；S8 收尾。


---

## 8. S7 · e2e 与页面级组件验证（2026-10-26）

### 8.1 交付（`web/e2e/smoke.spec.ts`，8 → 13 条）

| 新增用例 | 断言 |
|---|---|
| 成本与最慢阶段 | 新 run 头部出现 `$x.xxxx` + `最慢 <stage> <ms>` |
| 409 内联 | mock POST run → 409 `E_LOCK_HELD`，对话框内联提示 |
| SSE 断线 | abort `/stream`，轮询仍把 run 推进到 succeeded 并可读报告 |
| 失败卡 | mock 失败 run，显示"本次运行未成功 + 错误码 + 重跑" |
| 错误条 | mock GET run 500，页面显示错误文案与详情 |

### 8.2 取舍

- **不引入 Vitest**：失败卡/错误条用 Playwright 页面级 mock 断言，覆盖同样的渲染与交互；
  避免为两个组件新增一套测试依赖（记为偏差 2.2-a）。
- 生成型用例前统一 `waitTopicIdle()`，避免上一条 run 未结束导致 409（真实 flaky 根因）。

### 8.3 本轮抓到的真 UX 缺陷

现象：run 已经 succeeded，但**左侧列表仍显示 running**（头部正确）。
根因：轮询只 `loadSnapshot`（更新 current），从不刷新 `items`。
修复：run 进入终态时 `void runs.loadList(topicId)`，列表与头部同步。

---

## 9. S8 · 阶段收尾（2026-10-26）

### 9.1 交付

| 产物 | 说明 |
|---|---|
| `scripts/verify_phase2_2.py` | H1–H8 一条命令（pytest 选择 + e2e + 基线 + 文档检查），输出 JSON |
| `docs/implementation/phase2.2-report.json` | 机读报告 |
| 本文档 | 收尾数字、偏差、backlog |

### 9.2 实测

```text
verify_phase2_2 --all     8/8 PASS
verify_phase2_1 --all     13/13
verify_phase2 --offline   12/12
verify_phase1 --online    13/13
pytest -q                 467 例
playwright                13 passed
vue-tsc / vite build      0 error / ✓
ruff                      clean
```

### 9.3 收尾结论

Phase 2.2 完成：配置/限额/漂移/观测/前端质量五项全部落地并**行为级验证**；
遗留项（PDF 下载、语义分节、F5 不打断的 e2e）已登记，归 Phase 3/P4/2.3。

**下一步**：进入 Phase 3（双层 Agent），先做 3.0 Foundations（Kernel + ShellSpec）。
