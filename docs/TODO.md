# TODO

> 版本：3.0（2026-11-03）
> 管理规则见 `docs/CONVENTIONS.md` §5。
> 当前优先级：**Report workflow > Report quality > D 盘存储整理 > 三库/RAG > Chat**。
> 旧的 M1–M6 待办已清理；历史记录保留在 git 历史中。

---

## 0. 当前路线

```text
P0  Report workflow v2
    KernelNodeAdapter 接入
    5 个特制 Node
    100 篇端到端真实报告

P1  Report quality
    citation / audit / fulltext / 分节重试

P1  D 盘存储约束
    大文件不落 C 盘

P2  三库 / RAG
    整条 report 链路连续稳定后再做

P3  Chat
    report 稳定后再复用 Kernel
```

---

## 1. Report Workflow v2

| ID | Module | Priority | Status | Title |
|---|---|---|---|---|
| TODO-201 | W/K | P0 | open | WorkflowRunner 接入 KernelNodeAdapter |
| TODO-202 | W | P0 | open | 定义 5 节点 report workflow |
| TODO-203 | R/T | P0 | open | source/evidence 领域工具与 schema |
| TODO-204 | R/T | P0 | open | report.plan / write / audit 工具与 verifier |
| TODO-205 | R/W | P0 | open | 100 篇真实 LLM 端到端报告 |
| TODO-206 | W | P1 | open | Node checkpoint / resume / 局部重试 |
| TODO-207 | W | P1 | open | 移除生产路径 DemoOrchestrator |
| TODO-208 | R/V | P1 | open | 报告质量门禁 |

### TODO-201 · WorkflowRunner 接入 KernelNodeAdapter

- Module：W/K
- Status：open
- 问题：当前 CLI/API 仍使用旧 `Kernel` + `DemoOrchestrator`，不是通用 `AgentKernel`。
- Acceptance：
  - `WorkflowRunner` 的 kernel port 使用 `KernelNodeAdapter`；
  - `NodeSpec` → `KernelTask` → `AgentKernel` → `NodeResult`；
  - 每 Node 有独立 toolset / output schema / verifier / budget；
  - 旧 `DemoOrchestrator` 只在 demo flag 下保留；
  - workflow 单测覆盖 adapter 边界。

### TODO-202 · 定义 5 节点 report workflow

- Module：W
- Status：open
- 节点：
  - `source.collect`
  - `evidence.extract`
  - `report.plan`
  - `report.write`
  - `report.audit_finalize`
- Acceptance：
  - 每个 Node ≥3 tools；
  - 至少一个 `context.*` 或 `plan.*`；
  - Node 输出是引用路径，不是大文本；
  - optional `map.classify` 只在 classification 开启时插入；
  - `WorkflowDefinition.validate()` 通过。

### TODO-203 · source/evidence 领域工具与 schema

- Module：R/T
- Status：open
- 需要：
  - `source.search` / `source.fetch_pdf` / `source.fetch_html`
  - `fulltext.extract`
  - `corpus.store` / `corpus.dedupe` / `corpus.stats`
  - `corpus.read`
  - `claims.extract` / `quote.check` / `claims.filter` / `claims.dedupe`
  - `evidence.stats` / `evidence.coverage`
- Acceptance：
  - `SourceArtifact` / `EvidenceArtifact` schema 固定；
  - exact quote 可复算；
  - 作者列表、references、截断句被拒绝；
  - 工具输出落 D 盘 artifact。

### TODO-204 · report.plan / write / audit 工具与 verifier

- Module：R/T
- Status：open
- 需要：
  - `report.plan` / `outline.check`
  - `report.write_section` / `report.check_section` / `citation.check`
  - `report.assemble` / `report.persist`
  - `verify.code` / `verify.audit` / `artifact.hash`
- Acceptance：
  - section 级 citation / word gate；
  - 单 section 失败可局部重试；
  - finalize 有 code + audit 双验收；
  - `ReportPlan` / `ReportDraft` / `FinalReport` schema 固定。

### TODO-205 · 100 篇真实 LLM 端到端报告

- Module：R/W
- Status：open
- Acceptance：
  - 真实 LLM，不允许 `DemoOrchestrator`；
  - papers ≥100；
  - fulltext ≥35，或显式 degraded；
  - claims ≥100；
  - sections ≥10；
  - word_count 3500–8000；
  - citation_coverage = 1.0；
  - report.md + report.json 可打开；
  - run state complete；
  - 全过程 metrics / events 落库。

### TODO-206 · Node checkpoint / resume / 局部重试

- Module：W
- Status：open
- Acceptance：
  - source 成功后重跑不重下载；
  - evidence 成功后重跑不重抽取；
  - 单 section 失败只重写该 section；
  - 进程中断后可从 Node checkpoint 恢复；
  - 测试覆盖 committed / failed / degraded。

### TODO-207 · 移除生产路径 DemoOrchestrator

