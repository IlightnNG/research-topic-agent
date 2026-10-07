# Phase 0 实施步骤指导（项目初始化与可行性验证）

> 状态：**v0.1 执行清单**——Phase 0 的逐步施工指导；每一步都写明"内容要求 / 交付物 / 执行命令 / 验收标准 / 时间盒 / 失败应对"
> 定位：**原型验证阶段**，代码只是实验，**不是**交付仓库；不做 UI、不做周更调度、不做多 agent 拆分、不做完整守卫框架
> 总时间盒：**10.5 个工作日（约 2 周）**；出口 = 数字结论 + 最小闭环 demo + 埋点与守卫雏形 + 阶段决策门通过
> 关联：`implementation/implementation-guide.md`（§2 契约、§15 工作流、附录 A Wave）· `design/state-machine-and-guards.md`（G1/G4 与预算）· `implementation/evaluation-plan.md`（指标口径）· `design/agent-design-decisions.md`（问题台账）

---

## 0. Phase 0 的目标与出口标准

### 0.1 三个目标
1. **验证关键选型**：数据源覆盖度、存储栈性能、断点续跑能力——都要有**数字**（本地 vs 云模型质量本轮不做，见 Step 2 注记）；
2. **跑通最小闭环**：单个 topic 从检索到出报告（无 UI、无调度），且重复运行幂等；
3. **建立埋点与守卫雏形**：4 类事件可回放；漂移与循环两个守卫能"注入→检出→回退"。

### 0.2 出口标准（Phase 0 Exit Gate，全部勾选才算完成）
- [ ] Step 1/3/4 三个验证都有数字结论（**S2 本轮豁免**；含"结论为负"的情况需写明应对）；
- [ ] 三库（SQLite/Kuzu/Qdrant）可写可查、重复写入幂等；
- [ ] 单 topic 能自动产出一份报告，且每条 claim 带可回查 citation；
- [ ] 事件日志可按 run 完整回放（4 类事件齐全）；
- [ ] 注入漂移/循环/超时/预算后，能产出"检出→处置→恢复"事件链；
- [ ] `RESULTS.md` 汇总完成，五份主文档已按发现回写；
- [ ] 导师确认 → 决定是否按 `implementation/implementation-guide.md` 附录 A 启动正式仓库（Phase 1）。

### 0.3 明确不做清单（Phase 0 红线）
| 不做 | 原因 |
|---|---|
| Web 前端 / Vue / ECharts | 与验证核心假设无关，最耗时 |
| APScheduler 周更 / 多 topic 调度 | 依赖闭环稳定后再做 |
| 多 agent 角色拆分（retrieval/mapper/analyst/critic 独立进程） | 先用单 agent + 显式函数步骤验证流程 |
| G1–G13 完整守卫框架 | 只做 G1（漂移）+ G4（循环），阈值先粗后精 |
| 完整 SQLite schema / Alembic 迁移 | Phase 0 用 JSONL 事件 + 最小 SQLite 表即可 |
| 生产级错误处理与重试框架 | 只保证"失败可见 + 可重跑" |

---

## 1. 全局约定

### 1.1 代码位置与形态
```
agent/                            # 仓库根（= Phase 1 的 Python 项目根）
├─ docs/                          # 研究与设计文档
├─ .local/                        # 本地工具产物：uv 缓存/托管解释器/临时目录（gitignored）
├─ prototype/                     # Phase 0 实验区（可整体丢弃或部分升级）
│  ├─ README.md                   # 运行说明/依赖/密钥/已知限制/各 Step 命令索引
│  ├─ RESULTS.md                  # 每步结论、数字、证据、是否影响设计（模板见 §1.4）
│  ├─ FILEMAP.md                  # 文件职责表（与 §1.1.1 同步，含全部实际文件）
│  ├─ .env.example / .env         # 环境变量模板 / 真实密钥（.env 不入库）
│  ├─ config.local.yaml / config.example.yaml   # 运行配置 / 模板
│  ├─ pyproject.toml / uv.lock    # 依赖与工具配置 / 版本锁定
│  ├─ lit_agent_min/              # ★可升级到 Phase 1 的最小可复用代码
│  │  ├─ __init__.py              # 公共接口导出、版本与 selfcheck()
│  │  ├─ config.py                # YAML+env 配置加载与校验（安全默认）        ← 0.1 已交付
│  │  ├─ __main__.py              # CLI：python -m lit_agent_min selfcheck     ← 0.1 已交付
│  │  ├─ py.typed                 # 类型标记
│  │  ├─ models.py                # Pydantic 契约（Paper/EvidenceCard/Claim/Event/Verdict） ← 0.2
│  │  ├─ eventlog.py              # 事件写入（JSONL，seq 自增，字段对齐 §2.2）              ← 0.2
│  │  ├─ logging.py               # 结构化日志：配置/上下文绑定/脱敏/落盘（规范见 logging-and-observability.md） ← 0.3
│  │  ├─ sources.py               # OpenAlex/arXiv 客户端（分页/限速/退避/mailto）
│  │  ├─ normalize.py             # canonical_id、作者 name_norm、字段归一
│  │  ├─ parsing.py               # PDF 抽取（PyMuPDF→pdfplumber 兜底）+ 分块
│  │  ├─ stores.py                # SQLite/Kuzu/Qdrant 客户端封装（幂等 upsert/MERGE/search）
│  │  └─ report.py                # 报告生成 + claims/citation 解析（经 litellm 调用）
│  ├─ steps/                      # ✗Phase 0 专用脚本 s1–s7（结论保留，代码可丢弃；清单见 FILEMAP）
│  ├─ tests/                      # 单元测试（只依赖 lit_agent_min）
│  │  ├─ test_config.py           # ← 0.1 已交付（7 用例：配置/路径/密钥/目录/退出码）
│  │  ├─ test_contracts.py        # ← 0.2：模型往返 / 事件 seq / 配置校验
│  │  ├─ test_logging.py          # ← 0.3：字段完整性 / 脱敏 / 级别策略
│  │  ├─ test_normalize.py        # ← 5.2：id 优先级 / 缺字段 / 多作者
│  │  └─ test_stores.py           # ← 5.4：幂等与过滤
│  ├─ out/                        # 运行产物（gitignored）：events.jsonl / reports/ / data/ / *.csv / charts/
│  └─ logs/                       # 日志产物（gitignored）：app.jsonl / errors.jsonl / debug/
└─ (Phase 1 起在仓库根建 src/ 等正式布局，见 implementation/implementation-guide.md §1.1)
```
**Git**：分支 `prototype`；每次 Step 完成提交一次，commit 格式 `step-N: <结论摘要>`。

