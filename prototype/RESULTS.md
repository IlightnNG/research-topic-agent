# Phase 0 结果记录（RESULTS）

> 用途：Phase 0 每步的**结论台账**——结论 / 关键数字 / 证据文件 / 是否影响设计。
> 规则：数字必须可追溯到证据文件；"结论为负"同样记录并给出替代方案；被推翻的假设同步回写主文档。

## 1. 进度记录

| Step | 结论 | 关键数字 | 证据文件 | 是否影响设计 | 日期 | 状态 |
|---|---|---|---|---|---|---|
| 0.1 | 骨架/配置/自检就绪，**`uv run` 全链路验收通过** | `uv.lock` 935,775 B（111 包）；pytest 7/7；ruff check+format 通过；selfcheck 0/2/0；import ok（CPython 3.11.17 托管） | `README.md`、`FILEMAP.md`、`uv.lock` | 是（新增 2 条环境约束，见 §2.1） | 2026-10-05 | ☑ 完成 |
| 0.2 | 契约与事件写入完成，19 用例覆盖约束与并发 | pytest 26 passed（0.1 的 7 + 0.2 的 19）；`demo-events` → `lines=3 seqs=[1,2,3]`；ruff check + format 通过；版本 0.2.0 | `lit_agent_min/models.py`、`lit_agent_min/eventlog.py`、`tests/test_contracts.py` | 是（判定：事件 seq 按 run 独立 + 损坏行必须报错） | 2026-10-05 | ☑ 完成 |
| 0.3 | 日志基线交付；事件与日志可用 `run_id` 互查 | pytest 35 passed（7+19+9）；ruff/format 通过；`demo-logging` → events=3 / logs=3 / errors=1，`[OK]` 互查；版本 0.3.0 | `lit_agent_min/logging.py`、`tests/test_logging.py`、`logs/app.jsonl` | 是（判定：正文守卫在 info+ 生效、ERROR 必带 error_code） | 2026-10-05 | ☑ 完成 |
| 1 (S1) | 源覆盖度验证完成：**OpenAlex 为主成立**，arXiv 价值在时效而非补漏 | 白名单 venue 3 年召回 **386 篇（≈129/年，缺 NeurIPS/ICLR/OSDI，属下限）**；arXiv 预印本 OpenAlex 收录率 **91.7%（11/12）**；宽召回样本白名单命中仅 3.5–5%；OA 率 90–93%；引用完整率 18%；限速 20/20 无 429（p50 1.09s）；抽查 10/10 | `out/s1_coverage.csv`、`out/s1_coverage.json`、`out/s1_deep.log` | 是（见 §2.5：检索必须白名单过滤+去重；venue 白名单必须用 source id） | 2026-10-07 | ☑ 完成 |
| 1b (S1b) | 检索策略/去重/引用完整率验证完成，出现 3 个反直觉但决定性的发现（见 §2.6） | 白名单 vs 宽召回重叠 Jaccard 仅 **0.004–0.014**；查询扩展新增 **126/155** 篇；重复率 **19.3–19.8%**（version copies 101/93）；白名单引用完整率 **1.5%/14.3%（低于**宽召回 27%/25%）；`from_updated_date` **付费专属（429）**，`from_publication_date` 可用且游标分页稳定（page2 overlap=0）；发现 2050 年未来日期记录 | `out/s1b_records.csv`、`out/s1b_summary.json`、`out/s1b_run.log` | 是（检索必须显式白名单+多查询；引用图需反向边/Crossref；增量改用 publication_date 水位线） | 2026-10-07 | ☑ 完成 |
| 2 (S2) | **本轮不做**：项目当前只使用云端 DeepSeek API，本地模型不测试、不考虑 | — | — | 是（评测的 local vs cloud 对比维度延后；路由暂无本地分支） | 2026-10-07 | ⏸ 延后 |
| 3 (S3) | 存储栈验证完成：**三库方案成立，不需要换 Neo4j/Milvus**；唯一未达标项是向量检索延迟 | 5k 导入 sqlite 0.22s / kuzu 169.46s / qdrant 26.78s；图 2-hop p95 **4.42ms**、聚合 p95 5.06ms、向量 top-10 p95 **155.45ms（>100ms 目标）**、sqlite p50 0.07ms；幂等重导计数零增长；删库重建 376.53s 且计数一致；磁盘合计 **64.9MB**（kuzu 12.89 / qdrant 49.06 / sqlite 2.95）；20000 边全走 MERGE；并行访问被拒（单写者） | `out/s3_storage.json`、`out/s3_run_5000.log`、`out/events.jsonl` | 是（新增 F7：Kuzu 单文件路径 / 仅 Database.close() 落盘 / 非 ASCII 路径；新增 E_STORE_NOT_EMPTY 与计数对账守卫；向量延迟进 Phase 1） | 2026-10-08 | ☑ 完成 |
| 4 (S4) | — | — | — | — | — | ☐ |
| 5 (S5) | — | — | — | — | — | ☐ |
| 6 (S6) | — | — | — | — | — | ☐ |
| 7 (S7) | — | — | — | — | — | ☐ |
| 8 | — | — | — | — | — | ☐ |

状态图例：☐ 待办 / ◐ 进行中 / ☑ 完成 / ⛔ 阻塞

## 2. Step 0.1 记录

**已完成**
- 目录骨架与依赖清单：`pyproject.toml`、`.python-version`(3.11)、`.gitignore`
- 配置：`config.local.yaml`、`config.example.yaml`、`.env.example`
- 最小内核：`lit_agent_min/{__init__.py, config.py, __main__.py, py.typed}`
- 验收单测：`tests/test_config.py`（7 个用例：加载/路径解析/错误可预期/未知键拒绝/密钥校验/目录创建/退出码）
- 文档：`README.md`、`FILEMAP.md`、本文件

