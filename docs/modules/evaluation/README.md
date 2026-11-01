# E · Evaluation

> 模块：Evaluation
> 版本：2.0（2026-11-01）
> 状态：target；M5 代码可复用
> 目标：gold、scorecard、judge、calibration。

---

## 1. 职责

```text
dataset
gold
scorecard
judge
calibration
tuning experiments
```

## 2. 不负责

```text
报告生成
Workflow 调度
修改报告
```

## 3. 目标文件

```text
domains/evaluation/dataset.py
domains/evaluation/gold.py
domains/evaluation/scorecard.py
domains/evaluation/judge.py
domains/evaluation/calibration.py
```

## 4. 可选 Node

```text
scorecard.build
  tools: eval.scorecard, eval.judge
  optional: true
```

不阻塞报告生成。

## 5. 规则

- scorecard 不在 report 节点内部硬编码；
- judge 不替代代码 hard gate；
- AI-only gold 只能标 `ai-prelabel`；
- gold 与 generation 路径隔离；
- 100 gold 未完成前不得作为晋级依据。

## 6. 验收

```text
scorecard
hard gate
confidence
judge schema
calibration
```

## 7. Phase docs

```text
E-P01-scorecard-node.md
E-P02-gold-calibration.md
```

## 8. 文档

- [GOLD-ANNOTATION.md](GOLD-ANNOTATION.md)