### 1.1.1 文件职责表（后续优化与 AI 生成的文件级依据）

| 文件/路径 | 功能责任 | 关键接口或内容 | 输入 → 输出 | 依赖 | 归属 Step | 下一阶段归属 |
|---|---|---|---|---|---|---|
| `README.md` | 上手与运行索引 | 环境/密钥/各 Step 命令/已知限制 | — | — | 0.1 | 重写为正式 README |
| `RESULTS.md` | **结论台账**（唯一数字来源） | 结论/数字/证据文件/是否影响设计 | 各 Step 产出 → 表行 | — | 全程 | 升级为"实现进度"附录 |
| `.env.example` | 密钥与运行变量模板 | `DEEPSEEK_API_KEY` 等 | — | — | 0.1 | 沿用（正式仓库同名） |
| `config.local.yaml` | 运行配置 | providers/路径/白名单/阈值初值 | — | — | 0.1 | 作为 `config/config.example.yaml` 种子 |
| `pyproject.toml`+`uv.lock` | 依赖与工具配置、版本锁定 | 依赖列表、ruff/pytest 配置 | — | — | 0.1 | 裁剪后作为正式项目依赖基线 |
| `lit_agent_min/models.py` | **数据契约**（唯一结构定义） | `Paper/EvidenceCard/Claim/Event/Verdict` | dict/API 响应 → 校验后对象 | pydantic | 0.2 | → `src/lit_agent/models/` |
| `lit_agent_min/eventlog.py` | **事件真相源写入** | `emit(type, stage, payload, run_id)`；seq 自增 | 事件 dict → `out/events.jsonl` | models | 0.2 | → `runtime/events.py`（迁 SQLite） |
| `lit_agent_min/config.py` | 配置加载与校验 | `load_config() -> Config`；缺项报错 | YAML+env → Config | pydantic-settings | 0.2 | → `src/lit_agent/config.py` |
| `lit_agent_min/logging.py` | **结构化日志**：配置、上下文绑定、脱敏、落盘 | `setup_logging(cfg)`、`get_logger(name)`、`bind_context(run_id, stage)` | 代码调用 → `logs/app.jsonl` + 控制台 | structlog | 0.3 | → `src/lit_agent/logging.py` |
| `lit_agent_min/sources.py` | 源 API 访问（增量、限速、重试） | `fetch_updated(since, selector)` | 游标+白名单 → `SourceRecord[]` | httpx/pyalex/arxiv | 5.1（S1 复用） | → `sources/` |
| `lit_agent_min/normalize.py` | 归一化与稳定键 | `canonical_id()`、`name_norm()`、`to_paper()` | `SourceRecord` → `Paper` | models | 5.2 | → `sources/normalize.py` |
| `lit_agent_min/parsing.py` | 全文抽取与分块 | `extract_text() -> str`、`chunk(text, budget) -> Chunk[]` | PDF 路径 → 文本/分块 | pymupdf/pdfplumber/tiktoken | 5.3 | → `parsing/` |
| `lit_agent_min/stores.py` | 三库读写（幂等） | `upsert_paper()`、`search()`、`graph_upsert()` | Paper/向量 → 三库 | sqlalchemy/kuzu/qdrant-client | 5.4（S3 复用） | → `db/` + `stores/` |
| `lit_agent_min/report.py` | 报告生成与引用解析 | `draft_report(cards) -> (md, Claim[])` | 证据卡 → 报告 + claims | litellm/models | 5.6 | → `agents/reporter.py` |
| `steps/s1_source_coverage.py` | 源覆盖度实验（✅ 已交付） | CLI：`--topics --years --limit --venue-sufficiency --arxiv-existence --skip-probe` | 源 API → `out/s1_coverage.csv/.json` + 结论 | httpx/arxiv | 1 ✅ | 逻辑并入 `sources/` + `eval/` |
| `steps/s2_model_baseline.py` | 双引擎基线实验（⏸ 本轮不做：只用云端 DeepSeek） | CLI：`--tasks --local --cloud --out` | 任务集 → 对比 CSV | litellm | 2（延后） | 逻辑并入 `eval/`，结论进路由策略 |
| `steps/s3_storage_spike.py` | 存储性能与幂等实验 | CLI：`--papers --out` | 元数据 → 指标 JSON | stores | 3 | 逻辑并入 `stores/` 测试 |
| `steps/s4_checkpoint_spike.py` | 断点续跑实验 | CLI：`--run-id`（可中断重跑） | 图执行 → 事件 JSONL | langgraph | 4 | 配置结论进 `runtime/` |
| `steps/s5_walking_skeleton.py` | 端到端编排（子步 5.1–5.7） | CLI：`--topic --run-id` | topic → 报告 + claims + 事件 | lit_agent_min 全部 | 5 | 拆解进 sources/parsing/stores/agents |
| `steps/s6_guards_demo.py` | 守卫与注入演示 | CLI：`--topic --inject --repeats` | 注入场景 → 事件链 + 结论 | lit_agent_min + guards | 6 | → `graph/guards.py` + `eval/faultinject.py` |
| `steps/s7_metrics.py` | 指标聚合 | CLI：`--events --out` | `events.jsonl` → 指标 CSV | 无（纯计算） | 7 | → `eval/metrics.py` |
| `tests/test_contracts.py` | 契约与事件单测 | 模型往返/seq 单调/必填校验 | — | models/eventlog/config | 0.2 | → `tests/unit/` |
| `tests/test_normalize.py` | 归一化单测 | id 优先级/缺字段/多作者 | — | normalize | 5.2 | → `tests/unit/` |
| `tests/test_stores.py` | 存储幂等单测 | 重复写入零增长/过滤命中 | — | stores | 5.4 | → `tests/integration/` |
| `out/events.jsonl` | **事件真相源（Phase 0）** | 4 类事件 + 守卫/指标事件 | 运行时 → 追加写 | — | 全程 | 迁入 SQLite `run_events` |
| `out/reports/*.md`、`claims.json` | 报告产物与断言映射 | 报告正文 + 每条 claim 的 citation | 生成 → 落盘 | — | 5 | 迁入 `reports` 表 + 文件系统 |
| `out/data/{sqlite.db,kuzu/,qdrant/,papers/}` | 本地数据与索引 | 三库文件 + 全文缓存 | — | — | 3–5 | 迁入正式 `data/` 目录 |
| `out/*.csv` / `*.json` / `charts/` | spike 结论证据 | 各 Step 的原始数据与图表 | — | — | 1–7 | 作为论文附录数据 |

