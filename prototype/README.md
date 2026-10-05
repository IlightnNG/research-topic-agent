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
   │  ├─ __init__.py  config.py  __main__.py  py.typed
   │  ├─ models.py / eventlog.py            # ← 0.2
   │  └─ logging.py                         # ← 0.3
   ├─ tests/test_config.py                  # ← 0.1（7 用例）
   ├─ steps/                                # ← S1–S7（一次性脚本）
   └─ out/ + logs/                          # 运行产物（gitignored）
```

## Step 命令索引

| Step | 命令（规划中，随实现补齐） | 状态 |
|---|---|---|
| 0.1 | `python -m lit_agent_min selfcheck` | ✅ 已实现 |
| 0.2 | 契约模型 + `eventlog.py`（`tests/test_contracts.py`） | ⏳ |
| 0.3 | 日志基线：`lit_agent_min/logging.py` + `logs/app.jsonl` + `jq` 查看段 | ⏳ |
| 1 (S1) | `python steps/s1_source_coverage.py --topic T1 --years 3 --limit 200 --out out/s1_coverage.csv` | ⏳ |
| 2 (S2) | `python steps/s2_model_baseline.py --tasks out/s2_tasks.yaml --local ollama/qwen2.5:7b --cloud deepseek/deepseek-chat` | ⏳ |
| 3 (S3) | `python steps/s3_storage_spike.py --papers 5000 --out out/s3_storage.json` | ⏳ |
| 4 (S4) | `python steps/s4_checkpoint_spike.py --run-id p0-s4-001`（可中断重跑） | ⏳ |
| 5 (S5) | `python steps/s5_walking_skeleton.py --topic T1 --run-id p0-s5-001` | ⏳ |
| 6 (S6) | `python steps/s6_guards_demo.py --topic T1 --inject drift --repeats 3` | ⏳ |
| 7 (S7) | `python steps/s7_metrics.py --events out/events.jsonl --out out/metrics_summary.csv` | ⏳ |

## 日志查看

> Step 0.3 实现日志基线后，此处补齐 5 条 `jq` 常用命令（按 run 取时间线、按错误码过滤、慢调用 Top10、阶段耗时均值、错误码计数）。规范见 `docs/implementation/logging-and-observability.md` §9。

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

## 变更与提交约定

- 分支：`prototype`；每个 Step 完成提交一次，commit 格式 `step-N: <结论摘要>`。
- 新增/重命名文件必须同步更新 `FILEMAP.md`（Step 0.1 验收项之一）。
- 契约（表/事件/模型/API）变更走 ADR：`docs/implementation/adr/`。
