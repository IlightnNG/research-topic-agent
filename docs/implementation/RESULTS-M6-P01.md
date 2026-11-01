# RESULTS · M6-P01

> Phase：M6-P01 Report API + Minimal UI
> 日期：2026-11-01
> 状态：done

## 门禁

```text
pytest tests/v2   77 passed（含 3 个 live LLM）
ruff              clean
contract freeze   v1.2 passed
```

## 已实现

```text
api/app.py
  POST /api/v2/runs
  GET  /api/v2/runs/{id}
  GET  /api/v2/runs/{id}/events
  POST /api/v2/runs/{id}/pause
  POST /api/v2/runs/{id}/resume
  POST /api/v2/runs/{id}/abort
  GET  /api/v2/runs/{id}/report
  GET  /api/v2/reports/{id}
  GET  /
```

### Error envelope

```json
{
  "error": {
    "code": "E_RUN_NOT_FOUND",
    "message": "...",
    "details": {}
  }
}
```

错误码：

```text
E_RUN_NOT_FOUND
E_REPORT_NOT_FOUND
E_CORPUS_NOT_FOUND
E_INVALID_REQUEST
E_INTERNAL
E_HTTP
```

### UI

`GET /`：

- topic/limit；
- run；
- SSE 事件；
- node/section 进度；
- report sections；
- 错误显示；
- 不依赖前端框架。

### Chat

未改。

## 测试

```text
tests/v2/test_m6_api.py
  - report API + sections
  - minimal UI
  - error envelope
  - missing corpus
```

## 未完成

- 还没有 report scorecard endpoint（M5 接入）；
- UI 没有 markdown 渲染；
- 没有生产静态资源/构建；
- Chat 不在本 phase。

## Commit

```text
feat(M6-P01): add report api and minimal workflow ui
```