**本机环境事实（2026-10-05 实测）**
| 项 | 现状 | 影响与处理 |
|---|---|---|
| uv | ✅ 0.12.23（`pip install uv`，用户级） | `uv lock` 生成锁文件；`uv sync` 全量安装成功（托管 CPython 3.11.17） |
| Python | uv 托管 **CPython 3.11.17**（`uv python install 3.11`，位于 `.uv-python/`） | 项目运行使用托管解释器；系统另有 3.14（仅语法检查）与 Anaconda 3.11.5（未使用） |
| git | 工作区已是仓库，分支 `main` | 按约定应切 `prototype` 分支；**尚未切换**（待确认） |
| ruff / pytest | 本机验证时装在工作区 `.pylibs`；标准路径是 `uv sync` | 两者均已跑通（见下表） |
| 沙箱/临时目录 | 早期策略禁止写 harness 临时目录，`venv`/`pip` 报 `PermissionError` | 把 `TEMP/TMP/PIP_CACHE_DIR/UV_CACHE_DIR` 重定向到工作区内 `.tmp/.pip-cache/.uv-cache`（已入 `.gitignore`） |
| 工作区路径含中文 | `E:\大学\...` 触发 `site.py` GBK 解码 `.pth` 失败 | 见 §2.1：关闭可编辑安装（`package = false`）+ 托管解释器 + pytest `pythonpath` |

**验收数字（Step 0.1）**
| 验收项 | 命令 | 结果 |
|---|---|---|
| 依赖锁定 | `uv lock` | ✅ `uv.lock` 935,775 B，解析 111 个包 |
| 依赖安装 | `uv sync --python 3.11 --python-preference only-managed` | ✅ exit 0（托管 CPython 3.11.17） |
| 导入自检 | `uv run python -c "import lit_agent_min"` | ✅ `import ok 0.1.0 3.11.17` |
| 单元测试 | `uv run pytest -q` | ✅ 7 passed |
| 代码规范 | `uv run ruff check .` | ✅ All checks passed |
| 格式化 | `uv run ruff format --check .` | ✅ 7 files already formatted |
| 自检（宽松） | `uv run python -m lit_agent_min selfcheck --lax` | ✅ exit 0（缺密钥仅告警） |
| 自检（严格·缺密钥） | `uv run python -m lit_agent_min selfcheck` | ✅ exit 2 + 修复指引（无堆栈） |
| 自检（有密钥） | `DEEPSEEK_API_KEY=sk-fake … selfcheck` | ✅ exit 0 |
| 目录创建 | `ensure_dirs`（selfcheck 内） | ✅ 首次创建 6 个目录；重复调用不重建 |

**待办（关闭 Step 0.1 的最后一步）**
1. 切到 `prototype` 分支并提交 `step-0.1: skeleton + config + selfcheck`；
2. 核对 `FILEMAP.md` 与实际目录一致（README 提供现成命令）。

## 2.1 实际执行中发现的问题（已修复）

| 问题 | 根因 | 修复 |
|---|---|---|
| `test_ensure_dirs_creates_layout` AttributeError | 测试里误写 `settings.logs_dir`（正确为 `settings.paths.logs_dir`） | 修正断言 |
| ruff 报 1 个 import 顺序错误 | `tests/test_config.py` 导入未按 isort 排序 | `ruff check --fix` + `ruff format` |
| `venv`/`pip` PermissionError | 沙箱限制写 harness 临时目录 | 当时把 `TEMP`/缓存重定向到工作区内；**环境归位后已不再需要**（见 §2.2） |
| `uv run` 全部 exit 2，`site.py` 报 `UnicodeDecodeError: 'gbk' codec … byte 0xad` | 可编辑安装生成的 `.pth` 内含中文路径（`E:\大学\…`，0xAD 为"学"的 UTF-8 第二字节），中文 Windows 下 `site.py` 以 GBK 读取该 UTF-8 文件 | ① `pyproject.toml` 设 `[tool.uv] package = false`（Phase 0 不装本项目）；② 改用托管解释器 `uv python install 3.11` + `--python-preference only-managed`；③ `[tool.pytest.ini_options] pythonpath = ["."]` 保证 pytest 能 import |
| 旧 venv 残留损坏的 `.pth`，连解释器自身都起不来 | 失败的 sync 留下了 `_editable_impl_*.pth` | 删除 `.venv` 重建 |

> **经验（写入 Phase 1 待办）**：根因是**工作区路径含中文**。实测（Python 3.11.17 / cp936）：`-X utf8` 与 `PYTHONUTF8=1` **不能**修复——`site.py` 以 `encoding="locale"` 读 `.pth`，该别名取 `locale.getencoding()`（恒为 cp936），而 UTF-8 模式只改 `getpreferredencoding()`（诊断输出：`utf8_mode=1, getencoding=cp936, getpreferred=utf-8`）。因此：① **根治 = 正式仓库改用纯 ASCII 路径**（恢复 `package = true` 与可编辑安装）；② 现用规避 = `package = false`，代价是 `import lit_agent_min` 只在项目目录下有效（从仓库根运行实测 `ModuleNotFoundError`）；③ 备选 = `uv sync --no-editable`（未实测）。

## 2.2 布局调整记录（2026-10-05）

