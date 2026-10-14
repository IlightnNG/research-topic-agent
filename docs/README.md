# docs 目录索引（Documentation Index）

> 组织方式：4 个目录，按"项目与选型 → 设计 → 实现 → 演示"划分；文档间引用统一写**相对 docs/ 根**的路径（如 `project/framework-selection.md`）。
> 整理记录：目录重构（8 个子目录 → 4 个；两轮共修正 60+ 处交叉引用，已校验 0 遗漏）。

## 1. 目录结构

```
docs/
├─ README.md                      # 本索引
├─ project/                       # 需求、组会记录、决策史、技术选型
├─ design/                        # 架构、状态机与守卫规范、设计问题手册、重难点预想
├─ implementation/                # 实现指导、Phase 0 步骤、评测方案、adr/
└─ ppt/                           # 汇报演示材料
   ├─ README.md                    # ppt 目录索引（组会文件夹 / 工具链 / 跨会议材料）
   ├─ 2026-10-14-group-meeting/    # 本次组会：底稿 + 提示词 + 决策门 + 成品 PPTX + S5/S6 演示 brief
   ├─ scripts/                     # 成品再生成与校验工具链（重生成 SVG / 版式自检 / 导出实测）
   ├─ framework-selection-brief.md # 选型主题分页稿（跨会议复用）
   └─ ppt-master-usage-guide.md    # ppt-master 用法与提示词范式（工具文档）
```

## 2. 文档地图

| 路径 | 版本 | 作用 | 更新时机 |
|---|---|---|---|
| `project/project-analysis.md` | v0.2 | 需求拆解、组会记录、确认过的决策、关联项目（Jetson）备注 | 每次组会后 |
| `project/framework-selection.md` | v0.6 | 10 个模块选型、业界主流对照、未采用理由（含 LangChain 逐模块分析）、规模化迁移路径 | 选型变化（需 ADR） |
| `design/architecture-overview.md` | v0.4 | 分层架构、周更/对话时序、三存储分工、埋点与路由策略（含 S3 存储约束） | 架构变化时 |
| `design/state-machine-and-guards.md` | v0.3 | Topic/Run/Stage 状态机、条件边、**G1–G15 守卫判决表**（G14 数据完整性对账 = S3 实测新增；G15 运行身份与恢复一致性 = S4 实测新增）、阈值标定与验收目标 | Phase 0/1 实测后更新阈值 |
| `design/agent-design-decisions.md` | v0.3 | **71 条**设计问题与解法台账（A–K 类，含 F6–F9 数据/一致性、H5 reasoning 截断、I8 日志≠事件、J6 指标口径、K5 run_id 与续跑、G3/G14/G15 实测守卫） | 持续追加条目 |
| `design/challenges-and-self-healing.md` | v0.1 | 重难点与自愈机制预想（三层防线、升级阶梯） | 与上一条联动 |
| `implementation/implementation-guide.md` | v0.2 | 冻结契约（表/事件/模型/API）、10 模块实现方案、P1–P6 验收门、AI 生成工作流、§15.6 文档规范 | 契约变更走 ADR |
| `implementation/phase0-implementation-steps.md` | v1.0 | **Phase 0 逐步施工清单**：Step 0.1–8、文件职责表、进度表、出口检查清单（含 S1/S1b/S3/S4/S5/S6/S7 实测结果；Step 8 收尾已定稿） | 每完成一步更新进度与 RESULTS |
| `implementation/evaluation-plan.md` | v0.3 | 评测方案与数据集计划（D1–D7 规格、指标公式、**§5.4b Phase 0 实测口径映射**、实验设计、验收标准） | 评测口径变化时 |
| `implementation/logging-and-observability.md` | v0.1 | **日志与可观测性规范**（三层模型、字段字典、级别与脱敏、轮转保留、调试开关、debug bundle、框架日志接管、慢点告警、运维反馈闭环） | 可观测口径变化时 |
| `implementation/adr/README.md` | v0.1 | ADR 索引、触发条件与模板；**已收录 0001–0003**（merged_ids / 指标事件契约 / 本地存储路径与身份） | 契约变更时追加 |
| `ppt/README.md` | v0.1 | **ppt 目录索引**：组会文件夹 / 工具脚本 / 跨会议材料各自的位置与用途 | 结构变化时 |
| `ppt/framework-selection-brief.md` | v0.4 | 英文 15 页 PPT 分页稿（模块选型 + 重难点 + 评测预想）；跨会议复用的选型素材 | 选型/架构更新后同步 |
| `ppt/ppt-master-usage-guide.md` | — | ppt-master 使用说明与提示词范式（工具文档，与具体会议无关） | 按需 |
| `ppt/scripts/` | — | **成品再生成与校验工具链**：`build-deck-pages.py` + `deck_content.py`（由内容数据重生成 21 页 SVG）、`svg-layout-check.py`（版式/列碰撞自检）、`verify-pptx.py`（导出后实测页数/备注/最小字号）、`svg-render-preview.py` + `build-contact-sheet.py`（渲染预览）、`roster-quota-check.py`（roster 配额与模块规则） | 工具或版式变化时 |
| `ppt/2026-10-14-group-meeting/` | v1.0 | **本次组会材料文件夹**（入口见其 `README.md`）：思路底稿 + ppt-master 提示词 + 决策门一页纸 + **成品 PPTX** + S5/S6 演示 brief + 问题页双语参考 | 每次组会新建日期文件夹 |
| `ppt/2026-10-14-group-meeting/group-meeting-outline.md` | v1.1 | **组会汇报整体思路（详细底稿）**：①选型补充（LangChain 拆解 + 编排/网关多选一 + Q&A 预案）②重难点设计方案（三层防线 + **6 个代表性问题** + 周更状态图节点表 + 验证方式表）③初步可行性验证（6 组验证：为什么验/数字/结论）+ 数字速查与证据索引 | 每次组会前更新 |
| `ppt/2026-10-14-group-meeting/group-meeting-ppt-prompt.md` | v1.5 | 给 ppt-master 的生成提示词：**21 页 Roster**（开场 2 + 选型 4 + **周更状态图 1** + 代表性问题 **6 页一页一问** + 可行性验证 **8 页一页一验**）；**每页内容详实并逐条标注重要度层级**（`[H]` hero 唯一 · `[1]` 1–4 条论证主干 · `[2]` ≤8 条支撑细节 · `[3]` ≤6 条脚注，含空格不足时的舍取顺序）+ **层次规范**（L1→L5）+ 每页底部 takeaway；**英文为主、中文为辅** | 汇报结构变化时同步 |
| `ppt/2026-10-14-group-meeting/2026-10-14-group-meeting.pptx` | v4 | **成品 deck**：21 页 + 演讲备注（实测最小字号 **14.2 pt**、notes 21/21），由 `ppt/scripts/` 从上面的提示词 md 生成 | 汇报后冻结 |
| `ppt/2026-10-14-group-meeting/phase0-decision-gate.md` | v1.0 | **Phase 0 决策门一页纸**（一页数字 + 5 分钟 demo 脚本 + 6 项待导师确认 + Phase 1 backlog + 诚实边界） | 决策门后归档 |
| `ppt/2026-10-14-group-meeting/problem-pages-bilingual.md` | v0.1 | 问题页（8–13）中英对照参考；**注：内容对应改版前的 8–13 页，与成品 deck 不一致** | 问题页改版后同步或归档 |
| `ppt/2026-10-14-group-meeting/s6-guards-brief.md` | v0.1 | **S6 守卫演示 brief**（阈值标定过程、注入矩阵、事件链、工程规则、3 分钟讲法） | 每次守卫实测后更新数字 |
| `ppt/2026-10-14-group-meeting/s5-closed-loop-demo.md` | v0.1 | **S5 最小闭环演示 brief**（闭环流程图、真实运行数字、成本表、验收对照、诚实边界、3 分钟讲稿） | 每次闭环实测后更新数字 |
| `ppt/2026-10-14-group-meeting/ppt-master-prompt-group-meeting.md` | — | 组会 PPT 生成提示词的**第一版**（已被 `group-meeting-ppt-prompt.md` 取代，留作过程记录） | 归档 |