> **实际交付的文件职责表以 `prototype/FILEMAP.md` 为准**（含本节未列出的 `.gitignore`、`.python-version`、`config.example.yaml`、`py.typed`、`tests/test_config.py`、`logs/` 等）；本节表格是面向选型说明的摘要版。

### 1.1.2 文件边界与命名约定（防职责漂移）

1. **单向依赖**：`steps/` 可以 import `lit_agent_min/`；`lit_agent_min/` **不得** import `steps/`；`out/` 不被任何代码 import（只被脚本写）。
2. **一个文件一个责任**：契约只在 `models.py`；事件写盘只在 `eventlog.py`；三库访问只在 `stores.py`。其他文件不得各自直连数据库/直写事件文件。
3. **实验与可复用分离**：结果数据放 `out/`，可复用逻辑放 `lit_agent_min/`——升级 Phase 1 时只搬 `lit_agent_min/`，`steps/` 的结论留在 `RESULTS.md`。
4. **命名规则**：脚本 `s<step>_<purpose>.py`；模型类用名词单数（`Paper`、`Claim`）；事件类型用 `snake_case`（`phase_change`）；产物文件名含 `run_id` 便于回放（如 `reports/T1-p0-s5-001.md`）。
5. **配置不外泄**：阈值/路径/白名单一律来自 `config.local.yaml`，代码内不得硬编码（Phase 1 同样适用）。
6. **文档同步**：新增/重命名文件必须更新本表（§1.1.1）与 `README.md`；这也是后续所有 step 文档的强制要求（见 `implementation/implementation-guide.md` §15.6）。

### 1.2 环境初始化（一次性）
```bash
cd prototype
uv init --python 3.11 .
uv add httpx pyalex arxiv pymupdf pdfplumber qdrant-client kuzu sqlalchemy pydantic pydantic-settings tiktoken litellm langgraph langgraph-checkpoint-sqlite
uv add --dev pytest pytest-asyncio ruff respx
cp .env.example .env      # 填 DEEPSEEK_API_KEY
uv run python -c "import kuzu, qdrant_client, langgraph; print('ok')"
```

### 1.3 最小埋点要求（贯穿所有 Step）
事件以 JSONL 落 `out/events.jsonl`，**字段与 `implementation/implementation-guide.md` §2.2 一致**（Phase 1 直接迁到 SQLite 事件表）：
```json
{"id":1,"run_id":"p0-s5-001","seq":1,"ts":"2026-01-01T03:00:00Z","type":"phase_change",
 "stage":"retrieve","agent":"single","severity":"info","payload":{},"schema_version":"1.0"}
```
四类必写：`phase_change` / `tool_call` / `llm_call` / `error`（守卫与指标另加 `guard_trigger`、`metric`）。
**规则**：先落盘后使用；失败也要写 `error` 事件；`llm_call` 必须含 provider/model/token/时延/成本。

> 完整字段字典、脱敏规则、轮转与调试开关见 `logging-and-observability.md`；本阶段只实现其中的**最小基线**（Step 0.3）。

### 1.4 记录模板（`RESULTS.md` 每步一行 + 一段说明）
| Step | 结论 | 关键数字 | 证据文件 | 是否影响设计 | 日期 |
|---|---|---|---|---|---|
| S1 | 例：OpenAlex 覆盖达标 | venue 覆盖 82%、OA 率 41% | `out/s1_coverage.csv` | 是（白名单加 arXiv 补漏） | |

**记载要求**：数字必须可追溯到证据文件；"结论为负"同样要记录并给出替代方案；被推翻的假设同步回写主文档（§8）。

---

## 2. Step 0：项目初始化

