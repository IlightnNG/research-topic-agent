# Phase 0 原型（prototype）

> 定位：**实验区**——验证选型与最小闭环的临时代码，**不是**交付仓库。
> 当前进度：**Step 0.1 完成**（骨架 + 配置 + 自检）；后续 Step 0.2/0.3 见 `docs/implementation/phase0-implementation-steps.md`。
> 可复用代码在 `lit_agent_min/`（Phase 1 会搬运升级）；`steps/` 与 `out/` 属一次性实验产物。

## 前置条件

| 项 | 要求 | 本机现状（2026-10-05） |
|---|---|---|
| uv | **>= 0.5**（管理依赖与解释器） | ✅ 0.12.23（`pip install uv`，用户级） |
| Python | **3.11 或 3.12**（`.python-version` 固定 3.11） | uv 托管 **CPython 3.11.17**（`uv python install 3.11`）；系统 3.14 仅作语法检查 |
| 密钥 | `DEEPSEEK_API_KEY`（写进 `.env`） | 待填；未填时 `selfcheck` 返回 **2** 并给出修复指引 |

```bash
# 安装 uv（任选其一）
winget install --id astral-sh.uv -e
python -m pip install uv
```

## 快速开始

```bash
cd prototype          # 从仓库根进入本目录
uv sync                    # 按 pyproject.toml/.python-version 建 .venv 并安装依赖
cp .env.example .env       # Windows: copy .env.example .env，然后填入 DEEPSEEK_API_KEY
uv run python -m lit_agent_min selfcheck
```

## Step 0.1 验收命令

```bash
# 1) 导入自检（打印版本与配置路径）
uv run python -c "import lit_agent_min; print(lit_agent_min.__version__)"
# 2) 结构自检：配置 → 目录 → 密钥（缺密钥时给出修复指引并返回码 2，不打印堆栈）
uv run python -m lit_agent_min selfcheck
uv run python -m lit_agent_min selfcheck --lax     # 暂不需要云端密钥时的宽松模式
# 3) 代码规范
uv run ruff check .
# 4) 单元测试
uv run pytest -q
# 5) 生成依赖锁文件（交付物要求）
uv lock
```

**文件职责表一致性检查**（`FILEMAP.md` 与实际目录必须一一对应）
```powershell
# PowerShell
Get-ChildItem -Recurse -File | Where-Object { $_.FullName -notmatch '\\\.venv\\|__pycache__|\\out\\|\\logs\\' } | ForEach-Object { $_.FullName.Replace((Get-Location).Path + '\','') }
```
```bash
# bash
find . -type f -not -path './.venv/*' -not -path './out/*' -not -path './logs/*' -not -name '*.pyc' | sed 's|^\./||' | sort
```

## 本机验证记录（2026-10-05）

| 验收项 | 结果 |
|---|---|
| `uv sync --python 3.11 --python-preference only-managed` | ✅ exit 0（托管 CPython 3.11.17） |
| `uv lock` | ✅ 935,775 B / 111 包 |
| `uv run python -c "import lit_agent_min"` | ✅ import ok 0.1.0 / 3.11.17 |
| `uv run pytest -q` | ✅ 7 passed |
| `uv run ruff check .` + `ruff format --check .` | ✅ 通过（7 files formatted） |
| `uv run … selfcheck`（lax / 缺 key / 有 key） | ✅ 0 / 2 / 0 |
| Step 0.2 `uv run pytest -q` | ✅ 26 passed（含 `tests/test_contracts.py` 19 用例） |
| Step 0.2 `uv run python -m lit_agent_min demo-events` | ✅ `lines=3 seqs=[1, 2, 3]`，事件 JSON 形状与契约一致 |
| Step 0.3 `uv run pytest -q` | ✅ 35 passed（0.1 的 7 + 0.2 的 19 + 0.3 的 9） |
| Step 0.3 `uv run python -m lit_agent_min demo-logging` | ✅ `events=3 / log lines=3 / error lines=1`，`[OK]` 事件与日志可用 `run_id` 互相定位 |
| Step 1 (S1) `python steps/s1_source_coverage.py --topics T1,T2 --limit 100 --skip-probe --venue-sufficiency --arxiv-existence 12` | ✅ 白名单 venue 3 年召回 386 篇（≈129/年，下限）；arXiv 收录率 91.7%；抽查 10/10；限速 20/20 无 429 |
| Step 1b (S1b) `python steps/s1b_retrieval_and_dedup.py --topics T1,T2 --per-page 100` | ✅ 白名单 vs 宽召回重叠 0.004–0.014；扩展查询 +126/155 篇；重复率 19.3–19.8%；白名单引用完整率 1.5%/14.3%；`from_updated_date` 不可用（付费），`from_publication_date`+cursor 可用且稳定 |
| Step 3 (S3) `python steps/s3_storage_spike.py --papers 5000` | ✅ 5k 全量：kuzu 169.5s / qdrant 26.8s 导入，图 2-hop p95 4.42ms、聚合 p95 5.06ms、向量 p95 155.45ms、sqlite p50 0.07ms；幂等零增长；删库重建计数一致；磁盘 64.9MB；20000 边全 MERGE；单写者语义成立 |
| Step 3b (S3b) `python steps/s3b_vector_latency_probe.py` | ✅ 归因：5000 点约 190ms 中纯算力仅 **0.65ms（0.3%）**、local 无过滤 49.91ms、payload 过滤 +140ms（占 74%）；**Qdrant local 无 ANN、payload 索引无效**；规模线性 ≈0.038ms/点（2 万篇外推 ~0.76s/查询）→ 判为"部署形态选型 + 验收目标错配"，非架构缺陷；local = 精确 kNN，召回不受损 |

