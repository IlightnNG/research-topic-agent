# RESULTS — Phase 3.6 真实联调（OpenAlex + v2）

> 日期：2026-10-31
> 目标：真实论文抓取 + source/evidence/map/write/persist/chat/API 联调
> 结论：**真实链路已跑通，但报告状态为 degraded，不是 complete。**

## 1. 真实抓取

OpenAlex，无需 API key，mailto 标识。

| 项 | 结果 |
|---|---|
| 查询 | 10 个主题 query |
| 去重后 | **135 篇** |
| 选定 | **100 篇** |
| 含 metadata | 135 |
| 下载 PDF 全文 | **5 篇** |
| 全文比例 | **5%** |

查询包括：

```text
large language model agents tool use
LLM agent planning
LLM agent memory
agent evaluation benchmark
retrieval augmented generation agents
LLM agent safety
multi-agent collaboration
web navigation agents
code generation agents
agentic workflow automation
```

## 2. 100 篇真实报告

| 项 | 结果 |
|---|---|
| run | `run-...` |
| papers | 100 |
| claims | 185 |
| fulltext | 5 |
| directions | **3** |
| count_quality | **deficit** |
| min direction size | 6 |
| words | 2519 |
| state | **degraded** |
| 耗时 | 10.1s（本地，无 LLM） |

方向：

```text
D1 Agents / Language
D2 ...
D3 ...
```

问题：

- 方向数 3，不满足 5–8；
- 全文只有 5/100；
- 报告为 degraded；
- 报告是确定性模板，不是 LLM 科研写作。

因此：

> **链路已跑通，不能宣称“百篇科研级 complete 报告”。**

## 3. 指标

| 指标 | 值 |
|---|---|
| search.coverage | 1.0 |
| search.duplicate_rate | 0.0 |
| fulltext.available_ratio | 0.05 |
| card.quote_verbatim_rate | 1.0 |
| claim.purity | 1.0 |
| claim.citation_coverage | 1.0 |
| cluster.count | 3 |
| cluster.min_size | 6 |
| cluster.outlier_rate | 0.0 |
| report.words | 2519 |
| report.citation_coverage | 1.0 |
| report.uncited_facts | 0 |

## 4. Chat 真实语料

问题：

```text
What do LLM agents use tools for?
memory in agents
planning benchmark
```

结果：

- 有回答；
- 有 3 条 citation；
- 基于本地 corpus 检索；
- 未接 LLM。

## 5. API 真实联调

使用 60 篇真实 corpus：

```text
POST /api/v2/runs           202
GET  /api/v2/runs/{id}      succeeded
GET  /api/v2/reports/{id}   10 sections
POST /api/v2/chat           200, answered, 3 citations
```

## 6. 结论

**已证明：**

- 真实 OpenAlex 抓取可用；
- PDF 文本提取可用；
- evidence/claim/quote 可用；
- map/write/persist 可用；
- 指标可落库；
- Chat 可用；
- v2 API 可用。

**未证明：**

- 100 篇完整全文；
- 5–8 个方向；
- 科研级 complete 报告；
- LLM 写作质量；
- 人工评估。

## 7. 下一步必须先解决

1. PDF 获取率：5% → ≥30%；
2. 方向数：3 → 5–8，且每方向 ≥3；
3. 报告状态 complete 条件；
4. LLM writer；
5. 真实评估集。


---

## 8. S3/S4 优化后复测（2026-10-31）

- PDF/HTML 多源 fallback 已加；
- map 使用 title+abstract+claims，目标方向数 `min(8,max(5,ceil(n/15)))`；
- 大方向 `max_share` 门禁 ≤0.6；
- claim ledger 覆盖全部 claims，`report.claim_coverage=1.0`；
- artifact 只存 sha，payload 进内容寻址文件；
- 100 篇复测：

```text
claims 185
directions 3
min_size 6
max_share 0.86
words 2519
state degraded
```

仍然 degraded，原因：

1. `cluster.count=3`，不足 5；
2. `direction.max_share=0.86`，单方向过大；
3. `fulltext.available_ratio=0.05`。

这证明优化没有掩盖问题，门禁正确地把报告标成 degraded。
