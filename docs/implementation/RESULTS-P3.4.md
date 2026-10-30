# RESULTS — Phase 3.4（Workflow + Kernel 重构）

> 规范：`phase3.4-workflow-kernel-refactor.md`
> 当前进度：**S1–S9 完成**；S10+ 待做。
> 评价体系：未实现，见 `docs/OPEN-ISSUES.md`。

## 0. 一页摘要

| 指标 | 结果 |
|---|---|
| 阶段 | **S1–S9 完成** |
| 测试 | `pytest` **629 例**；Playwright **18 passed** |
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