### Step 0.1 环境与骨架（时间盒 0.5 天）
**内容要求**
1. 执行 §1.2 全部命令，确认依赖可 import；
2. 按 §1.1 建目录树，并**按 §1.1.1 建立"文件职责表"**（可先放 `README.md` 或独立 `FILEMAP.md`）：每行写路径 / 功能责任 / 关键接口 / 输入→输出 / 依赖 / 归属 Step / Phase 1 归属；
3. 建 `.env.example`、`config.local.yaml`（含：providers、storage 路径、source 白名单、guards 初值）；
4. 写 `README.md`：如何运行、需要哪些密钥、已知限制、各 Step 命令索引与文件职责表链接；
5. 建 `RESULTS.md`（表头 + 空行）。

**交付物**：可运行的 `prototype/` 骨架 + 依赖锁定（`uv.lock`）。
**验收标准**
- `uv run python -c "import lit_agent_min"` 成功（导入自检脚本打印版本与配置路径）；
- 缺 `DEEPSEEK_API_KEY` 时给出清晰报错而非堆栈崩溃；
- `uv run ruff check .` 通过；
- **文件职责表与实际目录一致**：脚本 `ls` 得到的文件与表中行一一对应，无"表里没有的文件"或"表里有但不存在"。
**失败应对**：依赖冲突 → 降级到 `pip` 临时环境并记录；Windows 编译问题 → 换预编译 wheel（Kuzu/Qdrant 均为纯 wheel，一般无编译）。

### Step 0.2 最小契约与事件写入（时间盒 0.5 天）
**内容要求**（`lit_agent_min/`）
1. Pydantic 模型：`Paper`、`EvidenceCard`、`Claim`、`Event`、`Verdict`（字段抄 `implementation/implementation-guide.md` §2.3，**只落 Phase 0 用得到的**）；
2. `eventlog.py`：`emit(type, stage, payload, ...)` 追加 JSONL，带 `seq` 自增与 `run_id`；
3. `config.py`：YAML + env 读取，含安全默认；
4. 单测：模型 JSON 往返、事件 seq 单调、配置缺项报错。

**交付物**：`lit_agent_min/{models.py,eventlog.py,config.py}` + `tests/test_contracts.py`。
**验收标准**
- `uv run pytest -q` 全绿；
- 连续 `emit` 3 条事件，`events.jsonl` 行数 = 3 且 `seq` 为 1/2/3；
- 任一必填字段缺失时抛结构化错误（含字段名）。
**失败应对**：模型字段不确定 → 先在 `RESULTS.md` 记录"待 Phase 1 冻结"，用最小字段集继续。

### Step 0.3 最小日志基线（时间盒 0.5 天）

**内容要求**
1. `lit_agent_min/logging.py`：structlog JSON 配置（字段照 `logging-and-observability.md` §2.1）；`bind_context()` 绑定 `run_id/stage`；脱敏 processor（密钥 / 邮箱 / 家目录路径 / 正文摘要）；双 handler（`logs/app.jsonl` + 控制台）；`error` 级额外写 `logs/errors.jsonl`；
2. 把三条纪律落进代码：`info` 不含正文；错误必带 `error_code`；外部调用**双写**（日志 + 事件）；
3. README 增补"日志查看"段：5 条 `jq` 命令（规范 §9：按 run 取时间线、按错误码过滤、慢调用 Top10、阶段耗时均值、错误码计数）。

**交付物**：`lit_agent_min/logging.py`、`tests/test_logging.py`、README 日志查看段。
**验收标准**
- 一次 S5 run 后，`logs/app.jsonl` 与 `out/events.jsonl` 可用 `run_id` 互相定位（三向关联第一环打通）；
- 错误行 **100%** 带 `error_code`；`info` 行经自动扫描无正文；
- 脱敏用例（密钥 / 邮箱 / 家目录路径 / 长正文）全部通过；
- 日志写入开销 **< 3%**（S5 计时对比）。
**失败应对**：字段与规范冲突 → 改代码不改规范（规范为唯一口径）；开销超标 → 减 debug 明细，但保持 info 字段完整。

---

## 3. W1：四项可行性验证（Step 1–4）

### Step 1（S1）数据源覆盖度验证（时间盒 1 天）
**要回答的问题**：OpenAlex 为主 + arXiv 为辅，能否覆盖我的目标方向与 venue？OA 全文可得率多少？
**内容要求**
1. 选 1–2 个候选测试 topic（英文，如 "multi-agent LLM orchestration reliability"、"quantized VLM deployment on edge devices"）；
2. 用 OpenAlex API（带 `mailto`）查询：近 3 年、按 venue 白名单过滤、按 relatedness/搜索词召回，取前 100–200 篇；
3. 统计并导出 CSV：
   - 白名单 venue 命中数 / 目标领域论文总数 = **venue 覆盖率**；
   - `referenced_works`（引用字段）非空比例 = **引用完整率**；
   - 有 OA 全文链接（`best_oa_location`）比例 = **OA 可得率**；
   - arXiv 侧：同 topic 用 category 查询，统计与 OpenAlex 结果的重叠/补漏数 = **补漏率**；
   - 抽取 10 篇人工抽查元数据正确性（作者、年份、venue）。
4. arXiv 官方 API 礼貌限速验证：连续 20 次请求无封禁、退避生效。
**执行命令（示例）**
```bash
uv run python steps/s1_source_coverage.py --topic T1 --years 3 --limit 200 --out out/s1_coverage.csv
```
**期望输出**：`out/s1_coverage.csv` + 控制台打印四个百分比 + 10 篇抽查结论。
**验收标准**
- 四个数字齐备且可追溯到 CSV；
- 10 篇抽查元数据正确率 ≥ 90%；
- 明确回答："只用 OpenAlex 会漏什么？arXiv 补上多少？"
**失败应对**：覆盖率 < 60% → 记录并评估加 DBLP/Crossref/自定义源；OA 率 < 20% → 确认"仅摘要"为默认策略，评测 grounding 口径写入文档。

