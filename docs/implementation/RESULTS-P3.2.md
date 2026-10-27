# RESULTS — Phase 3.2（Report 核心能力）

> 规范：`phase3.2-report-quality.md`（S1–S14 / H1–H15）。
> 当前进度：**S1–S2 完成**；S3+ 待做。

## 0. 一页摘要

| 指标 | 结果 |
|---|---|
| 阶段 | **S1–S4 完成** |
| 测试 | `pytest` **587 例**（S3/S4 新增 9 例） |
| 验证器 | `verify_phase3 13/13`、`verify_phase2_1 13/13` |
| 迁移 | `0006_report_v2`（26 张表）已应用到 dev store |
| 兼容 | 旧报告可读；未接入 report 节点（S4 做） |

## 1. S1 · 数据模型与配置

| 产物 | 说明 |
|---|---|
| `ReportSettings` | `language/synthesis/token_budget/batch_size/concurrency/deep_read_ratio/max_chunks_per_paper/max_claims_per_paper/min_cluster_size/max_sections/min_words/max_words/repair_attempts/cache/pdf_enabled/max_text_chars` |
| `Settings.report` | 环境变量 `LIT_AGENT_REPORT__*` 可覆盖 |
| 迁移 `0006_report_v2` | `paper_cards`、`report_steps`；`reports/runs/papers` 扩列；幂等 |
| ORM | `tables.py` 增 `t_paper_cards`、`t_report_steps`；表数 24 → 26 |
| 契约 | ADR-0009；contract test 与 health 断言更新 |

## 2. S2 · PaperCard

| 产物 | 说明 |
|---|---|
| `report/cards.py` | `PaperCard`、`build_card`、`get_or_build_card`、`quote_ok`、`source_sha` |
| `db/repo/paper_cards.py` | 按 `paper_id + content_sha + version` 缓存；UPSERT |
| 确定性兜底 | 标题/摘要 → findings/claims；无文本 → `missing` |
| LLM 增强 | 严格 JSON；quote 必须原文子串；非法字段/claim 丢弃；失败回落 |
| 日志 | `paper_card.cache_hit/built/llm_ok/llm_fallback/cache_write_failed` |
| 错误 | `E_REPORT_QUOTE` / `E_REPORT_LLM`；缓存写失败不阻断 |

## 3. 实测

```text
pytest -q                    578 例，exit 0
verify_phase3 --all          13/13
verify_phase2_1 --all        13/13
tests/report                 9 passed
```

覆盖：配置默认/环境覆盖、迁移建表、quote 校验、非法 LLM quote 丢弃、LLM 失败回落、缓存命中、内容变更失效、无文本标记。

## 4. 下一步（S3/S4）

1. **S3**：claim 去重 + claim_id + 每篇 ≤3；
2. **S4**：聚类 + 方向命名；
3. 之后把 `get_or_build_card` 接入 `report` 节点（S4/S5）。


---

## 5. S3 · Claims 规范化

| 产物 | 说明 |
|---|---|
| `report/claims.py` | `build_claims`：稳定 `P12-C1`、跨论文 `text_sha` 去重、每篇上限、citation 必填 |
| 统计 | `ClaimSet.duplicates / dropped / by_paper()` |
| 日志 | `report.claims.built` |

## 6. S4 · 方向聚类

| 产物 | 说明 |
|---|---|
| `report/clusters.py` | 轻量 Jaccard 单链接聚类；`min_size`、`max_clusters`、`threshold` 可调；singletons 合并 Other |
| `report/context.py` | `build_context`：PaperCard → claims → directions；单篇失败不阻断 |
| 命名 | 关键词名 + 可选 LLM 命名（失败保留算法名） |
| 确定性 | 论文按 paper_id 排序；方向按规模排序；同输入同输出 |
| 日志 | `report.clusters.built`、`report.context.built`、`paper_card.*` |

### 测试

`tests/report/test_claims_and_clusters.py`（9 例）：稳定 ID、跨论文去重、每篇上限、相似聚类、确定性、空输入、LLM 失败、context 缓存、坏论文容错。

### 未做（S5）

- 未接入 `report` 节点；`ReportContext` 已就绪，S5 用它做方向综合与对比。
