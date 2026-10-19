# ADR 0005: 论文实体表、事件序号分配与幂等键（Phase 1 契约补充）

Status: **accepted**（Phase 1 Step 1.3 前置，2026-10-19）
Supersedes: 无
Relates: ADR-0001（`Paper.merged_ids` + `paper_merges`）、ADR-0002（指标事件契约）、ADR-0003（存储路径与库身份）、
ADR-0004（向量来源与嵌入模型）

---

## 1. Context（为什么必须决策）

1. **guide §2.1 的 SQLite schema 只有"运行侧"表**：`topics / topic_sources / runs / run_events / reports /
   chat_sessions / chat_messages / llm_calls / metrics / sync_state / job_locks / eval_judgments`。
   **没有任何论文实体表**（`papers / authors / paper_authors / citations`），也没有 `claims`、`llm_cache`。
   而 guide §3 的源适配、§4 的存储、§7 的报告、§11 的"作者动向"全部依赖这些实体。
2. **Phase 0 已经"事实上"用了一批表**（`../prototype/lit_agent_min/stores.py` 的 `papers/authors/paper_authors/
   citations/claims/sync_state/paper_merges`），但那是实验区实现，**未进契约**：
   没有索引定义、没有幂等键口径、没有 `merged_ids` 列，Phase 1 若照搬就会出现"每步各写一套表名"。
3. **事件序号的并发语义未定义**：guide §2.2 只写了"幂等键 `(run_id, stage, step_key)`"与"先落库后广播"，
   没写 `seq` 怎么分配、冲突怎么办。Phase 0 S5/S6 用 JSONL 自增，迁到 SQLite 后若用 `MAX(seq)+1`
   在并发/重试下会**重号或跳号**，直接破坏"事件可按 run 回放"（Phase 1 出口标准 D5）。
4. **幂等键散落在各模块**：哪个资源用什么键、冲突时是覆盖还是忽略，若不集中定义，
   "同 fixture 重跑零增长"（D4）只能靠运气。
5. **语料范围需要落在 `topics`/`topic_sources` 的种子数据里**：导师方向为 **AI / 计算机 / 电子硬件 / 通信**，
   这四个域的期刊会议白名单必须按 OpenAlex `source.id` 解析（Phase 0 结论：按名称匹配会漏），
   而 `topic_sources.selector_json` 的结构由本 ADR 定义（§8）。

---

## 2. Decision 总览

| # | 决策 | 一句话 |
|---|---|---|
| D1 | **新增 11 张实体/证据/缓存表** | `papers / papers_raw / authors / paper_authors / citations / paper_merges / paper_chunks / claims / claim_citations / llm_cache / embeddings`（DDL 见 §3） |
| D2 | **新增 1 张库身份表 `store_meta`** | 取代 ADR-0003 的"空库哨兵"实现细节，同时承载向量库的模型/维度身份（§4） |
| D3 | **seq 分配 = `runs.next_seq` 单行自增（事务内 `UPDATE ... RETURNING`）** | 不用 `MAX(seq)+1`；崩溃回滚不消耗序号（§5） |
| D4 | **双唯一约束**：`(run_id, seq)` + 部分唯一索引 `(run_id, dedupe_key) WHERE dedupe_key IS NOT NULL` | 序连续性 与 操作幂等 分离（§6） |
| D5 | **幂等键总表**：每个资源的冲突动作显式定义（覆盖 / 忽略 / 拒绝） | 集中一处，仓储层照表实现（§7） |
| D6 | **`papers.merged_ids_json` + `paper_merges` 并存** | 前者读优化（对齐 `Paper.merged_ids`），后者审计源（ADR-0001 已倾向二者并存） |
| D7 | **`metrics` 改为可复算**：`UNIQUE(scope, scope_id, metric)` + `INSERT OR REPLACE`，并**取代** guide §2.1 的"metrics 提交后不可改" | 同一 run 重算指标不产生重复行；`reports` 仍不可改（§7.3） |
| D8 | **`topics`/`topic_sources` 结构 + 四域白名单种子** | `selector_json` 结构见 §8，白名单候选见 §8.2 |
| D9 | **Phase 0 的 `out/*.db` 不迁移** | 新库从 fixture 重建；旧数据只作对照（§9） |

---

## 3. SQLite DDL（`db/tables.py` 的契约来源）

> 约定：时间一律 `TEXT` ISO-8601 UTC（如 `2026-10-19T03:00:00Z`）；布尔用 `INTEGER 0/1`；
> JSON 列以 `_json` 结尾，schema 版本记在 `store_meta.schema_version`（当前 `1.0`）。
> **所有表创建顺序即下方顺序**（被引用表在前），降级迁移按逆序 `DROP`。

### 3.0 表清单（共 24 张 = 12 张修订 + 12 张新增）

| 类别 | 表 | 相对 guide §2.1 / ADR 的变化 |
|---|---|---|
| **修订** | `topics` | +`scope_keywords_json`、`seed_queries_json`、`status` |
| 修订 | `topic_sources` | 明确 `selector_json` 结构（§8.1） |
| 修订 | `runs` | +`next_seq`、`dup_events`、`input_hash`、`stage`、`last_ok_stage`、`app_version`；+`ux_runs_one_running` |
| 修订 | `run_events` | +`dedupe_key`；+部分唯一索引；`UNIQUE(run_id,seq)` |
| 修订 | `reports` | +`content_sha`、`n_claims`、`degraded`；`UNIQUE(run_id, content_sha)` |
| 修订 | `llm_calls` | +`request_sha`、`cache_hit`、`cost_estimated`、`ok`、`error_code` |
| 修订 | `metrics` | 改 `PRIMARY KEY(scope, scope_id, metric)`（可复算，§7.3） |
| 修订 | `sync_state` | +`selector`、`last_since` |
| 修订 | `job_locks` | +`expires_at`（孤儿判定） |
| 修订 | `chat_sessions` / `chat_messages` | 仅补外键与索引（P3 启用） |
| 修订 | `eval_judgments` | +`detail_json`、索引（P5 启用） |
| **新增** | `store_meta` | 库身份（ADR-0003 哨兵的落地 + 向量身份） |
| 新增 | `papers` | 论文主表（canonical_id） |
| 新增 | `papers_raw` | 源记录原样留存（ADR-0001 要求） |
| 新增 | `authors` | 作者实体（P4 作者动向） |
| 新增 | `paper_authors` | 作者-论文（保序） |
| 新增 | `citations` | 引用边（仅语料内） |
| 新增 | `paper_merges` | 去重合并审计（ADR-0001） |
| 新增 | `paper_chunks` | 分块（P3 启用，先建表） |
| 新增 | `claims` | 论断（不可落地也要入库） |
| 新增 | `claim_citations` | 论断-证据 |
| 新增 | `llm_cache` | 内容寻址缓存（F8） |
| 新增 | `embeddings` | 嵌入缓存（ADR-0004） |