#### Step 1b（S1b）检索策略 / 去重 / 过滤后引用完整率（S1 的衍生，时间盒 0.5–1 天）

**要回答的问题**（S1 只测了"覆盖与噪声"，这些是"怎么检索、怎么去重"的可行性）
1. **白名单过滤后的引用完整率**是多少（宽召回样本仅 ~18%，过滤后是否显著更高）→ 决定关联图是否需要 Crossref 补源；
2. **去重方案**是否可行：同标题/同 DOI 的多版本占多少？指纹去重后剩多少唯一论文？
3. **检索策略**怎么选：宽召回 / 白名单过滤 / 多查询扩展并集 → 产出量、白名单命中、彼此重叠（Jaccard）；
4. **增量游标**语义：`from_updated_date` 是否可用？游标分页是否稳定？是否存在回溯更新（updated ≫ published）？

**内容要求**
- 脚本 `steps/s1b_retrieval_and_dedup.py`：三策略抓取（每策略记录 strategy 标签）+ 去重统计 + 完整性统计 + 增量探测；
- 白名单读自 `config.sources.venues`（**必须是人工确认的 source id**，见 S1 结论 3）；
- 产出 `out/s1b_records.csv`（逐条含 strategy/去重键）与 `out/s1b_summary.json`（四项结论 + 数字）。

**执行命令**
```bash
uv run python steps/s1b_retrieval_and_dedup.py --topics T1,T2 --years 3 --per-page 100
```

**验收标准**
- 四个问题都有数字，且可追溯到 CSV/JSON；
- 给出**检索策略结论**（默认策略 + 是否需要查询扩展）与**去重键结论**（指纹够不够、是否需要标题+DOI+年份组合键）；
- 增量探测给出"时间戳游标是否可用/分页是否稳定"的明确答复。

**失败应对**：空间不足或接口限制导致策略 3 不可跑 → 保留策略 1/2 结论并记录；引用完整率仍低（<50%）→ 在 S3/S5 前把 Crossref 补源列入计划。

**实测结果（2026-10-07，脚本已交付）**

| topic | broad n/refs | whitelist n/refs/OA | expansion n/refs | 重复率 | 唯一/总 |
|---|---|---|---|---|---|
| T1 | 100 / 27.0% | 200 / **1.5%** / 100% | 211 / 1.9% | 19.8% | 410/511 |
| T2 | 100 / 25.0% | 147 / **14.3%** / 100% | 236 / 9.8% | 19.3% | 390/483 |

**结论（三项改动直接进入 S5 前置）**
1. **白名单必须作主通道**：白名单与宽召回标题重叠 **Jaccard 0.014/0.004**，白名单中 196/146 篇是宽召回没捞到的 → 只做宽召回会系统性漏目标会议论文；
2. **去重键必须是三元组**：同标题多记录 19.3–19.8%（version copies 101/93）→「DOI + 归一化标题 + 年份」合并为一条主记录并保留 `merged_ids`；
3. **引用图要反向构边**：白名单记录引用完整率仅 1.5%/14.3%（宽召回 25–27%），DOI 交叉核对确认**不是版本问题**（AAAI/IJCAI/ACL proceedings 记录本身无 references）→ 用 `cited_by` 反向构边 + 后续评估 Crossref；评测注明引用覆盖不完整；
4. **增量改用 publication_date 水位线**：`from_updated_date` 为付费专属（429 Plan upgrade required）；`from_publication_date + sort=publication_date:desc + cursor` 可用且稳定（page1 两次一致、page2 与 page1 重叠 0）；并对"未来日期"记录（实测到 2050-02-21）做合理性过滤。

### Step 2（S2）本地 vs 云质量基线（时间盒 1 天）

> **⏸ 本轮不做（2026-10-07 决定）**：项目当前只使用**云端 DeepSeek API**，本地模型不测试、不考虑；本节保留为将来（若恢复本地档需求）的执行定义。S5 的依赖因此为 **1、3、4**（不含 S2）。
**要回答的问题**：本地小模型（Ollama）在哪些任务上可用？质量差多少、成本与延迟差多少？
**内容要求**
1. 任务集 20 条（固定、可复跑）：10 条**字段抽取**（从摘要抽方法/年份/任务）+ 5 条**摘要概括** + 5 条**相关性判定**（相关/不相关）；
2. 两个引擎同任务跑：`local = ollama qwen2.5:7b`（或当前可用最小模型）、`cloud = DeepSeek`；
3. 评分：抽取类按字段命中率，概括类按 1–5 人工/规则评分，判定类按准确率；
4. 记录每条的 token、时延、成本（本地记 0）。
**执行命令（示例）**
```bash
uv run python steps/s2_model_baseline.py --tasks out/s2_tasks.yaml --local ollama/qwen2.5:7b --cloud deepseek/deepseek-chat --out out/s2_results.csv
```
**期望输出**：`out/s2_results.csv` + 一张对比表（任务类型 × 引擎：准确率 / P50 时延 / token / 成本）。
**验收标准**
- 20 条全部有结果（失败也记录原因）；
- 给出**可执行结论**：如"抽取/分类类本地可用（≥70%），长文概括必须走云"；
- 敏感度路由规则据此确认（哪类任务允许走本地）。
**失败应对**：本地模型无法安装/太慢 → 记录环境结论，Phase 0 后续全部走云，本地档留待 P3 再验证。

