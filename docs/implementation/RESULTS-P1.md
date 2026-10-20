# Phase 1 结论台账（RESULTS-P1）

> **定位**：Phase 1 的**唯一数字来源**（沿用 Phase 0 `../prototype/RESULTS.md` 的定位）。
> 其他文档引用数字必须注明本文件小节，禁止二次抄写。
> **当前覆盖**：Step 1.1–1.4（2026-10-19）。后续步骤按 §2 追加。

---

## 0. 一页摘要

| 项 | 实测 |
|---|---|
| 交付步骤 | **Step 1.1–1.18 + 1.16 前端三页骨架 + 1.19 收口文档** |
| 结构完整性 | `scripts/check_structure.py` → **129/129 present, missing=0**（17 个包） |
| 自检 | `lit-agent doctor` → **6/6 OK**（structure / deps / config / paths / stores / version） |
| 测试 | **222 passed**（unit + contract + integration，无网络、无真实 LLM；向量用 HashingEmbedder） |
| 前端 | `web/` 可构建：`npm run build` → `dist/`（JS 72 kB / gzip 28 kB） |
| 代码质量 | `ruff check .` → All checks passed；`ruff format --check .` → 157 files already formatted |
| 数据库 | 迁移建出 **24 张表**，`schema_version=1.0`，WAL + `foreign_keys=ON` 生效 |
| 事件 | seq 连续（`1..N`）、幂等命中**不跳号**、事务内取号回滚不消耗序号、40×2 线程并发各自连续 |
| 迁移 | `upgrade → downgrade base → upgrade` 三轮一致；`db reset` 可重建 |
| 存储位置 | 全部运行数据在 **D:\lit-agent-store**（C: 盘曾 0 可用，见 §1.1） |
| 已知未做 | 骨架模块 12 个包为 D-SKEL（调用即 `E_FEATURE_DISABLED`），Kuzu/Qdrant 尚未落盘 |

---

## 1. 环境事实（本机）

### 1.1 磁盘：C: 曾满，全部易变存储迁到 D:

| 事实 | 证据 |
|---|---|
| 首次 `uv sync` 失败：`os error 112 磁盘空间不足`（下载 `langsmith` 时），C: 可用 **0 GB** | sync 日志 |
| C: 上最大占用是 `%TEMP%` = **12.21 GB**（其中 `cheatsheet-pdf` 10.4 GB 属**另一个项目**，未动） | 目录实测 |
| 已迁移：`uv cache` 0.46 GB → `D:\lit-agent-store\uv-cache`（robocopy /MOVE） | `uv cache dir` 返回 D: |
| 已清理：7 天以上临时项 2,612 个（1.61 GB）+ 明确可弃项 42 个（325 MB） | 清理脚本输出 |
| 已持久化（用户级环境变量）：`UV_CACHE_DIR` / `PIP_CACHE_DIR` / `HF_HOME` / `TORCH_HOME` / `TEMP` / `TMP` / `npm_config_cache` | `[Environment]::GetEnvironmentVariable(...,'User')` |
| 结果 | C: **5.86 → 8.27 GB** 可用；`D:\lit-agent-store` 现占 **0.50 GB**（uv-cache 0.46 + data 0.32 MB + 其余） |

> 未迁移：`%APPDATA%\uv\python`（管理解释器 69 MB）与 `.venv`（1.1 GB，在仓库盘）。
> 原因：`.venv/pyvenv.cfg` 指向该解释器，移动会破坏 venv；69 MB 不值得冒重建风险。
> **若后续需要**：`UV_PYTHON_INSTALL_DIR=D:\lit-agent-store\python` + `uv sync` 重建（约 25 MB 下载）。

### 1.2 路径：仓库路径含非 ASCII，因此**不做 editable 安装**

- 仓库位于 `E:\大学\NUS\EE5003\agent`；editable 安装会写一个含该路径的 `*.pth`，
  CPython 的 `site.py` 用 locale 编码（zh-CN Windows = GBK）读取 → `UnicodeDecodeError`，**整个 venv 起不来**。
- 因此：`pyproject.toml` 设 `[tool.uv] package = false`；
  - pytest 用 `pythonpath = ["src"]`；
  - CLI 用 `scripts/lit-agent.ps1`（内部 `python -m lit_agent`）；
  - 任何直接命令先 `. .\scripts\env.ps1`（设置 `PYTHONPATH=src`）。
