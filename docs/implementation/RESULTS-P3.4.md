# RESULTS — Phase 3.4（Workflow + Kernel 重构）

> 规范：`phase3.4-workflow-kernel-refactor.md`
> 当前进度：**Phase 3.4 收尾**；S15/S20 旧 graph 切换明确挂起。
> 评价体系：未实现，见 `docs/OPEN-ISSUES.md`。

## 0. 一页摘要

| 指标 | 结果 |
|---|---|
| 阶段 | **Phase 3.4 收尾** |
| 测试 | `pytest` **640 例**；Playwright **18 passed** |
| 代码 | `kernel/`、`workflow/` 基础层 |
| 兼容 | chat/report 已接新 workflow，保留 legacy fallback |

## 1. S1 · 类型与固定 Workflow

| 产物 | 说明 |
|---|---|
| `kernel/types.py` | `KernelGoal / KernelResult / KernelState / ToolCallRecord`，可序列化 |
| `workflow/spec.py` | `NodeSpec / WorkflowSpec / validate_workflow` |
| 约束 | Workflow 静态；节点顺序声明即执行顺序；无运行时 plan |

测试：序列化、重复节点、非法输入、缺工具。

## 2. S2 · Kernel Tools

| 产物 | 说明 |
|---|---|
| `kernel/tools.py` | `KernelTools.from_cards` |
| 工具 | `search_topic / rewrite_query / verify_claim / extract_claims / compress_context` |
| 事件 | `tool.called / tool.result` |
| 约束 | ToolSpec schema、timeout、白名单 |

测试：混合检索、事件顺序。

## 3. S3 · Kernel Runtime

| 产物 | 说明 |
|---|---|
| `kernel/runtime.py` | 有界 agent loop |
| 停止条件 | `final / max_steps / budget / timeout / cancelled / no_progress / failed` |
| 事件 | `kernel.started / kernel.finished` |
| 预算 | 从 tool meta 累计 cost |

测试：tool→final、max_steps、unallowed tool、cancel、no_progress、budget。

## 4. 下一步

- S4：Context 分层 / handoff / compress；
- S5：checkpoint / resume；
- S6：WorkflowRunner + ArtifactStore；
- S7：Verifier。


## 5. S4 · Context

- `ContextLayers.start_node/finish_node`：保留 L0 invariants + L1 artifacts，清空 L2 working。
- `compress` 超长 working 只保留 key 摘要。
- 测试：跨节点保留 topic/papers/cards，raw 临时状态不泄漏。

## 6. S5 · Checkpoint

- `KernelCheckpoint`：goal/step/trace/output/cost/context。
- `CheckpointStore` 支持内存与路径。
- `Kernel.run(..., checkpoint=store, resume=True)`：恢复 trace/context，从下一 step 继续。
- 测试：max_steps 中断后恢复，不重复已完成工具。

## 7. S6 · Workflow Runner

- `WorkflowRunner`：固定顺序执行 Node。
- `ArtifactStore`：节点只通过 input/output key 传值。
- `CodeVerifier`：output/postcondition 结构校验。
- 独立 Verifier 接口已留出（S7 接入）。
- 测试：确定性/agent 节点、失败停在节点、checkpoint 恢复跳已完成节点、verifier reject。

## 8. 下一步

- S7：独立 Verifier Agent；
- S8：ChatWorkflow 迁移；
- S9：ReportWorkflow 迁移；
- S10：事件/stream 接 UI。


## 9. S7 · 独立 Verifier

- `AgentVerifier`：独立 prompt/上下文，只看 artifact + node contract。
- 输出 `accept / repair / fail`；异常一律 reject。
- CodeVerifier 始终先执行。

## 10. S8 · ChatWorkflow

- 单节点 `answer`，Kernel 工具：`search_topic / verify_claim`。
- `/api/.../chat` 默认走 ChatWorkflow；异常回退旧 `answer`。
- 行为保持：引用、拒答、中文镜像、LLM query rewrite。
- 测试：13 chat + 2 workflow 全部通过。

## 11. S9 · ReportWorkflow

- `ReportWorkflow` 通过 WorkflowRunner + Kernel 调用 `generate_report` 工具。
- `report` 节点优先走 Workflow；异常回退旧 `build_report_bundle`。
- **当前是迁移缝合层**：内部仍复用现有 report engine；下一步再拆 `evidence/map/write` 节点。
- 测试：report 全量 + e2e 18。

