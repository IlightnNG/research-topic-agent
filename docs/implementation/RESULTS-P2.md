# RESULTS — Phase 2（滚动记录）

> 口径：本文件只记**实测**；数字由命令产出，不手写。
> 规范：`phase2-implementation-steps.md` v2.0.0（M1–M8 × S1–S14，H1–H10）。

## 0. 一页摘要

| 指标 | 当前值 |
|---|---|
| 阶段 | **S1–S9 完成（图 + 角色 + 判定 + 折叠 + 守卫/运行时）** |
| 能力基线 | `verify_phase2 --offline` → **10/12 PASS，2 RED**（剩 S10 hybrid、S12 前端） |
| Phase 1 回归 | `verify_phase1 --online` → **13/13 PASS** |
| 后端测试 | `pytest -q` → **342 例**（其中 32 例属守卫/控制）全绿 |
| 静态检查 | `ruff check .` → clean |

---

## 1. S1 · 基线冻结（2026-10-21）

### 1.1 交付

| 产物 | 说明 |
|---|---|
| `scripts/verify_phase2.py` | 12 条**能力探针**（离线）+ 可选在线回归；默认"全绿才 0"，`--baseline` 允许 RED 并落 JSON |
| `docs/implementation/phase2-baseline-report.json` | 基线红绿表（机器可读） |
| 本文件 | 滚动记录起点 |

### 1.2 基线红绿表（实测）

| 探针 | 结果 | 详情 | 目标 |
|---|---|---|---|
| `graph.nodes(10)` | 🔴 RED | `stages=4`，缺 scope/retrieval/parse/normalize/mapping/analysis/critique/evaluate | S2 |
| `graph.edges(E1-E13)` | 🔴 RED | `unimplemented=13/13` | S3 |
| `graph.resume` | 🟢 PASS | `resume=yes`（能力位存在；行为测试在 S4） | S4 |
| `agents.4roles` | 🔴 RED | `implemented=[]` | S5/S6 |
| `context.summarize` | 🔴 RED | `summarize=not implemented` | S7 |
| `guards.15` | 🔴 RED | `guards=2`（`Guard`, `NoProgressGuard`） | S8 |
| `runtime.control` | 🔴 RED | pause/resume/inject 全 501 | S9 |
| `retrieval.hybrid` | 🔴 RED | 无 `hybrid_search` | S10 |
| `eval.suite` | 🔴 RED | judge/faultinject/datasets 均未实现 | S11 |
| `web.10stages` | 🔴 RED | UI 仅 2/10 阶段 | S12 |
| `baseline.phase1` | 🟢 PASS | `verify_phase1 --offline 11/11` | 必须 GREEN |
| `baseline.tests` | 🟢 PASS | unit+contract 全绿 | 必须 GREEN |

```
TOTAL: 3/12 PASS, 9 RED (baseline mode)
```

### 1.3 使用方式（后续每一步）

```powershell
. .\scripts\env.ps1
uv run python scripts/verify_phase2.py --offline          # 全绿才 0
uv run python scripts/verify_phase2.py --online           # 额外跑真实数据回归
uv run python scripts/verify_phase2.py --baseline --json docs/implementation/phase2-baseline-report.json
```

**纪律**：只能通过"实现能力"把 RED 变 GREEN；**禁止改探针断言来变绿**（改断言需在 `phase2-implementation-steps.md` §11 记录并说明理由）。

### 1.4 已知偏差

- `graph.resume` 目前只验证"函数存在"，不是行为验证 → S4 会补"中断后 resume 不重复事件"的硬测试；
- `retrieval.hybrid` 的探针只查工具位，S10 会换成"固定查询集 recall@10 ≥ 基线+10pp"的可执行判据（见 M6）。

## 2. S2 · 十节点主干（2026-10-21）

### 2.1 交付

| 产物 | 说明 |
|---|---|
| `graph/nodes.py` | `Phase2Nodes`：intake / scope / retrieval / parse / normalize / mapping / analysis / critique / report / evaluate（**只做数据，不发事件**） |
| `graph/pipeline.py` | `build_phase2_graph()`：十节点 + 条件边；保留 Phase 1 的三节点冒烟图（`SMOKE_MAINLINE`） |
| `runtime/graph_runner.py` | `run_graph()`：拿锁建 run → 逐阶段发 `phase_change`（带 `dedupe_key`）→ 收尾；支持 `resume` 与崩溃注入 |
| `graph/state.py` | 新增 `focus_hint` / `edge` / `budget` 字段 |