- 数据路径仍必须纯 ASCII（ADR-0003）：本机 `storage.data_root = D:/lit-agent-store/data`。

### 1.3 运行时版本

| 项 | 值 |
|---|---|
| Python | **3.11.17**（uv 管理，`.python-version=3.11`；系统 3.14.5 未使用） |
| SQLite | **3.53.1**（≥3.35，`UPDATE … RETURNING` 可用） |
| 依赖 | `uv.lock` 解析 **181 个包**；含 `torch 2.14.1` / `transformers 5.17.0` / `sentence-transformers` / `kuzu` / `qdrant-client` / `litellm` / `langgraph 1.2.16` |
| 安装体积 | `.venv` ≈ **1.1 GB**（torch 是最大单项） |

---

## 2. 各步骤实测

### Step 1.1 工程基座（2.5 d 计划）

- **交付**：`src/lit_agent/` 全目录（17 包 / 127 文件）、`cli.py`（9 组子命令）、`doctor.py`（6 类检查 + 三态清单）、`config.py`、`logging.py`（自 Phase 0 迁移）、`errors.py`（60+ 错误码）、`structure.py`（结构清单可执行版）、`scripts/{env,lit-agent}.ps1`、`scripts/check_structure.py`。
- **实测**：`doctor` 6/6；`check_structure` 127/127；未实现子命令返回退出码 **60** + `E_FEATURE_DISABLED`。
- **偏差**：`logging.py` 未逐字迁移——加了 `RotatingFileHandler`（guide §1.4 要求轮转）与 `is_configured()`/`cleanup_debug_dirs()`。

### Step 1.2 契约模型（1.5 d 计划）

- **交付**：12 个模型文件，导出 **33 个名字**（模型 + 枚举 + `RunId` 别名）。
- **guide §2.3 全覆盖**：`Author/Paper/SourceRecord/ParsedDoc/Chunk/EvidenceCard/Claim/Verdict（=GuardVerdict）/RetrievalResult/MappingResult/AnalysisResult/ReportDraft/EvalRecord` 全部存在（`tests/contract/test_models_vs_guide.py` 解析 guide 原文比对）。
- **实测**：契约用例 20 个；`RunContext.resources` 不参与序列化（可进 checkpoint）。
- **偏差**：`Claim` 的证据约束放宽为"仅 supported/contradicted 必须带 citation"——见 §3.1。

### Step 1.3 数据库（2.0 d 计划）

- **交付**：`db/tables.py`（24 表 + 全部索引，含 3 个部分唯一索引）、`db/session.py`（引擎/事务/迁移/schema 守卫）、11 个仓储模块、Alembic `0001_initial`、`lit-agent db upgrade|reset|status`。
- **实测**：
  - 24 表，`schema_version=1.0`，`journal_mode=wal`，`foreign_keys=1`；
  - `upgrade → downgrade base → upgrade` 三轮：降级后表数 **0**，再升回 **24**；
  - `db reset --yes` 重建后 `topics` 计数 0（旧数据确实清掉）；
  - 仓储幂等：`upsert` 两次 → 1 行；`papers_raw` 同 sha 忽略、异 sha 记新版本；
  - **字段边界**：重新抓取后 `parse_status/n_chunks/merged_ids` 未被覆盖（ADR-0005 §7.2）；
  - 引用只收语料内的边（语料外 id → 0 行）；
  - `ux_runs_one_running` 生效（第二个 running run → IntegrityError）；
  - `metrics` 可复算（同 `(scope,scope_id,metric)` 两写 → 1 行，值取最新）。
- **偏差**：初始迁移用 `metadata.create_all()` 而非手写 `op.create_table`（见 §3.2）。

### Step 1.4 事件总线（1.5 d 计划）

