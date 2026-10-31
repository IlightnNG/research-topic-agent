# M6-P01 · Report API + Minimal UI

> 模块：M6 Interface
> 版本：1.0（2026-10-31）
> 状态：planned
> 依赖：M4-P02、M5-P01
> 目标：让完整 Report 可从 API 创建、观察、读取，并有一个最小可读 UI。
> **Chat 不在本 phase。**

---

## 1. 目标

当前：

```text
POST /api/v2/runs
GET  /api/v2/runs/{id}
GET  /api/v2/runs/{id}/report
GET  /api/v2/runs/{id}/events
GET  /api/v2/reports/{id}
GET  /
```

Phase 4：

```text
创建报告 run
→ SSE 观察节点/section
→ 读取报告
→ 最小 UI 阅读
→ 错误格式统一
```

---

## 2. 边界

### 改

```text
src/lit_agent_v2/api/app.py
src/lit_agent_v2/cli.py
src/lit_agent_v2/api/templates/       # 可选
```

### 不改

- Chat（保留现状，不开发）；
- source/evidence/map/write；
- 评分算法。

---

## 3. API

### POST /api/v2/runs

```json
{"topic_id": "llm-agents", "limit": 100, "focus_hint": "..."}
```

返回 202：

```json
{
  "run_id": "...",
  "state": "running",
  "events": "/api/v2/runs/.../events"
}
```

### GET /api/v2/runs/{id}

```json
{
  "id": "...",
  "state": "running|succeeded|failed|paused|aborted",
  "phase": "...",
  "error_code": null
}
```

### GET /api/v2/runs/{id}/report

```json
{"run_id": "...", "report_id": "..."}
```

### GET /api/v2/reports/{id}

```json
{
  "report": {
    "report_id": "...",
    "title": "...",
    "state": "complete|degraded",
    "word_count": 2500,
    "n_claims": 120,
    "content_md": "..."
  },
  "sections": [
    {"section_id": "D1", "kind": "deep_dive", "title": "...", "body": "..."}
  ]
}
```

### GET /api/v2/runs/{id}/events

SSE：

```text
id: 12
event: section.delta
data: {"seq":12,"type":"section.delta","node_id":"write","payload":{"section_id":"D1"}}
```

支持 `Last-Event-ID`。

---

## 4. 最小 UI

`GET /`：

```text
[ topic ] [ limit ] [ Run ]

Workflow:
  source ✓
  evidence ✓
  map ✓
  write ...
  finalize

Sections:
  At a Glance
  D1 ...
  Comparison
  Gaps
  Method
  Index
```

要求：

- 纯 HTML/JS，不引入 Vue；
- EventSource 消费；
- section 可点击定位；
- 错误可见；
- 不显示 prompt/key；
- 不实现 Chat。

---

## 5. 错误格式

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
400/404/409/422/500
```

错误码见 `docs/ERRORS.md`。

---

## 6. 测试

```text
tests/v2/test_m6_report_api.py
tests/v2/test_m6_sse_ui.py
tests/v2/test_m6_errors.py
```

必须覆盖：

- create → poll → report；
- SSE 收到 node/section；
- Last-Event-ID 重放；
- 404；
- 错误格式；
- UI 页面可读；
- 不调用 Chat。

E2E：

```text
运行 20 篇
→ 页面显示 sections
→ 报告可读
```

---

## 7. 指标

| 指标 | 目标 |
|---|---|
| `api.create_latency_ms` | 记录 |
| `api.error_rate` | <1% |
| `sse.replay_success` | 1.0 |
| `ui.load_success` | 1.0 |
| `report.sections_visible` | 全 |
| `chat.requests` | 0（本 phase 不变） |

---

## 8. 验收

```text
1. API 创建报告；
2. 状态可轮询；
3. SSE 可见；
4. 报告可读；
5. 页面可打开；
6. 错误格式统一；
7. Chat 未改；
8. 无旧前端。
```

---

## 9. 回滚

- 保留现有 API；
- 新 UI 独立路由；
- 不删除 Chat；
- 失败可回退旧 timeline。

---

## 10. Commit

```text
feat(M6-P01): add report api and minimal workflow ui
```
