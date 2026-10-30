# RESULTS — Phase 3.3（Report 质量、稳定性与调参）

> 规范：`phase3.3-report-quality-and-stability.md`（M1–M9 / S1–S12 / H1–H15）。
> 当前进度：**S1–S2 完成**。

## 0. 一页摘要

| 指标 | 结果 |
|---|---|
| 阶段 | **Phase 3.3 收尾（S1–S12）** |
| 测试 | `pytest` **613 例**；Playwright **18 passed（24.9s）** |
| E2E | **18 passed**（24.9s） |
| 验证器 | `verify_phase3 13/13` |
| 前端 | typecheck ✓ / build ✓ |

## 1. S1 · Source selector：queries + preview

| 产物 | 说明 |
|---|---|
| `sources/openalex.py` | `build_search()`；`fetch_works_page(search=...)` |
| `sources/preview.py` | `preview_selector()`：按 selector 取 1–50 篇样例 |
| `POST /api/sources/preview` | 返回 `sample_count + items`，用于创建前确认 |
| 测试 | query 传递、空 selector、样例数量 |

## 2. S2 · AI venue 建议 + 人工确认

| 产物 | 说明 |
|---|---|
| `sources/suggest.py` | LLM 只提 venue 名称/query；`resolve_venues` 解析真实 ID；失败 fallback |
| `POST /api/sources/suggest` | 返回 `{venues, queries, from_year, source}` |
| `SourceSuggest.vue` | 候选勾选、置信度、手动 source ID、Preview 5 papers |
| Topic 创建页 | 选择结果写入 `sources`；用户必须确认，不自动应用 |
| 测试 | 名称→ID、未知 venue 0 置信、无 key fallback、API 路由 |

## 3. 关键行为

- LLM **不会生成** `S...` ID，ID 只来自 OpenAlex；
- 没有 API key 时 `suggest` 返回 query fallback，不阻塞创建；
- 用户可移除 AI 候选、粘贴手动 ID；
- `preview` 用真实 OpenAlex 调用，帮助确认范围；
- 当前 UI 在 **New topic** 对话框，后续迁到 Settings（OI-013）。

## 4. 下一步

- S3：批量 PaperCard + token/JSON repair；
- S4：提交后缓存；
- S5：claim 纯度；
- S6：聚类去 boilerplate。

## 5. 已知限制

- suggest 的 confidence 是“名称是否解析成功”，不是语义相关度；
- preview 只取样例，不代表总量；
- 未自动应用高置信配置；
- Settings 页面未做。


---

## 6. S3 · 批量 PaperCard 与 token

| 产物 | 说明 |
|---|---|
| `report/cards.py` | `build_cards`：`batch_size` 一篇批；`batch_size=5` |
| 失败策略 | 批次失败 → 二分递归 → 单篇兜底（不再无限递归） |
| token | `max_tokens_card` / `max_tokens_cluster` / `max_tokens_synthesis` 全部可配 |
| 测试 | 单次调用、失败拆分、缓存命中 |

## 7. S4 · Post-commit 缓存

| 产物 | 说明 |
|---|---|
| `nodes.report` | `report_cards_json` 放入 artifacts（schema 门禁排除大字段） |
| `commit.py` | 报告提交成功后写 `paper_cards`；失败只告警 |
| 测试 | v2 落库后 `paper_cards` 有行；二次读取命中且不调用 LLM |

### 注意

- 缓存写入不在 run 事务内，避免嵌套写锁；
- 批次失败会二分重试，最坏情况退化为单篇；
- `max_tokens_card=1200` 默认，按论文长度可调。


---

## 8. S5–S7 · 纯度、聚类、hybrid

### S5 · Claim 纯度

| 项 | 实现 |
|---|---|
| 过滤 | `published/proceedings/conference/DOI/arXiv/authors/et al` 等 |
| 作者列表 | 连续 `Name Name, Name Name` 模式拒绝 |
| Prompt | 只抽 research claims；禁止 venue/publication/authors |
| 统计 | `ClaimSet.filtered`、`context.meta.filtered_claims` |
| 测试 | 书目 claim、作者列表、正常 claim |