- **交付**：`runtime/events.py`（唯一入口 `SqliteEventLog.emit`）、`db/repo/events.py`（读写/去重查询/回放）、JSONL 导出、`dump_jsonl`。
- **实测**：
  - seq 连续 `1,2,3…`；`after_seq` 分页无重无漏；
  - **幂等命中不跳号**：重复 `dedupe_key` → 原事件不重复写、`runs.dup_events=1`、额外一条 `E_DATA_DUP`（其 `dedupe_key IS NULL`），seq 仍连续；
  - 非幂等事件（`dedupe_key=None`）可重复；
  - **先落库后广播**：广播回调里用**另一个连接**能读到该行；
  - 调用方事务内 `conn=` 写入时**不广播**；
  - 并发：两个 run 各 60 条事件、两线程两引擎 → 各自 `1..60` 连续（`test_seq_concurrency.py`）；
  - 回滚不消耗序号（`next_seq` 保持 0）。
- **结论**：D5（事件可回放）的机制已就绪；下游 `api/sse.py` 只需读库补发。

### 测试构成（122 例）

| 目录 | 内容 | 数量级 |
|---|---|---|
| `tests/unit` | config 15 / errors 7 / contracts 20 / surface 6 | ≈48 |
| `tests/contract` | 模型↔guide、表↔ADR、索引与幂等列 | ≈11 |
| `tests/integration` | 迁移 7 / 仓储 15 / 事件 12 / 并发 3 / schema 守卫 5 | ≈42 |

> 注：Phase 0 的 112 例中，`config/models/logging` 三类已被重写覆盖（配置结构与模型字段都变了），
> 其余（normalize/chunking/dedup/llm/stores/guards/scoring/metrics）随各自实现步骤迁移（1.6–1.18），
> **不删断言**。

---

## 3. 与方案的偏差（需在 1.19 回写对应文档）

### 3.1 `Claim` 的证据约束放宽 ⚠️

- **原**（Phase 0）：`support != unverified` 就必须带 citation。
- **现**：仅 `supported`/`contradicted` 必须带；`unsupported`/`unverified` 允许无引用。
- **原因**：Phase 0 静默错误 #6——"无法落地的 claim 被丢弃 → grounding 恒 100%"。
  若模型层禁止 `unsupported` 空引用，则"无法落地"这一事实根本无法入库。
- **影响**：`design/agent-design-decisions.md` 若引用了旧规则需同步；1.12 的 reporter 用例已按新规则写。

### 3.2 初始迁移用 `metadata.create_all()`

- **原因**：`db/tables.py` 是 DDL 唯一来源，再手写 24 张 `op.create_table` 等于维护两份 DDL，必然漂移（正是 Phase 0 #1）。
- **代价**：后续**增量**迁移仍必须手写/autogenerate；`create_all` 只用于 `0001_initial`。
- **验证**：`downgrade base` 后表数 0，`upgrade` 后 24，三轮一致。

### 3.3 `GuardVerdict` 命名与字段

- 按 `design/state-machine-and-guards.md`：`GuardVerdict{ok,severity,action,code,reasons[]}`，
  `severity=info/warn/block`，`action=continue/retry/degrade/replan/abort/annotate`。
- `Verdict` 保留为别名（Phase 0 名称）；`models.Severity`（日志级别）与 `GuardSeverity` 是两套词表，不混用。
- 已修正两处文档笔误（guide §2.3 增量注释、phase1 §3.2/Step 1.2 的 `guard_id`/`allow`）。

### 3.4 依赖安装与 C: 盘

- guide §1.2 基线 + ADR-0004 增量**一次性全量安装**（含 torch/transformers/kuzu/qdrant/litellm/deepeval），
  以便后续步骤不再被网络阻塞；代价是 `.venv` 1.1 GB、首次安装耗时较长。
- uv 缓存与 TEMP 落在 D:（§1.1），否则 C: 无法完成安装。

### 3.5 `BEGIN IMMEDIATE` 只用于写事务

- **原方案**：给所有连接加 `begin` 事件发 `BEGIN IMMEDIATE`。
- **实测问题**：`db status` 自锁——一个连接持读事务、同进程 `inspect(engine)` 再开一个连接取写锁 → `database is locked`。
- **现方案**：`connect(engine, immediate=False|True)`；仅事件写入/`ensure_store_meta` 用 `immediate=True`，
  读路径用默认延迟事务。ADR-0005 §5 的语义（取号前拿写锁）保持不变。

### 3.6 其它小偏差

