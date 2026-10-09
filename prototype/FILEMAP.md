# 文件职责表（FILEMAP）

> 与 `docs/implementation/phase0-implementation-steps.md` §1.1.1 对应；**新增/重命名文件必须同步更新本表**（Step 0.1 验收项）。
> 「下一阶段归属」列是本文件升级到 Phase 1 时的搬运映射。

| 文件/路径 | 功能责任 | 关键接口或内容 | 输入 → 输出 | 依赖 | 归属 Step | 下一阶段归属 |
|---|---|---|---|---|---|---|
| `README.md` | 上手与运行索引 | 快速开始 / 验收命令 / Step 索引 / 已知限制 | — | — | 0.1 | 重写为正式 README |
| `RESULTS.md` | **结论台账**（唯一数字来源） | 进度表 / 环境事实 / 假设记录 | 各 Step 产出 → 表行 | — | 全程 | 升级为"实现进度"附录 |
| `FILEMAP.md` | **文件职责表** | 本表（与 §1.1.1 同步） | — | — | 0.1 | 沿用（随代码更新） |
| `.env.example` | 密钥与运行变量模板 | `DEEPSEEK_API_KEY` / `LIT_AGENT_CONFIG` / `OLLAMA_BASE_URL` | — | — | 0.1 | 沿用（正式仓库同名） |
| `config.local.yaml` | 运行配置（非敏感） | paths / providers / sources / guards / logging | — | — | 0.1 | 作为 `config/config.example.yaml` 种子 |
| `config.example.yaml` | 配置模板 | 同 `config.local.yaml` | — | — | 0.1 | 沿用 |
| `.gitignore` | 忽略规则 | `.venv/ .env out/ logs/ __pycache__` 等 | — | — | 0.1 | 沿用 |
| `.python-version` | 解释器版本固定 | `3.11` | — | — | 0.1 | 沿用 |
| `pyproject.toml` + `uv.lock` | 依赖与工具配置、版本锁定 | 依赖清单 / ruff / pytest 配置 | — | — | 0.1 | 裁剪后作为正式项目依赖基线 |
| `lit_agent_min/__init__.py` | 包入口与自检 | `__version__`、`selfcheck()`、`open_event_log()`，并再导出契约与事件类型 | — | config/models/eventlog | 0.1（0.2 扩充导出） | → `src/lit_agent/__init__.py` |
| `lit_agent_min/config.py` | 配置加载/校验/目录准备 | `load_settings()`、`ConfigError`、`ensure_dirs()`、`missing_env()` | YAML+env → `Settings`（不可变） | pydantic / pyyaml / dotenv | 0.1（最小）→ 0.2（扩展） | → `src/lit_agent/config.py` |
| `lit_agent_min/__main__.py` | CLI 入口（单一入口、可扩展子命令） | `selfcheck [--lax] [--config]`；`demo-events [--run-id] [--out]` | argv → 退出码 | __init__ | 0.1（0.2 增子命令） | → `src/lit_agent/cli.py` |
| `lit_agent_min/py.typed` | 类型标记 | — | — | — | 0.1 | 沿用 |
| `tests/test_config.py` | Step 0.1 验收单测 | 7 用例：加载/路径/错误可预期/未知键/密钥/目录/退出码 | — | config | 0.1 | → `tests/unit/test_config.py` |
| `out/`（含 `data/`、`reports/`、`*.csv`） | 运行产物与三库文件 | events.jsonl / reports / sqlite.db / kuzu / qdrant / papers | 运行时 → 追加写 | — | 全程 | 迁入正式 `data/` 目录 |
| `logs/`（`app.jsonl`、`errors.jsonl`、`debug/`） | **日志落盘**（字段/轮转/脱敏见规范） | 结构化 JSON 行；debug 目录仅在调试模式生成 | 代码调用 → 追加写 | structlog | 0.3 | → `logs/`（同结构） |
| `lit_agent_min/models.py` | **数据契约**（唯一结构定义；✅ 0.2 已交付） | `Author / Paper / EvidenceCard / Citation / Claim / Verdict / Event` + 枚举 `Severity / EventType / GuardAction / Support`；约束内建（证据必带引用、失败判决必给原因、ts 必带时区、payload 必可 JSON 序列化） | dict/API 响应 → 校验后对象 | pydantic | 0.2 ✅ | → `src/lit_agent/models/` |
| `lit_agent_min/eventlog.py` | **事件真相源写入**（✅ 0.2 已交付；append-only JSONL） | `JsonlEventLog(path, run_id).emit(...)`、`read_events()`、`EventSink` 协议（Phase 1 直接替换为 SQLite 实现） | 事件 dict → 追加 `out/events.jsonl` | models | 0.2 ✅ | → `runtime/events.py`（迁 SQLite） |
| `lit_agent_min/_version.py` | 单一版本来源（避免循环导入） | `__version__`（当前 0.3.0） | — | — | 0.3 | → `src/lit_agent/_version.py` |
| `lit_agent_min/logging.py` | **结构化日志基线**（✅ 0.3 已交付） | `setup_logging(settings, force=)`、`bind_context(**fields)`、`log_event(severity, event, msg, **fields)`、`validate_no_bodies()`；脱敏（密钥/邮箱/家目录）+ 正文守卫 + 错误双写 | 代码调用 → `logs/app.jsonl` + `logs/errors.jsonl` + 控制台 | structlog | 0.3 ✅ | → `src/lit_agent/logging.py` |
| `lit_agent_min/sources.py` | 源 API 访问（增量、限速、重试） | `fetch_updated(since, selector)` | 游标+白名单 → `SourceRecord[]` | httpx/pyalex/arxiv | 5.1（S1 复用） | → `sources/` |
| `lit_agent_min/normalize.py` | 归一化与去重（✅ 5.2 已交付） | `canonical_id()`(DOI→W→arxiv→标题指纹)、`name_norm()`、`reconstruct_abstract()`、`openalex_work_to_paper()`、`dedup_papers()`(D6 三段式) | 源记录 → `Paper` + 合并关系 | models | 5.2 ✅ | → `sources/normalize.py` |
| `lit_agent_min/chunking.py` | 分块与 PDF 抽取（✅ 5.3 已交付，PDF 本轮未启用） | `count_tokens()`(确定性启发式，免联网词表)、`chunk_text()`(预算+句子边界+overlap)、`extract_pdf_text()`(PyMuPDF→pdfplumber 兜底) | 文本 → 块列表 / 坏文件 → 错误对象 | pymupdf/pdfplumber | 5.3 ✅ | → `parsing/`（Phase 1 换 tiktoken/bge tokenizer） |
| `lit_agent_min/stores.py` | SQLite 真相源（✅ 5.4 已交付；Kuzu/Qdrant 留 Phase 1） | `SqliteStore`(6 表幂等 upsert/计数/游标/schema 校验)、`verify_counts()`(写入对账)、`StoreSchemaError` | `Paper`/`Claim` → SQLite | sqlite3 | 5.4 ✅ | → `db/` + `stores/`（补 Kuzu/Qdrant） |
| `lit_agent_min/report.py` | 报告生成与引用解析 | `draft_report(cards) -> (md, Claim[])` | 证据卡 → 报告 + claims | litellm/models | 5.6 | → `agents/reporter.py` |
| `steps/s1_source_coverage.py` | 源覆盖度实验（✅ 已交付） | CLI：`--topics --years --limit --venue-sufficiency --arxiv-existence --skip-probe`；产出覆盖度四指标 + 白名单召回量 + arXiv 收录率 + 限速探测 | 源 API → `out/s1_coverage.csv` / `.json` / `s1_deep.log` + 事件/日志 | httpx/arxiv/pyalex | 1 ✅ | 逻辑并入 `sources/` + `eval/` |
| `steps/s1b_retrieval_and_dedup.py` | 检索策略/去重/引用完整率实验（✅ 已交付） | CLI：`--topics --years --per-page --out --summary`；三策略对比（broad/whitelist/expansion）+ 去重统计 + 增量语义探测 | 源 API → `out/s1b_records.csv` / `s1b_summary.json` + 事件/日志 | httpx | 1b ✅ | 逻辑并入 `sources/`（检索器+去重器） |
| `steps/s2_model_baseline.py` | 双引擎基线实验（⏸ 本轮不做：项目当前只用云端 DeepSeek） | 规划 CLI：`--tasks --local --cloud --out` | 任务集 → 对比 CSV | litellm | 2（延后） | 逻辑并入 `eval/` |
| `steps/s3_storage_spike.py` | 存储栈验证（✅ 已交付，5k 全量）：导入/四类查询/幂等/可重建/边界探针 | CLI：`--papers --rounds --[no-]rebuild-check --summary`；`reset_store_path()`（文件/目录通用清理）、`path_size_mb()`、`store_is_empty()`（导入前空库哨兵）、写入后计数对账 | 元数据 → `out/s3_storage.json` + 事件/日志 | kuzu/qdrant-client/sqlite3 | 3 ✅ | 逻辑并入 `stores/` + `tests/integration/` |
| `steps/s3b_vector_latency_probe.py` | 向量延迟归因探针（✅ 已交付）：拆解"纯算力下限 / local 模式开销 / payload 过滤成本"、1250–5000 规模曲线、payload 索引有效性 | 无 CLI（`ROUNDS`/`SIZES` 为文件内常量）；写入路径复用 S3 的 `init_qdrant`/`qdrant_upsert` 保证同口径 | 5000 点 → `out/s3b_vector_latency.json` | numpy/qdrant-client | 3 ✅ | **一次性归因脚本，不迁移**；结论进 Phase 1 部署形态决策 |
| `steps/s4_checkpoint_spike.py` | 断点续跑验证（✅ 已交付）：6 场景（对照/单崩/连崩/输入漂移/重复触发/正确续跑）+ 事件级校验 | CLI：`--mode {baseline,crash,resume,verify} --run-id --label --topic --crash-at --arm --input-mode {fresh,none} --ckpt`；崩溃用**一次性臂文件 + `os._exit(9)`**（确定性，非掐时间）；`node_attempts()`/`seq_report()` 校验 | 3 节点图 → `out/events_s4.jsonl` / `out/s4_summary.json` / `out/s4/*.json` / `out/data/s4_*.db` | langgraph + langgraph-checkpoint-sqlite（本地、零网络） | 4 ✅ | 结论进 `runtime/`（续跑用 `invoke(None)`、节点幂等）、G3、G15 |
| `steps/s5_walking_skeleton.py` | 单 topic 端到端最小闭环（✅ 已交付，真实云 LLM）：5.1 fetch→5.2 normalize→5.3 chunk→5.4 store→5.5 retrieve→5.6 report→5.7 events | CLI：`--topic --run-id --top-k --card-batch --max-usd --model --no-cache --reset-store`；含 W→canonical 引用映射、citation 回查强制校验、确定性报告渲染 | 语料 fixture → `out/reports/*.md` + `out/claims_<run_id>.json` + `out/s5_summary.json` + 事件 | litellm/numpy | 5 ✅ | 逻辑并入 `graph/` + `agents/` + `runtime/` |
| `steps/s6_guards_demo.py` | 守卫与注入演示 | CLI：`--topic --inject --repeats` | 注入场景 → 事件链 | lit_agent_min + guards | 6 | → `graph/guards.py` + `eval/faultinject.py` |
| `steps/s7_metrics.py` | 指标聚合 | CLI：`--events --out` | `events.jsonl` → 指标 CSV | 无（纯计算） | 7 | → `eval/metrics.py` |
| `tests/test_contracts.py` | 契约与事件单测（✅ 0.2 已交付，19 用例） | 模型往返/未知字段拒绝/冻结、claim 证据规则、verdict 原因规则、事件时区与 payload 可序列化、seq 单调与续写、并发唯一性、损坏行定位、失败不留半行 | — | models/eventlog | 0.2 ✅ | → `tests/unit/test_contracts.py` |
| `tests/test_logging.py` | 日志基线单测（✅ 0.3 已交付，9 用例） | 字段完整性/上下文关联/脱敏/正文守卫/错误双写/严格契约/DEBUG 例外 | — | logging | 0.3 ✅ | → `tests/unit/test_logging.py` |
| `lit_agent_min/guards.py` | 守卫（✅ S6 已交付） | `DriftGuard`(G1：分数→warn/block，支持相对分位口径)、`LoopGuard`(G4：签名窗口 k 成环→replan→abort)、`ProgressGuard`(停滞→degrade→abort)、`BudgetWatchdog`(4 维，80% warn/100% stop)、`build_recovery_packet`、`GuardRail`；**纯判定，不写事件** | 观测值 → `Verdict` | models | 6 ✅ | → `graph/guards.py` |
| `lit_agent_min/scoring.py` | 词法打分与阈值标定（✅ S6 已交付，S5 检索共用） | `tokenize`/`build_idf`/`cosine`/`rank`/`build_centroid`/`cosine_to_vector`/`calibrate_threshold`/`calibrate_drift_thresholds`（按分布间隙定 block/warn） | 文本 → 分数/排序 | 无（纯函数） | 6 ✅ | → `eval/scoring.py` + `stores/vector.py`（Phase 1 换 embedding，**阈值须重标定**） |
| `lit_agent_min/topics.py` | 主题定义（scope statement 唯一来源） | `TOPICS`/`TopicSpec`/`get_topic` | — | — | 6 ✅ | → `config.yaml` 的 `topics:` 段 |
| `steps/s6_guards_demo.py` | 守卫 + 看门狗 + 注入演示（✅ 已交付）：6 场景 ×N 次 + 阈值扫描 | CLI：`--inject {none,drift,loop,stagnation,timeout,budget,all} --repeats --sweep --drift-warn/--drift-block --loop-window/--loop-repeat --no-progress-steps --budget-tokens` | → `out/s6_summary.json`、`out/s6_threshold_sweep.json`、`out/s6/guards_*.jsonl` | guards/scoring | 6 ✅ | 逻辑并入 `graph/guards.py` + `eval/faultinject.py` |
| `tests/test_guards.py` | 守卫单测（✅ 已交付，18 用例，全离线） | G1 阈值两侧/相对口径/history、G4 签名稳定与窗口、停滞阶梯、预算 80/100 边界、恢复包结构、GuardRail 按需调用 | — | guards | 6 ✅ | → `tests/unit/` |
| `tests/test_scoring.py` | 打分与标定单测（✅ 已交付，9 用例） | 分词/余弦/排序确定性、质心可分性、间隙标定（block=中点、warn<min(正)）、重叠时如实标注、空样本 | — | scoring | 6 ✅ | → `tests/unit/` |
| `lit_agent_min/llm.py` | 云 LLM 网关（✅ 5.6 已交付） | `LLMGateway.chat_json()/chat()`：内容寻址缓存、超时+指数退避重试、**reasoning 截断检测**、token/cost 计量、预算熔断、事件回调 | 消息 → `LLMCall`（无正文入库） | litellm | 5.6 ✅ | → `llm/gateway.py`（P2 加路由与熔断） |
| `tests/test_chunking.py` | 分块与 PDF 兜底单测（✅ 已交付，9 用例） | 预算上界严格 / 预算充足时 ≥0.9 利用率 / 超长句硬切 / 空文本 / 坏 PDF 不崩且记录错误 | — | chunking | 5.3 ✅ | → `tests/unit/` |
| `tests/test_llm.py` | LLM 网关单测（✅ 已交付，9 用例，注入假 completer 不触网） | JSON 解析 / 截断重试并放大预算 / 空正文判失败 / 缓存不重复计费 / 禁用缓存 / 预算熔断 / 围栏剥离 | — | llm | 5.6 ✅ | → `tests/unit/` |
| `tests/test_normalize.py` | 归一化单测（✅ 已交付，14 用例） | id 优先级 / 缺字段 / 多作者 / 摘要还原 / D6 去重（同 id、版本副本、主记录选择） | — | normalize | 5.2 ✅ | → `tests/unit/test_normalize.py` |
| `tests/test_stores.py` | 存储幂等与 schema 守卫单测（✅ 已交付，9 用例） | 重复写入零增长 / 更新覆盖 / 仅语料内引用成边 / 游标 / claims / schema 不匹配报错 / reset 重建 / 计数对账 | — | stores | 5.4 ✅ | → `tests/integration/` |

**与选型文档 §1.1.1 的差异（本表为准）**：新增 `.gitignore`、`.python-version`、`config.example.yaml`、`py.typed`、`tests/test_config.py`、`logs/`；`config.py` 归属改为「0.1（最小）→ 0.2（扩展）」；`logging.py` 归属 **0.3**（对应 `docs/implementation/logging-and-observability.md` §12）。