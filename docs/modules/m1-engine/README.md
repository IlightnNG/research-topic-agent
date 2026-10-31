# M1 · Engine

> 模块 ID：M1
> 代码：`src/lit_agent_v2/{contracts.py,run_shell.py,workflow/,kernel/,storage/}`
> 目标：所有业务模块共用的运行外壳与内核，不包含任何领域逻辑。

---

## 1. 职责

M1 负责：

- Run 生命周期：prepare / run / pause / resume / abort；
- 固定 Workflow 的定义与执行；
- Node 契约、artifact 传递、commit、checkpoint；
- Kernel：单节点 agent loop、工具调用、步数/预算/取消；
- 状态机、事件、日志、错误边界；
- SQLite schema、artifact store。

M1 不负责：

- 抓论文；
- 解析 PDF；
- 抽 claim；
- 聚类/写报告；
- 评估/调参；
- API/UI/Chat 业务。

---

## 2. 边界

### 允许依赖

```text
M1 → 无领域模块
M1 只依赖标准库、SQLite、少量第三方
```

### 禁止

- M1 import `domains/report`、`domains/chat` 的具体实现；
- M1 直接调用 OpenAlex/PDF；
- M1 里写 report section；
- M1 里算 report score。

Workflow 通过注册的 handler 调用领域模块。

---

## 3. 核心对象

### RunRequest

```python
RunRequest(topic_id, limit=100, focus_hint=None, workflow="report")
```

### NodeSpec

```python
NodeSpec(
    id, kind, input_keys, output_key,
    allowed_tools, postconditions,
    budget_usd, timeout_s, verifier
)
```

### WorkflowDefinition

```python
WorkflowDefinition(name, version, nodes)
```

### NodeResult

```python
NodeResult(node_id, state, output, artifact_sha, error, steps)
```

### Kernel

```python
Kernel.run(goal, toolbox, completer)
```

---

## 4. 状态机

### Run

```text
pending → running → succeeded
                  → failed
                  → paused → running
                  → aborted
```

### Node

```text
pending → running → committed
                  → failed
                  → skipped
```

恢复规则：

- 只从 committed 之后恢复；
- 当前 Node 未 commit → 重跑该 Node；
- artifact sha 缺失 → 从最近完整 Node 重跑。

---

## 5. 目标 Kernel（ReAct）

```text
Observe(context)
  → Think
  → Act(tool)
  → Observe(tool result)
  → ... bounded
  → Final(outputs)
```

Phase 必须补齐：

- LLM completer；
- tool schema/参数校验；
- no-progress 检测；
- cost 累计；
- step checkpoint；
- token/step 事件；
- context 压缩。

当前 Kernel 只有 minimal action loop，不满足完整 ReAct。

---

## 6. 指标

| 指标 | 目标 |
|---|---|
| `run.success_rate` | ≥0.95 |
| `run.resume_success` | 1.0 |
| `node.commit_rate` | 1.0 |
| `node.retry_count` | 记录 |
| `checkpoint.integrity` | 1.0 |
| `event.lag_ms` | 记录 |
| `kernel.steps` | 记录 |
| `kernel.no_progress` | 0 |
| `kernel.cost_usd` | 预算内 |

指标只用于模块评分，不把“跑完”当质量。

---

## 7. 验收

Phase 收尾必须通过：

```text
1. fake workflow 端到端；
2. committed Node 不被重跑；
3. pause/resume 后结果一致；
4. artifact sha 校验；
5. 事件 seq 连续；
6. 无 legacy import；
7. 指标落库；
8. 集成测试调用 M2–M4。
```

---

## 8. 测试

```text
tests/v2/test_s1_s2.py
tests/v2/test_s6_control.py
```

后续新增：

```text
tests/v2/test_m1_*.py
```

测试必须覆盖：

- run 状态；
- node 状态；
- resume；
- pause；
- corrupted artifact；
- event replay；
- kernel max_steps/cancel。

---

## 9. 失败模式

| 错误 | 处理 |
|---|---|
| artifact 缺失 | 从最近 committed Node 重跑 |
| Node handler 异常 | Node failed，run failed |
| pause 在 Node 内 | 当前 Node 完成后暂停 |
| 事件 seq 冲突 | 单写者/allocator |
| checkpoint 损坏 | 拒绝恢复，重跑 |

错误码见 `docs/ERRORS.md`。

---

## 10. 当前状态

| 能力 | 状态 |
|---|---|
| RunShell | ✅ |
| WorkflowRunner | ✅ |
| artifact sha | ✅ |
| Node resume | ✅ |
| pause/resume | ✅ 边界 |
| Kernel minimal loop | ✅ |
| 完整 ReAct | ❌ |
| step checkpoint | ❌ |
| 单写者事件 | ❌ |
| 旧系统 | 已移出 |

---

## 11. 相关文档

- `docs/ARCHITECTURE.md`
- `docs/CONVENTIONS.md`
- `docs/ERRORS.md`
- `docs/LOGGING.md`
- `docs/TODO.md`


---

## Phase docs

- [M1-P01-kernel-react-and-llm.md](M1-P01-kernel-react-and-llm.md)
