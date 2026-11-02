# W · Workflow

> 模块：Workflow
> 版本：2.1（2026-11-02）
> 状态：runner 已实现；Phase 4.2 改为“特制 workflow + 通用 runner”
> 目标：为不同任务提供特制的外层约束

---

## 1. 定位

```text
Kernel 是通用发动机。
Workflow 是特制任务外壳。
```

Workflow 不是通用层。

它针对具体任务定义：

```text
阶段拆分
阶段顺序
阶段输入/输出
阶段工具集
阶段验收
重试 / 暂停 / 人工确认
并行
```

## 2. 职责

```text
WorkflowDefinition
NodeSpec
Node order
enabled / optional
node skipped
stage commit / retry
pause / resume / abort
run state
events
artifact handoff
```

## 3. 不负责

```text
LLM 循环
工具执行
上下文压缩
通用 repair
报告领域判断
```

## 4. 双层调用

```text
Workflow
  → NodeSpec
  → KernelTask
  → Kernel 自主执行
  → stage verifier
  → commit
  → next Node
```

Workflow 只约束阶段，不替代 Kernel。

## 5. 特制 Workflow

```text
workflow/report.py
  source.collect
  evidence.extract
  report.generate
  finalize

workflow/chat.py
  retrieve
  answer
  verify

workflow/research.py
workflow/evaluation.py
```

不存在“通用报告 Workflow”。

## 6. 规则

- Workflow 是领域相关的。
- Workflow 不 import Kernel 内部实现，只通过 `KernelTask` 调用。
- Node 至少 3 个工具，禁止单工具 Agent Node。
- Node 间只传 artifact。
- commit 前必须过 stage verifier。
- pause 在 Node/step 边界生效。

## 7. 目标文件

```text
workflow/core/definition.py
workflow/core/runner.py
workflow/core/state.py
workflow/report.py
workflow/chat.py
workflow/research.py
```

## 8. 验收

```text
report workflow 可构建
每个 Node 调用同一 Kernel
Node 多工具
阶段验收
optional/skip
resume 跳过 committed
报告 workflow 不污染 Kernel
```

详见 [`docs/KERNEL-WORKFLOW.md`](../../KERNEL-WORKFLOW.md)。