| 项 | 变更 | 影响 |
|---|---|---|
| 代码位置 | `code/prototype/` → **`prototype/`**（仓库根，与 `docs/` 平级）；`code/` 目录删除 | 文档中 `code/...` 引用已批量更新；`implementation-guide.md` §1.1 与 Phase 0 §1.1 的目录树改为"仓库根 = 项目根" |
| 正式仓库规划 | Phase 1 起在**仓库根**建 `src/`、`tests/`、`config/`、`migrations/`、`web/`、`eval_data/` | 不再有 `code/` 中间层 |
| 根级 `.gitignore` | **追加**（保留原有条目）：`.local/`、`.uv-cache/`、`.uv-python/`、`.pylibs/`、`.pip-cache/`、`.tmp/`、`out/`、`logs/`、`node_modules/`、`dist/` | 本地产物不入库 |
| uv 缓存/解释器 | 从工作区 `.local/` 迁到 **uv 默认位置**（`…\AppData\Local\uv\cache`、`…\AppData\Roaming\uv\python`），随后删除 `.local/` | 后续只需标准 `uv sync`，不再需要 `UV_CACHE_DIR`/`UV_PYTHON_INSTALL_DIR`/`TEMP` 重定向 |
| `.venv` | 删除后在新位置重建（避免残留绝对路径） | 426 MB 重新生成 |
| 验收重跑（新位置） | `uv sync` exit 0；`import ok 0.1.0 / 3.11.17`；`pytest` 7 passed；`ruff check`+`format --check` 通过；`selfcheck` **0 / 2 / 0** | 搬迁后功能等价 ✅ |
| Git 暂存区 | 索引中仍是 `AD code/prototype/...`（已暂存后删除）与 ` M .gitignore` | 需 `git add -A` 记录搬迁，再提交 `step-0.1: prototype at repo root` |
| 根级 `README.md` | **未改动**（属你已有的项目概览，2026-09-17） | 开发者快速开始见 `prototype/README.md` |

## 2.3 Step 0.2 记录（契约与事件写入）

**交付物**
- `lit_agent_min/models.py`：`Author / Paper / EvidenceCard / Citation / Claim / Verdict / Event` + 枚举 `Severity / EventType / GuardAction / Support`；
- `lit_agent_min/eventlog.py`：`EventSink` 协议 + `JsonlEventLog`（append-only、seq 自增、可续写、并发安全）+ `read_events()`；
- `tests/test_contracts.py`：19 用例；`lit_agent_min/__main__.py` 增 `demo-events` 子命令。

**契约约束（写进模型而非注释）**
| 约束 | 理由 |
|---|---|
| `extra="forbid"` + `frozen=True` | 拼写错误在入口暴露；契约对象构造后不可变，避免跨步骤被悄悄改写 |
| 非 `unverified` 的 `Claim` 必须带 ≥1 条 `Citation` | 对应 D1"断言必须可回查"，把 grounding 纪律下沉到数据层 |
| `Verdict(ok=False)` 必须给 `reasons` | 守卫判决必须可解释（对应 state-machine §7） |
| `Event.ts` 必须带时区；`payload` 必须可 JSON 序列化 | 事件是回放/评测的真相源：时区缺失与不可序列化 payload 必须在写盘前拦住 |
| `paper_id` 不得含空白；`year ∈ [1800, 2200]` | canonical id 与明显异常值在入口拦截 |

**语义决定（写入文档，供后续步骤依赖）**
1. **`seq` 按 run 独立**：同一文件可容纳多个 run，各自从 1 开始；`JsonlEventLog` 打开已有文件时从该 run 的最大 seq 续写（重跑不产生重复 seq）。
2. **失败不留痕**：`emit` 任一步失败（契约校验/IO）→ 抛 `EventLogError` 且不写半行、不推进 seq。
3. **不掩盖损坏**：`read_events` 遇到非法行立即报错并给出行号（Phase 1 迁移 SQLite 前，JSONL 是唯一真相源）。
4. **sink 可替换**：上层只依赖 `EventSink.emit(...)`，Phase 1 用 SQLite 实现即可，无需改调用方。

**验收数字**：`uv run pytest -q` → 26 passed；`uv run ruff check .` / `format --check .` → 通过；`demo-events` → `lines=3 seqs=[1, 2, 3]`，首行 JSON 与 `implementation-guide.md` §2.2 形状一致（`id: null` 由 Phase 1 数据库分配）。
**版本**：`lit_agent_min.__version__` 0.1.0 → **0.2.0**。
**待办**：Step 0.3（日志基线 `logging.py` + `logs/app.jsonl` + 双写纪律）。

## 2.4 Step 0.3 记录（日志基线）

**交付物**
- `lit_agent_min/logging.py`：`setup_logging()`（幂等；app/errors 双 handler + 可选控制台）、`bind_context()/clear_context()`、`log_event()`、`get_logger()`、`validate_no_bodies()`、`config_version()`（配置短哈希，便于复现对比）；
- `lit_agent_min/_version.py`：单一版本来源（`__init__` 与 `logging` 共用，避免循环导入）；版本 → **0.3.0**；
- `tests/test_logging.py`：9 用例；`__main__.py` 增 `demo-logging` 子命令；`config.Logging` 增 3 个开关。

**落地的三条纪律（规范 §1/§3）**
| 纪律 | 实现方式 |
|---|---|
| info 及以上不得含正文 | `_guard_body` processor：超 `max_field_chars`(500) 的字符串字段 → `<redacted chars=… sha1=…>`；DEBUG 例外（受控目录） |
| ERROR 必须带 `error_code` | `log_event()` 严格模式直接抛 `LoggingContractError`（`strict_contracts` 可关） |
| 外部调用双写（日志 + 事件） | `demo-logging` 演示同 run 的 3 事件 / 3 日志 / 1 错误行，并断言 `run_id` 互查 |

