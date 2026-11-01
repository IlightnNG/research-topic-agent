# Tools Design · DSH-informed

> 日期：2026-11-01
> 范围：Phase 4.1.4 ToolRegistry
> 参考：DSH `@deepseek-ai/dsh-tools`

---

## 1. DSH 做法

DSH tool pipeline：

```text
register ToolSpec
  → model-visible schema
  → validate args
  → policy allow/deny/ask
  → execute with timeout
  → canonical output
  → render / presentation
  → normal error result
```

关键点：

- 工具名、描述、参数 schema 自动进入 system prompt；
- 参数先校验，非法输入是普通错误结果；
- 有 timeout；
- 有 side-effect / parallel-safety 信息；
- 工具错误不结束 turn；
- registry 可按 agent 收窄；
- 输出与展示分离。

来源：

- [DSH tools README](https://github.com/deepseek-ai/DeepSeek-Harness/blob/HEAD/packages/core/tools/README.md?plain=1#1)
- 本地：`packages/core/tools/src/`

---

## 2. 本阶段实现

```text
tools/schema.py
  object/string/number/integer/boolean/array/object
  required
  additionalProperties=False

tools/registry.py
  register / names / spec / subset / call
  schema validation
  timeout
  max_retries / retry_on
  on_call hook

tools/packs/corpus.py
  corpus.stats
  corpus.dedupe
  corpus.store

tools/packs/claims.py
  claims.extract
  quote.check

tools/packs/source.py
  source.search
  source.fetch_pdf
  source.fetch_html

tools/packs/report.py
  report.plan
  report.check_section
  report.assemble
```

---

## 3. 有意未实现

```text
allow/deny/ask policy
PTC / run_code mode
presentation rendering
LLM-facing output rendering
MCP
per-agent registry restriction beyond subset()
```

原因：

```text
当前 Node 已有 allowlist；
demo 不需要 presentation；
policy 可以后续做。
```

---

## 4. 下一阶段

```text
4.1.5 Verify
4.1.6 report.write_section / report.persist
```

`report.write_section` 需要 LLM，将在 report node 中接。