### Step 3（S3）存储栈验证（时间盒 1 天）
**要回答的问题**：Kuzu + Qdrant local 在万级规模下的导入、查询、幂等表现是否够用？
**内容要求**
1. 用 S1 抓取的真实元数据（不足 5k 则用 S1 结果 + 复制扰动凑到 5k，标注为合成数据）导入；
2. 写入：SQLite（最小 `papers` 表）+ Kuzu（Paper/Author 节点 + PAPER_AUTHOR/CITES 边，全部 MERGE）+ Qdrant（`papers` collection，随机向量或 bge 向量二选一，注明）；
3. 跑四类查询并计时：
   - 向量 top-10 检索（含 topic/year 过滤）；
   - 图 2-hop（作者 → 论文 → 引用）；
   - 作者近 3 年发文聚合；
   - **重复导入一次**（验证幂等：节点/边/向量计数不变）；
4. 记录：导入耗时、查询 P95、磁盘占用、失败条数。
**执行命令（示例）**
```bash
uv run python steps/s3_storage_spike.py --papers 5000 --out out/s3_storage.json
```
**期望输出**：`out/s3_storage.json`（含各指标）+ 控制台结论。
**验收标准**（示例目标，可调）
- 导入 5k ≤ 5 min；向量查询 P95 ≤ 100 ms；图 2-hop P95 ≤ 200 ms；磁盘 ≤ 500 MB；
- 重复导入：三库计数零增长（幂等通过）；
- 明确回答："Kuzu/Qdrant 是否需要换 Neo4j/Milvus？"（默认预期：不需要）。
**失败应对**：Kuzu 写入失败/性能不达标 → 记录具体瓶颈，评估 Neo4j；Qdrant local 内存问题 → 评估 server 模式或 LanceDB。

### Step 4（S4）长跑恢复验证（时间盒 0.5 天）
**要回答的问题**：LangGraph checkpoint 在进程中断后能否恢复到正确位置，且事件不重不漏？
**内容要求**
1. 3 节点小图（`fetch → transform → emit`），每节点写事件、sleep 模拟耗时；
2. `SqliteSaver` 持久化，`thread_id = run_id`；
3. 在节点 2 执行中 `Ctrl+C`/kill 进程 → 重启 → 从 checkpoint 续跑；
4. 校验：节点 1 不重跑；节点 2 完成；事件序号连续且无重复语义事件。
**执行命令（示例）**
```bash
uv run python steps/s4_checkpoint_spike.py --run-id p0-s4-001   # 中途 Ctrl+C 后再次执行同命令
```
**期望输出**：两次运行的 `out/events_s4.jsonl` + 恢复成功结论。
**验收标准**
- 恢复后最终状态与"不中断跑完"一致；
- 已完成节点不重复执行（用事件计数验证）；
- 记录"恢复点粒度 = 节点边界"这一结论（写进守卫文档）。
**失败应对**：恢复语义不符预期 → 记录框架行为（这本身是有价值结论），Phase 1 调整 checkpoint 配置或自管状态。

---

## 4. W2：最小闭环（Step 5）

### Step 5（S5）Walking Skeleton：单 topic 端到端（时间盒 2.5 天）
**要回答的问题**：从"新论文"到"一份可核验的报告"这条链，能否在一个脚本里跑通？接口/schema/成本是否可行？
**内容要求**（按子步骤交付，每子步可单独运行与验证）
| 子步 | 内容 | 交付物 | 验收 |
|---|---|---|---|
| 5.1 fetch | OpenAlex + arXiv 拉取 topic 近 3 年论文（增量游标落 SQLite `sync_state`） | `steps/s5_fetch.py` | 连续两次运行第二次新增 ≈ 0 |
| 5.2 normalize | 转统一 `Paper`（canonical_id：DOI→W→arxiv，作者 `name_norm`） | `lit_agent_min/normalize.py` | 单测：id 优先级、缺字段、多作者 |
| 5.3 parse+chunk | OA PDF → PyMuPDF（失败 pdfplumber 兜底）→ 递归分块（token 预算） | `steps/s5_parse.py` | 坏 PDF 有 fallback；分块 token ±10% |
| 5.4 store | 写 SQLite/Kuzu/Qdrant（MERGE/upsert 幂等） | 复用 `lit_agent_min/stores.py` | 重复运行计数不变 |
| 5.5 retrieve | 向量 top-k + 过滤 + 去重 → `EvidenceCard` 列表 | `steps/s5_retrieve.py` | 卡片带 paper_id/来源/片段 |
| 5.6 report | LLM 依证据卡生成 markdown 报告；解析出 claims 及 citation | `out/reports/<topic>-<date>.md` + `claims.json` | 报告 ≥ 800 字；≥10 条 claim 且 100% 带 citation |
| 5.7 events | 全流程写事件（phase/tool/llm/error） | `out/events.jsonl` | 单次 run 事件 ≥ 30 条，可按 seq 回放 |
**执行命令（示例）**
```bash
uv run python steps/s5_walking_skeleton.py --topic T1 --run-id p0-s5-001
```
**期望输出**：一份报告文件 + `claims.json` + 完整事件日志 + 一份"本次成本/耗时"摘要。
**验收标准**
- 端到端一次跑通（允许人工在 curl/HTTP 层兜底，但要在 README 记录）；
- 报告每条 claim 的 citation 能在本次语料中回查到（用脚本核对，输出支持率）；
- 重跑一次：论文记录数不变、成本可重复（±30%）。
**失败应对**：报告质量差 → 记录"证据卡信息量不足"的结论，改进检索而非先改提示词；链路太长导致超时 → 拆分为两个脚本并记录真实耗时（这本身就是成本数据）。