| 项 | 说明 |
|---|---|
| ruff `extend-exclude = ["docs/ppt/scripts", "prototype"]` | 前者是 Phase 0 的 PPT 构建脚本（19 处历史风格问题），后者待 1.19 删除 |
| 新增模型 `SourceRecord/ParsedDoc/Chunk/EvalRecord` | guide §2.3 早已列出，1.2 一并落地（原计划分散到 1.6/1.7） |
| `structure.SCHEMA_VERSION` 与 `tables.SCHEMA_VERSION` 双写 | 有同名测试锁一致性（`test_schema_version_is_single_source`） |

---

## 4. 踩坑与静默错误（新增，供 Phase 2 起警惕）

| # | 现象 | 根因 | 固化防护 |
|---|---|---|---|
| E1 | `UnicodeDecodeError: 'gbk' codec ...` 启动即崩 | `alembic.ini` 含中文注释，alembic 用 **locale 编码**读 ini | ini 改纯 ASCII；文档写清"外部工具读的配置必须 ASCII" |
| E2 | PowerShell 解析报 `Unexpected token '}'` | `.ps1` 为无 BOM UTF-8 含中文，Windows PowerShell 按 GBK 读 | 脚本保持 ASCII-only |
| E3 | `database is locked`（同进程） | 全局 `BEGIN IMMEDIATE` + 同进程第二个连接自锁 | §3.5：只对写事务 IMMEDIATE |
| E4 | `uv sync` 报 `os error 112` | C: 盘 0 可用（TEMP 12 GB） | 缓存/TEMP 迁 D:，写进 `scripts/env.ps1` 与本文 §1.1 |
| E5 | 写入文件报 `ENOSPC` | uv 解压临时文件瞬时占满 C: | 同上；重试即恢复 |
| E6 | pytest 临时目录可能在 C: | 默认 `%TEMP%` | `TEMP` 已指向 D:；本文记录 |

---

### Step 1.5 三库（2.0 d 计划）

- **交付**：`stores/graph.py`（Kuzu 0.11.3，MERGE 幂等；**关系必须先 MATCH 再 MERGE**，否则端节点被当新建 → 主键冲突）、`stores/vector.py`（Qdrant local 1.19.1 + `Embedder` 协议 + `HashingEmbedder` 降级 + `SentenceTransformerEmbedder` 懒加载）、`stores/files.py`、`stores/rebuild.py`（三方对账）、`db/session.write_store_identity`、`lit-agent stores verify|rebuild`。
- **实测**：31 例（图幂等/关系/落盘、向量 payload 六字段/过滤/身份、文件魔数与大小、重建对账）。
  - MERGE 写两次节点数不变（2），标题可更新；引用写两次边数 1；
  - 数据只在 `close()` 后落盘（before ≤ after，且 after > 0）；
  - 向量 payload 键集合 **恰为 §2.6 六字段**；`year_from` / `paper_ids` 过滤生效；
  - 伪造 `store_meta.model_id` → `E_VECTOR_MODEL_MISMATCH`；768 维 embedder → `E_VECTOR_DIM_MISMATCH`；
  - `rebuild_graph`+`rebuild_vector` 后 `verify_counts` 通过；手工塞入"幽灵节点"→ 报 `graph.papers` 不一致。
- **真实模型**：`BAAI/bge-m3` 已下载到 `D:\lit-agent-store\hf`（1024 维，编码可用）；测试一律注入 `HashingEmbedder`，不加载 2.27 GB 权重。
- **已知限制**：Qdrant **local 不支持 payload 索引**（官方 warn，no-op）→ 已移除建索引调用；Kuzu 逐条 `MERGE`（5k 量级见 Phase 0 的 34 ms/篇，P1 不做批量优化）。

### Step 1.6 源适配（1.5 d 计划）

