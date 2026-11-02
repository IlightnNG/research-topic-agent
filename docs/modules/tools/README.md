# T · Tools

> 模块：Tools
> 版本：2.1（2026-11-02）
> 状态：target；Phase 4.2 优先实现 ToolRuntime
> 目标：所有外部交互的唯一入口

---

## 1. 职责

```text
ToolSpec
ToolRuntime
input/output schema
allow / deny / ask
timeout / cancel
retry
parallel-safe / exclusive
idempotency
side-effect boundary
artifact spill
tool packs
adapters
```

## 2. 不负责

```text
Node 顺序
LLM 推理
报告质量判断
Workflow 状态
```

## 3. ToolSpec

```python
ToolSpec(
    name,
    namespace,
    title,
    description,
    version,

    input_schema,
    output_schema,

    side_effect,
    parallel_safe,
    idempotent,
    requires_approval,

    timeout_s,
    max_output_chars,
    max_retries,
    retry_on,
    cost_usd,

    capabilities,
    tags,

    handler(args, context),
    render(args, output),
)
```

## 4. Tool 执行流水线

```text
resolve visible tool
→ validate input
→ policy / guard
→ execute with timeout + cancellation
→ validate output
→ artifact spill
→ postprocess / render
→ structured result
→ tool/result event
```

工具失败返回 `ToolResult`，不抛到 Kernel。

## 5. 工具分层

一个 Runtime，通过 metadata 分类：

```text
general:
  context.*
  plan.*
  memory.*
  artifact.*
  fs.*
  test.run
  verify.*

domain:
  source.*
  corpus.*
  claims.*
  report.*
  chat.*
  eval.*
```

分类用于：

```text
权限
prompt 体积
预算
审计
UI 分组
```

不是两个互不相通的 Registry。

## 6. 工具集

```python
GENERAL_TOOLSET
REPORT_TOOLSET
CHAT_TOOLSET
SOURCE_TOOLSET
```

Node / Agent 只看到自己的 toolset。

## 7. 规则

- 所有外部 I/O 只能通过 Tool。
- 工具参数和输出必须 schema 校验。
- 有副作用工具必须幂等或可回滚。
- 工具错误必须有结构化 error code。
- 大输出必须写 artifact，返回 preview。
- Kernel 不直接 import domain service。

## 8. 目标文件

```text
tools/runtime.py
tools/schema.py
tools/sets.py
tools/general/context.py
tools/general/plan.py
tools/general/memory.py
tools/general/artifact.py
tools/general/test.py
tools/general/verify.py
tools/domain/source.py
tools/domain/corpus.py
tools/domain/claims.py
tools/domain/report.py
tools/domain/chat.py
```

## 9. 验收

```text
schema 失败拒绝
未注册工具拒绝
timeout / cancel
output schema
parallel scheduler
artifact spill
toolset 可见性
```

详见 [`docs/implementation/PHASE4.2-agent-kernel-tools.md`](../../implementation/PHASE4.2-agent-kernel-tools.md)。