---

## 5. W3：守卫与指标（Step 6–7）

### Step 6（S6）两个守卫 + 预算看门狗 + 注入钩子（时间盒 2 天）
**内容要求**
1. **G1 漂移守卫**：`cos(embed(阶段产物摘要), embed(scope_statement))`；初值 warn < 0.60 / block < 0.45；命中写 `guard_trigger`；动作 = 回退到检索并注入"恢复包"（失败原因 + 可信状态 + 下一步约束）；
2. **G4 循环守卫**：工具调用签名（工具名+参数哈希）窗口 k=5 成环检测；命中 → 强制 replan（Phase 0 用"清空本轮查询并换策略"模拟）→ 再次命中 → 终止并 annotate；
3. **预算看门狗**：run 级 token/时长上限（先设 80% warn、100% stop），超限写 `metric` + `guard_trigger`；
4. **注入钩子**：`INJECT=<scenario>` 环境变量或 `--inject` 参数，支持：`drift`（返回越界结果）、`loop`（重复工具序列）、`stagnation`（无新增）、`timeout`（provider 超时）、`budget`（人为放大 token 计数）；
5. 守卫判决必须是结构化 `Verdict`，并写事件。
**执行命令（示例）**
```bash
uv run python steps/s6_guards_demo.py --topic T1 --inject drift --repeats 3
uv run python steps/s6_guards_demo.py --topic T1 --repeats 3      # 正常样本（测误报）
```
**期望输出**：`out/guards_<scenario>.jsonl`（完整事件链）+ 一页结论。
**验收标准**
- 四类注入各 3 次：**检出率 ≥ 90%**，处置动作符合预期，能恢复到正常完成态或按规则终止；
- 3 次正常 run：**误报 = 0**（否则调阈值并记录过程）；
- 事件链可读作："起因 → 检出 → 处置 → 结果"。
**失败应对**：误报率高 → 记录阈值扫描结果（不同阈值下 TPR/FPR），确定为 Phase 1 标定输入；恢复包注入无效 → 记录 A/B 对比结论。

### Step 7（S7）最小指标集与汇总（时间盒 1 天）
**内容要求**
1. 从 JSONL 事件聚合 5 个数字：**grounding 支持率**、**幻觉率（无支撑占比）**、**漂移检出率**、**循环检出率**、**单 run 成本与时延**；
2. 输出 `out/metrics_summary.csv`（每个 run 一行）与一页结论（`RESULTS.md` 段落）；
3. 可选：一张简单柱状图（matplotlib 即可，Phase 0 不要求前端）。
**执行命令（示例）**
```bash
uv run python steps/s7_metrics.py --events out/events.jsonl --out out/metrics_summary.csv
```
**验收标准**
- 五个指标都能从事件算出，且与 Step 5/6 的原始记录一致（抽查 1 个 run 手工核对）；
- 指标口径与 `implementation/evaluation-plan.md` §5 一致（不一致要回写文档）。
**失败应对**：事件字段缺失导致算不出 → 补埋点后重跑对应 Step（这正是"埋点先于指标"的价值）。

---

## 6. Step 8：阶段收尾与决策门（时间盒 0.5–1 天）

**内容要求**
1. **汇总 `RESULTS.md`**：Step 0–7 全部结论 + 数字 + 对设计的影响；
2. **回写主文档**（逐项检查是否需更新）：
   - `project/framework-selection.md`：源覆盖结论、本地/云结论、存储结论 → 是否调整选型；
   - `design/architecture-overview.md`：接口/schema 摩擦点、恢复点粒度；
   - `design/state-machine-and-guards.md`：G1/G4 实测阈值与误报、恢复包有效性；
   - `implementation/evaluation-plan.md`：指标口径修正、OA 率对 grounding 的影响；
   - `design/agent-design-decisions.md`：把新发现的问题补成条目；
   - `implementation/implementation-guide.md`：把 Phase 0 结论固化为 Phase 1 契约（必要的 ADR）。
3. **决策门材料**：一页数字摘要 + 一个 5 分钟 demo（跑一次 S5 + 注入一次 S6）；
4. **Phase 1 启动条件确认**：见 §9。

**交付物**：`RESULTS.md` 定稿 + 文档更新提交 + 决策门一页纸。
**验收标准**：出口检查清单（§9）全绿；导师确认进入 Phase 1（或给出调整意见）。

---

## 7. 进度跟踪表

| Step | 内容 | 时间盒 | 依赖 | 状态 | 结论/数字 |
|---|---|---|---|---|---|
| 0.1 | 环境与骨架 | 0.5 d | — | ☐ 待办 / ◐ 进行中 / ☑ 完成 / ⛔ 阻塞 | |
| 0.2 | 最小契约与事件写入 | 0.5 d | 0.1 | ☑ 完成（26 passed；`demo-events` seq=1/2/3） | |
| 0.3 | 最小日志基线 | 0.5 d | 0.2 | ☑ 完成（35 passed；`demo-logging` 互查 OK） | |
| 1 | S1 源覆盖度 | 1 d | 0.2 | ☑ 完成（白名单 386 篇/3 年；arXiv 收录率 91.7%；抽查 10/10） | |
| 1b | S1b 检索/去重/引用完整率 | 0.5–1 d | 1 | ☑ 完成（重叠 0.004–0.014；重复 19%；白名单 refs 1.5%/14.3%；updated 过滤付费） | |
| 2 | S2 本地 vs 云基线 | 1 d | 0.2 | ⏸ 本轮不做（云-only） | |
| 3 | S3 存储栈 | 1 d | 0.2 | ☐ | |
| 4 | S4 断点续跑 | 0.5 d | 0.2 | ☐ | |
| 5 | S5 最小闭环 | 2.5 d | 1、3、4（S2 跳过） | ☐ | |
| 6 | S6 守卫与注入 | 2 d | 5 | ☐ | |
| 7 | S7 指标聚合 | 1 d | 5, 6 | ☐ | |
| 8 | 收尾与决策门 | 0.5–1 d | 1–7 | ☐ | |

