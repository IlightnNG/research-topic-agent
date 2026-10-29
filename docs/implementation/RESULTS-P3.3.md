# RESULTS — Phase 3.3（Report 质量、稳定性与调参）

> 规范：`phase3.3-report-quality-and-stability.md`（M1–M9 / S1–S12 / H1–H15）。
> 当前进度：**S1–S2 完成**。

## 0. 一页摘要

| 指标 | 结果 |
|---|---|
| 阶段 | **S1–S2 完成** |
| 测试 | `pytest` **606 例**（新增 5 例 source 测试） |
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