> 依赖装在 `prototype/.venv`（由 `uv sync` 创建）；uv 缓存与托管解释器在 **uv 默认位置**（`uv cache dir` / `uv python dir`），因此**不需要任何自定义环境变量**，换机器只需 `uv sync`。
> 若 Windows 终端把中文显示成乱码，属控制台编码问题（程序输出为 UTF-8），`chcp 65001` 可解决。

## 仓库布局

- 仓库根 `agent/` 下：**`docs/`（研究与设计文档）与 `prototype/`（本目录）平级**；
- **Phase 1 起正式代码直接建在仓库根**（`src/`、`tests/`、`config/`、`migrations/`、`web/`、`eval_data/`），`prototype/` 按 `FILEMAP.md` 的"下一阶段归属"列搬运完成后删除；
- **不存在 `code/` 中间层**（历史上短暂存在，已移除；相关文档引用已同步）。

## 目录结构

```
agent/                          # 仓库根 = Phase 1 的项目根
├─ docs/                        # 选型/架构/实现/评测/演示文档
└─ prototype/                   # Phase 0 实验区（本目录，可整体丢弃或部分升级）
   ├─ README.md / FILEMAP.md / RESULTS.md   # 说明 / 文件职责表 / 结果台账
   ├─ .env.example / .gitignore / .python-version
   ├─ config.local.yaml / config.example.yaml
   ├─ pyproject.toml / uv.lock              # 依赖与锁定
   ├─ lit_agent_min/                        # ★可升级到 Phase 1 的最小内核
   │  ├─ _version.py  __init__.py  config.py  __main__.py  py.typed
   │  ├─ models.py / eventlog.py            # ✅ 0.2
   │  └─ logging.py                         # ✅ 0.3
   ├─ tests/test_config.py                  # ✅ 0.1（7 用例）
   ├─ tests/test_contracts.py               # ✅ 0.2（19 用例）
   ├─ tests/test_logging.py                 # ✅ 0.3（9 用例）
   ├─ steps/                                # S1 ✅ / S1b ✅ / S3 ✅ 已交付；S2 本轮不做；S4–S7 待做
   └─ out/ + logs/                          # 运行产物（gitignored）
```

## Step 命令索引

| Step | 命令（规划中，随实现补齐） | 状态 |
|---|---|---|
| 0.1 | `python -m lit_agent_min selfcheck` | ✅ 已实现 |
| 0.2 | 契约与事件：`python -m lit_agent_min demo-events`；测试 `uv run pytest -q tests/test_contracts.py` | ✅ 已实现（19 用例） |
| 0.3 | 日志基线：`python -m lit_agent_min demo-logging`；测试 `uv run pytest -q tests/test_logging.py` | ✅ 已实现（9 用例） |
| 1 (S1) | `python steps/s1_source_coverage.py --topics T1,T2 --years 3 --limit 200 --venue-sufficiency --arxiv-existence 12` | ✅ 已实现（覆盖度 + 白名单召回量 + arXiv 收录率） |
| 1b (S1b) | `python steps/s1b_retrieval_and_dedup.py --topics T1,T2 --years 3 --per-page 100` | ✅ 已实现（检索策略对比 + 去重 + 过滤后引用完整率 + 增量语义） |
| 2 (S2) | ~~`python steps/s2_model_baseline.py …`~~ | ⏸ 本轮不做（只用云端 DeepSeek API） |
| 3 (S3) | `python steps/s3_storage_spike.py --papers 5000`（`--no-rebuild-check` 可跳过删库重建校验） | ✅ 已实现（导入/四类查询/幂等/可重建/边界探针 + 写入计数对账） |
| 3b (S3b) | `python steps/s3b_vector_latency_probe.py` | ✅ 已实现（向量延迟归因：算力下限 / local 开销 / 过滤成本 / 规模曲线；**一次性探针，不迁移**） |
| 4 (S4) | `python steps/s4_checkpoint_spike.py --run-id p0-s4-001`（可中断重跑） | ⏳ |
| 5 (S5) | `python steps/s5_walking_skeleton.py --topic T1 --run-id p0-s5-001` | ⏳ |
| 6 (S6) | `python steps/s6_guards_demo.py --topic T1 --inject drift --repeats 3` | ⏳ |
| 7 (S7) | `python steps/s7_metrics.py --events out/events.jsonl --out out/metrics_summary.csv` | ⏳ |