**合计 ≈ 10.5 个工作日。** 节奏建议：每天结束时更新本表 + `RESULTS.md`；每完成一个 Step 提交一次 Git。

---

## 8. 常见失败与应对

| 症状 | 应对 |
|---|---|
| 某 spike 结论为负（如本地模型太弱） | **不是失败**：如实记录数字与影响，调整路由策略并回写选型文档 |
| 时间超预算（某步 > 1.5× 时间盒） | 停止深挖，记录"未验证"与原因，进入下一步；把深挖项写进 Phase 1 待办 |
| 源 API 限流/字段变动 | 礼貌限速 + 退避；保留原始响应作为 fixture；必要时换查询参数 |
| 链路太长一次跑不通 | 拆成子步单独可跑（S5 已按子步设计），先保证每段有验收 |
| 指标算不出来 | 补埋点重跑；不要手工估算 |
| 想顺手做 UI/调度 | 记入 Phase 1 待办，**不在 Phase 0 做** |

---

## 9. Phase 0 出口检查清单（逐项勾选）

- [ ] Step 0：环境可复现（README + uv.lock）；事件 JSONL 格式与 §2.2 对齐；**日志可用 `run_id` 与事件三向定位、错误行 100% 带 `error_code`、info 无正文**；
- [x] S1：四项数字齐，且白名单 venue 3 年召回 386 篇（≈129/年，下限）、arXiv 收录率 91.7%、抽查 10/10；
- [x] S1b：检索策略（白名单主通道 + 多查询扩展）、去重键（DOI+标题+年份）、增量语义（publication_date 水位线）三项结论齐，引用覆盖缺口已量化；
- [~] S2 **本轮豁免**：只用云端 DeepSeek API（本地档测试推迟，见 Step 2 注记）；
- [ ] S3：5k 导入与四类查询达标，**重复导入幂等**，给出是否需要换库的结论；
- [ ] S4：中断恢复成功，已完成节点不重跑，恢复粒度结论已记录；
- [ ] S5：单 topic 出报告（≥800 字、≥10 claim、100% 带 citation、事件 ≥30 条），重跑幂等；
- [ ] S6：四类注入检出率 ≥ 90%、正常样本误报 0、事件链完整；
- [ ] S7：5 个指标可从事件算出，与 `implementation/evaluation-plan.md` 口径一致；
- [ ] Step 8：`RESULTS.md` 定稿、六份文档回写、决策门材料就绪；
- [ ] 导师确认 → 启动 Phase 1。

---

## 10. 与 Phase 1 的衔接

**保留并升级到正式仓库**
- `lit_agent_min/` 的 Pydantic 模型与事件写入（→ `src/lit_agent/models/`、`runtime/events.py`）；
- S5 的分步脚本逻辑（→ `sources/`、`parsing/`、`stores/`、`agents/`）；
- S6 的守卫检测函数与注入钩子（→ `graph/guards.py`、`eval/faultinject.py`）；
- S7 的指标聚合（→ `eval/metrics.py`）。

**丢弃**
- `steps/` 下的胶水脚本、`out/` 产物、合成数据（保留真实抓取结果作 fixture）。

**Phase 1 第一张正式任务卡**（示例，来自 `implementation/implementation-guide.md` 附录 B）
```
Task ID: W1-CFG-01
Goal: 配置加载（YAML+env，含安全默认）
Files: src/lit_agent/config.py, tests/unit/test_config.py
Depends: Phase 0 Exit Gate 通过
Acceptance: uv run pytest -q tests/unit/test_config.py；空配置启动自检通过
Forbidden: 修改 §2 冻结契约；新增未批准依赖
```

**数据源优化 backlog（来自 S1/S1b，转入 Phase 1，不在 Phase 0 继续）**

| 优化项 | 归属 | 前置/触发 |
|---|---|---|
| 白名单扩充与治理（硬件/EDA/网络/系统；source id 人工确认） | `sources/` | 每 topic 订阅集定义 |
| 三段式去重 + `merged_ids`（需 ADR 改 `Paper` 契约） | `sources/normalize.py` | S5 前置 |
| `cited_by` 反向构边 + 引用覆盖率指标 | `stores/graph.py` + 评测 | S3 之后 |
| Crossref 补引用评估 | 待评估 | 反向构边不足时 |
| topic 质心相关性过滤（embedding） | 检索 agent | Qdrant 就绪（P3） |
| publication_date 水位线增量 + 日期校验 + 周期性浅刷新 | `runtime/` + `sources/` | S3/S5 |
| 滚雪球（references + citers）召回通道 | `sources/` | 同上 |

> 数据源 track 的可行性验证已在 **S1 + S1b 收口**（结论、数字与 backlog 见 `prototype/RESULTS.md` §2.5–§2.7）。Phase 0 剩余：S3 存储栈、S4 断点续跑、S5 最小闭环。

> 使用方式：把本文件当"施工日志"。每完成一步，在 §7 表里改状态、在 `RESULTS.md` 记数字、在 §9 勾一项；全部勾完即 Phase 0 完成，可向导师申请开工 Phase 1。
