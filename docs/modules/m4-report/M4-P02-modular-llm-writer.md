# M4-P02 · Modular LLM Writer

> 模块：M4 Report
> 版本：1.0（2026-10-31）
> 状态：done（20 live complete；100 live 待复跑）
> 依赖：M4-P01
> 目标：把“一次性模板拼报告”改成“先 Plan，再逐方向 LLM 写作，最后全局组装”。

---

## 1. 目标

当前：

```text
evidence → map → 一次 write → 模板
```

Phase 4：

```text
ReportPlan
  → direction 1 EvidencePack
  → LLM section
  → gate + verifier + score
  → append
  → direction 2 ...
  → overview / comparison / gaps
  → full consistency check
```

---

## 2. 边界

### 改

```text
src/lit_agent_v2/domains/report/write.py
src/lit_agent_v2/domains/report/workflow.py
src/lit_agent_v2/domains/report/contracts.py
src/lit_agent_v2/workflow/runner.py（section hook）
```

### 不改

- source；
- claim；
- map（M4-P01）；
- API。

---

## 3. 数据契约

### ReportPlan

```json
{
  "title": "...",
  "sections": [
    {"id": "overview", "kind": "overview"},
    {"id": "D1", "kind": "deep_dive", "paper_ids": ["..."]},
    {"id": "comparison", "kind": "comparison"},
    {"id": "gaps", "kind": "gaps"},
    {"id": "method", "kind": "method"},
    {"id": "index", "kind": "paper_index"}
  ]
}
```

### EvidencePack（每方向）

```json
{
  "direction_id": "D1",
  "direction_name": "...",
  "papers": [{"paper_id": "...", "title": "..."}],
  "claims": [{
    "claim_id": "P1-C1",
    "text": "...",
    "quote": "...",
    "type": "finding"
  }],
  "quotes": [{"paper_id": "...", "text": "...", "section": "...", "page": 1}]
}
```

### SectionArtifact

```json
{
  "section_id": "D1",
  "kind": "deep_dive",
  "title": "...",
  "body": "...",
  "claim_ids": ["..."],
  "common_ground": [{"text": "...", "claim_ids": ["..."]}],
  "differences": [{"text": "...", "claim_ids": ["..."]}],
  "open_questions": [{"text": "...", "claim_ids": ["..."]}],
  "state": "accepted|repaired|failed"
}
```

---

## 4. Section prompt

```text
You are writing one section of a research report.
Use ONLY the supplied claims and quotes.
Each factual sentence must end with [C#] referencing a supplied claim.
Do not introduce new papers, numbers, or claims.
Write in English; target length comes from report policy (not a fixed 250–500).
Required structure:
- definition / scope
- common ground (>=2 claims)
- differences (>=2 papers)
- open questions (evidence-derived)
Return JSON:
{"title":str,"body":str,"claim_ids":[str],
 "common_ground":[{"text":str,"claim_ids":[str]}],
 "differences":[...],"open_questions":[...]}
```

后处理：

- unknown claim_id → reject；
- body 无 `[C#]` → reject；
- claim coverage <0.8 → repair；
- word >600 → compress；
- 作者名/venue 名 → reject；
- 模板句检测。

---

## 5. Overview

输入：

- 已接受 sections；
- counts；
- gaps。

Prompt：

```text
Write 150–250 word overview from accepted sections.
No new facts. Every number must match supplied counts.
Return JSON {"body":str}.
```

代码校验：

```text
counts equal
no new claims
```

## 6. Comparison

- 表格由代码生成；
- 正文由 LLM 写；
- 只允许比较已接受方向；
- 每个对比句引用 claim_ids；
- 不得把不同任务的 claim 当同一比较轴。

Prompt：

```text
Compare the accepted directions on task, method, data, evaluation, findings.
Use only supplied rows/claims. Do not rank by unsupported claims.
Return JSON {"body":str,"claim_ids":[str]}.
```

## 7. Gaps

- 由 verifier + coverage 数据生成；
- LLM 只写解释，不改数字；
- 必须列出：
  - fulltext 覆盖；
  - 方向缺口；
  - 单篇支持；
  - 未解决矛盾。

---

## 8. 流式

每个 section 生成后立即：

```text
section.delta
```

失败：

- 只重写该 section；
- 最多 2 次；
- 仍失败 → 用 claim 列表模板并标 degraded。

---

## 9. 指标

| 指标 | 目标 |
|---|---|
| `section.claim_coverage` | ≥0.8 |
| `section.citation_density` | ≥1/2 sentences |
| `section.boilerplate_rate` | 0 |
| `section.word_count` | 由 policy 分配 |
| `section.repair_count` | 记录 |
| `report.count_reconciliation` | 1.0 |
| `report.comparison_completeness` | 1.0 |

---

## 10. 测试

```text
tests/v2/test_m4_writer_contract.py
tests/v2/test_m4_section_gate.py
tests/v2/test_m4_live_writer.py
```

必须覆盖：

- fake LLM 正常 section；
- unknown claim；
- 无引用；
- 模板句；
- 作者名；
- 字数超限；
- 失败重试；
- 100 篇真实 LLM 写作。

---

## 11. 验收

```text
1. 5 个方向独立生成；
2. 每 section claim coverage ≥0.8；
3. 每个事实句有引用；
4. overview 计数一致；
5. comparison 有正文；
6. 失败只重写 section；
7. section 流式；
8. 100 篇报告可读；
9. LLM audit 从 reject 提升。
```

---

## 12. 回滚

- 保留 deterministic writer；
- LLM 不可用 → 模板 + degraded；
- 不能静默生成空 section。

---

## 13. 实施记录（2026-10-31）

已完成：

- ReportPlan / EvidencePack；
- per-direction LLM section；
- structured JSON schema；
- claim refs 校验、去重、coverage、uncited；
- retry + deterministic fallback；
- section streaming callback；
- 20 篇 live complete；
- 57 tests。

未完成：

- 100 篇 live LLM writer 复跑；
- overview/comparison 在部分模型上会回退 deterministic；
- LLM 成本/延迟预算。

## 14. Commit

```text
feat(M4-P02): add per-direction llm report writer
```