## 12. 下一步

- S10：Report 节点拆分 + 事件/stream；
- S11：旧 graph 兼容/删除；
- S12：收尾。


## 12. S10 · Report 拆节点 + step 事件

- `ReportWorkflow` 从单节点改为 `evidence → map → write`。
- `report` 节点通过 `phase_change` payload 发出 step 事件；run_events 可见。
- 输出仍保持 `report_draft_json`、`report_cards_json`、两阶段提交。
- e2e 18。

## 13. S11 · 旧 graph 兼容

- 10 节点 `graph_runner` 保留为**兼容外壳**。
- 没有删除，避免一次性破坏 CLI/API/测试。
- 删除计划列入 `docs/OPEN-ISSUES.md`，待所有调用点迁移完成。
- 当前 `report` 节点内部已走 Workflow；外层仍是旧 graph。

## 14. S12 · 收尾

- Report：evidence/map/write 三节点；
- Chat：单节点 workflow；
- Kernel：context/checkpoint/tools/verifier；
- 结果：630 pytest、18 e2e；
- 评价体系仍未做，见 OPEN-ISSUES。

### 已知边界

- Report 的 evidence/map/write 目前是 deterministic handler，不是每个节点都启动 Kernel；
- S10 只做到“节点拆分 + step 事件”，token 级流式 UI 未做；
- 旧 graph 删除延后。


## 15. 后续阶段（S13–S20）

Phase 3.4 已扩展为完整目标：

- S13/S14：Report `source/evidence/map/write` 真正 Kernel 化；
- S15：Report 脱离旧 graph；
- S16：指标 definitions/points/spans；
- S17：固定评估集 + eval CLI；
- S18：自动评估器 + 人工 rubric；
- S19：自优化闭环；
- S20：20/50/100 压测、删除旧 graph、收尾。

详见 `phase3.4-workflow-kernel-refactor.md` v3.0.0。


## 16. S13–S14 · Report 节点 Kernel 化

- `ReportWorkflow` 的 `source/evidence/map/write` 各自拥有独立 `Kernel` 与 `KernelTools`。
- 工具：`load_scope / build_context / synthesize / assemble`。
- 每个节点有 Kernel loop、tool trace、独立 goal/budget。
- 节点之间仍通过 `WorkflowRunner` + artifact 传递。
- 测试：v2 wiring、step 事件、e2e 18。

### S15 状态

- 节点已不再直接调用 report engine；
- 但 API/CLI 仍是“10 节点 graph 外壳 → report 节点 → ReportWorkflow”；
- 真正删除 graph 需要迁移 run 生命周期/事件/CLI；当前未做，避免破坏 10 阶段契约。


## 17. S16–S19 · 指标与评估

### S16 已完成

- 迁移 `0009_metrics_v2`：`metric_definitions / metric_points / run_spans / experiments`；
- 表总数 26 → 30；ADR-0010；
- `eval/metric_catalog.py`：指标目录；
- `eval/metric_store.py`：点/span/采集；`evaluate` 自动采集 report 指标；
- `NULL` 与 0 分离。

### S17 部分

- `eval/datasets/ai-agents.json` fixture；
- `scripts/eval_run.py`、`scripts/eval_compare.py`；
- 真实 20 篇 `tune-cheap` 评估：score 0.5478，coverage .6087，citation 1.0，fallback .2；
- 20/50/100 冻结集尚未建立。

### S18 部分

- `eval/evaluators.py`：claim purity/citation 规则、LLMJudge 接口；
- `eval/rubrics/report.md`；
- 人工双评审未执行。

### S19 部分

- `eval/optimizer.py`：promotion policy、experiments 记录；
- `scripts/optimize.py`：baseline/candidate 晋级/拒绝；
- 自动多轮搜索/执行尚未做。

### 当前限制

- 指标采集只覆盖 report/claims/LLM，search/RAG 仍缺；
- 评估集是 fixture，不是真实冻结集；
- 自动优化未闭环，只做晋级判定。


## 18. Phase 3.4 关闭

- 640 pytest、18 e2e、30 表；
- Report 4 节点均走 Kernel；
- 指标 schema/采集/评估基础可用；
- **未完成**：API/CLI 完全脱离旧 graph、删除旧 graph、真实 20/50/100 冻结集、自动多轮闭环；
- 这些是明确的下一阶段迁移项，不是“已完成”。
