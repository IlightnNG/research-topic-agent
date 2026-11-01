# RESULTS · M5-P02

> Phase：M5-P02 Gold + Judge Calibration
> 日期：2026-11-01
> 状态：template done；人工标注未完成

## 门禁

```text
pytest tests/v2   75 passed（含 3 个 live LLM）
ruff              clean
contract freeze   v1.2 passed
```

## AI-only 预标注

已实现：

```text
evaluation/gold_prelabel.py
```

双模型：

```text
ai-a  deepseek-flash
ai-b  deepseek-v4-pro
```

两个 annotator 独立 context、独立 prompt、独立 cache。

运行：

```powershell
python -m lit_agent_v2.evaluation.gold_prelabel `
  --template "D:\lit-agent-store\v2-eval\gold\template" `
  --output "D:\lit-agent-store\v2-eval\gold\ai-prelabel" `
  --model-a deepseek-flash `
  --model-b deepseek-v4-pro `
  --batch-size 8 `
  --workers 4
```

输出：

```text
annotation-sheet-ai-a.csv
annotation-sheet-ai-b.csv
gold-ai-a/dataset.json
gold-ai-b/dataset.json
run-metadata.json
```

状态必须保持：

```text
ai-prelabel
```

注意：本轮没有完成 300 篇 AI 实际生成；脚本和模板已完成。

## 已实现

```text
evaluation/gold.py
  GoldClaim
  GoldPaper
  GoldCase
  GoldDataset
  load_gold

evaluation/gold_template.py
evaluation/gold_annotation.py
evaluation/calibration.py
  CalibrationSample
  CalibrationReport
  calibrate
  pearson / spearman / mae / cohen_kappa
```

## 已生成模板

```text
D:\lit-agent-store\v2-eval\gold\template\dataset.json
D:\lit-agent-store\v2-eval\gold\template\annotation-sheet.csv
```

```text
3 cases
100 papers / case
300 annotation rows
0 gold claims
status = draft
```

标注流程：

```text
docs/modules/evaluation/GOLD-ANNOTATION.md
```

## Gold schema

- 3 cases（代码支持 `min_cases=3`）；
- 100 papers/case（代码支持 `papers_per_case=100`）；
- 1–2 claims/paper；
- quote 必须原文命中；
- relevance / importance 1–5；
- direction 覆盖 ≥80%；
- dataset hash freeze。

## Calibration

指标：

```text
pearson
spearman
mae
cohen_kappa
```

门槛：

```text
pearson >= 0.6
spearman >= 0.6
mae <= 0.5
kappa >= 0.6
```

样本不足 → `passed=False`。

## 测试

```text
tests/v2/test_m5_gold.py
  - load
  - freeze
  - bad quote
  - duplicate IDs
  - perfect calibration
  - poor/small sample
  - kappa
```

## 未完成

- 3 × 100 篇人工 gold；
- 双人标注；
- inter-annotator kappa；
- judge-human 30-sample calibration；
- 真实 dataset hash 写入；
- M5-P02 的 acceptance 仍不能关闭。

## Commit

```text
feat(M5-P02): add gold schema and judge calibration
```
