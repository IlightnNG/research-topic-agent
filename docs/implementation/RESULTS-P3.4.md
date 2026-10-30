# RESULTS — Phase 3.4（Workflow + Kernel 重构）

> 规范：`phase3.4-workflow-kernel-refactor.md`
> 当前进度：**S1–S6 完成**；S7+ 待做。
> 评价体系：未实现，见 `docs/OPEN-ISSUES.md`。

## 0. 一页摘要

| 指标 | 结果 |
|---|---|
| 阶段 | **S1–S6 完成** |
| 测试 | `pytest` **625 例**（新增 12 例 kernel/workflow） |
| 代码 | `kernel/`、`workflow/` 基础层 |
| 兼容 | 未改旧 graph/report/chat 路径 |

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