### 2.2 实测

```
phase_change start 序列：
["run", "intake", "scope", "retrieval", "parse", "normalize", "mapping", "analysis", "critique", "report", "evaluate"]
end 序列 == 十个阶段
pytest -q tests/graph  → 42 例全绿
verify_phase2 → graph.nodes(10) PASS
```

### 2.3 关键设计

- **节点不写事件、不写锁**：事件由 `graph_runner` 统一发，保证幂等与可回放；
- **单一取数入口**：`retrieval` 把 `paper_ids` 放进 artifacts，`report` 用 `persist_report_for_state()` 复用同一批证据；
- **state 只放引用**：卡片正文不进状态，避免 checkpoint 膨胀。

### 2.4 偏差

生产入口 `run_topic` 仍走 Phase 1 的四阶段链；十节点图先以 `run_graph` 并行提供，**切换计划在 S9**，避免 S2 就改动既有测试行为。

---

## 3. S3 · 条件边 E1–E13（2026-10-21）

### 3.1 交付

`graph/edges.py` 重写为规则表：

```
EdgeRule(edge, stage, action, predicate, note)  ×13
PRIORITY: annotate < warn < skip < degrade < retry/rewrite/expand < replan < abort
route_after(stage, state) → 动作名 | 下一阶段 | "end"
backoff_edge(edge) → 动作名（不再抛"未实现"）
```

### 3.2 实测

```
13 条边 ×（触发 + 不触发）用例全绿
预算边优先：route_after("scope", {"counters": {"drift_warn": 1, "budget_stop": 1}}) == "abort"
未知阶段仍显式报 E_FEATURE_DISABLED
```

### 3.3 修掉的一个设计缺陷

首版把"零值型"边（E4 `new_papers == 0`、E7 `cards == 0`）写成单纯 `== 0`，导致**空状态也触发**。
改为 `_has(state, name) and _counter(...) == 0`：先确认该阶段确实写过计数，再判断零值。

---

## 4. S4 · 续跑与幂等（2026-10-21）

### 4.1 交付

- `run_graph(..., crash_after_stage=...)`：模拟进程中断（不 finish，checkpoint 已落盘）；
- `run_graph(..., resume=True)`：`graph.invoke(None)` 续跑；
- 事件 `dedupe_key`：`{stage}:start` / `{stage}:end` / `run:start:{fresh|resume}`。

### 4.2 实测

```
中断于 analysis → resume → 最终 succeeded
十个业务阶段各出现 1 次 start（无重复）
resume 标记出现在事件 payload 中（便于审计）
```

### 4.3 已知边界

`run:start` 允许出现两次（fresh + resume 各一次），十个业务阶段严格唯一——刻意保留的"续跑审计点"。

## 5. S5 · retrieval / mapper（2026-10-21）

| 产物 | 说明 |
|---|---|
| `agents/retrieval.py` | 词面打分（hint 命中×2 + 标题命中 + 有摘要）；**有 hint 只保留命中项，全不命中返回空**；无 hint 按原序截断 |
| `agents/mapper.py` | `map_clusters(primaries, edges)` 纯函数；孤儿合并单列；`run()` 从库读取 |

## 6. S6 · analyst / critic / grounding / gold / judge（2026-10-21）

| 产物 | 说明 |
|---|---|
| `analyst.py` | 确定性（一卡一 claim、全带引用）+ LLM 抽取（paper_id 必须来自输入卡；异常回落） |
| `critic.py` | 缺引用 → BLOCK `E_GROUND_UNRESOLVED_CITATION`；重复 → RETRY；比例 <0.6 → DEGRADE；空 → DEGRADE |
| `eval/grounding.py` | token 覆盖率 ≥0.5 **且**有引用才算 supported |
| `eval/datasets.py` | **20 条冻结 gold**（10 正 + 10 负） |
| `eval/judge.py` | 有 completer 用 LLM，失败回落 grounding；Cohen's κ |

实测：`gold=20 accuracy=1.00 kappa=1.00`；critic 正确拦住无引用 claim。

## 7. S7 · 折叠与注入物化（2026-10-21）

