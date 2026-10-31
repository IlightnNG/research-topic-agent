# Errors

> 版本：1.0（2026-10-31）
> 目标：统一错误码、HTTP 映射、重试语义、日志字段。
> 当前 v2 仍以 `RuntimeError` 为主；本文件是目标注册表，实施时逐步落地。

---

## 1. 错误码格式

```text
E_<DOMAIN>_<DETAIL>
```

示例：

```text
E_SOURCE_HTTP
E_EVIDENCE_QUOTE
E_REPORT_COUNT
```

规则：

- 全大写；
- domain 属于模块；
- 不可重复；
- 不把异常类名当错误码；
- 不把动态内容写进 code。

---

## 2. 错误响应

API：

```json
{
  "error": {
    "code": "E_RUN_NOT_FOUND",
    "message": "run not found",
    "run_id": "...",
    "details": {}
  }
}
```

HTTP：

```text
400 invalid input
401 auth (未来)
403 forbidden
404 not found
409 conflict/lock
422 schema
429 rate limit
500 internal
503 dependency
```

规则：

- 不返回 traceback；
- 不返回 API key；
- 不返回全文 prompt；
- `message` 可展示；
- `details` 可审计；
- `run_id` 用于关联。

---

## 3. 重试语义

```text
retryable:
  E_SOURCE_HTTP
  E_SOURCE_RATE_LIMIT
  E_SOURCE_TIMEOUT
  E_EVIDENCE_LLM_TIMEOUT

non-retryable:
  E_SOURCE_EMPTY
  E_EVIDENCE_QUOTE
  E_REPORT_COUNT
  E_EVAL_DATASET
```

重试必须有上限和 backoff；不允许无限重试。

---

## 4. 注册表

| Code | Module | HTTP | Retry | 状态 | 说明 |
|---|---|---|---|---|---|
| `E_RUN_NOT_FOUND` | M1 | 404 | no | planned | run 不存在 |
| `E_RUN_STATE_INVALID` | M1 | 409 | no | planned | 当前状态不允许操作 |
| `E_NODE_HANDLER` | M1 | 500 | no | planned | Node handler 未注册/异常 |
| `E_ARTIFACT_MISSING` | M1 | 500 | yes | planned | artifact sha 找不到 |
| `E_CHECKPOINT_INVALID` | M1 | 500 | no | planned | checkpoint 损坏 |
| `E_SOURCE_HTTP` | M2 | 503 | yes | planned | OpenAlex/PDF HTTP 失败 |
| `E_SOURCE_RATE_LIMIT` | M2 | 429 | yes | planned | 429/配额 |
| `E_SOURCE_TIMEOUT` | M2 | 503 | yes | planned | 超时 |
| `E_SOURCE_EMPTY` | M2 | 422 | no | planned | 0 篇 |
| `E_SOURCE_METADATA` | M2 | 500 | no | planned | 标题/年份缺失 |
| `E_SOURCE_PDF` | M2 | 200 | no | planned | PDF 失败，降级 abstract |
| `E_EVIDENCE_QUOTE` | M3 | 422 | no | planned | quote 不命中 |
| `E_EVIDENCE_CLAIM_INVALID` | M3 | 422 | no | planned | 作者列表/截断句 |
| `E_EVIDENCE_LLM_TIMEOUT` | M3 | 503 | yes | planned | claim LLM 超时 |
| `E_REPORT_DIRECTION` | M4 | 422 | no | planned | 方向数/规模不达标 |
| `E_REPORT_COUNT` | M4 | 422 | no | planned | 计数不一致 |
| `E_REPORT_CITATION` | M4 | 422 | no | planned | 引用/事实失败 |
| `E_REPORT_WORDS` | M4 | 422 | no | planned | 字数 gate 失败 |
| `E_EVAL_DATASET` | M5 | 422 | no | planned | 数据集 hash/格式 |
| `E_EVAL_JUDGE` | M5 | 503 | yes | planned | judge 调用失败 |
| `E_API_INVALID` | M6 | 422 | no | planned | 请求 schema |
| `E_API_NOT_FOUND` | M6 | 404 | no | planned | 资源不存在 |

---

## 5. 错误与指标

每次错误必须记录：

```text
run_id
module
error_code
retryable
attempt
node_id
step
duration_ms
```

指标：

```text
error.rate
error.retryable_rate
error.by_module
```

---

## 6. 错误与日志

- 错误日志用 `level=error`；
- 可重试用 `level=warning`；
- 同一错误不要打多份重复日志；
- 不记录完整 prompt/全文；
- 记录 hash 而不是内容。

详见 `docs/LOGGING.md`。

---

## 7. 实施顺序

1. M1：run/node/artifact/checkpoint；
2. M2：source HTTP/PDF；
3. M3：claim/quote；
4. M4：report gate；
5. M5：dataset/judge；
6. M6：API 映射。

当前状态全部是 `planned`；代码尚未统一使用。