> 计数口径：修订行里 `chat_sessions` 与 `chat_messages` 合并为一行书写，实际是 2 张表 → 修订 **12 张**；
> 加上新增 **12 张**（含 `store_meta`）= 总计 **24 张**。


### 3.1 库身份与元数据

```sql
CREATE TABLE store_meta (
    store_name        TEXT PRIMARY KEY,      -- 'sqlite' | 'kuzu' | 'qdrant'
    schema_version    TEXT NOT NULL,         -- '1.0'
    app_version       TEXT,
    model_id          TEXT,                  -- 仅向量库：'BAAI/bge-m3'
    model_rev         TEXT,                  -- 仅向量库：模型 commit/短哈希（可复现）
    dim               INTEGER,               -- 仅向量库：1024
    active_collection TEXT,                  -- 仅向量库：'papers_v1'
    built_at          TEXT NOT NULL,
    extra_json        TEXT
);
```

- **空库哨兵**（ADR-0003 §3 的落地）：`SELECT schema_version FROM store_meta WHERE store_name='sqlite'` 必须存在且
  等于代码期望值，否则 `E_STORE_NOT_EMPTY` / `E_STORE_SCHEMA_MISMATCH`。
- **向量库身份**：`model_rev` 与当前加载模型不一致 → 拒绝写入（`E_VECTOR_MODEL_MISMATCH`），必须先重嵌入（ADR-0004 §5）。

### 3.2 主题与抓取范围

```sql
CREATE TABLE topics (
    id                  TEXT PRIMARY KEY,                 -- slug，如 'ai-agents'
    name                TEXT NOT NULL UNIQUE,
    description         TEXT,
    scope_statement     TEXT NOT NULL,                    -- 范围唯一来源（守卫判 scope 用）
    scope_keywords_json TEXT NOT NULL DEFAULT '[]',
    seed_queries_json   TEXT NOT NULL DEFAULT '[]',
    status              TEXT NOT NULL DEFAULT 'active',   -- active | paused | archived
    config_json         TEXT,
    schedule_cron       TEXT,                             -- NULL = 不调度（Phase 1 恒 NULL）
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE topic_sources (
    topic_id      TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    source        TEXT NOT NULL,                          -- 'openalex' | 'arxiv'
    selector_json TEXT NOT NULL,                          -- 结构见 §8.1
    PRIMARY KEY (topic_id, source)
);
```

### 3.3 论文实体（核心）

```sql
CREATE TABLE papers (
    paper_id          TEXT PRIMARY KEY,                   -- canonical_id（DOI→W→arXiv→标题指纹）
    source            TEXT NOT NULL,                      -- 'openalex' | 'arxiv'
    source_id         TEXT NOT NULL,                      -- 源侧 id（OpenAlex 'W...' / arXiv id）
    doi               TEXT,
    title             TEXT NOT NULL,
    title_norm        TEXT NOT NULL,                      -- 去重指纹（小写/去标点/折叠空白）
    abstract          TEXT,
    year              INTEGER,
    published_at      TEXT,
    venue_id          TEXT,                               -- OpenAlex source.id（白名单口径）
    venue_name        TEXT,
    is_oa             INTEGER NOT NULL DEFAULT 0,
    oa_pdf_url        TEXT,
    language          TEXT,                               -- 源侧 language，未知为 NULL
    parse_status      TEXT NOT NULL DEFAULT 'pending',    -- pending | ok | partial | failed | na
    n_chunks          INTEGER NOT NULL DEFAULT 0,
    cited_by_count    INTEGER,
    merged_ids_json   TEXT NOT NULL DEFAULT '[]',         -- 读优化（对应 Paper.merged_ids）
    source_updated_at TEXT,                               -- 源侧 updated_date（增量水位线依据）
    row_updated_at    TEXT NOT NULL,                      -- 本库写入时间
    created_at        TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_papers_doi ON papers(doi) WHERE doi IS NOT NULL;
CREATE UNIQUE INDEX ux_papers_source ON papers(source, source_id);
CREATE INDEX ix_papers_title_norm ON papers(title_norm);
CREATE INDEX ix_papers_venue_year ON papers(venue_id, year);
CREATE INDEX ix_papers_parse_status ON papers(parse_status);
```

**约束说明**
- `ux_papers_source` 保证同一源记录只有一个 canonical 行（ADR-0001 "不删除原始记录"由 `papers_raw` 承担）。
- `parse_status='na'` = 无需解析（非 OA 或无 PDF），与 `failed`（尝试过但失败）区分，便于算解析成功率。

```sql
CREATE TABLE papers_raw (
    raw_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    source     TEXT NOT NULL,
    source_id  TEXT NOT NULL,
    run_id     TEXT,                                      -- 首次抓取该版本的 run
    fetched_at TEXT NOT NULL,
    content_sha TEXT NOT NULL,                            -- 源记录 JSON 的 sha256
    raw_json   TEXT NOT NULL,                             -- 原样留存（ADR-0001 要求）
    UNIQUE (source, source_id, content_sha)
);
CREATE INDEX ix_papers_raw_lookup ON papers_raw(source, source_id, fetched_at DESC);
```

