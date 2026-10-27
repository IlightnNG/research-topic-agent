# ADR-0009 · Phase 3.2 报告表（paper_cards / report_steps）

- **状态**：Accepted
- **日期**：2026-10-26
- **相关**：ADR-0005（实体表契约）、phase3.2-report-quality.md

## 背景

Phase 3.2 需要缓存每篇论文的结构化卡片（PaperCard），并记录报告子步骤的耗时/错误/tokens，用于排错与调参。
这两类数据不属于业务事实，但需要持久化、可查询。

## 决策

新增两张表（`db/tables.py` 与迁移 `0006_report_v2` 同时定义）：

| 表 | 用途 | 关键列 |
|---|---|---|
| `paper_cards` | 每篇论文的结构化卡片缓存 | `paper_id PK, content_sha, version, card_json, created_at` |
| `report_steps` | 报告生成子步骤日志 | `id PK, run_id, report_id, step, status, duration_ms, tokens, cost_usd, error_code, meta_json, created_at` |

同时在既有表上扩列：

- `reports.language / generated_by / word_count / fallback_reason`
- `runs.report_language`
- `papers.pdf_path / pdf_url / full_text_status`

## 后果

- 表总数从 **24 → 26**；相关计数测试与 health 断言同步更新；
- `paper_cards` 可用 `paper_id + content_sha + version` 失效；
- `report_steps` 只记元数据，不记 prompt/论文全文；
- 迁移 0006 幂等，可回滚；旧报告补 `language='en', generated_by='template'`。
