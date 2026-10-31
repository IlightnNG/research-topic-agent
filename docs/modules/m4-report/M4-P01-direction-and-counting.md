# M4-P01 · Direction Quality + Count Reconciliation

> 模块：M4 Report
> 版本：1.0（2026-10-31）
> 状态：done（100 篇方向/计数通过；words 待 M4-P02）
> 依赖：M2-P01、M3-P01
> 目标：先让报告的“骨架和会计”正确，再让 LLM 写正文。

---

## 1. 目标

当前：

```text
100 篇 → 3 方向
D1 86 篇 / 6 claims
overview 185 / section 18 / ledger 103
Paper Index 只有 ID
```

Phase 4：

```text
5–8 方向
每方向 ≥3 篇
max_share ≤0.6
overview = sections = matrix = ledger
Paper Index metadata 完整
```

---

## 2. 边界

### 改

```text
src/lit_agent_v2/domains/report/map.py
src/lit_agent_v2/domains/report/write.py
src/lit_agent_v2/domains/report/persist.py
```

### 不改

- source/PDF；
- claim 抽取；
- LLM writer（下一 phase）；
- API。

---

## 3. 方向

### 规则

```text
5 <= directions <= 8
min_size >= 3
max_share <= 0.6
coherence >= threshold
no author/venue names
```

### 命名

- 只允许 task/method/benchmark/finding 词；
- 禁止作者姓、机构、会议；
- 每个名字 ≤5 words；
- 重复名字拒绝。

### 失败

- 3 方向 → degraded；
- 1 方向 86 篇 → degraded；
- 小方向 <3 → merge 到 Other 或单独 outlier；
- 不允许伪造方向。

---

## 4. 计数一致性

报告必须满足：

```text
overview.total_claims
= sum(section.displayed_claims)
= comparison.total_claims
= ledger.total_claims
= claims table total
```

当前 `ledger` 是刷覆盖率；本 phase 改为：

- 正文展示 claims；
- ledger 只做索引；
- `report.claim_coverage` 只算正文；
- 不允许 ledger 抬高 coverage。

---

## 5. Paper Index

每行：

```text
| paper_id | title | authors | venue | year | url |
```

规则：

- title 必须真实；
- authors 至少第一作者；
- 缺 metadata 标 `metadata_missing`；
- 不伪造。

---

## 6. 报告结构

```text
At a Glance
Direction 1..N
Comparison Matrix
Gaps
Method
Paper Index
```

每个 deep dive：

```text
common ground
differences
open questions
evidence notes
```

要求：

- 每方向正文至少 80% claims；
- 不接受 86 篇只写 6 条；
- 每个事实句 `[C#]`；
- 字数 1500–3000 gate。

---

## 7. 指标

| 指标 | 目标 |
|---|---|
| `cluster.count` | 5–8 |
| `cluster.min_size` | ≥3 |
| `direction.max_share` | ≤0.6 |
| `report.claim_coverage` | ≥0.8 |
| `report.count_reconciliation` | 1.0 |
| `report.index_completeness` | 1.0 |
| `report.uncited_facts` | 0 |
| `report.words` | 1500–3000 gate |

---

## 8. 测试

```text
tests/v2/test_m4_directions.py
tests/v2/test_m4_counting.py
tests/v2/test_m4_index.py
```

fixture：

- 5 方向；
- 3 方向；
- 1 方向 86 篇；
- 方向名作者；
- 计数不一致；
- index 缺 metadata。

验收：

```text
1. 3 方向报告必须 degraded；
2. max_share 0.86 必须 degraded；
3. 计数不一致必须 reject；
4. index 有 title；
5. 正文 cover ≥0.8（fixture）。
```

---

## 9. 失败模式

| 错误 | 处理 |
|---|---|
| 方向 <5 | degraded |
| max_share >0.6 | degraded/rebuild |
| 计数不一致 | verifier fail |
| 作者名方向 | reject name |
| index 缺 title | reject paper |
| words <1500 | degraded |

错误码见 `docs/ERRORS.md`。

---

## 10. 当前 → 目标

| 项 | 当前 | 目标 |
|---|---|---|
| 方向 | 3 | 5–8 |
| max_share | 0.86 | ≤0.6 |
| 每方向 claims | 6 | ≥80% |
| 计数 | 不一致 | 一致 |
| index | ID | metadata |
| 字数 | 2519 | 1500–3000 |

---

## 11. 回滚

- 保留旧模板 writer；
- 新 gate 只影响 `state`；
- 不影响 persist schema；
- 失败可回退到上一版 writer。

---

## 12. 实施记录（2026-10-31）

已完成：

- 5–8 方向 / min size / max share；
- 小方向不再合并成单一 Other；
- 作者/venue 名过滤；
- 全报告 claim 计数一致；
- Paper Index metadata；
- deep dive 覆盖全部 claims；
- `report.count_reconciliation`。

未完成：

- 100 篇 words 仍 >3000；
- LLM writer / comparison 正文 / 非模板 open questions。

## 13. Commit

```text
fix(M4-P01): enforce direction quality and claim-count reconciliation
```