- 同一记录**多次抓取但内容未变** → 唯一约束命中，不再插入（避免每次全量刷出几十万重复行）。
- 内容变化（源侧修订）→ 新增一行，形成可审计的版本链；`papers` 只保留最新。

```sql
CREATE TABLE authors (
    author_id        TEXT PRIMARY KEY,                    -- OpenAlex author id
    name             TEXT NOT NULL,
    name_norm        TEXT NOT NULL,
    orcid            TEXT,
    works_count      INTEGER,
    last_institution TEXT,
    source           TEXT,
    source_updated_at TEXT,
    row_updated_at   TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_authors_orcid ON authors(orcid) WHERE orcid IS NOT NULL;
CREATE INDEX ix_authors_name_norm ON authors(name_norm);

CREATE TABLE paper_authors (
    paper_id         TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    author_id        TEXT NOT NULL REFERENCES authors(author_id) ON DELETE CASCADE,
    position         INTEGER NOT NULL,                    -- 0-based，保留作者顺序
    is_corresponding INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (paper_id, position)
);
CREATE INDEX ix_paper_authors_author ON paper_authors(author_id);
```

```sql
CREATE TABLE citations (
    citing_id     TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    cited_id      TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    source        TEXT NOT NULL DEFAULT 'openalex',
    first_seen_at TEXT NOT NULL,
    run_id        TEXT,
    PRIMARY KEY (citing_id, cited_id)
);
CREATE INDEX ix_citations_cited ON citations(cited_id);
```

- **只保留两端都在 `papers` 里的引用**（外键强制；Phase 0 已定的"仅语料内引用成边"口径）。
- 规模预估：2 万篇 × 平均 20 条 = **40 万行**，`cited_by` 查询走 `ix_citations_cited`。

```sql
CREATE TABLE paper_merges (
    primary_id TEXT NOT NULL,                             -- 主记录
    merged_id  TEXT NOT NULL,                             -- 被并入的记录
    run_id     TEXT,
    reason     TEXT,                                      -- exact_id | fingerprint | fuzzy
    created_at TEXT NOT NULL,
    PRIMARY KEY (primary_id, merged_id)
);
CREATE INDEX ix_paper_merges_merged ON paper_merges(merged_id);
```

```sql
CREATE TABLE paper_chunks (                               -- P3 启用；Phase 1 建表不写入
    paper_id    TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    chunk_idx   INTEGER NOT NULL,
    section     TEXT,
    text_sha    TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    page_from   INTEGER,
    page_to     INTEGER,
    char_start  INTEGER,
    char_end    INTEGER,
    PRIMARY KEY (paper_id, chunk_idx)
);
```

### 3.4 运行、事件与报告

```sql
CREATE TABLE runs (
    id                   TEXT PRIMARY KEY,                -- run_id（ULID/时间戳+随机）
    topic_id             TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    trigger              TEXT NOT NULL,                   -- manual | schedule | retry
    state                TEXT NOT NULL,                   -- pending|running|succeeded|failed|aborted
    stage                TEXT,                            -- 当前阶段
    last_ok_stage        TEXT,                            -- 最后成功阶段（失败报告用）
    error_code           TEXT,
    next_seq             INTEGER NOT NULL DEFAULT 0,      -- ★ 事件序号分配器（§5）
    dup_events           INTEGER NOT NULL DEFAULT 0,      -- 幂等命中计数（§6）
    config_snapshot_json TEXT NOT NULL,                   -- guide §2.1
    input_hash           TEXT NOT NULL,                   -- topic+config+since 的哈希（G15 输入漂移）
    app_version          TEXT,
    started_at           TEXT,
    finished_at          TEXT,
    created_at           TEXT NOT NULL
);
CREATE INDEX ix_runs_topic_created ON runs(topic_id, created_at DESC);
CREATE UNIQUE INDEX ux_runs_one_running ON runs(topic_id) WHERE state = 'running';
```

- **`ux_runs_one_running`**：DB 层保证"一个 topic 同时只有一个 running run"，
  这是 API `409 E_LOCK_HELD` 的**最后一道防线**（内存锁可能因进程重启失效）。
- `input_hash` 供 G15（输入漂移）判断"续跑/重跑时的输入是否变了"。

```sql
CREATE TABLE run_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    seq           INTEGER NOT NULL,
    ts            TEXT NOT NULL,
    type          TEXT NOT NULL,                          -- guide §2.2 白名单
    stage         TEXT,
    agent         TEXT,
    severity      TEXT NOT NULL,                          -- debug|info|warn|error
    dedupe_key    TEXT,                                   -- '<stage>:<step_key>'；非幂等事件为 NULL
    payload_json  TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    UNIQUE (run_id, seq)
);
CREATE UNIQUE INDEX ux_run_events_dedupe
    ON run_events(run_id, dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX ix_run_events_type_ts ON run_events(type, ts);
```

- **`UNIQUE(run_id, seq)` 同时充当排序索引**（无需再建 `(run_id, seq)` 普通索引）。
- 部分唯一索引让"非幂等事件"（`dedupe_key IS NULL`，如 `llm_call`、`message`）**不参与去重**。

```sql
-- 注：SQLite 允许**前向 FK 引用**（建表时不校验父表存在），claims 先于 reports 出现不影响
-- CREATE TABLE；但写入 reports.report_id 之前该行必须已存在，且 DROP 顺序必须反过来（§9）。
CREATE TABLE claims (
    claim_id  TEXT PRIMARY KEY,                           -- '<run_id>:<短hash>'
    run_id    TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    report_id TEXT REFERENCES reports(report_id) ON DELETE CASCADE,
    text      TEXT NOT NULL,
    text_sha  TEXT NOT NULL,                              -- sha256(规范化 text)
    support   TEXT NOT NULL,                              -- supported|partially|unsupported
    created_at TEXT NOT NULL,
    UNIQUE (run_id, text_sha)
);
CREATE INDEX ix_claims_run ON claims(run_id);
CREATE INDEX ix_claims_report ON claims(report_id);

CREATE TABLE claim_citations (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id  TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    paper_id  TEXT NOT NULL,
    chunk_idx INTEGER NOT NULL DEFAULT -1,                -- -1 = 摘要/整篇级（非 NULL，避免唯一索引失效）
    snippet   TEXT,
    score     REAL,
    UNIQUE (claim_id, paper_id, chunk_idx)
);
CREATE INDEX ix_claim_citations_claim ON claim_citations(claim_id);
CREATE INDEX ix_claim_citations_paper ON claim_citations(paper_id);
```

