# RESULTS · M5-P01

> Phase：M5-P01 Scorecards + LLM Judge
> 日期：2026-11-01
> 状态：done（scorecard/judge 可独立运行；100 篇 gold 未接）

## 门禁

```text
pytest tests/v2   64 passed（含 3 个 live LLM）
ruff              clean
contract freeze   v1.2 passed
```

## 已实现

```text
metrics/scorecard.py
  ModuleScore
  DirectionScore
  ScoreCard
  build_scorecard
  build_scorecard_from_points
  normalize_metric

evaluation/judge.py
  JudgeScores
  JudgeResult
  JudgePort
  LLMJudge
  RUBRIC
```

## Scorecard

模块权重：

```text
source .10
evidence .15
claims .15
map .15
writing .20
cross .10
grounding .10
process .05
```

规则：

- metric normalization；
- 方向分；
- hard gate；
- confidence；
- verdict。

Hard gate：

```text
search.coverage
search.duplicate_rate
card.quote_verbatim_rate
claim.purity
claim.citation_coverage
report.count_reconciliation
report.citation_coverage
report.uncited_facts
```

失败 → `total <= 0.5`，`verdict=fail`。

## LLM Judge

固定 rubric：

```text
relevance
coverage
grounding
synthesis
readability
actionability
```

输出：

```json
{
  "scores": {"relevance": 1-5, "...": "..."},
  "problems": [],
  "verdict": "accept|repair|fail"
}
```

真实 DeepSeek judge 测试通过。

## 测试

```text
tests/v2/test_m5_scorecard.py
tests/v2/test_m5_judge.py
```

覆盖：

- clean run accept；
- hard gate cap；
- confidence；
- normalization；
- judge schema；
- bad score；
- live judge。

## 未完成

- 100 篇 gold / double annotation；
- judge-human calibration；
- scorecard 自动写入 report API；
- M5 与 M6 的 score endpoint；
- Tuner 仍使用旧简化 score 公式。

## Commit

```text
feat(M5-P01): add module scorecards and llm judge
```