**脱敏（规范 §3）**：键名匹配 `api_key/token/secret/password/authorization` → `***`；邮箱保留域名打码（`z***@nus.edu.sg`）；家目录前缀 → `~`；`sk-…`/`Bearer …` 值 → `***`。

**字段（规范 §2.1）**：必填 `ts/level/event/logger/msg/app_version/config_version/host/pid/schema_version`；上下文 `run_id/topic_id/stage/agent` 由 `bind_context` 注入。事件 `seq`（0.2）与日志 `run_id` 构成跨层关联键。

**踩坑与修复**：`structlog` 未在 0.1 依赖清单中 → 本次补入 `pyproject.toml` 并 `uv sync`（`uv.lock` 更新）；`BoundLogger.info(msg, event=…)` 位置参数本身叫 `event` → 改为 `log_event` 内部显式 `event=/msg=` 关键字传参（并移除 `EventRenamer` processor）。

**验收数字**：`pytest -q` → **35 passed**；`ruff check` / `format --check` → 通过；`demo-logging --run-id p0-log-smoke` → `events=3 / log lines=3 / error lines=1`，`[OK] 事件与日志可用 run_id 互相定位`（exit 0）。
**待办**：W1 的四个 spike（S1 源覆盖度 / S2 本地 vs 云 / S3 存储栈 / S4 断点续跑）。

## 2.5 Step 1（S1）记录：源覆盖度验证

**运行**（脚本 `steps/s1_source_coverage.py`；`sources.openalex_mailto = hepengzhou@u.nus.edu`）

| 轮次 | 参数 | topic | n | venue_cov | refs | OA | arxiv_gap | 抽查 |
|---|---|---|---|---|---|---|---|---|
| 首轮 | `--limit 200`（含限速探测） | T1 | 400 | 4.25% | 16.3% | 90.3% | 98.0% | 9/10 |
| 首轮 | 同上 | T2 | 400 | 7.0% | 19.8% | 93.5% | 71.6% | — |
| 深测轮 | `--limit 100 --skip-probe --venue-sufficiency --arxiv-existence 12` | T1 | 200 | 3.5% | 18.0% | 90.0% | 100% | **10/10** |
| 深测轮 | 同上 | T2 | 200 | 5.0% | 18.0% | 93.0% | 75.0% | — |

**决策级附加测量**
- **白名单 venue 召回量**（12 个核心 venue 名 → 10 个 source id 命中）：两个 topic 查询 3 年合计 **386 篇 ≈ 128.7 篇/年**（T1=253、T2=133）；
- **arXiv 论文在 OpenAlex 的收录率**：抽样 12 篇 → **11 篇已收录（91.7%）**；未命中示例 *Lachesis: Lifetime-Aware KV Cache Placement…*；
- **礼貌限速**：20 次连续请求全部 200，无 429，p50 1087 ms，max 4196 ms → 退避未触发，可安全放开抓取。

**可执行结论**
1. **"OpenAlex 为主 + arXiv 为辅"成立，但理由要改**：arXiv 的价值是**时效/新鲜度**（提交日排序、先于正式发表），**不是**补 OpenAlex 的收录缺口（缺口仅 ~8%）；
2. **检索必须"白名单过滤 + 去重"**：宽召回（relevance top-N）中白名单命中仅 3.5–5%，且出现同标题多版本（*Antrocon…* 两条不同 W id，Zenodo 与出版方各一份）→ 过滤与指纹去重是硬要求，不能靠搜索引擎式宽召回；
3. **venue 白名单必须用 OpenAlex `source.id`，不能按名字搜索**：`neurips` 被解析成 *International Cybersecurity Law Review*，`iclr`/`osdi` 未解析 → 印证"白名单以 source id 表达"的选型决定；因此 386 篇是**下限**（缺 NeurIPS/ICLR/OSDI 三大主会）；
4. **引用元数据稀疏（~18%）**：`referenced_works` 大面积缺失 → 关联图需评估补齐路径（限制到白名单/出版方论文后复测，或将 Crossref 作为补源），列为后续待办；
5. **OA 率高（90–93%）** → 全文可得性好，grounding 可基于全文而非仅摘要（对评测方案有利）；
6. **入口需做字段有效性校验**：首轮抽查出现 title 仅 `Moral` 的残缺记录（9/10）→ 入库前校验是必要的（脚本已实现自动判定）。

**待办（承接给后续 Step）**
- 白名单改为**人工确认的 source id 列表**（补齐 NeurIPS/ICLR/OSDI），并重测"过滤后引用完整率"；
- 检索侧实现"白名单过滤 + 标题/DOI 指纹去重"（S5 前置）；
- 若过滤后引用完整率仍 <50%，评估 Crossref 补引用。

## 2.6 Step 1b（S1b）记录：检索策略 / 去重 / 引用完整率（S1 衍生）

**运行**：`steps/s1b_retrieval_and_dedup.py --topics T1,T2 --years 3 --per-page 100`（白名单 = `config.sources.venues` 的 12 个 source id）
产出：`out/s1b_records.csv`（994 条）、`out/s1b_summary.json`、`out/s1b_run.log`

| topic | 策略 | n | 引用完整率 | OA 率 |
|---|---|---|---|---|
| T1 | broad（宽召回） | 100 | **27.0%** | — |
| T1 | whitelist（白名单过滤） | 200 | **1.5%** | 100% |
| T1 | expansion（3 查询并集 + 白名单） | 211 | 1.9% | — |
| T2 | broad | 100 | **25.0%** | — |
| T2 | whitelist | 147 | **14.3%** | 100% |
| T2 | expansion | 236 | 9.8% | — |

**三个反直觉但决定性的发现**