- **不可落地的 claim 也必须入库**并标 `support='unsupported'`（Phase 0 静默错误 #6：丢弃会伪造 grounding=100%）。
- `source`/`span` 等扩展信息放 `claim_citations.snippet`（片段）+ 事件 payload，不进契约。

```sql
CREATE TABLE reports (
    report_id      TEXT PRIMARY KEY,
    topic_id       TEXT NOT NULL REFERENCES topics(id),
    run_id         TEXT NOT NULL REFERENCES runs(id),
    period         TEXT,                                  -- '2026-W42' / NULL
    title          TEXT,
    content_md     TEXT NOT NULL,
    content_sha    TEXT NOT NULL,                         -- sha256(content_md)，幂等键（D4 校验）
    claims_json    TEXT,                                  -- 渲染快照（可复算校验用）
    metrics_snapshot_json TEXT,
    n_claims       INTEGER NOT NULL DEFAULT 0,
    degraded       INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    UNIQUE (run_id, content_sha)
);
CREATE INDEX ix_reports_topic_created ON reports(topic_id, created_at DESC);
```

- `UNIQUE(run_id, content_sha)`：**内容相同 → 不新增行**（幂等）；
  **内容不同 → 新增行**（这是"重跑漂移"的证据，需记 `metric{kind=report_drift}`，不许覆盖）。

### 3.5 网关、缓存与向量

```sql
CREATE TABLE llm_calls (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT NOT NULL,
    run_id         TEXT REFERENCES runs(id) ON DELETE SET NULL,
    agent          TEXT,
    provider       TEXT NOT NULL,                         -- 'deepseek'
    model          TEXT NOT NULL,
    route_reason   TEXT,                                  -- 敏感拦截/预算降级等决策理由
    request_sha    TEXT NOT NULL,                         -- 与 llm_cache 同键
    cache_hit      INTEGER NOT NULL DEFAULT 0,
    req_tokens     INTEGER,
    resp_tokens    INTEGER,
    cost           REAL,
    cost_estimated INTEGER NOT NULL DEFAULT 0,            -- usage 缺失时估算（禁止静默记 0）
    latency_ms     INTEGER,
    degraded       INTEGER NOT NULL DEFAULT 0,
    ok             INTEGER NOT NULL DEFAULT 1,
    error_code     TEXT
);
CREATE INDEX ix_llm_calls_run ON llm_calls(run_id);
CREATE INDEX ix_llm_calls_ts ON llm_calls(ts);

CREATE TABLE llm_cache (
    request_sha   TEXT PRIMARY KEY,                       -- sha256(model+messages+temperature+max_tokens+schema_ver)
    model         TEXT NOT NULL,
    response_json TEXT NOT NULL,
    usage_json    TEXT,
    created_at    TEXT NOT NULL,
    hit_count     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE embeddings (                                 -- ADR-0004：本地嵌入结果缓存
    text_sha   TEXT NOT NULL,
    model_id   TEXT NOT NULL,                             -- 'BAAI/bge-m3'
    model_rev  TEXT NOT NULL,                             -- 模型 commit 短哈希
    dim        INTEGER NOT NULL,
    vec        BLOB NOT NULL,                             -- float32 little-endian，L2 已归一化
    created_at TEXT NOT NULL,
    PRIMARY KEY (text_sha, model_id, model_rev)
);
```

- `llm_calls` **append-only**：真实发生的调用就是事实，重试产生多行是正确的（指标按 `run_id` 聚合）。
- `embeddings`：4 KB/行 × 2 万篇 ≈ **80 MB**，换模型时 `model_rev` 变化 → 旧行保留可对照，按需清理。

### 3.6 指标、同步、锁、会话、评测

```sql
CREATE TABLE metrics (
    scope      TEXT NOT NULL,                             -- run | topic | campaign | global
    scope_id   TEXT NOT NULL,
    metric     TEXT NOT NULL,                             -- grounding_rate / hallucination_rate / ...
    value      REAL NOT NULL,
    meta_json  TEXT,
    ts         TEXT NOT NULL,
    PRIMARY KEY (scope, scope_id, metric)                 -- ★ 可复算（D7）
);

CREATE TABLE sync_state (
    source          TEXT NOT NULL,
    selector        TEXT NOT NULL,                        -- 规范化 selector 键（§8.1 的 hash）
    last_cursor     TEXT,                                 -- OpenAlex deep-paging cursor
    last_since      TEXT,                                 -- 增量水位线（publication_date）
    last_success_at TEXT,
    status          TEXT NOT NULL,                        -- idle|running|error
    error_code      TEXT,
    PRIMARY KEY (source, selector)
);

CREATE TABLE job_locks (
    topic_id     TEXT PRIMARY KEY REFERENCES topics(id) ON DELETE CASCADE,
    owner        TEXT NOT NULL,                           -- '<host>:<pid>:<run_id>'
    acquired_at  TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    expires_at   TEXT NOT NULL                            -- 过期即视为孤儿锁（§7.4）
);

CREATE TABLE chat_sessions (
    id         TEXT PRIMARY KEY,
    topic_id   TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);

CREATE TABLE chat_messages (
    id             TEXT PRIMARY KEY,
    session_id     TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role           TEXT NOT NULL,                         -- user|assistant
    content        TEXT NOT NULL,
    citations_json TEXT,
    run_id_ref     TEXT,
    ts             TEXT NOT NULL
);
CREATE INDEX ix_chat_messages_session ON chat_messages(session_id, ts);

CREATE TABLE eval_judgments (
    id          TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,                            -- claim|report|run
    target_id   TEXT NOT NULL,
    metric      TEXT NOT NULL,
    score       REAL NOT NULL,
    judge_model TEXT,
    human       INTEGER NOT NULL DEFAULT 0,
    detail_json TEXT,
    ts          TEXT NOT NULL
);
CREATE INDEX ix_eval_target ON eval_judgments(target_type, target_id, metric);
```