## 3. 引用与维护约定

1. **引用路径**：一律写相对 docs/ 根的路径（例：`design/state-machine-and-guards.md` §12），不要只写文件名——避免移动后失效。
2. **新增/重命名/移动文档**：① 更新本索引；② 全仓检索旧引用并修正；③ 保留版本行与修订摘要。
3. **版本行**：每份文档首部保留 `> 版本 vX.Y · 修订摘要`，便于追溯决策演变。
4. **ADR**：任何冻结契约（表结构、事件 schema、API、模型字段）或依赖/选型变更 → 在 `implementation/adr/` 新增 `NNNN-<title>.md`（模板见该目录 README 与 `implementation/implementation-guide.md` 附录 C）。

## 4. 阶段/步骤类文档的必备章节（强制）

按 `implementation/implementation-guide.md` §15.6，所有 step/phase 文档必须含 8 个章节：
① 目标与出口标准（含"不做清单"）→ ② 全局约定 → ③ **文件结构与职责（目录树 + 文件职责表 + 边界与命名约定）** → ④ Step 明细（内容要求/交付物/命令/期望输出/验收/时间盒/失败应对）→ ⑤ 进度跟踪表 → ⑥ 常见失败与应对 → ⑦ 出口检查清单 → ⑧ 与下一阶段衔接。
范式模板：`implementation/phase0-implementation-steps.md` §1.1–§1.1.2。

## 5. 推荐阅读顺序（按用途）

| 用途 | 顺序 |
|---|---|
| 快速了解项目 | `project/project-analysis.md` → `project/framework-selection.md` → `design/architecture-overview.md` |
| 准备动手实现 | `implementation/implementation-guide.md` → `implementation/phase0-implementation-steps.md` → `design/state-machine-and-guards.md` → `design/agent-design-decisions.md` |
| 设计评测 | `implementation/evaluation-plan.md` → `design/state-machine-and-guards.md`（自愈指标口径） |
| 排障与运维 | `implementation/logging-and-observability.md` → `design/agent-design-decisions.md` I 类（可观测问题）→ `implementation/phase0-implementation-steps.md` Step 0.3 |
| 做汇报 PPT | `ppt/2026-10-14-group-meeting/README.md`（材料入口）→ `ppt/ppt-master-usage-guide.md`（怎么生成）→ `ppt/scripts/`（再生成与校验） |

## 6. 与 docs 之外的关系

| 位置 | 内容 | 说明 |
|---|---|---|
| `prototype/` | Phase 0 实验代码（含 `FILEMAP.md` 文件职责表） | Phase 1 起建正式 `src/` |
| `eval_data/` | 评测数据集 | 结构见 `implementation/evaluation-plan.md` §4 |
| `prototype/out/` | 实验产物（事件日志、报告、指标） | 不入库 |
| `implementation/adr/` | 架构决策记录 | 首次契约变更时新增 `NNNN-*.md` |
