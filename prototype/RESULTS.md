# Phase 0 结果记录（RESULTS）

> 用途：Phase 0 每步的**结论台账**——结论 / 关键数字 / 证据文件 / 是否影响设计。
> 规则：数字必须可追溯到证据文件；"结论为负"同样记录并给出替代方案；被推翻的假设同步回写主文档。

## 1. 进度记录

| Step | 结论 | 关键数字 | 证据文件 | 是否影响设计 | 日期 | 状态 |
|---|---|---|---|---|---|---|
| 0.1 | 骨架/配置/自检就绪，**`uv run` 全链路验收通过** | `uv.lock` 935,775 B（111 包）；pytest 7/7；ruff check+format 通过；selfcheck 0/2/0；import ok（CPython 3.11.17 托管） | `README.md`、`FILEMAP.md`、`uv.lock` | 是（新增 2 条环境约束，见 §2.1） | 2026-10-05 | ☑ 完成 |
| 0.2 | — | — | — | — | — | ☐ |
| 0.3 | — | — | — | — | — | ☐ |
| 1 (S1) | — | — | — | — | — | ☐ |
| 2 (S2) | — | — | — | — | — | ☐ |
| 3 (S3) | — | — | — | — | — | ☐ |
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

## 3. 假设与发现

| 日期 | 假设 | 结果（证实/证伪/待验证） | 依据 | 回写位置 |
|---|---|---|---|---|
| 待填 | 例：`.env` 作为兜底可满足 Phase 0 密钥管理 | 待验证 | `selfcheck` 输出 | `design/agent-design-decisions.md` H2 |
