# RESULTS · M1-P01

> Phase：M1-P01 Kernel ReAct + LLM client
> 日期：2026-10-31
> 状态：done（metric handoff 未接 M4）

## 门禁

```text
pytest tests/v2   39 passed（含 1 live LLM）
ruff              clean
```

## 已实现

```text
src/lit_agent_v2/kernel/
  llm.py          DeepSeekChatClient / LLMConfig / LLMUsage / LLMClient
  tools.py        ToolSpec / ToolBox / schema / timeout / cost
  checkpoint.py   KernelCheckpoint / KernelCheckpointStore
  loop.py         LLM ReAct / no-progress / budget / cancel / events / step checkpoint
```

## 测试

```text
tests/v2/test_m1_kernel.py   7 tests
  - tool → final
  - checkpoint/resume
  - tool schema failure
  - no-progress
  - dotenv config
  - checkpoint store
  - tool timeout
  - live DeepSeek JSON
```

## 当前边界

- M4 report 节点仍是 deterministic handler；
- Kernel 结果尚未写入 `metric_points`；
- M4-P02 才把 LLM writer 接入报告；
- 本次只改 M1，没有改 M2–M6 契约。

## Commit

```text
feat(M1-P01): add llm react kernel with step checkpoints
```
