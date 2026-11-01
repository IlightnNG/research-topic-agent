# W · Workflow

> 模块：Workflow
> 版本：2.0（2026-11-01）
> 状态：target；当前代码仍在旧 `M1` 结构中
> 目标：管理 Node 链、状态、提交与恢复。

---

## 1. 职责

```text
WorkflowDefinition
NodeSpec
Node order
enabled / optional
node skipped
commit / retry
pause / resume / abort
run state
events
artifact handoff
```

## 2. 不负责

```text
LLM 调用
工具实现
领域逻辑
章节内容
数据库 SQL
```

## 3. 契约

```python
WorkflowDefinition(
    name,
    version,
    nodes: tuple[NodeSpec, ...],
    features: FeatureProfile,
)
```

Node：

```python
NodeSpec(
    id,
    goal,
    tools,
    inputs,
    output_schema,
    verifier,
    max_steps,
    max_usd,
    timeout_s,
    optional=False,
    enabled=True,
)
```

## 4. 目标文件

```text
workflow/definition.py
workflow/runner.py
workflow/state.py
workflow/definitions/report.py
```

## 5. 规则

- Workflow 就是 Node 链；
- 运行时不允许 LLM 增删 Node；
- `enabled=False` → `node.skipped`；
- `optional=True` 失败可降级；
- Node 间只传 artifact；
- commit 前必须过 Verifier。

## 6. 验收

```text
Node 链可构建
optional/skip 可用
resume 跳过 committed
Node 失败可重试
事件完整
```

## 7. 当前实现

```text
workflow/node/definition.py
workflow/node/runner.py
workflow/node/state.py
workflow/node/ports.py
```

状态：4.1.2 done；旧 workflow/runner.py 仍在迁移期保留。

## 8. Phase docs

```text
W-P01-node-chain.md
W-P02-optional-nodes.md
```
