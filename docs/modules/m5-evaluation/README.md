# M5 · Evaluation

> 模块 ID：M5
> 代码：`src/lit_agent_v2/{metrics,evaluation}/`
> 目标：让“好/坏”可度量、可复算、可比较，而不是靠字数或感觉。

---

## 1. 职责

- 指标目录（MetricSpec）；
- 指标落库；
- span/事件到指标的采集；
- 模块评分；
- 数据集加载/冻结；
- 规则评估；
- LLM judge；
- baseline/candidate；
- 参数调优；
- experiments。

不负责：

- 生成报告；
- 修改报道；
- 调参后直接改生产配置；
- 用指标替代人工判断。

---

## 2. 评分设计目标

```text
module_score = Σ(weight_i × normalized_metric_i)
direction_score = 该方向模块分
total = Σ(module_weight × module_score) × confidence
hard_fail → final = min(final, 0.5)
```

字数：

```text
1500–3000 = gate
不是 score
```

### 模块权重

| 模块 | 权重 |
|---|---|
| Source | 10% |
| Evidence | 15% |
| Claims | 15% |
| Map | 15% |
| Direction Writing | 20% |
| Cross Synthesis | 10% |
| Grounding | 10% |
| Process | 5% |

### 硬门禁

```text
citation_coverage = 1.0
quote_verbatim = 1.0
claim_purity >= 0.98
uncited_facts = 0
count_reconciliation = 1
```

### 指标公式

```text
higher_better: min(1, value / target)
lower_better:  min(1, target / value)
in_range:      1 inside, 线性衰减
```

分母为 0 → NULL，不写 0。

---

## 3. 指标目录

### Source

```text
search.coverage
search.recall_at_20
search.precision_at_20
search.topic_relevance
search.duplicate_rate
metadata.completeness
fulltext.available_ratio
```

### Evidence

```text
card.quote_verbatim_rate
claim.purity
claim.citation_coverage
claim.specificity
claim.nonresearch_rate
claim.count_per_paper
```

### Map

```text
cluster.count
cluster.min_size
cluster.coherence
cluster.outlier_rate
direction.max_share
direction.name_quality
```

### Report

```text
report.words
report.claim_coverage
report.citation_coverage
report.uncited_facts
report.comparison_completeness
report.count_reconciliation
report.state
```

### Process

```text
run.duration_ms
run.cost_usd
run.llm_failures
run.resume_count
run.stagnation
```

---

## 4. 数据集

```text
evaluation/datasets/
  ai-agents-100/
    topic.json
    papers.jsonl
    gold_claims.jsonl
    gold_directions.jsonl
    gold_report.md
    rubric.md
```

要求：

- 100 篇 × 3 topic；
- 双人标注；
- hash 冻结；
- 优化器只读；
- 训练/调参/测试分离。

---

## 5. LLM judge

必须做：

- 固定 rubric；
- pairwise 比较；
- 多 judge/重复采样；
- 与人工 20–30 样本校准；
- 输出分数分布，不只均值；
- judge 不作为唯一硬门禁。

---

## 6. 验收

```text
1. 每个指标有公式/单位/方向/版本；
2. NULL 与 0 分离；
3. 指标可从 events/artifacts 复算；
4. 100 篇 gold 集可复跑；
5. baseline/candidate 可比较；
6. experiments 可追溯；
7. 评估集不可被优化器修改；
8. LLM judge 有校准。
```

---

## 7. 测试

```text
tests/v2/test_s7_s8_eval.py
tests/v2/test_s1_s2.py::test_s1_metric_gate
tests/eval/test_metrics_v2.py（旧，已移出）
```

新增：

```text
tests/v2/test_m5_metric_formulas.py
tests/v2/test_m5_scorecard.py
tests/v2/test_m5_dataset_freeze.py
tests/v2/test_m5_judge_calibration.py
```

---

## 8. 失败模式

| 错误 | 处理 |
|---|---|
| 分母 0 | NULL |
| 数据集 hash 变 | 拒绝运行 |
| judge 输出非法 | 丢弃/重试 |
| hard gate 失败 | degraded/failed |
| 评估集被改 | 阻止 |
| 优化指标提升但 hard fail | 拒绝晋级 |

错误码见 `docs/ERRORS.md`。

---

## 9. 当前状态

| 能力 | 状态 |
|---|---|
| MetricSpec | ✅ 部分 |
| metric store | ✅ |
| 模块评分 | ❌ |
| direction score | ❌ |
| 100 篇 gold | ❌ |
| LLM judge | ❌ |
| judge 校准 | ❌ |
| 参数调优 | ⚠️ 20 篇 silver |
| experiments | ✅ |

---

## 10. 相关文档

- `docs/ARCHITECTURE.md`
- `docs/TODO.md`
- `docs/TESTING.md`
- `docs/ERRORS.md`