---

## 4. `store_meta` 取代"空库哨兵"的实现细节

ADR-0003 §3 要求"导入前空库哨兵"。落地方式统一为：**`store_meta` 里有 `store_name` 行即视为"已初始化"**。

| 场景 | 判定 | 错误码 |
|---|---|---|
| 库文件不存在 | 正常（首次） | — |
| 文件存在但无 `store_meta` 表 | 视为旧库/异常库 | `E_STORE_SCHEMA_MISMATCH` |
| `store_meta.schema_version != '1.0'` | schema 漂移 | `E_STORE_SCHEMA_MISMATCH`（附差异） |
| `store_meta.model_rev != 当前模型` | 向量来源变更 | `E_VECTOR_MODEL_MISMATCH` |
| `dim != 1024` | 维度不符契约 | `E_VECTOR_DIM_MISMATCH` |
| 目标库已有数据但本次声称"首次导入" | 脏库 | `E_STORE_NOT_EMPTY` |

---

## 5. 事件序号分配（D3）

### 5.1 算法（唯一允许的实现）

```sql
BEGIN IMMEDIATE;                                          -- ① 先拿写锁，避免读升级死锁
UPDATE runs SET next_seq = next_seq + 1
 WHERE id = :run_id RETURNING next_seq;                   -- ② 返回分配到的 seq
INSERT INTO run_events (run_id, seq, ts, type, stage, agent, severity,
                        dedupe_key, payload_json, schema_version)
VALUES (:run_id, :seq, :ts, ...);
COMMIT;                                                   -- ③ 与业务写入同事务（可合并）
```

**规则**
1. `BEGIN IMMEDIATE` 而非默认的 `BEGIN`：SQLite 默认延迟事务在"先读后写"时会尝试升级锁，
   并发下可能直接 `SQLITE_BUSY`；`IMMEDIATE` 一开始就持写锁。
2. 事务内**先**取 seq、**后**插入事件；`UPDATE` 的行锁保证并发 run 之间不抢同一 seq
   （同一 run 由 `job_locks` + 单写者保证串行）。
3. `seq` **从 1 开始**、按 run 内单调递增、**不允许重置**（同 run 重跑必须续号，否则 D5 回放破坏）。
4. 业务写入（如 `papers.upsert`）与事件插入**可同事务**：宁可"事实与事件一起提交或一起回滚"，
   也不要"事实提交了但事件丢了"（Phase 0 静默错误 #5 的反面）。
5. **禁止** `MAX(seq)+1`、`SELECT next_seq` 再 `UPDATE`（两步之间有竞态）、以及 Python 侧计数器。

### 5.2 SQLite 版本要求

`UPDATE ... RETURNING` 需 SQLite ≥ 3.35。`doctor` 必须检查：

```python
assert sqlite3.sqlite_version_info >= (3, 35, 0), "需要 SQLite>=3.35（RETURNING）"
```

若不满足（极旧环境）→ 允许的**唯一**退路：`BEGIN IMMEDIATE` + `UPDATE ... ; SELECT next_seq`（同事务内两步），
并在 `RESULTS-P1.md` 记录；**不得**退化为 `MAX(seq)+1`。

### 5.3 崩溃与重试语义

| 情形 | 结果 |
|---|---|
| 事务未提交即崩溃 | seq 未消耗（`runs.next_seq` 回滚），**不产生空号** |
| 事件已提交、后续阶段崩溃 | seq 已消耗，事件已存在；重试时**同一 `dedupe_key` 会被忽略**（§6），不会重号 |
| 进程被 kill -9 在提交瞬间 | SQLite WAL 保证原子：要么整事务可见，要么完全不可见 |
| `UNIQUE(run_id, seq)` 冲突 | 理论不可达；若发生 → `E_DATA_SEQ_CONFLICT`，整事务重试 1 次后失败并留痕 |

---

## 6. 幂等键（D4）

### 6.1 两类键，职责分离

| 键 | 约束 | 语义 |
|---|---|---|
| `(run_id, seq)` | `UNIQUE` | **顺序不变量**：一个 run 内事件序号唯一且连续 |
| `(run_id, dedupe_key)` | 部分唯一索引（`dedupe_key IS NOT NULL`） | **操作幂等**：同一逻辑操作只落一次 |

`dedupe_key = f"{stage}:{step_key}"`，其中 `step_key` 由调用方给出、必须**对同一逻辑操作稳定**，例如：

| 事件 | `step_key` 示例 |
|---|---|
| 源分页抓取 | `openalex:page:3` |
| 单篇解析 | `parse:<paper_id>` |
| 单批投影 | `project:kuzu:batch:7` |
| LLM 调用 | `llm:<request_sha 前 12 位>` |
| 报告写入 | `report:<content_sha 前 12 位>` |
| 阶段进出 | `None`（阶段本身只发生一次，但仍可给 `phase:<stage>:start`） |

### 6.2 冲突处理（必须照此实现）

```python
# 伪代码：emit_event
try:
    with tx():  # BEGIN IMMEDIATE
        seq = allocate_seq(run_id)  # §5.1
        insert_event(run_id, seq, ..., dedupe_key)
except DuplicateDedupeKey:
    # 不回滚业务、不中断 run
    increment_dup_events(run_id)  # runs.dup_events += 1
    log.warn("event_dedup_hit", run_id=..., dedupe_key=...)
    emit_error_event(code="E_DATA_DUP", dedupe_key=None)  # ★ dedupe_key 必须为 NULL，否则自我冲突
```

- **`E_DATA_DUP` 自身的 `dedupe_key` 必须为 `NULL`**：否则同一重复操作第二次命中时会试图写一条
  与已存在 `E_DATA_DUP` 相同 `dedupe_key` 的事件，形成"去重事件被去重"的死循环。
