# ADR-0010 · Phase 3.4 metrics tables

- **状态**：Accepted
- **日期**：2026-10-30
- **相关**：ADR-0005、ADR-0009、phase3.4-workflow-kernel-refactor.md

## 决策

新增四张跨阶段指标表：

| 表 | 用途 |
|---|---|
| `metric_definitions` | 指标目录：ID/版本/单位/方向/公式/目标 |
| `metric_points` | 标准化观测点：分母、样本量、config_hash、prompt_version |
| `run_spans` | 阶段/步骤/工具 trace |
| `experiments` | baseline/candidate、配置 hash、score、hard fail |

表总数从 **26 → 30**；迁移 `0009_metrics_v2` 幂等，可回滚。

## 规则

- 分母为 0 时 `value=NULL`，不写 0；
- 不记录 prompt 正文/论文全文/密钥；
- 指标可从 events/spans 复算。
