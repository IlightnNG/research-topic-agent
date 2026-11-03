# TODO

> 版本：4.0（2026-11-03）
> 状态：Phase 4.2 已完成；下一阶段 4.3 暂缓。
> 原则：RAG / Qdrant / Kuzu 先不做；先保持 report 链路稳定。

---

## 0. 当前结论

```text
Phase 4.2: complete
Report workflow: 5 Node, API + CLI, 100 papers
Fulltext: 98 / 100
Claims: 196
Sections: 23
Quality gate: deterministic hard gate
LLM audit: hard on explicit reject; fail-open if audit unavailable
Chat: deferred
RAG / Qdrant / Kuzu: deferred
```

当前没有必须立即完成的 report workflow 项。

---

## 1. Phase 4.3 · deferred

> 触发条件：report 链路连续稳定，且论文量/检索质量需要 semantic retrieval。

### 1.1 RAG / 三库

| ID | Module | Priority | Status | Title |
|---|---|---|---|---|
| TODO-301 | S/RAG | P2 | deferred | Qdrant collection + D 盘 storage |
| TODO-302 | S/RAG | P2 | deferred | embedding / chunking / reindex |
| TODO-303 | S/RAG | P2 | deferred | hybrid retrieval + rerank |
| TODO-304 | S/RAG | P2 | deferred | Kuzu schema 与作者/引用图 |
| TODO-305 | S/RAG | P2 | deferred | 三库一致性 / ingestion outbox |
| TODO-306 | E/RAG | P2 | deferred | RAG recall / citation 评估 |

职责：

```text
SQLite
  论文元数据、runs、nodes、events、claims、citations、reports

Qdrant
  摘要/全文 chunk embedding
  semantic / hybrid retrieval

Kuzu
  Paper / Author / Venue / Topic
  AUTHORED_BY / CITES / SIMILAR_TO / BELONGS_TO
```

原则：

```text
SQLite 是 source of truth
Qdrant / Kuzu 是可重建索引
先 Qdrant，后 Kuzu
统一 ingestion service，不在工具里三写
每条索引记录带 content_hash / schema_version
```

现在不做：

```text
100 篇 demo 不需要向量库
report workflow 刚稳定，检索接口不应现在改
三库一致性成本高
```

### 1.2 D 盘约束

| ID | Module | Priority | Status | Title |
|---|---|---|---|---|
| TODO-311 | S | P1 | open | 统一 D 盘 storage root 与启动检查 |
| TODO-312 | S | P1 | open | 论文/全文/artifact/report 路径迁移 |
| TODO-313 | S | P1 | open | 临时目录与模型缓存固定到 D |

目标：

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

规则：

```text
PDF / fulltext / report / artifact / Qdrant / Kuzu 全部 D 盘
SQLite 只存元数据、索引、状态、路径
HF_HOME、TEMP、TMP 固定 D 盘
启动检查 root 不在 C 盘
```

### 1.3 Chat

| ID | Module | Priority | Status | Title |
|---|---|---|---|---|
| TODO-321 | C | P3 | deferred | Chat workflow |

依赖：

```text
report workflow 稳定
RetrievalPort 可用
```

---

## 2. Report backlog

| ID | Module | Priority | Status | Title |
|---|---|---|---|---|
| TODO-331 | R/V | P2 | open | LLM audit 校准与 fail-open 监控 |
| TODO-332 | R | P2 | open | 剩余 2/100 fulltext |
| TODO-333 | R/V | P3 | deferred | 并行 section 写入 |
| TODO-334 | I | P3 | deferred | 质量历史趋势 / 对比视图 |

说明：

```text
4.2.11.2 已实现 hard-on-explicit-reject
audit 基础设施不可用时 fail-open，并记录 audit.status=unavailable
这不是长期理想状态，但保证流程可跑
```

---

## 3. 已完成 · Phase 4.2

```text
AgentKernel + tools + scheduler + checkpoint
L3 gate passed
5 Node report workflow
API + CLI
Node-level section loop
per-section retry + checkpoint
100 papers / 98 fulltext / 196 claims / 23 sections
deterministic quality gate
compact LLM audit
section progress UI
failed section retry API + UI
API pause/resume real probe
DemoOrchestrator removed
demo package/scripts cleaned
```

旧 TODO-001–015、TODO-101–109、TODO-201–216 已合并；历史在 git 中。
