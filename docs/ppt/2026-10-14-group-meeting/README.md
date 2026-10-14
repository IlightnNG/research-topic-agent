# 2026-10-14 组会材料（Phase 0 进展汇报）

> 本文件夹收纳**本次组会专用**的全部材料：中文底稿、生成提示词、成品 PPTX、决策门 handout、S5/S6 演示 brief。
> 引用约定：路径一律相对**仓库根**书写（如 `docs/ppt/2026-10-14-group-meeting/…`）；工具链见 `docs/ppt/scripts/`（用法与再生成命令见 `docs/ppt/README.md`）。

## 1. 本文件夹内容（9 份，含本 README）

| 文件 | 用途 | 状态 |
|---|---|---|
| `group-meeting-outline.md` | **汇报整体思路（详细底稿）**：①选型补充（LangChain 拆解 + 编排/网关多选一 + Q&A 预案）②重难点设计方案（三层防线 + 6 个代表性问题 + 周更状态图节点表 + 验证方式表）③可行性验证（8 组：为什么验/数字/结论）+ 数字速查与证据索引 | 现行 |
| `group-meeting-ppt-prompt.md` | **内容权威（给 ppt-master 的生成提示词）**：21 页 Roster；逐条重要度层级 `[H]/[1]/[2]/[3]/[F]`（含配额与舍取顺序）+ 层次规范（L1→L5）+ 每页 takeaway + **渲染契约**（问题页机制化、验证页四块含公式、中文四处、**字号底线 19 px = 14.25 pt**）+ 版式几何 + 导出后检查要点 | 现行（v1.5） |
| `2026-10-14-group-meeting.pptx` | **成品 deck**：21 页 + 演讲备注 | 已导出（v4） |
| `phase0-decision-gate.md` | **决策门一页纸**（不在 PPT 内，单独 handout 或末尾口头讲）：一页数字摘要 + 5 分钟 demo（3 条命令）+ 6 项待导师确认 + Phase 1 backlog + 诚实边界 | 现行 |
| `s5-closed-loop-demo.md` | S5 闭环演示 brief（流程图、真实数字、成本表、3 分钟讲稿）——对应成品第 19 页 | 现行 |
| `s6-guards-brief.md` | S6 守卫演示 brief（阈值标定过程、注入矩阵、事件链、3 分钟讲法）——对应成品第 20 页 | 现行 |
| `problem-pages-bilingual.md` | 问题页（8–13）中英对照参考 | ⚠️ 内容对应**改版前**的 8–13 页，与成品不一致，待同步或归档 |
| `ppt-master-prompt-group-meeting.md` | 本组会提示词的**第一版**（已被 `group-meeting-ppt-prompt.md` 取代） | 归档（过程记录） |

**推荐顺序**：`group-meeting-outline.md` 定口径 → `group-meeting-ppt-prompt.md` 作为内容权威生成/再生成 → 用 `docs/ppt/scripts/` 校验 → 成品 deck 汇报 → `phase0-decision-gate.md` 收口。

## 2. 成品 deck 速览

- **21 页 + 演讲备注**；导出后实测：最小字号 **14.2 pt**（≥14 pt 硬底线）、备注 **21/21**、版式碰撞 **0**。
- 页面结构：开场 2 → 选型 4 → 周更状态图 1 → **代表性问题 6**（机制页：Problem + Methods + 机制 hero + `→ evidence` 交叉引用，**不含测量数字**）→ **可行性验证 8**（四块 How we measured / Formulas / Results / Impact，含公式与中文注解）。
- 再生成与校验命令：见 `docs/ppt/README.md` §二（`build-deck-pages.py` → `svg-layout-check.py` → 技能质量门 → `svg_to_pptx.py` → `verify-pptx.py`）。

## 3. 支撑证据（按需查阅，不进 PPT）

| 内容 | 位置 |
|---|---|
| Phase 0 结果台账（v1.0 定稿） | `prototype/RESULTS.md`（§0 一页摘要 / §2.x 分步记录 / §4 十二条静默错误 / §5 决策门结论） |
| 施工清单与出口清单 | `docs/implementation/phase0-implementation-steps.md`（v1.0） |
| 选型依据 | `docs/project/framework-selection.md`（§2.4/§2.5/§2.6/§3.4/§3.5/§14b） |
| 重难点与问题台账 | `docs/design/challenges-and-self-healing.md`；`docs/design/agent-design-decisions.md`（71 条） |
| 守卫与阈值 | `docs/design/state-machine-and-guards.md`（G1–G15 + §12 实测小结） |
| 指标口径 | `docs/implementation/evaluation-plan.md`（§5.1/§5.3/§5.4b/§5.6） |
| 契约与 ADR | `docs/implementation/implementation-guide.md` §2.9；`docs/implementation/adr/0001–0003` |
| 原始产物 | `prototype/out/`（报告、claims、metrics_*、s3/s4/s6 汇总、llm_cache） |

## 4. 汇报前检查清单

- [ ] 三模块叙事顺畅：**结论先行 → 选型 → 重难点 → 验证 → 决策门**
- [ ] 关键数字与底稿一致（4.42 ms / 155 ms / 1.00 / 0 / 0.7949 / $0.006294 / 0.0777）
- [ ] **两处口径已定**：①向量检索部署形态倾向（A/B/C）②grounding 讲法（自报标签 + citation 可回查率 1.0）
- [ ] 未验证项如实标注（恢复包 A/B、真实故障注入、跨主题泛化、gold 事实集、伪向量与全文级核验）
- [ ] **版式与字号实测**：`verify-pptx.py` 报 21 页 / notes 21/21 / 最小 ≥14 pt；`svg-layout-check.py` 报 0 issue
- [ ] demo 可跑：`s5_walking_skeleton`（缓存命中约 0.1 s）→ `s6_guards_demo --inject all`（约 3 s）→ `s7_metrics`（约 1 s）
