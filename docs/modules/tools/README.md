# T · Tools

> 模块：Tools
> 版本：2.0（2026-11-01）
> 状态：target
> 目标：所有外部交互的唯一入口。

---

## 1. 职责

```text
ToolSpec
ToolRegistry
input/output schema
allowlist
timeout / cost
idempotency
side-effect boundary
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

## 3. 工具命名空间

```text
source.*
corpus.*
claims.*
report.*
eval.*
audit.*
storage.*
llm.*
http.*
```

## 4. 目标文件

```text
tools/spec.py
tools/registry.py
tools/packs/source.py
tools/packs/corpus.py
tools/packs/evidence.py
tools/packs/claims.py
tools/packs/report_plan.py
tools/packs/report.py
tools/packs/storage.py
tools/adapters/openalex.py
tools/adapters/pdf.py
tools/adapters/llm.py
```

## 5. 规则

- 所有外部 I/O 只能通过 Tool；
- 工具参数先 schema 校验；
- 有副作用工具必须幂等或可回滚；
- 工具错误必须返回 `ToolResult`；
- Node 只能看 allowlist；
- kernel 不直接 import domain service。

## 6. 验收

```text
schema 失败拒绝
未注册工具拒绝
timeout
side-effect failure
idempotency
```

## 7. Phase docs

```text
T-P01-registry.md
T-P02-source-tools.md
T-P03-report-tools.md
```