1. **白名单过滤不是"去噪"，而是"换了一个召回集合"**：白名单 vs 宽召回的标题重叠 **Jaccard 仅 0.014（T1）/ 0.004（T2）**；白名单里 **196/146** 篇是宽召回 top-100 完全没有的。
   → **检索必须以白名单为主通道**；只做宽召回会系统性漏掉目标会议论文（反过来，宽召回也不是白做工：它提供跨源候选与预印本）。
2. **引用元数据在白名单侧更稀疏（1.5%/14.3% < 宽召回 25–27%）**，且**不是版本问题**：随机抽 3 篇无引用的白名单论文，按 DOI 查全部版本 → 均只有 1 个版本、`referenced_works` 为 0（AAAI v40、IJCAI、ACL proceedings 记录本身就不含参考文献）。
   → **论文关联图不能只依赖"正向 references"**：需要 ① 用 `cited_by` **反向构边**（别人引用它时，引用方的 references 里会出现它）；② 规划 **Crossref 补源**实验；③ 评测里注明"引用覆盖不完整"这一口径。
3. **查询扩展收益显著**：在单条白名单查询之外，扩展查询再带来 **126（T1）/ 155（T2）** 篇新论文；而白名单侧 OA 率 **100%**。
   → 检索 agent 默认采用"**多查询扩展 + 白名单过滤**"；OA 100% 对 grounding（基于全文）是利好。

**去重结论**
- 同标题多记录占比 **19.8%（T1，101/511）/ 19.3%（T2，93/483）**；重复组 78/79 个，示例：*Do Multi-Agent LLM Systems Actually Help?…*、*Comparative Evaluation Of FP32 And INT8 Quantization…*（会议版 + 期刊版/存档版）。
- → **指纹去重（`sha1(canonical_id)`）不够**：同一论文的多版本 canonical id 不同 → 去重键必须是「**DOI（若有）+ 归一化标题 + 年份**」三元组，并把多版本合并为一条主记录（保留 `merged_ids`）。

**增量语义结论**
- `from_updated_date` **不可用**（HTTP 429：*Plan upgrade required*，Premium/Institutional 专属）→ **不能用 updated 时间戳做增量**；
- `from_publication_date` + `sort=publication_date:desc` + **cursor 分页可用且稳定**：page1 两次请求 id 完全一致、page2 与 page1 重叠 0；
- → 增量方案改为「**publication_date 倒序 + 已见 paper_id 水位线**」：每次从最新往回拉，遇到连续 N 条都已在库即停止；
- **数据质量**：探测中发现 `publication_date = 2050-02-21` 的未来日期记录 → 入库必须做"日期合理性"过滤（> 今天 + 少量容差即丢弃或标记）。

**待办（写进 S3/S5 前置）**
- `Paper` 模型增加 `merged_ids: list[str]`（记录被合并的版本 id）与 `citers_checked_at`（反向引用抓取时间）；
- 检索器默认策略：白名单过滤 + 多查询扩展 + 三元组去重；
- 增量器：`publication_date` 水位线 + 日期合理性过滤；
- 引用补源：先做 `cited_by` 反向构边，再评估 Crossref。

## 2.7 S1 收官小结（数据源验证收口，2026-10-07）

**状态：数据源 track 的可行性验证到此为止**（S1 + S1b 完成并勾选）；后续的优化/健壮性工作**不在 Phase 0 继续**，全部转入 Phase 1 对应模块（见下方 backlog）。

**已固化的结论**

| # | 结论 | 关键数字 |
|---|---|---|
| 1 | 数据源结构成立：OpenAlex 为主 + arXiv 为辅（arXiv 负责时效） | arXiv 收录率 91.7%；白名单 3 年召回 386 篇（≈129/年，下限） |
| 2 | **白名单是主通道**（与宽召回几乎不重叠） | Jaccard 0.004–0.014；宽召回命中白名单仅 3.5–7% |
| 3 | 多查询扩展有效 | 额外新增 126（T1）/155（T2）篇 |
| 4 | 全文可得性好（对 grounding 有利） | 白名单侧 OA **100%**；宽召回 90–93% |
| 5 | 引用元数据稀疏，**关联图需反向构边** | 白名单 refs 1.5%/14.3%（宽召回 25–27%；DOI 交叉核对确认非版本问题） |
| 6 | 增量不能用 `updated`（付费能力），改用 publication_date 水位线 | updated 过滤 **429 Plan upgrade required**；cursor 分页稳定（page2 与 page1 重叠 0） |
| 7 | 去重必需，且键不能只用 canonical id | 同标题多记录 **19.3–19.8%**（详见 D6 三段式方案） |
| 8 | 入库需字段/日期合理性校验 | 未来日期 `2050-02-21`；title 过短（`Moral`） |
| 9 | 礼貌池可用 | 20/20 返回 200，无 429，p50 1.09 s |

**转入 Phase 1 的 backlog（不在 Phase 0 继续）**

| 优化项 | 归属模块/阶段 | 前置/触发 | 来源 |
|---|---|---|---|
| 白名单扩充与治理（硬件/EDA/网络/系统；source id 人工确认） | `sources/`（Phase 1） | 每个 topic 的订阅集定义 | S1 结论 3 / S1b |
| 三段式去重（精确键 → 指纹 → 模糊确认）+ `merged_ids` | `sources/normalize.py`（Phase 1，需 ADR 改 `Paper` 契约） | S5 前置 | S1b / D6 |
| `cited_by` 反向构边 + 引用覆盖率指标（目标：白名单论文 ≥60% 有入边） | `stores/graph.py`（Phase 1）+ 评测 | S3 之后（有图库） | S1b / F6 |
| Crossref 补引用评估 | 待评估（P2–P3） | 反向构边仍不足时 | S1b |
| topic 质心相关性过滤（embedding） | 检索 agent（P3） | Qdrant + embedding 就绪 | S1b 结论 1 |
| publication_date 水位线增量 + 日期校验 + 周期性浅刷新（补"回溯更新"盲区） | `runtime/` + `sources/`（Phase 1） | S3/S5 | S1b 增量结论 |
| 滚雪球召回通道（正向 references + 反向 citers） | `sources/`（Phase 1） | 同上 | S1 结论 1/2 |