## 日志查看

日志与事件都落盘在 `prototype/` 下：`logs/app.jsonl`（全量）、`logs/errors.jsonl`（仅 error/critical）、`out/events.jsonl`（事件真相源）。两者用 `run_id + stage` 关联。

```bash
# 1) 某 run 的完整日志时间线
jq -c 'select(.run_id=="p0-log-smoke")' logs/app.jsonl

# 2) 只看错误（含错误码与是否可重试）
jq -c 'select(.level=="error") | {ts,run_id,stage,error_code,retryable,msg}' logs/errors.jsonl

# 3) 错误码计数 Top（定位高发故障类型）
jq -r 'select(.error_code!=null) | .error_code' logs/app.jsonl | sort | uniq -c | sort -rn

# 4) 慢调用 Top10（工具/LLM 延迟）
jq -c 'select(.latency_ms!=null)' logs/app.jsonl | jq -s 'sort_by(-.latency_ms)[:10] | .[] | {ts,event,tool,latency_ms}'

# 5) 事件与日志互查：先取事件 seq，再查同一 run 的日志
jq -c 'select(.run_id=="p0-log-smoke")' out/events.jsonl
```

> Windows 未装 `jq` 时：`winget install jqlang.jq`（或 `scoop install jq`）。没有 jq 也可用 Python 一行替代：
> `uv run python -c "import json,sys;[print(l,end='') for l in open('logs/app.jsonl',encoding='utf-8') if json.loads(l).get('level')=='error']"`
> 完整规范（字段字典/轮转/调试开关/debug bundle/慢点告警）见 `docs/implementation/logging-and-observability.md`。

## 已知限制

1. **环境准备**：uv 已安装（0.12.23）；换机器时需先装 uv（见上方命令）。
2. **Python 版本**：请用 3.11/3.12；3.13+ 部分依赖（如 `kuzu`）可能还没有预编译 wheel。
3. **原型范围**：无前端、无周更调度、无多 agent 拆分、守卫只有最小雏形（见 Phase 0 不做清单）。
4. **缺密钥行为**：`selfcheck` 返回码 **2** 并打印"哪里缺 + 怎么修"，不打印异常堆栈；`--lax` 仅告警。
5. **配置为不可变**：运行期不允许改配置（避免半途改参数导致不可复现）；改配置请改文件后重启。
6. **路径含非 ASCII 字符**（本工作区为 `E:\大学\…`）：可编辑安装生成的 `.pth` 含中文路径，中文 Windows 的 `site.py` 以 `encoding="locale"`（= `locale.getencoding()` = cp936）读取该 UTF-8 文件 → `UnicodeDecodeError`。**实测结论：`-X utf8` / `PYTHONUTF8=1` 在 Python 3.11 下无效**（UTF-8 模式只改 `getpreferredencoding()`，不改 `getencoding()`）。
   - 当前规避：`[tool.uv] package = false` + 托管解释器；代价是 **`import lit_agent_min` 只在项目目录下有效**（从仓库根 `uv run --project prototype …` 会 `ModuleNotFoundError`，已实测）；
   - **根治（Phase 1 推荐）**：正式仓库放到**纯 ASCII 路径**，恢复 `package = true` 与可编辑安装；
   - 备选（未实测）：保留中文路径但用 `uv sync --no-editable`（安装 wheel 副本，不生成带路径的 `.pth`）。
7. **Kuzu 要求纯 ASCII 数据路径**（S3 实测）：`kuzu.Database("E:\\大学\\…\\kuzu")` → `RuntimeError: IO exception: Cannot open file … Error 3`。因此 `config.local.yaml` 的 `kuzu_path` 指向 ASCII 目录（本机 `E:\lit-agent-data\kuzu`）；Qdrant local 无此限制（可放中文路径）。
8. **Kuzu 的库路径是单文件、且只在 `Database.close()` 时落盘**（S3 实测）：清理必须区分文件/目录（`rmtree` 对文件会抛 `NotADirectoryError`，配 `ignore_errors=True` 会被静默吞掉 → 旧库残留、`MERGE` 跨运行累积）；磁盘统计要在 `db.close()` 之后做，否则读到 `0.0MB` 假值。脚本内已固化为 `reset_store_path()` / `path_size_mb()` / 导入前空库哨兵 `store_is_empty()`。

## 变更与提交约定

- 分支：`prototype`；每个 Step 完成提交一次，commit 格式 `step-N: <结论摘要>`。
- 新增/重命名文件必须同步更新 `FILEMAP.md`（Step 0.1 验收项之一）。
- 契约（表/事件/模型/API）变更走 ADR：`docs/implementation/adr/`。