- **交付**：`sources/base.py`（协议 + `SyncResult` + `E_SRC_*` 分类 + 指数退避）、`sources/openalex.py`（游标深分页 + 礼貌池 + 日期合理性 + 空 selector 显式报错）、`sources/whitelist.py`（名称→`source.id` 解析、按 id 判定、selector 规范化哈希）、`sources/arxiv.py`、`sources/normalize.py`（自 Phase 0 迁移 + **补 `source_id/venue_id/is_oa/language/cited_by_count` 五个 ADR-0005 字段**）、`sources/sync.py`（落 `papers`/`papers_raw`/`sync_state`）、`lit-agent sources sync`。
- **实测**（respx 拦截，无网络）：首次 sync `papers_new=2`、`raw_records=2`；**第二次 `papers_new=0`、`papers_updated=2`**；`venue_id=S42 / source_id=W7 / is_oa=1 / language=en` 落库；`venue_ids=[]` → `E_SRC_NO_SELECTOR`；白名单"同名不同 id"不命中。
- **偏差**：增量水位线暂用 `selector.from_year`（幂等重扫），真增量（`from_updated_date`）留 P4；引用边需 canonical 映射 → 由 Step 1.8 的投影写入（本步 `citations` 仍为 0）。

### Step 1.7 解析与分块（1.5 d 计划）

- **交付**：`parsing/chunking.py`（**tiktoken `cl100k_base`**，离线退回确定性启发式；`tokenizer_name()` 可观测）、`parsing/pdf.py`（`download_oa` + PyMuPDF→pdfplumber→失败对象）、`parsing/pipeline.py`（下载→抽取→分块→写 `paper_chunks`+`parse_status`）、`db/repo/chunks.py`（整体替换，无孤儿块）。
- **实测**：块 token ≤ 预算，除末块外利用率 ≥85%；400 词长句硬切；空文本 → 0 块；真实 PDF（PyMuPDF 生成）解析 `ok=1`、`n_chunks≥1`；坏 PDF（无 xref）→ `failed=1` 且**不抛异常**；已解析论文不重复处理（`candidates=0`）。
- **踩坑**：用 PowerShell `Set-Content -Encoding utf8` 改写含中文的 `.py` 会把 UTF-8 当 GBK 破坏文件（已改回 `Copy-Item` 字节拷贝 + 编辑工具）——**再次印证"外部工具读写的文件编码要盯死"**。



### Step 1.8 去重与投影（2.0 d 计划）

- **交付**：`sources/dedup.py`（`run_dedup` 落 `paper_merges` + `merged_ids_json`；`project_citations` 从 `papers_raw.referenced_works` 投影引用）、`db/repo/papers.set_merged_ids`、`db/repo/chunks`、`lit-agent sources dedup|project`；`rebuild` 改为**跳过被合并记录**（只投影主记录）。
- **实测**：同标题/同年的版本副本 → 合并对 ≥1、`unique=1`；`paper_merges` 有行且 `merged_ids_json` 非空；图里只有 1 个主记录节点；引文投影只收语料内两端（W9 被丢弃），重跑边数不变（1）。

### Step 1.9 LLM 网关（2.0 d 计划）

