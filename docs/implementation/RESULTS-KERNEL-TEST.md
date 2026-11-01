# RESULTS · Kernel + Tools Test

> 日期：2026-11-01
> 范围：Node Kernel、ToolRegistry、WorkflowRunner
> 性质：fake LLM + 1 个 live LLM smoke test

---

## 1. 总门禁

```text
pytest tests/v2   123 passed
ruff              clean
```

包含：

```text
Node workflow runner
Node kernel
Tool registry
Tool packs
Kernel + Tool integration
```

---

## 2. 已覆盖情况

| 场景 | 结果 |
|---|---|
| 单 tool → final | ✅ |
| 一个 step 多 tool calls | ✅ |
| tool schema 非法 | ✅ 作为 observation，不终止 |
| 未授权 tool | ✅ failed |
| tool timeout | ✅ observation，继续 |
| tool retry | ✅ |
| read-only 并行 | ✅ |
| side-effect serial | ✅ |
| budget | ✅ |
| no-progress | ✅ |
| max_steps | ✅ |
| cancel | ✅ |
| checkpoint resume | ✅ |
| tool output pruning | ✅ |
| multiple node chain | ✅ |
| corpus tools | ✅ |
| claims/quote tools | ✅ |
| report plan/check/assemble | ✅ |
| streaming callback | ✅ |
| SSE stream transport | ✅ |
| inbox steering | ✅ |
| journal / per-call checkpoint | ✅ |
| history compaction | ✅ |
| trace/call-id invariants | ✅ |

---

## 3. Live LLM smoke test

Node：

```text
id: inspect
goal: Use corpus.stats exactly once, then final with paper count
tools: corpus.stats
```

输入：

```text
tmp corpus with 2 papers
```

结果：

```text
stop_reason: final
calls:
  step 1, call_1, corpus.stats, ok=True
output: {"papers": 2}
usage: prompt 720 / completion 102 tokens
model: deepseek-flash
```

补充 live streaming：

```text
stream_json
  → SSE delta
  → {"ok": true}
  → usage 65/26
```

结论：

> 真实 LLM 能按 Kernel 的 tool schema 调用本地工具，并把结果用于 final；
> 也支持关闭/开启 streaming。

---

## 4. 发现的限制

```text
streaming 依赖 LLM stream_json
没有 token-level context compaction
inbox/steering 只在 step boundary 生效
没有独立 session projection/store
report.write_section 未实现
report.persist 未实现
```

这些不是本次 bug，是明确的后续范围。

---

## 5. 结论

当前 Kernel + Tools：

```text
可以运行单 Node
可以运行多 Node
可以处理工具错误
可以并行 read-only
可以串行 side-effect
可以 checkpoint/resume
可以 streaming
可以 steering
可以 journal
可以 compact history
可以被真实 LLM 驱动
```

但仍不是完整报告链路，因为：

```text
report.write_section
report.persist
verifier
```

尚未接入。
