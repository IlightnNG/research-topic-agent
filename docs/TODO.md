# TODO

> 版本：4.1（2026-11-04）
> 状态：Phase 4.2 complete；Phase 4.3 next
> 原则：先把“检索到高质量、可拿全文的论文”做稳，再上 RAG / Qdrant / Kuzu / Chat。
> 约束：SQLite 是 source of truth；Qdrant / Kuzu 是可重建索引；不在工具里三写。

---

## 0. 当前状态

```text
Phase 4.2              complete
Report workflow        5 Node, API + CLI, SSE, pause/resume
Kernel                 AgentKernel + ToolRuntime + checkpoint + repair
Default demo           20 papers
Benchmark              100 papers / 98 fulltext / 196 claims / 23 sections
Report quality         dynamic thresholds + strict finalize
Source                 local / online
Online fulltext        skip no-fulltext, continue until limit
Paper API              local corpus + run-level papers.jsonl
Tests                  128 passed
RAG / Qdrant / Kuzu    deferred
Chat                   deferred
```

当前最重要的判断：

```text
报告链路已经能跑通。
真正的瓶颈是：
  找什么论文
  怎么排序
  怎么拿到全文
  怎么证明找到的是好论文
```

---

## 1. 阶段路线

```text
4.3A  Retrieval Hardening      P0  先做
4.3B  Evidence & Report Quality P1
4.3C  Storage & Paper Registry  P1
4.3D  RAG / Qdrant              P2
4.3E  Kuzu / 三库               P2
4.3F  Chat                      P3
4.3G  Security & Operations     P1  贯穿
```

建议顺序：

```text
4.3A → 4.3B → 4.3C → 4.3D → 4.3E → 4.3F
4.3G 与 4.3A/4.3D 并行
```

---

## 2. 4.3A · Retrieval Hardening

> 目标：从“能搜到一些论文”变成“稳定找到高质量、可解释、可拿全文的论文”。

### TODO-401 · LLM query planning + multi-query retrieval

状态：`open` · Priority：`P0`

问题：

```text
query = null
→ Agent 从 topic_id 猜 “AI agents”
→ 结果很泛
```

目标：

```text
topic / focus / description / keywords
→ LLM 生成 5–10 个互补 query
→ 并行检索
→ 合并、去重、排序
```

query 必须覆盖：

```text
core terms
synonyms
methods
applications
benchmark / dataset
survey
recent work
```

验收：

```text
至少生成 5 个互补 query
query 为空不再由 Agent 猜 topic 名
source artifact 保存 generated_queries
UI 展示 generated queries / hits / kept / skipped
```

---

### TODO-402 · 多源检索与合并

状态：`open` · Priority：`P0`

目标：

```text
OpenAlex
Semantic Scholar
arXiv
Crossref
```

合并：

```text
paper_id
DOI
normalized title
preprint / published version
```

验收：

```text
同一论文不重复进入 corpus
preprint 与 published 能合并
每条记录保留 source provenance
```

---

### TODO-403 · 高价值论文排序

状态：`open` · Priority：`P0`

问题：

```text
当前使用 OpenAlex 默认 relevance
不是“最有价值”
```

排序信号：

```text
topical relevance
citation count
field-normalized citation impact
recency
venue quality
fulltext availability
paper type（survey / benchmark / empirical）
diversity penalty
```

建议 score：

```text
score =
  relevance
+ normalized_citation
+ recency
+ venue_quality
+ fulltext_bonus
- duplicate_penalty
- same_author_or_venue_penalty
```

后续：

```text
citation graph centrality
influential citation count
```

验收：

```text
每条候选保存 score breakdown
UI 能看到排序原因
至少支持 relevance / citation / recency / venue 四维
```

---

### TODO-404 · Paper identity 与去重

状态：`open` · Priority：`P0`

目标：

```text
paper_id
DOI
arXiv id
normalized title
author + year
```

处理：

```text
同一论文多版本
preprint vs published
重复搜索结果
标题轻微变化
```

验收：

```text
duplicate rate 可统计
corpus 内 paper_id 唯一
重复版本保留 canonical paper
```

---

### TODO-405 · Fulltext acquisition pipeline

状态：`open` · Priority：`P0`

当前：

```text
拿不到 fulltext 就跳过
```