**为什么现在停**：Phase 0 的目标是"验证选型可行性 + 跑通最小闭环"；上述项目都属于"必须在真实模块里做才有效"的优化（依赖 Kuzu/Qdrant/SQLite、检索器、评测回路），提前做等于写产品代码，且必然重做。**Phase 0 剩余的是 S3（存储栈）、S4（断点续跑）、S5（最小闭环）**——它们不是数据源优化。

**证据文件（全部可追溯）**：`out/s1_coverage.csv`、`out/s1_coverage.json`、`out/s1_deep.log`、`out/s1b_records.csv`、`out/s1b_summary.json`、`out/s1b_run.log`；事件 `out/events.jsonl` 与日志 `logs/app.jsonl` 按 `run_id` 关联。

## 2.8 Step 3（S3）记录：存储栈验证（2026-10-08）

**状态：完成**（脚本 `steps/s3_storage_spike.py`，全量 5000 篇 + 重建校验；run_id `p0-s3-20261008084413`）

**方法**：S1/S1b 抓到的 1089 条真实元数据 + 合成扰动补到 5000 篇；1024 维**伪向量**（只验证存储/检索链路，不代表 embedding 质量）；三库同源导入后跑四类查询各 30 轮，再重复导入一次验幂等，最后删 Kuzu/Qdrant 从 SQLite 重建验可恢复性。

| 维度 | 实测 | 目标 | 判定 |
|---|---|---|---|
| 导入耗时 | sqlite 0.22s / kuzu 169.46s / qdrant 26.78s | ≤5min | ✅ |
| 写入对账 | 5000 论文 / 1010 作者 / 10000 PAPER_AUTHOR / 10000 CITES / 5000 向量；`mismatches={}` | 一致 | ✅ |
| 向量 top-10（含过滤） | p50 146.51ms / p95 **155.45ms** / max 179.98ms，0 错误 | p95 ≤100ms | ⚠️ 未达标 |
| 图 2-hop | p50 3.96ms / p95 **4.42ms** | p95 ≤200ms | ✅ 远优 |
| 作者近 3 年聚合 | p50 3.73ms / p95 5.06ms | — | ✅ |
| SQLite 主键查询 | p50 0.07ms / p95 0.16ms | — | ✅ |
| 幂等（重复导入） | 233.14s，计数零增长，0 失败 | 零增长 | ✅ |
| 删库重建 | 376.53s；重建前空库哨兵 0/0；重建后计数一致 | 一致 | ✅ |
| 磁盘 | kuzu 12.89MB / qdrant 49.06MB / sqlite 2.95MB = **64.9MB** | ≤500MB | ✅ |
| 边写入 | 20000 边全走 `MATCH+MERGE`（回退 0 次） | MERGE 幂等可用 | ✅ |
| 并发访问 | Qdrant 第二客户端被拒；Kuzu 第二连接拿不到锁 | 单写者成立 | ✅ |
| 边界 | 非法维度被拒；非 ASCII/超长标题正常；未来日期与超短标题各 1 条被检出 | — | ✅ |

**本步最有价值的是修掉的一个静默 bug（写进 F7）**

1. **Kuzu 的数据库路径是单文件，不是目录**。早期清理代码写 `shutil.rmtree(path, ignore_errors=True)`：对文件抛 `NotADirectoryError` 被 `ignore_errors=True` **静默吞掉** → 旧库从未删除 → `MERGE` 跨运行累积节点。症状极具特征：`expected_authors=631 / actual=957`，差集**只多不少**（+326 / −0）。
2. **两次 smoke 都是 500 篇论文**，论文数恰好对得上，把污染掩盖了——**只有"节点级对账"能发现它**。定位过程：先用独立最小实验排除"Kuzu 参数化 MERGE 会重复建点"（1000 次插入 → 唯一 742 = Kuzu 742，且重复插入不增长），再做集合差集诊断（`actual−expected` 非空且 `expected−actual` 为空 ⇒ 跨运行残留），最后由 `NotADirectoryError` 反证文件 vs 目录假设。
3. **Kuzu 仅 `Database.close()` 触发 checkpoint**：导入 300 篇后 0.004MB → `conn.close()` 后仍 0.004MB → `db.close()` 后 2.426MB。磁盘统计必须放在关闭 DB 句柄之后，否则读到 **0.0MB 假值**（本步两次踩到）。
4. 修复：`reset_store_path()`（文件/目录都能清 + 清 `.wal/.lock/.shm`）、`path_size_mb()`、**导入前空库哨兵** `store_is_empty()`（非空 → `E_STORE_NOT_EMPTY`）。

**规模外推（Phase 1 参考）**：Kuzu 导入 34ms/篇（逐条 `conn.execute`）→ 2 万篇 ≈11min；周更增量数百篇为秒级，可接受；但首次全量导入应换 **`COPY FROM`** 批量路径。Qdrant 增量成本 ≈5.4ms/篇、磁盘 ≈9.8KB/点（1024 维，约为原始向量体积的 2.4 倍）→ 2 万篇 ≈196MB，仍宽裕。Kuzu 磁盘非线性（500 篇 10.86MB vs 5000 篇 12.89MB），固定开销占主导，容量估算应看边际斜率。