| 产物 | 说明 |
|---|---|
| `SummarizeFolding` | 每段保留首句 + 含两位数字/引用标记的句子，再按预算填充 |
| `folding_for("hierarchical")` | 仍显式 `E_FEATURE_DISABLED`（P3） |
| `slots.materialize_slots()` | 每个非空槽写一条 `phase_change`（slot/sha/chars/source），正文不入事件 |
| `SqliteEventLog.has_dedupe()` | 幂等探测，不产生"重复标记"事件 |

## 8. 本轮修掉的真实缺陷

| 缺陷 | 现象 | 根因 | 修法 |
|---|---|---|---|
| **artifacts 被覆盖** | `retrieval` 的 `paper_ids` 到 `analysis` 就丢了 → 报告退化为"无证据" | `AgentState.artifacts/counters` 无 reducer，节点返回即整体替换 | 加 `_merge_dicts` reducer（`STATE_SCHEMA_VERSION` → **1.1**） |
| **幂等语义误判** | 同一槽第二次仍算"写入" | `emit` 命中 dedupe 时返回已存在事件（并留 dup 标记） | 新增 `has_dedupe()` 预探测 |
| **折叠不够狠** | 降幅不足 40% | 剪枝保留 2 句/段过松 | 改为 1 句 + 数字/引用句 |

端到端：十节点图现在**真的用上了 agents**——`retrieval`→`analyst`→`critic`→`report`，报告里的 claim 全部带引用。

## 9. S8 · 15 类守卫 + 动作阶梯（2026-10-21）

| 守卫 | 触发条件 | 动作 |
|---|---|---|
| G1 ScopeDrift | `drift_block` / `drift_warn` | ABORT / ANNOTATE |
| G2 RetrievalFailure | `retrieval_errors>0` | RETRY |
| G3 ZeroNewPapers | `new_papers==0`（键存在） | DEGRADE |
| G4 ParseFailure | `parse_failed≥1` | DEGRADE |
| G5 SchemaOutput | `schema_errors>0` | RETRY |
| G6 EvidenceSufficiency | `cards==0`（键存在） | RETRY |
| G7 NoProgress | 连续 N 步累计产出不增 | DEGRADE |
| G8 RepeatTool | 同一工具重复 | **RETRY(提醒)** → 3 次后 **REPLAN** |
| G9 CitationIntegrity | `unresolved_citations>0` | RETRY(BLOCK) |
| G10 GroundingRatio | `grounding_rate<0.6` | DEGRADE |
| G11 Loop | `loop>0` | REPLAN |
| G12 Budget | 预算 80%/100% | DEGRADE / ABORT |
| G13 Timeout | `idle_seconds≥阈值` | ABORT |
| G14 Stagnation | 连续 N 步产物数不变 | REPLAN |
| G15 EvalQuality | 重试用尽 / 评测不达标 | DEGRADE / ANNOTATE |

- `GuardRail` 按 `_ORDER` 取最重动作（abort > replan > degrade > retry > annotate > continue）；
- **两条纪律落地**：零值型守卫先判"键是否存在"（防误报）；重复工具先**提醒**再升级（DSH 对照）。

## 10. S9 · 熔断 / 暂停 / 续跑 / 注入（2026-10-21）

| 产物 | 说明 |
|---|---|
| `gateway/breaker.py` | `closed → open → half_open` 三态；`failure_threshold` + `cooldown_s` + 注入时钟（测试确定性） |
| `LLMGateway` | 调用前 `allow()`，拒绝 → `E_LLM_QUOTA`；失败 `record_failure()`；成功 `record_success()` |
| `control` | `request_pause/is_paused/clear_pause` + `inject_prompt/consume_inject/pending_inject` |
| `graph_runner` | 阶段边界检查暂停 → `PauseRequested` → run 置 **paused**（checkpoint 保留）；续跑合并注入词并写 `inject` 事件 |
| API | `POST /runs/{id}/pause`（202/409）、`/resume`（202，后台续跑）、`/inject`（写回 `runs.focus_hint`） |

实测：

```
熔断：2 次失败 → open；冷却后可放行 1 次；成功 → closed
暂停：paused → resume → succeeded（十阶段各 1 次 start）
注入：focus_hint 含 "tool use"，事件里有 inject payload
```