还需要：

```text
DOI → Unpaywall
arXiv → PDF
publisher → PDF / HTML
失败重试 / 换源
PDF 解析
空文本检测
乱码检测
paywall / 403 / 404 分类
```

记录：

```text
downloaded
parsed
empty
failed_reason
source_url
```

验收：

```text
fulltext_yield 可统计
跳过原因可解释
默认 online corpus 不混入 abstract-only
达到 limit 后才停止
```

---

### TODO-406 · Source-level quality gate

状态：`open` · Priority：`P0`

当前 quality gate 在 finalize 才检查。

应该在 `source.collect` 后就检查：

```text
papers >= limit
fulltext_ratio
metadata completeness
duplicate rate
topic coverage
empty abstracts
```

验收：

```text
source 不足时尽早失败
错误信息说明缺什么
不要把低质量 corpus 送进 evidence/report
```

---

### TODO-407 · Source provenance UI

状态：`open` · Priority：`P1`

展示：

```text
generated queries
每个 query 的命中数
候选数
最终保留数
跳过数
fulltext 失败原因
ranking score
```

验收：

```text
用户能回答“为什么是这 20 篇”
不再只看到 papers=20
```

---

### TODO-408 · Retrieval evaluation

状态：`open` · Priority：`P1`

指标：

```text
precision@k
recall@k
NDCG
fulltext_yield
duplicate_rate
topic_coverage
```

需要：

```text
固定评估 query set
人工相关性标注
至少 20 个 topic
```

验收：

```text
query planning / ranking 改动前后可比较
```

---

## 3. 4.3B · Evidence and Report Quality

### TODO-411 · Claim extraction 升级

状态：`open` · Priority：`P1`

当前：

```text
规则抽句
```

问题：

```text
漏 claim
漏方法贡献
漏 limitation
跨句结论丢失
```

目标：

```text
规则 + LLM extraction
quote 必须回查原文
claim type
confidence
source span / page
```

---

### TODO-412 · Section-level evidence retrieval

状态：`open` · Priority：`P1`

问题：

```text
report.write 使用全局 claims
```

目标：

```text
按 section 标题 / kind 检索最相关 claims
再写作
```

验收：

```text
overview / synthesis / paper_analysis 使用不同证据集
重复段落减少
```

---

### TODO-413 · Citation support / entailment

状态：`open` · Priority：`P1`

当前：

```text
citation coverage 只说明“有引用”
```

需要：

```text
句子是否被 quote 支持
是否存在错引
是否存在过度概括
```

---

### TODO-414 · LLM audit 校准

状态：`open` · Priority：`P2`

当前：

```text
explicit reject hard fail
audit unavailable fail-open
```

目标：

```text
audit 评分校准
fail-open 监控
不可用时显著标记
```

---

### TODO-415 · Report template 与人工评估

状态：`open` · Priority：`P2`

需要和导师确认：

```text
Scope / Method
Research Landscape
Paper-by-paper
Synthesis
Evidence Notes
Open Problems
Limitations
```

验收：

```text
section contract
per-section target length
人工 rubric
```

---

## 4. 4.3C · Storage and Paper Registry

### TODO-421 · 统一 D 盘 storage root

状态：`open` · Priority：`P1`

```text
D:\lit-agent-store\
  data\v2.sqlite
  corpus\pdf
  corpus\fulltext
  corpus\chunks
  artifacts
  reports
  qdrant
  kuzu
  cache\hf
  cache\embeddings
  temp
  logs
```

启动检查：

```text
root 不在 C 盘
路径存在或可创建
```

---

### TODO-422 · 路径迁移

状态：`open` · Priority：`P1`

迁移：

```text
PDF / fulltext / artifact / report
```

规则：

```text
SQLite 只存元数据、状态、路径
Qdrant / Kuzu 只存索引
```

---

### TODO-423 · 临时目录与模型缓存固定 D 盘

状态：`open` · Priority：`P1`

```text
HF_HOME
TEMP / TMP
embedding cache
uv/pip cache
```

---

### TODO-424 · Paper registry

状态：`open` · Priority：`P1`

问题：

```text
当前 paper() 会扫描 corpus / run 目录
```

目标表：

```text
papers
paper_versions
paper_sources
paper_metrics
paper_fulltext_status
```

验收：