**转入 Phase 1 的 backlog（不在 Phase 0 继续）**

| 项 | 归属 | 触发条件 | 来源 |
|---|---|---|---|
| 向量检索延迟优化（**先做 Phase 1 部署形态三选一决策**，再谈参数调优） | `stores/vector.py`（Phase 1） | 真实语料 + 真实 bge-m3 向量就绪后重测；决策依据见 §2.9 | S3 §2.9 |
| Kuzu 首导改 `COPY FROM` 批量导入 | `stores/graph.py`（Phase 1） | 首次全量建库前 | S3 外推 |
| `E_STORE_NOT_EMPTY` / `E_DATA_COUNT_MISMATCH` 纳入守卫表 | `graph/guards.py` + 守卫文档 | S5/S6 落地 | S3 结论 3 |
| 存储目录 ASCII 化（生产/部署路径规范） | 部署配置 | Phase 1 建仓时 | F7 |
| 补测"检索结果正确性 / 删除更新路径 / 崩溃一致性 / 同进程并发" | `tests/integration/` + S4/S5 | S4/S5 期间 | §2.10 |

**证据文件**：`out/s3_storage.json`、`out/s3_run_5000.log`、`out/s3b_vector_latency.json`（§2.9 归因）；事件 `out/events.jsonl`（按 run_id 关联），日志 `logs/app.jsonl`。

## 2.9 S3 补充：向量 top-10 延迟归因（2026-10-08）

**问题**：S3 全量测得 `vector_top10_filtered` p95 = 155.45 ms，未达"p95 ≤ 100 ms"的验收目标。需判定这是**设计问题**还是**优化/测法问题**。

**先查源码（决定性事实）**：Qdrant **local 模式是纯 Python 实现**（`qdrant_client/local/local_collection.py`，140 KB），其中 `HNSW` 出现 **0** 次、`np.dot` **0** 次 —— 它**没有 ANN 索引**，是 Python/numpy 逐点扫描 + Python 层 payload 过滤；库自身在 `create_payload_index()` 时直接告警：`Payload indexes have no effect in the local Qdrant. Please use server Qdrant if you need payload indexes.`

**再做归因探针**（`steps/s3b_vector_latency_probe.py`；写入路径复用 S3 的 `init_qdrant`/`qdrant_upsert` 保证同口径；证据 `out/s3b_vector_latency.json`）

| 测法（5000 点，1024 维） | p50 | p95 |
|---|---|---|
| 纯算力下限：numpy 暴力点积 + argsort（不经 Qdrant 代码） | **0.65 ms** | 0.89 ms |
| local 无过滤 top-10 | 49.91 ms | 67.80 ms |
| local 过滤 `topic=T1` top-10 | 177.20 ms | 222.15 ms |
| local 过滤 `year>=2020` top-10 | 161.58 ms | 170.75 ms |
| local 过滤 `topic+year` top-10（**S3 基线测法**） | 198.63 ms | 296.65 ms |
| local 同上、**建 payload 索引后** | 207.09 ms | 219.61 ms（**无改善**） |
| local `retrieve` by id | 0.02 ms | 0.03 ms |

> 绝对数与 S3 当时（p50 146.51 ms）同量级但不完全相同（本次 190–200 ms），差异来自机器负载与进程内存占用；探针结论以**同进程内的倍数关系**为准，不依赖绝对值。

**规模曲线（同一测法）**

| 点数 | 过滤命中 | local p50 | numpy 下限 p50 |
|---|---|---|---|
| 1250 | 672 | 51.93 ms | 0.42 ms |
| 2500 | 1297 | 102.03 ms | 0.42 ms |
| 5000 | 2547 | 189.32 ms | 0.65 ms |

**归因（5000 点约 190 ms 的构成）**

1. **纯算力 ~0.3%**（0.65 ms）：瓶颈不在维度、不在向量算法。
2. **local 模式 Python 胶水 ~26%**（无过滤也要 49.91 ms）。
3. **payload 过滤 ~74%**（+140 ms）：注意 `year>=2020` **命中全部 5000 点**却仍 +112 ms → **过滤开销与扫描点数成正比、与选择率无关**。故"把过滤写得更严"在 local 模式下**不提速**（反直觉但重要）。
4. **payload 索引在 local 模式无效**（索引是 server 能力）。
5. **线性增长 ≈0.038 ms/点**（无 ANN 的对数加速）→ 外推 **2 万篇 ≈ 0.76 s/查询**、5 万篇 ≈ 1.9 s/查询。

**判定：不是架构设计问题，而是"部署形态选型 + 验收目标错配"**

- 存储抽象本身健康：`retrieve` by id 0.02 ms、纯算力 0.65 ms，慢的全部来自 local 这一层。
- `p95 ≤ 100 ms` 这个目标隐含假设"生产级 ANN 引擎"，而 S3 实际跑的是 local 模拟实现 → 目标与实现形态不匹配。
- 但确有**一个真实的设计级岔路**需 Phase 1 显式决策：

| 方案 | 收益 | 代价 | 对现有架构前提的影响 |
|---|---|---|---|
| A. 接受 local 暴力扫描 | 零改动、单进程、无外部服务 | 2 万篇 ~0.76 s/查询且线性增长 | 需按实现形态**重新标定验收目标** |
| B. 起本地 Qdrant server 进程（仍单机、无 Docker） | HNSW + payload 索引 + 量化，预期个位数 ms | 多一个本地进程（端口/进程管理/崩溃恢复） | **改动架构 §8"无外部服务依赖"表述** |
| C. 换嵌入式 ANN 库（hnswlib / FAISS / LanceDB） | 保留单进程且拿到 ANN | 需自实现 payload 过滤、持久化、并发语义 | 改 `stores/` 实现，接口不变 |