- Module：W
- Status：open
- 前置：TODO-205 通过。
- Acceptance：
  - 生产 API/CLI 不再 import `DemoOrchestrator`；
  - `test_no_demo_orchestrator_in_src` 通过；
  - demo 仅保留为离线样本或测试 fixture。

### TODO-208 · 报告质量门禁

- Module：R/V
- Status：open
- Acceptance：
  - citation coverage = 1；
  - claim purity / exact quote；
  - section 覆盖；
  - audit accepted；
  - 失败原因可定位到 Node / section；
  - 指标写入 kernel_metrics / report metrics。

---

## 2. D 盘存储约束

> 大文件不得落 C 盘。P1，必须在批量论文导入前完成。

| ID | Module | Priority | Status | Title |
|---|---|---|---|---|
| TODO-209 | S | P1 | open | 统一 D 盘 storage root 与启动检查 |
| TODO-210 | S | P1 | open | 论文/全文/artifact/report 路径迁移 |
| TODO-211 | S | P1 | open | 临时目录与模型缓存固定到 D |

目标布局：

```text
D:\lit-agent-store\
  data\
    v2.sqlite
  corpus\
    papers.jsonl
    pdf\
    fulltext\
    chunks\
  artifacts\
  reports\
  qdrant\
  kuzu\
  cache\
    hf\
    embeddings\
    retrieval\
  temp\
  logs\
  benchmarks\
```

规则：

```text
SQLite      只存元数据、索引、状态、指标、路径
PDF         只存 D:\lit-agent-store\corpus\pdf
fulltext    只存 D:\lit-agent-store\corpus\fulltext
report      只存 D:\lit-agent-store\reports
artifact    只存 D:\lit-agent-store\artifacts
Qdrant      只存 D:\lit-agent-store\qdrant
Kuzu        只存 D:\lit-agent-store\kuzu
HF cache    HF_HOME=D:\lit-agent-store\cache\hf
TEMP/TMP    D:\lit-agent-store\temp
```

Acceptance：

```text
启动时校验 root 不在 C 盘
路径不存在自动创建
测试检查 PDF/fulltext/Qdrant/Kuzu 路径
浏览器 localStorage 只存 UI 偏好
```

---

## 3. 三库 / RAG · deferred

> 触发条件：report 链路连续 3 次稳定通过，且论文量 ≥500 或检索指标不达标。
> 在触发前不引入 Qdrant / Kuzu。

### 3.1 三库职责

```text
SQLite
  论文元数据、authors、runs、nodes、events、claims、citations、reports
  事实源 / 事务边界

Qdrant
  摘要 + 全文 chunk 的 embedding
  payload: paper_id, chunk_id, section, page, text, content_hash
  semantic / hybrid retrieval

Kuzu
  Paper / Author / Venue / Topic
  AUTHORED_BY / CITES / SIMILAR_TO / BELONGS_TO
  关系查询
```

### 3.2 TODO

| ID | Module | Priority | Status | Title |
|---|---|---|---|---|
| TODO-301 | S/RAG | P2 | deferred | Qdrant collection + D 盘 storage |
| TODO-302 | S/RAG | P2 | deferred | embedding / chunking / reindex |
| TODO-303 | S/RAG | P2 | deferred | hybrid retrieval + rerank |
| TODO-304 | S/RAG | P2 | deferred | Kuzu schema 与作者/引用图 |
| TODO-305 | S/RAG | P2 | deferred | 三库一致性 / ingestion outbox |
| TODO-306 | E/RAG | P2 | deferred | RAG recall / citation 评估 |

### 3.3 实施原则

```text
1. SQLite 仍是 source of truth
2. Qdrant / Kuzu 都是可重建索引，不是唯一事实源
3. 先加 RetrievalPort，再接 Qdrant，最后接 Kuzu
4. 先 Qdrant，后 Kuzu
5. 不在工具里三写，统一走 ingestion service
6. 每次索引写入带 content_hash / schema_version
```

### 3.4 现在不做的理由

```text
当前 100 篇 demo 不需要向量库
workflow 还未稳定，检索接口会反复改
三库一致性成本高
先把 report 完整跑通，才能评估 RAG 的真实收益
```

---

## 4. Chat · deferred

| ID | Module | Priority | Status | Title |
|---|---|---|---|---|
| TODO-401 | C | P3 | deferred | Chat workflow |
| TODO-402 | E | P3 | deferred | scorecard 可选 Node |

Chat 需要：

```text
ConversationSession
retrieve
answer
citation verify
```

等 report workflow 稳定后，复用同一 Kernel 和同一 RetrievalPort。

---

## 5. 已完成

```text
Phase 4.1 报告基线
100 篇报告链路
工具契约 / ToolRuntime
通用 AgentKernel
checkpoint / metrics / logs / errors
30 简单 + 14 复杂真实 LLM benchmark
trace-aware audit repair
L3 gate passed
```

旧 TODO-001–015、TODO-101–109 已合并或清理；需要追溯时看 git 历史。
