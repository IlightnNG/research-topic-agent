# M6 · Interface

> 模块 ID：M6
> 代码：`src/lit_agent_v2/{api,cli,domains/chat}/`
> 目标：对外暴露稳定 API/CLI/Chat/UI 契约，不承载领域算法。

---

## 1. 职责

- FastAPI v2；
- Run API：create/read/report/events；
- pause/resume/abort；
- SSE；
- Chat API；
- session 持久化；
- CLI；
- 最小 timeline；
- 错误响应格式。

不负责：

- 检索/PDF；
- claim；
- 聚类/写作；
- 评分算法。

---

## 2. API 契约

```text
POST /api/v2/runs
GET  /api/v2/runs/{id}
GET  /api/v2/runs/{id}/report
GET  /api/v2/runs/{id}/events       SSE
POST /api/v2/runs/{id}/pause
POST /api/v2/runs/{id}/resume
POST /api/v2/runs/{id}/abort
GET  /api/v2/reports/{id}
POST /api/v2/chat
GET  /api/v2/chat/sessions/{id}
GET  /api/v2/chat/stream
GET  /api/v2/health
```

---

## 3. Run API

### POST /runs

```json
{"topic_id": "llm-agents", "limit": 100, "focus_hint": "tool use"}
```

返回 `202`：

```json
{"run_id": "...", "state": "running", "events": "/api/v2/runs/.../events"}
```

### GET /runs/{id}

返回 run row：state / phase / error_code / times。

### GET /runs/{id}/report

返回 `report_id`；没有则 404。

---

## 4. SSE

```text
id: 12
event: node.finished
data: {"seq":12,"type":"node.finished","node_id":"map","payload":{},"ts":"..."}
```

支持：

- `Last-Event-ID` 重放；
- 终态结束；
- 心跳；
- 不发送敏感数据。

---

## 5. Chat

```text
POST /api/v2/chat
  {topic_id, message, session_id?}
  → {session_id, text, answered, citations}
```

```text
GET /api/v2/chat/sessions/{id}
  → messages
```

```text
GET /api/v2/chat/stream?topic_id=...&message=...
  → token.delta SSE
```

---

## 6. 边界

### 允许

- 调 M1 RunShell；
- 调 M4 report 读取；
- 调 M5 metrics 读取；
- 写 chat session 表；
- SSE。

### 禁止

- 直接写 reports/claims；
- 直接抽 claim；
- 直接改 Workflow；
- 返回 unsupported 数据；
- 把错误 500 当正常。

---

## 7. 错误响应

统一：

```json
{
  "error": {
    "code": "E_RUN_NOT_FOUND",
    "message": "...",
    "run_id": "...",
    "details": {}
  }
}
```

HTTP：

```text
400 invalid
404 not found
409 conflict/lock
422 schema
429 rate limit
500 internal
```

错误码见 `docs/ERRORS.md`。

---

## 8. 指标

| 指标 | 目标 |
|---|---|
| `api.latency_p95` | 记录 |
| `api.error_rate` | <1% |
| `sse.replay_success` | 1.0 |
| `chat.citation_fidelity` | 1.0 |
| `chat.refusal_precision` | ≥0.9 |
| `session.persistence` | 1.0 |
| `ui.e2e` | 通过 |

---

## 9. 验收

```text
1. create → poll → report；
2. SSE 收到 node/section；
3. Last-Event-ID 重放；
4. pause/resume；
5. chat session 4 条消息；
6. token.delta；
7. 错误格式；
8. 无领域逻辑。
```

---

## 10. 测试

```text
tests/v2/test_s4_api.py
tests/v2/test_s5_chat.py
```

新增：

```text
tests/v2/test_m6_errors.py
tests/v2/test_m6_sse_replay.py
tests/v2/test_m6_chat_contract.py
```

---

## 11. 当前状态

| 能力 | 状态 |
|---|---|
| FastAPI | ✅ |
| async run | ✅ |
| SSE | ✅ |
| replay | ✅ |
| pause/resume | ✅ |
| report read | ✅ |
| chat session | ✅ |
| chat LLM | ⚠️ composer 可注入，未默认 |
| 生产 UI | ❌ |
| 旧 Vue | 已移出 |

---

## 12. 相关文档

- `docs/ARCHITECTURE.md`
- `docs/ERRORS.md`
- `docs/LOGGING.md`
- `docs/TODO.md`