- 去重命中**不是错误级失败**：不改变 run 状态，只计数 + 告警日志（它是"重放安全"的正常现象）。
- `dup_events` 是对外可见的诊断指标（写进 `metric{kind=event_dedupe_hits}`），用于验证 D4。

---

## 7. 幂等键总表（D5，仓储层实现依据）

### 7.1 资源 → 键 → 冲突动作

| 资源 | 幂等键 | 冲突动作 | 冲突时**不得**做的事 |
|---|---|---|---|
| `run_events` | `(run_id, seq)` | 抛 `E_DATA_SEQ_CONFLICT` 并重试事务 | 静默改号 |
| `run_events` | `(run_id, dedupe_key)`（非 NULL） | **忽略** + `dup_events+1` + `E_DATA_DUP` | 覆盖已有事件内容 |
| `papers` | `paper_id` | **upsert 源字段**（见 §7.2） | 覆盖本地派生字段 |
| `papers` | `(source, source_id)` 唯一 | 同上（同一源记录只能对应一个 canonical） | 产生两个 canonical |
| `papers_raw` | `(source, source_id, content_sha)` | **忽略** | 重复存同一 JSON |
| `authors` | `author_id` | upsert 源字段 | 覆盖 `name_norm` 的人工修正 |
| `paper_authors` | `(paper_id, position)` | upsert | 打乱作者顺序 |
| `citations` | `(citing_id, cited_id)` | **忽略**（保留最早 `first_seen_at`） | 重复计数/改方向 |
| `paper_merges` | `(primary_id, merged_id)` | **忽略** | 反向重建关系 |
| `paper_chunks` | `(paper_id, chunk_idx)` | upsert（`text_sha` 变化则重算并清理多余 idx） | 留下孤儿 chunk |
| `claims` | `(run_id, text_sha)` | **忽略** | 合并两条不同 claim |
| `claim_citations` | `(claim_id, paper_id, chunk_idx)` | upsert `score`/`snippet` | 丢引用 |
| `reports` | `(run_id, content_sha)` | **忽略**；若同 run 出现不同 sha → 新增行 + `metric{kind=report_drift}` | 覆盖旧报告 |
| `llm_cache` | `request_sha` | **忽略** + `hit_count+1` | 覆盖缓存响应 |
| `llm_calls` | 无（append-only） | 追加 | 去重（调用事实不可合并） |
| `embeddings` | `(text_sha, model_id, model_rev)` | **忽略** | 混用不同模型向量 |
| `metrics` | `(scope, scope_id, metric)` | **`INSERT OR REPLACE`**（可复算） | 追加重复行 |
| `sync_state` | `(source, selector)` | upsert | 回退水位线 |
| `job_locks` | `topic_id` | **不 upsert**：必须走 `acquire()`（成功/失败显式） | 静默覆盖他人锁 |

### 7.2 `papers` 的两组字段（upsert 边界）

| 组 | 字段 | 谁能写 |
|---|---|---|
| **源字段**（每次抓取可更新） | `title,title_norm,abstract,year,published_at,venue_id,venue_name,is_oa,oa_pdf_url,language,cited_by_count,doi,source_updated_at,row_updated_at` | 源适配器（1.6） |
| **本地派生字段**（源不可覆写） | `parse_status,n_chunks,merged_ids_json,paper_id` | 解析（1.7）、去重（1.8）、投影（1.8） |

> 违反此边界的典型事故：重抓一次源数据，把 `parse_status` 重置为 `pending`、把 `merged_ids` 清空。

### 7.3 `metrics` 可复算（D7）

- 只存 `scope='run'` 的行（`scope_id=run_id`）；`topic/campaign/global` 由查询时聚合（避免"全历史聚合"假象，Phase 0 #9）。
- 同一 run 重算指标 → `INSERT OR REPLACE` 覆盖同 `(scope, scope_id, metric)`，行数不增长。
- 每次指标写入必须能追溯到事件（ADR-0002）；重算脚本本身是 `eval/metrics.py`（1.18）。
- **明确取代** guide §2.1 的"`reports`/`metrics` 提交后不可改（修订走新行）"中关于 **`metrics`** 的部分：
  指标是**派生量**，允许重算覆盖；其"修订历史"由事件流承担（ADR-0002），不靠多行快照。
  **`reports` 仍严格不可改**（内容不同即新增行 + `report_drift`，见 §7.1）。

### 7.4 锁的获取与孤儿判定

| 步骤 | 规则 |
|---|---|
| acquire | `INSERT INTO job_locks(...)`；`topic_id` 主键冲突 → `E_LOCK_HELD`（若已过期则先 `DELETE` 再重试一次） |
| heartbeat | 每分钟 `UPDATE heartbeat_at, expires_at`（`expires_at = now + 3×heartbeat`） |
| release | run 结束（含失败）在 `finally` 中 `DELETE` |
| orphan | 启动时 `DELETE FROM job_locks WHERE expires_at < now`；并把对应 `runs.state='running'` 且 `id NOT IN (locks.owner 的 run)` 的 run 标 `aborted(orphan)` |

---

## 8. 主题与抓取范围（D8）

### 8.1 `topic_sources.selector_json` 结构（冻结）

```jsonc
// openalex
{ "venue_ids": ["W2032197343", "W..."], "concepts": [], "from_year": 2023, "type": "article" }
// arxiv
{ "categories": ["cs.AI", "cs.LG", "cs.CL"], "from_year": 2023 }
```

- **白名单一律用 OpenAlex `source.id`（W 号）**，不接受期刊/会议名称（Phase 0 结论：名称匹配会漏 10%+）。
- `selector` 的规范化字符串（键排序 + 去空白）的 sha256 前 16 位 = `sync_state.selector`，保证"同一范围共用一个游标"。
- 论文与 topic 的**多归属**不进 SQLite（`topic_sources` 只定义"抓什么"）：多归属由图库 `BELONGS_TO` 表达
  （guide §2.5），供 P4 的跨域关系图使用。

### 8.2 初期四域白名单候选（Step 1.6 解析为 `source.id`）

