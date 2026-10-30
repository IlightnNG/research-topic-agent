# RESULTS — Phase 3.4（Workflow + Kernel 重构）

> 规范：`phase3.4-workflow-kernel-refactor.md`
> 当前进度：**S1–S3 完成**；S4+ 待做。
> 评价体系：未实现，见 `docs/OPEN-ISSUES.md`。

## 0. 一页摘要

| 指标 | 结果 |
|---|---|
| 阶段 | **S1–S3 完成** |
| 测试 | `pytest` **621 例**（新增 8 例 kernel/workflow） |
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
