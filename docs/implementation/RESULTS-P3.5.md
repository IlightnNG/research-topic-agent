# RESULTS — Phase 3.5（S1/S2/S3）

> 规范：`phase3.5-full-architecture-and-research-report.md`
> 当前：S1/S3 完成，S4–S6 基础完成，S2 未完成。

## 门禁

```text
pytest        648 例，exit 0
playwright    18 passed（26.1s）
ruff          clean
```

## S1 · RunShell + 新入口（部分）

| 产物 | 说明 |
|---|---|
| `runtime/report_shell.py` | prepare → ReportWorkflow → persist → metrics → finish |
| `POST /api/topics/{id}/report-workflow` | 不经过 10 节点 graph |
| `scripts/run_report_workflow.py` | CLI 直连 |
| 边界 | 默认 `/run` 仍是旧 graph |

## S2 · 旧 graph 删除（未完成）

- 旧 10 节点 graph 保留；
- 未删除，避免破坏 UI/10 阶段契约；
- 仍需后续迁移。

## S3 · source 节点（完成）

- `workflow/source.py`：topic/focus/limit/100；
- 本地论文按词面相关性排序；
- 支持显式 paper_ids；
- `empty_retrieval` 故障时返回空集，保留 degraded 路径；
- 20/50/100 直连 Workflow 测试已过。

## 已知问题

- 新入口同步执行，长报告需要换后台 job；
- S1 尚未切默认 `/run`；
- S2 未做；
- 100 篇真实评估集未建立。


## S4–S6（2026-10-31）

- S4：`select_evidence_tiers`，L1 全量、L2 深读、L3 quote；
- S5：`build_directions_embedding`，char-ngram cosine + 单链聚类；
- S6：Comparison Matrix、Cross-cutting Themes；
- 测试：647 pytest / 18 e2e。

边界：不是全文精读，也不是真实 embedding；报告仍偏结构化摘要。


## S7–S10（2026-10-31）

- S7：ReportVerifier 强制 Node，AgentVerifier 可选；
- S8：section.delta 事件已发，UI 未消费；
- S9：checkpoint 基础已有，API resume 未接；
- S10：search/cluster/comparison 指标落库并测试；
- 648 pytest / 18 e2e。