> 依据导师方向：**AI / 计算机 / 电子硬件 / 通信**。下表是**候选名单**，Step 1.6 必须用 OpenAlex 检索接口
> 把名称解析成 `source.id` 并固化到 `config/seeds/topics.yaml`，**不得**在代码里硬编码名称匹配。

| 域 | 候选 venue（名称，待解析） |
|---|---|
| **AI / 机器学习** | NeurIPS, ICML, ICLR, AAAI, IJCAI, ACL, EMNLP, NAACL, CVPR, ICCV, ECCV, TPAMI, JMLR, TACL |
| **计算机系统 / 软件** | SOSP, OSDI, ASPLOS, ISCA, MICRO, ICSE, FSE, ASE, TOCS, TOSEM, TPDS |
| **电子硬件 / 电路** | IEEE JSSC, IEEE TED, IEEE TCAS-I, IEEE TCAS-II, IEEE TPEL, DAC, ISSCC, IEEE EDL |
| **通信 / 网络** | IEEE TCOM, IEEE JSAC, IEEE TWC, IEEE TVT, IEEE TSP, INFOCOM, MobiCom, SIGCOMM, NSDI |

**交叉归属**：如 "edge AI / AI accelerator" 同时属 AI 与硬件 → 由 `paper_authors`/venue 决定其在各域的出现，
图库 `BELONGS_TO` 可多边；SQLite 侧不做多归属列（避免三处真相）。

### 8.3 种子 topic（`config/seeds/topics.yaml`，四域按导师方向）

```yaml
# 四域均写入 topics；`venue_names` 是**待解析**的种子字段，Step 1.6 解析成 venue_ids 后从 selector 中移除，
# 只保留 {venue_ids, from_year, type}（§8.1）。解析结果必须落在 config/seeds/topics.yaml 并提交。
topics:
  - id: ai-agents
    name: AI Agents & LLM Systems
    scope_statement: "LLM-based agents：规划、工具使用、多智能体协作、自纠错与评测可靠性"
    scope_keywords: [llm agent, tool use, multi-agent, planning, self-correction, agent evaluation]
    seed_queries: ["llm agent survey", "multi-agent collaboration", "agent self-correction"]
    venue_names: [NeurIPS, ICML, ICLR, ACL, EMNLP, AAAI, IJCAI, TPAMI, JMLR]
    sources:
      - {source: arxiv, categories: [cs.AI, cs.CL, cs.LG]}
      - {source: openalex, venue_ids: [], from_year: 2023, type: article}

  - id: computer-systems
    name: Computer Systems & Software
    scope_statement: "系统软件、体系结构、编译优化与软件工程方法"
    scope_keywords: [operating system, architecture, compiler, software engineering, distributed system]
    seed_queries: ["systems for machine learning", "compiler optimization", "software engineering agent"]
    venue_names: [SOSP, OSDI, ASPLOS, ISCA, MICRO, ICSE, FSE, ASE, TOCS, TOSEM, TPDS]
    sources:
      - {source: arxiv, categories: [cs.DC, cs.AR, cs.SE, cs.PL]}
      - {source: openalex, venue_ids: [], from_year: 2023, type: article}

  - id: electronic-hardware
    name: Electronic Hardware & Circuits
    scope_statement: "集成电路设计、半导体器件、EDA 与低功耗/边缘硬件"
    scope_keywords: [integrated circuit, semiconductor device, EDA, low power, accelerator, edge hardware]
    seed_queries: ["AI accelerator design", "low power circuit", "EDA flow optimization"]
    venue_names: [IEEE JSSC, IEEE TED, IEEE TCAS-I, IEEE TCAS-II, IEEE TPEL, IEEE EDL, DAC, ISSCC, DATE]
    sources:
      - {source: arxiv, categories: [eess.SP, eess.SY, cs.AR]}
      - {source: openalex, venue_ids: [], from_year: 2023, type: article}

  - id: communications
    name: Communications & Networking
    scope_statement: "无线/光通信、网络协议、信息论与网络智能化"
    scope_keywords: [wireless communication, network protocol, information theory, MIMO, network optimization]
    seed_queries: ["network optimization learning", "wireless resource allocation", "information theory bound"]
    venue_names: [IEEE TCOM, IEEE JSAC, IEEE TWC, IEEE TVT, IEEE TSP, INFOCOM, MobiCom, SIGCOMM, NSDI]
    sources:
      - {source: arxiv, categories: [eess.SP, cs.NI, cs.IT]}
      - {source: openalex, venue_ids: [], from_year: 2023, type: article}
```

- `venue_ids: []` 的含义是"尚未解析"：Step 1.6 的解析器必须把它填满，否则 `sources sync` 对 openalex 源
  报 `E_SRC_NO_SELECTOR`（**禁止**空 selector 退化为全量抓取）。
- 四个 topic 共享同一批论文时（如 `cs.AR` 同时属系统与硬件），SQLite 各自存 `topic_sources` 抓取范围，
  论文实体只有一份（`papers` 主键），多归属由图库 `BELONGS_TO` 承担（§8.1 末段）。

---

## 9. Migration（迁移步骤）

1. **本 ADR 不迁移 Phase 0 数据**：`../prototype/out/*.db` 视为实验产物，保留只读作对照。
2. `migrations/versions/0001_initial.py` 按 §3 顺序建 **24 张表**（12 张修订 + 12 张新增）+ 索引，
   实际 DDL 执行顺序：`store_meta → topics → topic_sources → papers → papers_raw → authors → paper_authors →
   citations → paper_merges → paper_chunks → runs → run_events → reports → claims → claim_citations →
   llm_cache → llm_calls → metrics → sync_state → job_locks → chat_sessions → chat_messages → eval_judgments →
   embeddings`（`reports` 先于 `claims`，便于外键与回滚）；
   `downgrade()` 按**逆序** `DROP`（先 `claim_citations` 再 `claims` 再 `reports`，避免外键顺序错误）。
3. 建表后写入库身份：
   ```sql
   INSERT INTO store_meta(store_name, schema_version, app_version, built_at)
   VALUES ('sqlite', '1.0', :app_version, :now);
   ```
