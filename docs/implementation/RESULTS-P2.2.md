# RESULTS — Phase 2.2（收尾 · 可观测 · 前端质量）

> 口径：只记**实测**；数字由命令产出。
> 规范：`phase2.2-closeout-and-observability.md`（M1–M5 × S1–S8，H1–H8）。

## 0. 一页摘要

| 指标 | 当前值 |
|---|---|
| 阶段 | **S1–S2 完成**（配置体系 / LLM 调用硬顶） |
| 测试 | `pytest` 收集 **448 例**（1 skip=浏览器 e2e） |
| Phase 2.1 验证器 | `verify_phase2_1 --all` **13/13 PASS** |
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
