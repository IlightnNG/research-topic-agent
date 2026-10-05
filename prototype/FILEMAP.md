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
| `lit_agent_min/__init__.py` | 包入口与自检 | `__version__`、`selfcheck(strict, config_path) -> int` | — | config | 0.1 | → `src/lit_agent/__init__.py` |
| `lit_agent_min/config.py` | 配置加载/校验/目录准备 | `load_settings()`、`ConfigError`、`ensure_dirs()`、`missing_env()` | YAML+env → `Settings`（不可变） | pydantic / pyyaml / dotenv | 0.1（最小）→ 0.2（扩展） | → `src/lit_agent/config.py` |
| `lit_agent_min/__main__.py` | CLI 入口（单一入口、可扩展子命令） | `python -m lit_agent_min selfcheck [--lax] [--config]` | argv → 退出码 | __init__ | 0.1 | → `src/lit_agent/cli.py` |
| `lit_agent_min/py.typed` | 类型标记 | — | — | — | 0.1 | 沿用 |
| `tests/test_config.py` | Step 0.1 验收单测 | 7 用例：加载/路径/错误可预期/未知键/密钥/目录/退出码 | — | config | 0.1 | → `tests/unit/test_config.py` |
| `out/`（含 `data/`、`reports/`、`*.csv`） | 运行产物与三库文件 | events.jsonl / reports / sqlite.db / kuzu / qdrant / papers | 运行时 → 追加写 | — | 全程 | 迁入正式 `data/` 目录 |
| `logs/`（`app.jsonl`、`errors.jsonl`、`debug/`） | **日志落盘**（字段/轮转/脱敏见规范） | 结构化 JSON 行；debug 目录仅在调试模式生成 | 代码调用 → 追加写 | structlog | 0.3 | → `logs/`（同结构） |
| `lit_agent_min/models.py` | **数据契约**（唯一结构定义） | `Paper / EvidenceCard / Claim / Event / Verdict` | dict/API 响应 → 校验后对象 | pydantic | 0.2 | → `src/lit_agent/models/` |
| `lit_agent_min/eventlog.py` | **事件真相源写入** | `emit(type, stage, payload, run_id)`；seq 自增 | 事件 dict → `out/events.jsonl` | models | 0.2 | → `runtime/events.py`（迁 SQLite） |
| `lit_agent_min/logging.py` | **结构化日志**：配置/上下文绑定/脱敏/落盘 | `setup_logging(cfg)`、`get_logger(name)`、`bind_context(run_id, stage)` | 代码调用 → `logs/app.jsonl` + 控制台 | structlog | 0.3 | → `src/lit_agent/logging.py` |
| `lit_agent_min/sources.py` | 源 API 访问（增量、限速、重试） | `fetch_updated(since, selector)` | 游标+白名单 → `SourceRecord[]` | httpx/pyalex/arxiv | 5.1（S1 复用） | → `sources/` |
| `lit_agent_min/normalize.py` | 归一化与稳定键 | `canonical_id()`、`name_norm()`、`to_paper()` | `SourceRecord` → `Paper` | models | 5.2 | → `sources/normalize.py` |
| `lit_agent_min/parsing.py` | 全文抽取与分块 | `extract_text()`、`chunk(text, budget)` | PDF 路径 → 文本/分块 | pymupdf/pdfplumber/tiktoken | 5.3 | → `parsing/` |
| `lit_agent_min/stores.py` | 三库读写（幂等） | `upsert_paper()`、`search()`、`graph_upsert()` | Paper/向量 → 三库 | sqlalchemy/kuzu/qdrant-client | 5.4（S3 复用） | → `db/` + `stores/` |
| `lit_agent_min/report.py` | 报告生成与引用解析 | `draft_report(cards) -> (md, Claim[])` | 证据卡 → 报告 + claims | litellm/models | 5.6 | → `agents/reporter.py` |
| `steps/s1_source_coverage.py` | 覆盖度统计实验 | CLI：`--topic --years --limit --out` | 源 API → CSV + 结论 | sources | 1 | 逻辑并入 `sources/` + `eval/` |
| `steps/s2_model_baseline.py` | 双引擎基线实验 | CLI：`--tasks --local --cloud --out` | 任务集 → 对比 CSV | litellm | 2 | 逻辑并入 `eval/` |
| `steps/s3_storage_spike.py` | 存储性能与幂等实验 | CLI：`--papers --out` | 元数据 → 指标 JSON | stores | 3 | 逻辑并入 `stores/` 测试 |
| `steps/s4_checkpoint_spike.py` | 断点续跑实验 | CLI：`--run-id` | 图执行 → 事件 JSONL | langgraph | 4 | 配置结论进 `runtime/` |
| `steps/s5_walking_skeleton.py` | 端到端编排（子步 5.1–5.7） | CLI：`--topic --run-id` | topic → 报告 + claims + 事件 | lit_agent_min 全部 | 5 | 拆解进 sources/parsing/stores/agents |
| `steps/s6_guards_demo.py` | 守卫与注入演示 | CLI：`--topic --inject --repeats` | 注入场景 → 事件链 | lit_agent_min + guards | 6 | → `graph/guards.py` + `eval/faultinject.py` |
| `steps/s7_metrics.py` | 指标聚合 | CLI：`--events --out` | `events.jsonl` → 指标 CSV | 无（纯计算） | 7 | → `eval/metrics.py` |
| `tests/test_contracts.py` | 契约与事件单测 | 模型往返 / seq 单调 / 必填校验 | — | models/eventlog/config | 0.2 | → `tests/unit/` |
| `tests/test_logging.py` | 日志基线单测 | 字段完整性 / 脱敏 / 级别策略 | — | logging | 0.3 | → `tests/unit/` |
| `tests/test_normalize.py` | 归一化单测 | id 优先级 / 缺字段 / 多作者 | — | normalize | 5.2 | → `tests/unit/` |
| `tests/test_stores.py` | 存储幂等单测 | 重复写入零增长 / 过滤命中 | — | stores | 5.4 | → `tests/integration/` |

**与选型文档 §1.1.1 的差异（本表为准）**：新增 `.gitignore`、`.python-version`、`config.example.yaml`、`py.typed`、`tests/test_config.py`、`logs/`；`config.py` 归属改为「0.1（最小）→ 0.2（扩展）」；`logging.py` 归属 **0.3**（对应 `docs/implementation/logging-and-observability.md` §12）。