```text
paper_id 唯一
run 不再依赖目录扫描
citation 能稳定回查论文
```

---

## 5. 4.3D · RAG / Qdrant

### TODO-431 · Qdrant collection + D 盘 storage

状态：`deferred` · Priority：`P2`

```text
collection
paper/chunk payload
content_hash
schema_version
```

---

### TODO-432 · embedding / chunking / reindex

状态：`deferred` · Priority：`P2`

```text
abstract chunk
fulltext chunk
embedding model
incremental index
full rebuild
```

---

### TODO-433 · hybrid retrieval + rerank

状态：`deferred` · Priority：`P2`

```text
BM25 / keyword
vector retrieval
hybrid merge
rerank
top-k evidence
```

---

### TODO-434 · RAG evaluation

状态：`deferred` · Priority：`P2`

```text
recall@k
citation support
evidence traceability
latency
```

---

## 6. 4.3E · Kuzu / 三库

### TODO-441 · Kuzu schema

状态：`deferred` · Priority：`P2`

```text
Paper
Author
Venue
Topic

AUTHORED_BY
CITES
SIMILAR_TO
BELONGS_TO
```

---

### TODO-442 · Ingestion outbox / 三库一致性

状态：`deferred` · Priority：`P2`

```text
SQLite = source of truth
Qdrant / Kuzu = rebuildable
outbox
retry
content_hash
```

---

### TODO-443 · Graph queries

状态：`deferred` · Priority：`P3`

```text
citation centrality
author graph
venue graph
survey discovery
```

---

## 7. 4.3F · Chat

### TODO-451 · Chat workflow

状态：`deferred` · Priority：`P3`

依赖：

```text
report workflow stable
RetrievalPort available
```

内容：

```text
Chat workflow
retrieval + answer
citation traceback
multi-turn context
```

---

## 8. 4.3G · Security & Operations

### TODO-461 · Untrusted content and SSRF

状态：`open` · Priority：`P1`

```text
URL allowlist
SSRF protection
PDF/HTML sanitize
prompt injection detection
tool argument isolation
```

---

### TODO-462 · Heartbeat / timeout / stale run

状态：`open` · Priority：`P1`

```text
node timeout
heartbeat
stale running detection
crash recovery
cancellation
```

---

### TODO-463 · Cost / rate limit / cache

状态：`open` · Priority：`P2`

```text
OpenAlex rate limit
download retry/backoff
query cache
PDF cache
embedding cost
per-run budget
```

---

## 9. 当前小问题清单

| 问题 | 状态 | 归属 |
|---|---|---|
| `query=null` 时 Agent 猜 “AI agents” | open | TODO-401 |
| 在线默认 relevance，不是高价值排序 | open | TODO-403 |
| 同一论文多版本/重复 | open | TODO-404 |
| fulltext 空文本/解析失败 | open | TODO-405 |
| source 质量到 finalize 才发现 | open | TODO-406 |
| paper() 依赖目录扫描 | open | TODO-424 |
| citation coverage ≠ 事实支持 | open | TODO-413 |
| audit fail-open | open | TODO-414 |
| 下载 URL 无 allowlist / SSRF 防护 | open | TODO-461 |
| 后台任务无 heartbeat | open | TODO-462 |

---

## 10. 已完成

```text
Phase 4.2 complete
5 Node report workflow
Kernel + ToolRuntime + checkpoint
API + CLI
SSE live events
run.failed 前端传播
pause / resume / section retry
dynamic quality gate
strict finalize
paper title links
local / online source
online fulltext-first skip
default 20 / benchmark 100
128 tests
```

历史 TODO-001–015、TODO-101–109、TODO-201–216 已合并；旧 TODO-301–335 已重组到本文件。

---

## 11. 第一个 Sprint 建议

只做 5 件事：

```text
1. TODO-401 LLM query planning
2. TODO-402 多源检索 + 去重
3. TODO-403 高价值排序
4. TODO-405 fulltext pipeline
5. TODO-406 source-level quality gate
```

完成标准：

```text
给定 topic + focus
→ 自动生成 query set
→ 多源检索
→ 去重排序
→ 拿到 limit 篇 fulltext
→ source 质量 gate 通过
→ UI 能解释为什么选这些论文
```

这时再开始 Qdrant。
