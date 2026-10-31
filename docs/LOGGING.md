# Logging & Events

> 版本：1.0（2026-10-31）
> 目标：统一事件、日志、指标三类可观测数据，避免重复和泄漏。

---

## 1. 三类数据

| 类型 | 用途 | 存储 |
|---|---|---|
| Event | 运行/节点/工具/流式状态 | `run_events` + SSE |
| Log | 调试/错误上下文 | 文件/stdout（后续） |
| Metric | 数值评估 | `metric_points` / `run_spans` |

不要用日志代替事件，不要用事件代替指标。

---

## 2. Event 合约

```json
{
  "schema_version": 1,
  "event_id": "uuid",
  "run_id": "...",
  "seq": 12,
  "ts": "2026-10-31T09:00:00Z",
  "type": "node.finished",
  "module": "M4",
  "node_id": "write",
  "severity": "info",
  "payload": {}
}
```

规则：

- `seq` 单调递增；
- `event_id` 唯一；
- `run_id` 必填；
- `module` 必填；
- `payload` 不放大文本/密钥；
- SSE `id` = `seq`。

---

## 3. Event 类型

```text
run.started
run.paused
run.resumed
run.finished
run.failed

node.started
node.finished
node.failed
node.skipped

step.started
step.finished

tool.called
tool.result

section.delta
token.delta

verifier.verdict
checkpoint.saved
```

---

## 4. 日志等级

```text
debug    开发细节
info     正常状态变化
warning  可恢复/降级
error    失败/阻断
```

规则：

- 同一事件只打一次主日志；
- 错误日志带 `error_code`；
- 重试用 warning；
- 不打印完整 prompt、论文全文、用户密钥；
- 大对象记录 hash/长度。

---

## 5. 关联字段

每条日志/事件尽量带：

```text
run_id
node_id
step
module
event_id
span_id
error_code
```

这样可以从报告问题反查到具体 Node。

---

## 6. 脱敏

禁止记录：

- API key；
- `.env` 内容；
- 用户 token；
- 论文全文；
- 完整 LLM prompt；
- 个人隐私。

允许记录：

- key 是否存在；
- hash；
- 长度；
- 模型名；
- token 数；
- 错误码。

---

## 7. 保留

建议：

```text
run_events      90 天
logs            30 天
metric_points   1 年
run_spans       90 天
report artifacts 永久（sha）
```

未来按存储压力调整。

---

## 8. 当前实现

`workflow/events.py`：

- 写 `run_events`；
- seq = MAX(seq)+1；
- SSE 支持 replay。

缺口：

- 无 `module` 字段；
- 无 `severity`；
- 无结构化日志文件；
- seq 非单写者；
- section 事件模块归属靠 payload。

---

## 9. 验收

```text
1. 事件 seq 连续；
2. SSE 重放不丢；
3. 无密钥/全文；
4. 每个 Node 有 started/finished；
5. 错误有 error_code；
6. 指标/事件/日志不重复；
7. 能从 report 反查 node。
```
