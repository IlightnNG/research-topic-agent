# RESULTS — Phase 3.2（Report 核心能力）

> 规范：`phase3.2-report-quality.md`（S1–S14 / H1–H15）。
> 当前进度：**S1–S9 核心完成**；S10–S14 为体验扩展。

## 0. 一页摘要

| 指标 | 结果 |
|---|---|
| 阶段 | **Phase 3.2 收尾（S1–S14）** |
| 测试 | `pytest` **601 例**；Playwright 18 passed（干净 store；live 数据下 17/18） |
| 验证器 | `verify_phase3 13/13`、`verify_phase2_1 13/13` |
| 迁移 | `0006_report_v2`（26 张表）已应用到 dev store |
| 兼容 | 旧报告可读；v2 已接入 report 节点（默认开） |

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


---

## 7. S5 · 方向综合

| 产物 | 说明 |
|---|---|
| `report/synthesis.py` | 每个方向输出 `definition / common_ground / differences / open_questions` |
| 约束 | claim_id 白名单；differences 至少 2 个引用；无有效项回落确定性 |
| 失败 | 单方向失败只回落该方向，不阻断整份报告 |
| 日志 | `report.synthesis.done/fallback` |

## 8. S6 · 组装、校验、两阶段提交

| 产物 | 说明 |
|---|---|
| `report/assemble.py` | Overview / Deep Dive / Gaps / Paper Index；`[C#]` 映射与 claim_indexes |
| `validate_report` | section 必须有 claim；引用索引必须存在；语言一致 |
| 回落 | 校验失败 → 无 insights 的模板报告 + `fallback_reason` |
| 接线 | `report.v2_enabled=true` 时走 `build_report_v2`，`pending_writes.draft` 在门禁后提交 |
| 持久化 | `reports.language/generated_by/word_count/fallback_reason` 落库 |
| 修复 | LLM 输出非法 → 丢弃非法项；全空 → 模板 |

### 测试

`tests/report/test_synthesis_and_assemble.py`（7 例）：claim 白名单、失败回落、空 synthesis、组装/校验、缺失 claim 拒绝、v2 端到端、空论文安全。

### 注意

- **v2 默认关闭**；打开方式：`LIT_AGENT_REPORT__V2_ENABLED=true`（或配置）；
- 打开后报告走新结构，旧报告仍可读；
- Claim DB ID 统一为 `run_id:sha`，报告里的 `P0-C1` 仅用于展示。


---

## 9. S7 · 报告指标与门禁

| 产物 | 说明 |
|---|---|
| `eval/report_metrics.py` | `report_words/sections/claims/cited_claims/cited_ratio/fallback/generated_llm` |
| `metrics` 落库 | 仅数值；可复算，不增长行数 |
| `gate_report_contract` | 校验 `report_draft_json`：section claim、`[C#]`、语言；失败 retry |
| 测试 | `test_report_metrics_are_numeric`、v2 全链路 |

## 10. S8 · 报告页与 Tab 工作台

| 产物 | 说明 |
|---|---|
| `ReportViewer.vue` | v2 sections + TOC + `[C#]` chip；有 sections 时隐藏重复 Claims 表 |
| `RunWorkspace.vue` | 固定 Trajectory/Report + 动态 Paper Tab（closable）；引用打开/激活 |
| `PaperPane.vue` | 论文标题/作者/摘要/报告内 claims；PDF 状态 |
| `/api/papers/{id}` | 论文详情；404 统一错误 |
| 测试 | `.cite-chip` 打开 Tab、F12 表数、17 e2e |

### 修复

- **嵌套写锁**：报告阶段构建 PaperCard 时不再 `BEGIN IMMEDIATE` 写缓存（`write_cache=False`），避免 run 事务内锁等待。
- **claim id 不一致**：`_persist_claims` 使用 `claim.text_sha` 计算 citation 的 claim_id，避免 FK 失败。
- **draft 契约**：`report_draft_json` 放 artifacts，`PendingWrite` 保持 `kind` only；schema 门禁排除大字段。

## 11. 当前限制

- 报告页暂无右侧面板（S9/S10 计划）；无 PDF 渲染（只显示状态/外链）。
- Tab 并列/拖拽未做；当前单 pane。
- 旧报告（v1）仍显示 Findings/Claims 回退。


---

## 12. S9 · e2e 与收尾

| 项 | 结果 |
|---|---|
| E2E | **18 passed / 21.8s**（retries=0，全局 45s，expect 10s） |
| 用例 | 固定 Tab、引用开 Tab、关闭回 Report、报告 sections、健康/F12、Chat/会话、失败卡 |
| 全量 | 596 pytest；verify 13/13、13/13、8/8 |
| 前端 | typecheck ✓、build ✓ |

### 核心边界

已完成 Report 生成链路 + 阅读工作台（Tab/引用/论文面板）。
S10–S14（右侧面板、PDF 阅读、作者面板、语言选择、虚拟列表、并列 Tab）作为后续体验增强，不阻塞 3.2 核心。


---

## 13. S10–S11 · PDF 与作者面板

| 能力 | 实现 |
|---|---|
| PDF | `/api/papers/{id}/pdf`：本地文件、Range 206、外部 URL 307；PaperPane iframe + Download |
| 论文详情 | authors 返回 `{author_id,name}`；点击作者打开右侧 AuthorPane |
| 作者 | `/api/authors/{id}`：机构/ORCID/论文/合作者；点击论文开 Paper Tab |
| 错误 | 无 PDF/作者 → `E_NOT_FOUND`（英文） |
| 测试 | `tests/api/test_papers_authors.py`（4 例）；e2e 18 passed |

### 当前完整度

- Report 生成 + 工作台 + 引用 + Paper Tab + PDF + 作者面板已完成。
- 待做：生成页语言选择（S12）、100+ 虚拟列表（S13）、双 Tab 并列（P2）。


---

## 14. S12–S13 · 语言与长列表

| 能力 | 实现 |
|---|---|
| 报告语言 | `POST /topics/{id}/run` 的 `report_language`（en/zh）→ 按 run 的 Settings；`runs.report_language` 落库 |
| 模板 | Overview/共同点/差异/开放问题/索引均中英；引用格式不变 |
| 生成页 | `GenerateReportDialog` 增加 Report language |
| 长列表 | `PaperIndexTable.vue`：每页 20，避免 100+ 行一次渲染 |
| 测试 | `test_report_language_zh_per_run`；601 pytest；18 e2e |

### 剩余

- S14：最终文档/结果归档；
- P2：双 Tab 并列/拖拽（可选）。


---

## 15. Phase 3.2 关闭（2026-10-29）

- 真实 20 篇（ACL/OpenAlex）+ 3 fixture：32 claims / 7 sections / 791 words；
- 报告：`out/live-report-ai-agents-live.md`；
- 结构通过，但 topic 相关性、聚类、claim 纯度、LLM 截断不达标；
- 23 篇规模下 e2e 偶发 report 卡住；
- 以上问题进入 **phase3.3-report-quality-and-stability.md**；
- 非阶段性问题进入 **docs/OPEN-ISSUES.md**。