- **交付**：`gateway/cache.py`（内容寻址键：model/messages/temperature/max_tokens/schema_version）、`gateway/policy.py`（strict 敏感硬门：api_key / private_key / credential 三类模式）、`gateway/metering.py`（`CallUsage` + 80/100 预算 + usage 缺失估算）、`gateway/llm.py`（`LLMGateway`：敏感→缓存→预算→调用→截断翻倍重试→计量）。
- **实测**：敏感样本 **completer 调用 0 次**（零出网）；同请求第二次 `cached=True`、`cost=0`、内容逐字节一致且只出网 1 次；`llm_calls` 2 行（1 命中）；截断样本 `max_tokens` 64→128 重试成功；二次仍截断 → `E_LLM_TRUNCATED`；预算耗尽时**调用前**抛 `E_BUDGET_COST`；`chat_json` 正确剥离 ```json 围栏。
- **已知限制**：`llm_calls.run_id` 暂为 NULL（尚无 run 上下文），事件双写待 1.11 接入 runner；熔断器仍为 SKELETON（P2）。

### Step 1.10 Harness 骨架（2.0 d 计划）

- **交付**：`graph/state.py`（`AgentState` TypedDict + `operator.add` 归约 + `STATE_SCHEMA_VERSION=1.0`）、`graph/edges.py`（E1–E13 常量 + `MAINLINE` 主干路由；回退类显式 `E_FEATURE_DISABLED`）、`graph/checkpoint.py`（`SqliteSaver` 接线 + `resume()` 只接受 `None`）、`graph/pipeline.py`（`build_graph`/`register_node`/`smoke_graph`/`invoke_once`）。
- **实测**：三节点冒烟 `intake→retrieve→draft`，事件序列与计数正确；`invoke(None)` 复跑返回同一终态、不重放节点；`get_state` 能读回 checkpoint；自定义节点替换默认节点后归约仍只追加。
- **测试抓到的真实缺陷**：`MERGE (a)-[e:CITES {first_seen:$ts}]->(b)` 因时间戳每次不同 → **每次重建都新增一条边**（1→2）。修复：关系改为无属性 `MERGE` 后 `SET e.first_seen`，且 `first_seen` 取"数据内稳定epoch"而非 `now`。
- **已知限制**：Phase 1 只接主干三节点；S0–S9 全边与失败分支按 `E_FEATURE_DISABLED` 显式未实现（P2-GRAPH-02）。

### Step 1.11 运行器 / 守卫 / 锁 / 看门狗（1.5 d 计划）

- **交付**：`runtime/budget.py`（三维预算 80/100）、`graph/guards.py`（`Guard` 协议 + `GuardRail` 取最重动作 + `BudgetGuardAdapter` + `NoProgressGuard`，纯判定不写事件）、`runtime/jobs.py`（拿锁建 run、结束释放、**失败报告四要素**、孤儿清理）、`runtime/watchdog.py`（无事件超时 → `guard_trigger`）、`runtime/runner.py`（线性编排：phase_change → 守卫 → report_written；异常→error 事件 + failed）、CLI `run-topic` 已接通。
- **实测**（8 例）：run 成功且事件 ≥5、锁被释放；同 topic 第二个 run → `E_LOCK_HELD`；阶段抛 `E_SRC_TIMEOUT` → `failed` + 失败报告四要素 + error 事件；预算预先耗尽 → 首阶段即 `E_BUDGET_EXCEEDED` 中止并留 `guard_trigger`；连续 4 步零产出 → 停滞告警但**不终止**（降级语义）；`stale_seconds=0` → 看门狗判定 stale 并写事件；孤儿 run（无锁仍 running）→ `aborted(orphan)`。
- **已知限制**：阶段链仍是占位实现（`intake/retrieve/report` 只发事件与计数），真实抓取/解析在 1.12–1.16 接入；看门狗只检测不取消（P2-WATCH-01）；drift/loop 等四类守卫显式未实现。

### Step 1.12–1.14 上层（agents / context / tools，各 1.5/1.5/1.0 d 计划）

- **交付**：`agents/base.py`（`Agent` 协议 + `AgentResult`，输入输出契约最小化）、`agents/reporter.py`（证据卡 → claims → 确定性 Markdown，**每条 claim 必带引用**，空证据也给 `unsupported` 占位）、`context/budget.py`（`fit_text/fit_many`，句界截断）、`context/folding.py`（`truncate` 实现；`summarize/hierarchical` 显式未实现）、`context/slots.py`（槽位注册 + 优先级渲染 + 重名/未知槽报错）、`tools/registry.py`（`Tool`/`ToolResult`/重名与未知保护，**工具异常转结构化结果**）、`tools/builtin/{openalex_search,kv_cache}.py`。
- **实测**（11 例）：同一组卡片正序/逆序渲染**逐字节一致**（D4 幂等前提），每条 claim 带 citation；空证据 → 1 条 `unsupported` 且无引用；`fit_text` 超预算必截且 `tokens ≤ budget`；`fit_many` 总预算不被突破；`folding_for("summarize")` → `E_FEATURE_DISABLED`；槽位重名/未知槽报错且渲染按优先级排序；工具重名/未知报错，工具内部异常 → `ok=False, E_UNEXPECTED`；kv_cache put/get/clear 往返；`openalex_search` 工具声明了 selector 参数与 timeout。
- **已知限制**：reporter 只做"一卡一 claim"的机械折衷（真正的 claim 抽取/去重/反驳留 P3）；kv_cache 是进程内字典（跨 run 缓存已在 `llm_cache`/`embeddings`）；context 的"注入物化进事件"尚未接（P3，见 DSH 对照 P0-3）。

### Step 1.15 API + SSE（2.0 d 计划）

- **交付**：`api/{app,schemas,dependencies,sse}.py` + 8 个 `api/routes/*.py`：`/api/health`、`/api/topics`(GET/POST/详情/触发运行/计数)、`/api/runs/{id}`、`/api/runs/{id}/events?after_seq=&limit=`、`/api/runs/{id}/report`、`/api/runs/{id}/stream`(SSE)、`/api/topics/{id}/reports`、`/api/metrics/summary`、`/api/sources`；`chat`/`graph` 返回 **501 + `E_FEATURE_DISABLED`**。
- **异常映射**：`E_LOCK_HELD`→409、`E_FEATURE_DISABLED`→501、`E_CONFIG_INVALID`→404、其余 500（响应体带 `code/retryable/action_taken/context`）。
- **SSE 语义**：`after_seq` / `Last-Event-ID` 起点，**从 SQLite 补发历史**再轮询；run 进入终态且无新事件后发 `event: end` 关闭；心跳 15s。流式帧**不进事件表**（1.15 补充纪律）。
- **实测**（8 例）：health 报告 schema 1.0 + 24 表；topic 创建/列表/详情（含 selector）；触发 run → `succeeded`，事件 seq `1..N` 连续，`after_seq=1` 返回从 2 开始；未知 run → 404；chat/graph → 501；OpenAPI 含 8 条关键路径；SSE 回放含 `id: 1` 与 `event: end`；`after_seq=2` 时不再包含 `id: 1`。
- **偏差（需知）**：①触发运行是**同步执行**（P1 简化），P2 改异步任务 + 立即返回 202；②"资源不存在"暂用 `E_CONFIG_INVALID` 映射 404（语义上应独立 `E_NOT_FOUND`，收口时可加）；③`api export-openapi` CLI 尚未接线（当前用 `create_app().openapi()` 导出）。

### Step 1.17 调度与运维骨架（1.0 d 计划）

- **交付**：`runtime/scheduler.py`（`build_scheduler` / `cron_kwargs` / `weekly_job` / `run_once` / `list_jobs`）。**`enabled=false` 时完全不注册 job**（"注册后跳过"仍会触发，是错的）。
- **实测**（4 例）：disabled → job 列表为空；enabled → 恰好 1 个 `weekly` job；`cron_kwargs("0 3 * * 1")` 解析正确；`run_once` 跑通并把 `runs.trigger` 回填为 `schedule`。
- **偏差**：`runner` 暂无 `trigger` 参数，`weekly_job` 用一次 UPDATE 回填（P2 改为参数下传，避免多一次写）。

### Step 1.18 指标地基（1.5 d 计划）

- **交付**：`eval/metrics.py`（`compute_run_metrics` / `compute_topic_metrics` / `persist_run_metrics`）、`eval/export.py`（json/csv/md）。
- **口径**：grounding=supported/claims、hallucination=unsupported/claims、citation_coverage=有引用的 claims/claims、dedup=merges/主记录、cost=SUM(llm_calls.cost)（并单列 `cost_estimated_calls`）。
- **关键约定**：**分母为 0 返回 `None` 而不是 0.0**（"算不出来"与"就是 0"必须可区分，避免 Phase 0 那种假指标）。
- **实测**（4 例）：空 run → claims=0 且 ratio 为 `None`；构造 2 条 claim（1 supported 带引用 / 1 unsupported）+ 1 次调用 → grounding/hallucination/coverage 均 0.5、cost=0.003；`persist_run_metrics` 重复调用行数不增（可复算）；导出三种格式均可读。
- **已知限制**：`compute_topic_metrics` 的 topic 过滤用 JOIN ON 写法（结果正确但可读性差，收口时重写）；`persist_run_metrics` 时间戳写死（应收敛到 `utcnow_iso()`）。judge/gold 集仍为 D-SKEL（P5）。

### Step 1.16 前端三页骨架（2.5 d 计划）

- **交付**：`web/{package.json,vite.config.js,index.html}` + `web/src/{main.js,api.js,App.vue}`。三个页签（Topics / Report / Chat）在单文件组件内切换：
  - Topics：health 徽标、topic 列表/创建、触发 run、**事件时间线**（`/events`）、计数摘要；
  - Report：按 run_id 拉报告，渲染 Markdown + claims 表（text/support/citations 数）；
  - Chat：探测 `/chat` 并显示"Phase 1 未启用（501）"说明。
- **实测**：`npm install` + `npm run build` 通过（`dist/` 11 modules，JS 72.03 kB / gzip 28.29 kB）。
- **偏差（需知）**：①计划是 Vue3+**TS**+Element Plus+**三独立页面文件**，实际为 **JS + 原生 CSS + 单 App.vue**（三页签而非三路由）——为在剩余预算内交付**可构建**的最小界面；②**未跑浏览器 e2e**（`tests/e2e/test_demo_path.py` 未写）；③未做类型生成（`types.gen.ts`），前端靠 `api.js` 手写封装。
- **踩坑**：`npm run build` 首次报 `Cannot find module @rollup/rollup-win32-x64-msvc`（npm 可选依赖未装），显式 `npm i @rollup/rollup-win32-x64-msvc -D` 后通过。

### Step 1.19 收口（0.5 d 计划，部分完成）

- **已完成**：RESULTS-P1 滚动更新到 1.16；phase1 §5 进度表回写到 1.18；`docs/api/openapi.json` 已由 `lit-agent api export-openapi` 导出（16 条路径）。
- **未完成（明确挂账）**：
  1. **guide 回写**（§3.6 差异登记 10 项 + ADR 索引补 0004/0005 链接）；
  2. **`prototype/` 未删除**——安全起见保留（`RESULTS-P1` 与 phase1 多处引用其数字），建议在确认 Phase 2 不再依赖后删除；
  3. 结构快照（`doctor --json` 存档）与出口清单逐条勾选；
  4. Phase 2 首张任务卡（`P2-GRAPH-02`）尚未落到 `phase2-implementation-steps.md`（该文件未创建）。

## 4.5 Phase 1.1 收口复核（2026-10-20，F10）

| 判据 | 命令 | 结果 |
|---|---|---|
| G1 测试 | `pytest -q` | **246 例 / 30 文件，全绿** |
| G2 静态 | `ruff check .` | `All checks passed!` |
| G3 结构/schema | `check_structure` + `db status` | `129/129`（D-FULL 4 / D-MIN 1 / D-SKEL 12）；schema `1.0`、24 表 |
| G4 离线全链路 | `verify_phase1.py --offline` | **11/11 PASS** |
| G5 真实数据全链路 | `verify_phase1.py --online` | **13/13 PASS**（`102/102/102`、`authors=556`、claims 全带引用） |
| G6 文档 | ADR-0006 / known-gaps / exit-checklist | 三份齐备 |

**Phase 1.1 关闭的缺口**：G-01 作者丢失（唯一 P0）、G-03 ADR-0006、G-06 `E_NOT_FOUND`、G-07 sync CLI 契约、G-13 Phase 2 文档、G-14 SSE 续传、G-16 结构快照。
**期间新发现并修复**：`claims` 未落表导致指标恒 0（F5）；`CODE_RETRYABLE` 缺 24 个码（F3）。
**仍开放**：G-02（guide §3.6 逐条回写）、G-04/G-05（前端 TS + e2e → Phase 1.2）、G-08–G-12（P2/P4）。

**冻结基线**：`verify_phase1.py --online` 13/13 + 本表；tag 建议 `git tag phase1-rc1`（由负责人执行）。

## 5. 待办与下一步

1. **Step 1.10（Harness 骨架）**：`graph/state` + `pipeline` 三节点冒烟 + `checkpoint` 接线 + `edges` 常量（Phase 2 铺全边）。
2. **`config/seeds/topics.yaml` 的 `venue_ids`**：仍为 `[]`，真实同步前必须用 `resolve_venues()` 解析回填（否则 `E_SRC_NO_SELECTOR`）。
3. **ADR-0005 §7.4 孤儿锁**：`job_locks.cleanup_expired` 已实现，但"把对应 run 标 aborted(orphan)"要等 1.11 的 runner。
4. **真实数据冒烟**：`sources sync` 只在 respx fixture 下验证过；接真实 OpenAlex 前先补一次 venue 解析。
5. **C: 盘**：当前约 8 GB 可用；如需再装大依赖，先确认 `UV_CACHE_DIR` / `HF_HOME` 仍在 D:。