### S6 · 聚类去噪

| 项 | 实现 |
|---|---|
| 停用词 | ACL/EMNLP/NeurIPS/Annual/Association/Proceedings/Conference… |
| 阈值 | `cluster_threshold` 默认 0.18 |
| 命名 | 不含 venue 词；失败回落 top terms |
| 测试 | `ACL 2024` 标题不会进入方向名 |

### S7 · hybrid 元信息

| 项 | 实现 |
|---|---|
| Report 字段 | `generated_by` = llm/hybrid/template；`fallback_count`、`coverage` |
| 迁移 | `0007_report_quality`（reports 扩列） |
| 持久化 | `reports` 落库；API 返回 |
| UI | 报告头显示 `hybrid · N fallbacks · coverage %` |
| 提交事件 | hybrid 也算 `extraction=llm`、`llm_used=true` |
| 测试 | hybrid 字段、v2 落库、e2e 18 |

### 当前限制

- 聚类仍为词面 Jaccard（embedding 在 S6 计划中但未引入）；
- 书目过滤是规则，可能误伤“conference room”类句式；
- `fallback_count` 只统计方向综合，不含 card 批次回落。


---

## 9. S8 · Thin / 旧报告兼容

| 项 | 实现 |
|---|---|
| `reports.thin` | 迁移 0008；`papers<5 or claims<5 or words<300` |
| API | 旧报告 `language/generated_by/fallback_count/coverage/thin/word_count` 补默认值 |
| UI | 报告头显示 Thin warning |
| 测试 | 2 篇 fixture 报告 `thin=true`；NULL 元数据回退 en/template/0 |

## 10. S9 · 超时与 E2E 隔离

| 项 | 实现 |
|---|---|
| 超时 | `report.step_timeout_s`（默认 120s）；context 超时 → 模板 + `E_REPORT_TIMEOUT` |
| E2E | `LIT_AGENT_STORAGE__DATA_ROOT=D:\lit-agent-store\e2e-data` + `scripts/seed_e2e_store.py` |
| 稳定性 | E2E 18 passed；live 数据不再污染 e2e |
| 限制 | 单 worker；并行 run 压测未做 |

## 11. 下一步

- S10：指标 + `tune_report.py` + 20/50/100 实验；
- S11：调参；
- S12：收尾。


---

## 12. S10 · 指标与调参

| 指标 | 来源 |
|---|---|
| `report_fallback_count` | `reports.fallback_count` |
| `report_coverage` | `reports.coverage` |
| `report_thin` | `reports.thin` |
| `report_cache_hit_rate` | `llm_calls.cache_hit / calls`（已绑定 run_id） |
| `report_llm_failures` | `llm_calls.ok = 0` |

`scripts/tune_report.py`：

```powershell
uv run python scripts/tune_report.py --topic ai-agents-live --preset cheap --runs 1 --execute
```

输出 CSV：`out/tune-report.csv`。

## 13. S11 · 20 篇 preset 实跑

| preset | claims | sections | words | coverage | fallback | cache hit | latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 18 | 5 | 587 | 0.6087 | 1 | 0.2 | 36.4s |
| token1200 | 18 | 5 | 638 | 0.6087 | 1 | 0.2 | 32.7s |
| cheap | 18 | 5 | 643 | 0.6087 | 1 | 0.6 | 22.9s |

**结论**：`cheap` 在当前 23 篇数据上延迟最低，claim/coverage 不变；  
**但“相关性/可读性”仍需人工评分**，不能只凭自动指标选型。

## 14. Phase 3.3 关闭

- 生成链路：Source → Card → Claim → Cluster → Synthesis → Validate → Report；
- S1–S12 代码/测试完成；
- 613 pytest、18 e2e、typecheck/build；
- 剩余：人工相关性评分、embedding 聚类、50/100 篇压测（Open Issues）。
