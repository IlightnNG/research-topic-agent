# M1-P01 · Kernel ReAct + LLM Client + Step Checkpoint

> 模块：M1 Engine
> 版本：1.0（2026-10-31）
> 状态：planned
> 依赖：无
> 目标：让 Node 内的 LLM agent loop 可运行、可观测、可恢复，而不是只有 action/final 的最小循环。

---

## 1. 目标

当前 `kernel/loop.py`：

```text
completer() → tool/final
```

Phase 4 要变成：

```text
LLM Observe → Think → Act(tool) → Observe
  → ... bounded
  → Final
```

并支持：

- 工具 schema；
- 参数校验；
- no-progress；
- cost/token；
- step checkpoint；
- step 事件；
- cancel/pause；
- prompt/config version。

---

## 2. 边界

### 本 phase 改

```text
src/lit_agent_v2/kernel/loop.py
src/lit_agent_v2/kernel/llm.py          # 新增
src/lit_agent_v2/kernel/context.py      # 新增
src/lit_agent_v2/kernel/checkpoint.py   # 新增
src/lit_agent_v2/workflow/runner.py     # step hook
src/lit_agent_v2/contracts.py           # Kernel 相关 contract
```

### 不改

- report/source/evidence/map/write；
- API；
- 评分；
- Chat。

---

## 3. 接口

### LLMClient

```python
class LLMClient(Protocol):
    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        max_tokens: int,
        temperature: float,
        prompt_version: str,
    ) -> tuple[dict, LLMUsage]: ...
```

`LLMUsage`：

```python
@dataclass
class LLMUsage:
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    model: str
    prompt_version: str
```

DeepSeek 使用：

```text
base_url = https://api.deepseek.com
model = deepseek-flash
Authorization: Bearer <get_secret_value()>
```

注意：禁止把 `SecretStr` 直接拼 header。

### Kernel

```python
class Kernel:
    def run(
        self,
        goal: Goal,
        toolbox: ToolBox,
        *,
        llm: LLMClient,
        checkpoint: KernelCheckpoint | None = None,
    ) -> KernelResult
```

### Goal

```python
Goal(
    node_id,
    objective,
    system_prompt,
    max_steps=6,
    max_usd=0.10,
    timeout_s=300,
)
```

### Tool

```python
ToolSpec(
    name,
    description,
    parameters: dict,
    timeout_s,
    cost_usd=0,
    handler,
)
```

---

## 4. Loop

```text
1. 读 checkpoint，恢复 step/history/tool trace/cost
2. 构造 prompt:
   - system
   - objective
   - available tools
   - artifact context
   - history
3. LLM 返回 JSON:
   {"action":"tool","tool":name,"args":{...}}
   或
   {"action":"final","outputs":{...}}
4. tool 参数 schema 校验
5. tool 执行
6. 记录 tool.called / tool.result
7. 写 step checkpoint
8. 检查:
   - max_steps
   - cost
   - timeout
   - cancel
   - no-progress
9. final → output
```

### no-progress

```text
same tool + same args 连续 2 次 → stop_reason=no_progress
```

### 失败

```text
LLM 非 JSON → 重试 1 次，仍失败 → failed
tool error → 记录，允许 LLM 换工具；连续 2 次同类失败 → failed
```

---

## 5. Checkpoint

```json
{
  "schema_version": 2,
  "node_id": "D1",
  "step": 2,
  "history": [],
  "trace": [],
  "cost_usd": 0.02,
  "usage": {"prompt_tokens": 1000, "completion_tokens": 200},
  "stop_reason": null
}
```

写入：

- `run_nodes.checkpoint_json` 或独立 `run_steps`；
- 每 step commit；
- resume 从 step+1。

---

## 6. Prompt

System：

```text
You are a report section worker inside a fixed workflow.
You can only use the provided tools.
Do not invent evidence.
Every claim must be traceable to a tool result.
Return JSON only.
```

Action schema：

```json
{"action":"tool","tool":"...","args":{}}
{"action":"final","outputs":{}}
```

禁止：

- 返回自然语言；
- 返回 markdown 包 JSON；
- 使用未注册工具；
- 修改 workflow。

---

## 7. 事件

```text
kernel.started
step.started
tool.called
tool.result
token.delta
kernel.finished
kernel.failed
```

payload：

```json
{"step": 2, "tool": "search", "args_hash": "...", "ok": true, "cost_usd": 0.01}
```

---

## 8. 指标

| 指标 | 目标 |
|---|---|
| `kernel.steps` | 记录 |
| `kernel.success_rate` | ≥0.95 |
| `kernel.no_progress` | 0 |
| `kernel.invalid_json` | <0.05 |
| `kernel.cost_usd` | 预算内 |
| `kernel.step_checkpoint` | 1.0 |
| `kernel.resume_success` | 1.0 |

---

## 9. 测试

```text
tests/v2/test_m1_kernel.py
tests/v2/test_m1_llm_client.py
tests/v2/test_m1_step_resume.py
```

必须覆盖：

- fake LLM tool→final；
- 非 JSON；
- 未注册工具；
- tool 异常；
- no-progress；
- max steps；
- cost；
- cancel；
- checkpoint/resume；
- SecretStr 正确取 key。

Live：

```text
DeepSeek 小请求 + 1 个工具
```

---

## 10. 验收

```text
1. LLM completer 可用；
2. tool schema 校验；
3. step checkpoint；
4. resume 不重复调用；
5. 事件完整；
6. 指标落库；
7. fake + live 各 1 条；
8. 无旧 import。
```

---

## 11. 回滚

- 保留原 minimal `completer` 模式；
- 新 Kernel 通过 `use_llm=False` 可退回；
- 但 Report 正式路径必须用 LLM。

---

## 12. Commit

```text
feat(M1-P01): add llm react kernel with step checkpoints
```
