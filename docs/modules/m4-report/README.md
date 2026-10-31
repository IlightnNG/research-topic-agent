# M4 · Report

> 模块 ID：M4
> 代码：`src/lit_agent_v2/domains/report/{map,write,persist,workflow}.py`
> 目标：把 evidence 变成可读、可引用、可审计的结构化报告。

---

## 1. 职责

- 方向聚类；
- 方向命名；
- 报告结构规划；
- 章节写作/组装；
- 对比矩阵；
- gaps / method / paper index；
- 报告落库；
- 报告状态 complete/degraded。

不负责：

- 检索论文；
- 抽 claim；
- 评分体系；
- API/UI。

---

## 2. 输入/输出

### 输入

```text
EvidenceArtifact
```

### 输出

```json
{
  "report_id": "...",
  "content_md": "...",
  "content_sha": "...",
  "sections": [{
    "section_id": "D1",
    "kind": "deep_dive",
    "title": "...",
    "body": "...",
    "claim_indexes": [1,2]
  }],
  "word_count": 2519,
  "state": "complete|degraded",
  "claims": []
}
```

---

## 3. 边界

### 允许

- 使用 M3 claims；
- 聚类；
- LLM section writer；
- 代码构建 matrix/index；
- 写 reports/sections/claims/citations。

### 禁止

- 重新抓论文；
- 重新抽 claim；
- 改 score 体系；
- 用 ledger/index 刷 coverage；
- 用 author 名命名方向；
- 无引用的事实句。

---

## 4. 目标流程

```text
ReportPlan
  → direction EvidencePack
  → LLM direction section
  → Code Gate + AgentVerifier + Section Score
  → append
  → global overview / comparison / gaps
  → full consistency check
```

当前流程：

```text
map → write（模板）→ finalize
```

当前 writer 是确定性模板，不是 LLM 写作。

---

## 5. 报告结构

```text
At a Glance
Direction 1..N
Comparison Matrix
Gaps & Limitations
Method
Paper Index
```

要求：

- 每个事实句有 `[C#]`；
- overview 计数 = 各 section = matrix = ledger；
- paper index 含 title/venue/year；
- comparison 有正文，不只是表；
- open questions 不能模板复用；
- 每个方向 ≥3 篇；
- 5–8 方向。

---

## 6. 指标

| 指标 | 目标 |
|---|---|
| `cluster.count` | 5–8 |
| `cluster.min_size` | ≥3 |
| `cluster.coherence` | 提升 |
| `direction.max_share` | ≤0.6 |
| `report.claim_coverage` | ≥0.8 正文实际引用 |
| `report.citation_coverage` | 1.0 |
| `report.uncited_facts` | 0 |
| `report.comparison_completeness` | 1.0 |
| `report.words` | 1500–3000 gate |
| `report.state` | 与质量门禁一致 |

字数只做 gate，不做质量正分。

---

## 7. 验收

```text
1. 5–8 方向；
2. 每方向 ≥3 篇；
3. 86 篇不再只写 6 条；
4. overview/section/matrix/ledger 计数一致；
5. paper index metadata 完整；
6. 每个 section 正文 claim 覆盖；
7. 无 author-list claim；
8. L1/L2 明示；
9. complete/degraded 正确；
10. 报告可从 API 读取。
```

---

## 8. 测试

```text
tests/v2/test_s3_report.py
tests/v2/test_research_pipeline.py
```

新增：

```text
tests/v2/test_m4_count_reconciliation.py
tests/v2/test_m4_direction_quality.py
tests/v2/test_m4_writer_contract.py
```

必须覆盖：

- 3/5/8 方向；
- 单方向 86 篇；
- 每方向 claims；
- 计数一致；
- index metadata；
- 模板 open question；
- 字数 gate。

---

## 9. 失败模式

| 错误 | 处理 |
|---|---|
| 方向 <5 | degraded |
| 方向 >8 | merge |
| max_share >0.6 | degraded/rebuild |
| 计数不一致 | verifier reject |
| claim 不在正文 | section 重写 |
| 字数超限 | 压缩，不删 claim 覆盖 |

错误码见 `docs/ERRORS.md`。

---

## 10. 当前状态

| 能力 | 状态 |
|---|---|
| map | ✅ |
| writer 模板 | ✅ |
| LLM writer | ❌ |
| comparison | ✅ 表 |
| paper index | ⚠️ 只有 ID |
| 计数一致 | ❌ |
| 方向质量 | ❌ |
| 100 篇 | ⚠️ degraded |
| report 落库 | ✅ |

---

## 11. 相关文档

- `docs/ARCHITECTURE.md`
- `docs/TODO.md`
- `docs/modules/m3-evidence/README.md`


---

## Phase docs

- [M4-P01-direction-and-counting.md](M4-P01-direction-and-counting.md)
- [M4-P02-modular-llm-writer.md](M4-P02-modular-llm-writer.md)
