# M5-P01 · Scorecards + LLM Judge

> 模块：M5 Evaluation
> 版本：1.0（2026-10-31）
> 状态：planned
> 依赖：M3-P01、M4-P02
> 目标：把“一个总分”改成模块分 + 方向分 + 硬门禁 + confidence，并用 LLM judge 评估质量。

---

## 1. 目标

当前：

```text
score = 0.5 * direction_f1 + 0.3 * citation + 0.2 * word_gate
```

问题：

- 字数进入评分；
- 没有模块分；
- 没有方向分；
- 没有 hard gate；
- 没有 confidence；
- 没有 LLM judge。

Phase 4：

```text
module_score
  = Σ(weight × normalized_metric)

direction_score
  = 该方向模块分

total
  = Σ(module_weight × module_score) × confidence

hard_fail
  → final = min(final, 0.5)
```

字数只做 gate，不做正分。

---

## 2. 边界

### 改

```text
src/lit_agent_v2/metrics/catalog.py
src/lit_agent_v2/metrics/gates.py
src/lit_agent_v2/metrics/scorecard.py     # 新增
src/lit_agent_v2/evaluation/evaluators.py
src/lit_agent_v2/evaluation/judge.py      # 新增
src/lit_agent_v2/evaluation/runner.py
```

### 不改

- report writer；
- source；
- API；
- workflow。

---

## 3. 模块权重

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

权重存配置，不硬编码在多个地方。

---

## 4. 指标归一化

```text
higher_better: min(1, value / target)
lower_better:  min(1, target / value)   value>0
in_range:      1 inside, linear decay outside
```

分母为 0：

```text
value = NULL
不参与分母
不写 0
```

confidence：

```text
confidence = min(1, sample_size / sample_min)
final = total * confidence
```

---

## 5. 硬门禁

```text
citation_coverage = 1.0
quote_verbatim = 1.0
claim_purity >= 0.98
uncited_facts = 0
count_reconciliation = 1.0
```

失败：

```text
module_score 封顶 0.5
overall state = degraded
严重失败 = failed
```

---

## 6. 方向分

每个方向独立算：

```text
direction.claim_coverage
direction.common_ground
direction.differences
direction.open_questions
direction.readability
direction.boilerplate
```

输出：

```json
{
  "direction_id": "D1",
  "score": 0.78,
  "metrics": {},
  "status": "accepted|repaired|failed"
}
```

总体：

```text
direction_score = weighted mean by direction size
```

---

## 7. LLM Judge

### rubric

| 维度 | 1 | 3 | 5 |
|---|---|---|---|
| relevance | 偏题 | 部分相关 | 精准 |
| coverage | 大量遗漏 | 基本覆盖 | 全面 |
| grounding | 无引用 | 部分 | 全部可追溯 |
| synthesis | 罗列 | 有对比 | 有洞察 |
| readability | 难读 | 可读 | 清晰 |
| actionability | 无用 | 一般 | 明确下一步 |

### 输入

- section/report；
- 对应 claims；
- 不传 producer 推理链；
- 不传完整 prompt。

### 输出

```json
{
  "scores": {
    "relevance": 1-5,
    "coverage": 1-5,
    "grounding": 1-5,
    "synthesis": 1-5,
    "readability": 1-5,
    "actionability": 1-5
  },
  "problems": ["..."],
  "verdict": "accept|repair|fail"
}
```

### 校准

- 20–30 人工样本；
- 双人评分；
- 计算 judge-human 相关性；
- 低于阈值不用于晋级；
- judge 不做唯一硬门禁。

---

## 8. 评分卡

```json
{
  "run_id": "...",
  "report_id": "...",
  "state": "complete|degraded|failed",
  "modules": {
    "source": 0.82,
    "evidence": 0.71,
    "claims": 0.93,
    "map": 0.60,
    "writing": 0.55,
    "cross": 0.40,
    "grounding": 1.0,
    "process": 0.90
  },
  "directions": [],
  "total": 0.68,
  "confidence": 0.95,
  "hard_fail": [],
  "verdict": "repair"
}
```

---

## 9. 测试

```text
tests/v2/test_m5_normalization.py
tests/v2/test_m5_hard_gate.py
tests/v2/test_m5_direction_score.py
tests/v2/test_m5_judge_schema.py
tests/v2/test_m5_judge_calibration.py
```

必须覆盖：

- higher/lower/in_range；
- 分母 0；
- sample_min；
- hard fail 封顶；
- 方向分加权；
- judge 非法 JSON；
- 校准样本。

---

## 10. 验收

```text
1. 字数不再进入正分；
2. 每个模块有分；
3. 每个方向有分；
4. hard gate 生效；
5. confidence 生效；
6. judge 输出 schema；
7. judge 与人工有相关性；
8. 评分可复算。
```

---

## 11. 回滚

- 旧 score 保留为 `legacy_score`；
- 新 scorecard 只读；
- 不影响报告生成；
- 评分失败不能阻塞报告落库，但必须标 `score_error`。

---

## 12. Commit

```text
feat(M5-P01): add module scorecards and llm judge
```
