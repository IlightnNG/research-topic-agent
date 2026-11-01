# I · Interface

> 模块：Interface
> 版本：2.0（2026-11-01）
> 状态：target；现有 API/UI 可复用部分
> 目标：只调用 Workflow use case。

---

## 1. 职责

```text
HTTP API
SSE
CLI
UI
error envelope
report view
```

## 2. 不负责

```text
domain service
SQL
report writer
Tool 调用
```

## 3. API

```text
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

## 4. 目标文件

```text
interface/api.py
interface/cli.py
interface/templates/
```

## 5. 规则

- Interface 只依赖 RunService/ReportReader；
- 不 import `ReportWorkflow`、`WriteService`、`OpenAlex`；
- 错误统一 envelope；
- SSE 支持 `Last-Event-ID`；
- Chat 不在 Phase 4.1。

## 6. 验收

```text
create → poll → report
SSE replay
error envelope
UI sections
```

## 7. Phase docs

```text
I-P01-report-api.md
I-P02-demo-ui.md
```