**对功能实现的影响**

1. **召回质量不受损反而更好**：local = 暴力扫描 = **精确 kNN**，召回率**高于** HNSW 近似 → "慢但准"，不会让报告出错。
2. **周更批处理无感**：几十次查询 ×0.2 s 相对 LLM 分钟级可忽略。
3. **对话 UI 是唯一有感知场景**：5k 时 +0.2 s/查询可接受；2 万篇外推 0.76 s/查询，一次提问若触发 3–5 次检索则累加 2–4 s，**届时必须解决**（即上述岔路）。
4. **换 server/HNSW 不是免费提速**：从精确 kNN 变近似 ANN，且 ANN+过滤组合影响召回，须重测召回率 —— 是权衡不是纯优化。
5. **接口零影响**：A/B/C 任一选择都不改上层调用（正是 S3 要验证的"存储栈可替换性"）。

## 2.10 S3 的功能性测试覆盖边界（明确"测了什么 / 没测什么"）

**已做（带对账，不是"跑通即过"）**：三库写入 + 节点/边/向量计数对账；幂等（重复导入零增长）；删库重建（从 SQLite 恢复且计数一致）；四类查询的延迟与错误率；单写者语义；磁盘占用；边界数据（非法向量维度、非 ASCII/超长标题、未来日期、超短标题）。

**未做（功能性空洞，须在 S4/S5 或 Phase 1 补）**

| 未覆盖项 | 风险 | 计划位置 |
|---|---|---|
| **检索结果正确性**（top-10 内容、过滤是否被严格遵守、payload 回读完整性） | 延迟达标但结果错 → 报告引用错论文 | P3（真实向量就绪后；伪向量无"正确"可言） |
| **删除/更新路径**（论文合并 `merged_ids`、撤回、版本更新、作者改名） | 合并/纠错只能重建全库 | Phase 1 `stores/`（配合 D6 去重 ADR） |
| **崩溃一致性**（写入中途进程被杀，三库是否半写、能否自愈） | 周更中断后索引与真相源不一致 | S4（部分）+ F1 投影重放 |
| **正式 SQLite schema / 迁移 / 事务边界** | 契约变更无迁移路径 | Phase 1（Alembic） |
| **全文字段与 `papers_dir` 文件存储**（PDF 落盘、命名、缓存去重） | 全文缓存是 grounding 前置 | S5.3 / Phase 1 `parsing/` |
| **同进程并发查询**（FastAPI 读 + 周更写同时进行） | 对话期间周更导致读失败/阻塞 | S5（最小闭环内验证） |

> 结论：**S3 完成的是"存储层"的功能性与可行性测试（且带对账）**；**整个系统的最小端到端功能测试尚未开始** —— 那是 S5（walking skeleton：topic → 报告 → claims → 事件）。两者不可互相替代。

## 3. 假设与发现

| 日期 | 假设 | 结果（证实/证伪/待验证） | 依据 | 回写位置 |
|---|---|---|---|---|
| 2026-10-08 | Kuzu 的参数化 `MERGE` 在重复 key 下会建出重复节点 | **证伪** | 1000 次插入 → 唯一 id 742 = Kuzu 计数 742；重复插入计数不变 | 无需回写（排查记录见 §2.8） |
| 2026-10-08 | 存储清理用 `rmtree(..., ignore_errors=True)` 是安全的 | **证伪** | Kuzu 路径是**文件**，`NotADirectoryError` 被静默吞掉 → 旧库残留（631 vs 957） | `design/agent-design-decisions.md` **F7** |
| 2026-10-08 | 导入后可立即统计 Kuzu 磁盘占用 | **证伪** | 0.004MB（conn.close）→ 2.426MB（db.close）：仅 `Database.close()` 触发 checkpoint | 同上 F7 |
| 2026-10-08 | Qdrant local + Kuzu 可多进程并发读写 | **证伪**（实测均被拒） | Qdrant "already accessed by another instance"；Kuzu "Could not set lock on file" | 支撑"单进程写入"架构（→ G 类/部署形态） |
| 2026-10-08 | 5k 规模下向量检索 p95 可 ≤100ms（Qdrant local） | **证伪**（155.45ms） | `out/s3_storage.json` queries；`first_vector_query_ms=179.98` ⇒ 非冷启动 | `implementation/phase0-implementation-steps.md` Step 3 结论 4 + Phase 1 backlog |
| 2026-10-08 | 向量检索慢是"高维/算法"问题 | **证伪** | 纯 numpy 算力下限 0.65ms（占 190ms 的 0.3%）；瓶颈是 local 模式 Python 扫描与 payload 过滤（§2.9） | 无需改算法；改为"部署形态三选一"决策（架构 §8） |
| 2026-10-08 | 过滤条件写得越严，向量检索越快 | **证伪** | `year>=2020` 命中全部 5000 点仍 +112ms；开销与扫描点数成正比、与选择率无关 | §2.9；禁止把"加过滤"当 local 模式下的提速手段 |
| 2026-10-08 | local 模式可用 payload 索引加速过滤 | **证伪** | 建索引后 207ms vs 198ms；库显式告警 "Payload indexes have no effect in the local Qdrant" | §2.9；索引属 server 能力 |
| 待填 | 例：`.env` 作为兜底可满足 Phase 0 密钥管理 | 待验证 | `selfcheck` 输出 | `design/agent-design-decisions.md` H2 |
