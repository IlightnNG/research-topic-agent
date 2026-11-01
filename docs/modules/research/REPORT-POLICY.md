# Report Policy

> 模块：M4 Report
> 版本：1.0（2026-10-31）
> 目标：方向数和报告篇幅由语料规模决定，不写死。

---

## 1. 输入

```text
n = selected papers
c = accepted claims
```

---

## 2. 方向数

```text
k_target = clamp(ceil(n / 20) + 2, 3, 12)
k_min    = max(3, k_target - 2)
k_max    = min(12, k_target + 2)
```

方向数不要求等于 `k_target`，只要求落在：

```text
k_min <= directions <= k_max
```

示例：

| 论文数 | target | 可接受范围 |
|---|---|---|
| 20 | 3 | 3–5 |
| 50 | 5 | 3–7 |
| 100 | 7 | 5–9 |
| 200 | 12 | 10–12 |

---

## 3. 方向规模

```text
min_size  = max(3, floor(n / (2 * k_target)))
max_share = min(0.6, max(0.3, 2.5 / k_target))
```

示例：

| 论文数 | target | min_size | max_share |
|---|---|---|---|
| 20 | 3 | 3 | 0.60 |
| 50 | 5 | 5 | 0.50 |
| 100 | 7 | 7 | 0.36 |
| 200 | 12 | 8 | 0.30 |

规则：

- 小方向不能合并成一个巨型 `Other`；
- 最大方向太大时分裂；
- 不为了数量伪造方向；
- `count_quality = deficit` 时报告必须 `degraded`。

---

## 4. 方向命名

禁止：

- 作者姓；
- venue 名；
- 机构名；
- 重复名。

允许：

```text
tool routing
dense retrieval
episodic memory
rubric evaluation
```

fallback：

```text
Topic N
```

---

## 5. 字数

```text
word_target = clamp(600 + 20*n + 10*c, 1200, 8000)
word_min    = round(word_target * 0.4)
word_max    = round(word_target * 1.4)
```

`word_count` 只统计叙事正文，不统计：

- Paper Index；
- Claim Ledger；
- 表格分隔行。

示例：

| 论文 | claims | target | 范围 |
|---|---|---|---|
| 20 | 20 | 1200 | 480–1920 |
| 50 | 50 | 2100 | 840–3360 |
| 100 | 100 | 3600 | 1440–5760 |
| 100 | 178 | 4380 | 1752–7008 |

不再使用固定的 `1500–3000`。

---

## 6. 重复

同一条 claim 在正文中只允许出现一次。

做法：

- common ground 用前 3 条；
- differences 用第 4–5 条；
- evidence notes 只列剩余 claim；
- ledger 只列 ID，不重复正文；
- 每条 claim 在所有 deep dive 中最多出现一次。

指标：

```text
report.duplicate_claim_rate = duplicate_refs / claim_refs
target <= 0.1
```

---

## 7. 属实与引用

每个事实句必须有 `[C#]`。

必须真实计算：

```text
report.citation_coverage = cited_claims / claims
report.uncited_facts     = deep_dive 中无引用的事实句
```

不再硬编码：

```python
report.citation_coverage = 1.0
report.uncited_facts = 0.0
```

---

## 8. 可读性 gate

报告进入 `complete` 必须同时满足：

```text
k_min <= directions <= k_max
min_size >= policy.min_direction_size
max_share <= policy.max_direction_share
word_min <= narrative_words <= word_max
claim_coverage >= 0.8
count_reconciliation == 1.0
citation_coverage == 1.0
uncited_facts == 0
duplicate_claim_rate <= 0.1
fulltext_ratio >= 0.3
```

否则：

```text
degraded
```

---

## 9. 代码

```text
domains/report/policy.py
domains/report/audit.py
domains/report/map.py
domains/report/write.py
domains/report/workflow.py
```