4. 对存量实验库（若确需）→ **不写自动迁移**，只提供 `scripts/import_phase0_fixture.py`（一次性、显式、可删），
   把 Phase 0 的真实抓取结果导入为 fixture 语料（供测试与 demo 语料用）。
5. `lit-agent db reset --yes`：删 `data/app.db` 后 `upgrade head`，并重建三个 `store_meta` 行。

---

## 10. Impact（受影响模块）

| 模块 | 影响 |
|---|---|
| `models/` | `Paper` +`source_id,venue_id,is_oa,language,parse_status,cited_by_count,merged_ids`；`Report` +`content_sha,n_claims,degraded`；`Run` +`next_seq,dup_events,input_hash,stage,last_ok_stage`；`Event` +`dedupe_key`；`Claim` +`claim_id,text_sha,report_id` |
| `db/repo/*` | 11 个仓储按 §7.1 实现冲突动作；`events.py` 实现 §5/§6 |
| `runtime/events.py` | `emit_event()` 按 §6.2；`dedupe_key` 由调用方传入 |
| `sources/` | `papers_raw` 写入、`papers` 源字段 upsert（§7.2 边界） |
| `parsing/` | 只写 `parse_status/n_chunks`（派生字段） |
| `stores/` | 向量库身份读写 `store_meta`（ADR-0004） |
| `eval/metrics.py` | `metrics` 可复算（§7.3）；`dup_events`、`report_drift` 纳入指标 |
| `api/` | `409 E_LOCK_HELD` 依赖 `ux_runs_one_running` |
| `tests/` | 新增 §11 的全部用例 |
| `doctor` | SQLite ≥3.35 检查、`store_meta` 三行检查、表清单比对 |

---

## 11. Verification（验收命令与判据）

```powershell
uv run lit-agent db upgrade                      # 期望：0001_initial applied，24 张表
uv run pytest -q tests/integration/test_migrations.py     -m "not slow"   # 升→降→升 schema 快照一致
uv run pytest -q tests/integration/test_repo_sqlite.py    -m "not slow"   # 幂等与 schema 守卫
uv run pytest -q tests/integration/test_events_replay.py  -m "not slow"   # seq 连续与回放
uv run pytest -q tests/integration/test_event_seq_concurrency.py          # 并发 seq 不重号
uv run pytest -q tests/integration/test_idempotency.py    -m "not slow"   # 同 fixture 重跑零增长
```

| # | 判据 | 方法 |
|---|---|---|
| V1 | 24 张表齐全（12 修订 + 12 新增），索引数符合 §3 | `PRAGMA table_info`/`index_list` 快照与期望清单比对（清单 = §3.0） |
| V2 | `journal_mode=wal`、`foreign_keys=1`、`busy_timeout=5000` | `PRAGMA` 断言 |
| V3 | **seq 并发安全**：两个线程各写 100 条事件 | 断言总行数 200、`seq` 集合 `{1..200}`、无重号 |
| V4 | **回滚不消耗 seq** | 事务内取 seq 后抛异常 → `runs.next_seq` 不变、事件行不存在 |
| V5 | **幂等命中**：同 `dedupe_key` 写两次 | 行数不变、`dup_events=1`、产生 1 条 `E_DATA_DUP`（其 `dedupe_key IS NULL`） |
| V6 | **部分唯一索引生效**：两条 `dedupe_key IS NULL` 的事件 | 均写入成功（不误判重复） |
| V7 | **一 topic 一 running**：并发 `INSERT` 两个 running run | 第二个抛唯一约束 → 映射为 `409 E_LOCK_HELD` |
| V8 | **FK 级联**：删 topic | `runs/run_events/job_locks` 同步消失；`reports` 因无 CASCADE 报错（见下） |
| V9 | **`papers` upsert 边界**：先写派生字段，再用源数据 upsert | `parse_status/merged_ids` 不被重置 |
| V10 | **报告幂等**：同 run 同内容写两次 → 1 行；改一个字符 → 2 行 + `report_drift` 事件 |
| V11 | **索引有效**：`EXPLAIN QUERY PLAN` 查 `cited_by` | 走 `ix_citations_cited`（输出不含 `SCAN citations`） |
| V12 | **迁移可降**：`downgrade base` 后表数 0（除 `alembic_version`） | 表清单断言 |

> **V8 的取舍**：`reports.topic_id` 故意**不加 `ON DELETE CASCADE`** —— 报告是研究产出，删 topic 不应静默删报告；
> 删 topic 前必须显式归档（`topics.status='archived'`）。此规则写入 `db/repo/topics.py` 的 `delete()` 注释。

---

## 12. Risks & Open questions

| 风险 | 现状 | 缓解 |
|---|---|---|
| `papers_raw` 体积（2 万 × ~8 KB ≈ 160 MB） | 接受了"原样留存"的可审计性 | 后续可加 `raw_gz BLOB`（需新 ADR）；保留策略：仅同 `(source,source_id)` 的最新 3 个版本 |
| `citations` 40 万行 + 双外键 | SQLite 可承受 | 批量 `executemany` 单事务；`PRAGMA journal_mode=WAL` |
| `embeddings` BLOB 80 MB | 可接受 | 换模型时批量清理旧 `model_rev` |
| `metrics` 只存 run 级 | 聚合在查询期 | 若 P5 需要 campaign 快照 → 新 ADR 加 `campaign` 表 |
| `title_norm` 指纹算法 | 暂定"小写→去标点→折叠空白→去 leading article" | 算法变更会使历史指纹不一致 → 需要重算脚本（1.8 实现时定版并写 docstring） |
| `claims` 与 `reports` 的写入顺序 | 先 claim 后 report（FK 允许 NULL `report_id`） | 报告写入后回填 `claims.report_id`（同事务） |

**明确不做**（避免本 ADR 被后续阶段"顺手"扩张）：
论文软删除/版本修订、跨库一致性协议、作者消歧（`name_norm` 之外）、引用语义（`is_influential`）、
`chats`/`eval` 表的实际写入（P3/P5 才启用，本 ADR 只建表）。
