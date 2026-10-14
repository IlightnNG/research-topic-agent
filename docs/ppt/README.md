# ppt 目录索引（Presentation Materials）

> **分工**：按会议分文件夹（`<日期>-group-meeting/`）；**跨会议复用的材料与工具留在本级**。
> **引用约定**：跨目录引用统一写相对仓库根的路径（如 `docs/ppt/2026-10-14-group-meeting/group-meeting-ppt-prompt.md`）——移动文件夹时只需全仓替换该前缀。

## 目录结构

```
docs/ppt/
├─ README.md                          # 本索引
├─ 2026-10-14-group-meeting/          # 本次组会（Phase 0 进展汇报）
├─ scripts/                           # 成品再生成与校验工具链
├─ framework-selection-brief.md       # 选型主题分页稿（跨会议复用）
└─ ppt-master-usage-guide.md          # ppt-master 用法与提示词范式（工具文档）
```

## 一、本次组会：`2026-10-14-group-meeting/`

| 文件 | 作用 | 状态 |
|---|---|---|
| `README.md` | 会议材料入口（阅读顺序、范围、边界） | 现行 |
| `group-meeting-outline.md` | 中文详细底稿（选型补充 + 6 个代表性问题 + 8 组验证 + 数字速查与证据索引） | 现行 |
| `group-meeting-ppt-prompt.md` | **内容权威**：21 页 Roster + 层级规范 + 版式几何 + 渲染契约 + 检查要点 | 现行 |
| `phase0-decision-gate.md` | 决策门一页纸（一页数字 + 5 分钟 demo + 6 项待确认 + Phase 1 backlog） | 现行 |
| `2026-10-14-group-meeting.pptx` | **成品 deck**：21 页 + 演讲备注（最小字号 14.2 pt，notes 21/21） | 已导出 |
| `s5-closed-loop-demo.md` | S5 闭环演示 brief（对应成品第 19 页） | 现行 |
| `s6-guards-brief.md` | S6 守卫演示 brief（对应成品第 20 页） | 现行 |
| `ppt-master-prompt-group-meeting.md` | 提示词**第一版**（已被 `group-meeting-ppt-prompt.md` 取代） | 归档 |
| `problem-pages-bilingual.md` | 问题页中英对照；**内容对应改版前的 8–13 页，与成品不一致** | 待同步/归档 |

## 二、工具链：`scripts/`

| 脚本 | 作用 | 用法 |
|---|---|---|
| `build-deck-pages.py` + `deck_content.py` | 由内容数据**重生成 21 页 SVG**（写入 `.agents/projects/gm1013v4_20261013/svg_output/`） | `python docs/ppt/scripts/build-deck-pages.py`（用仓库 `.venv`） |
| `svg-layout-check.py` | 版式自检：越界、文本重叠、卡片溢出、跨列碰撞 | `python docs/ppt/scripts/svg-layout-check.py <svg_dir>` |
| `verify-pptx.py` | 导出后实测：页数、备注覆盖率、**最小字号**（防止回到 12 px） | `python docs/ppt/scripts/verify-pptx.py <pptx>` |
| `svg-render-preview.py` | headless Chrome 渲染 PNG 预览（视觉复核） | `python docs/ppt/scripts/svg-render-preview.py <svg_dir> <out_dir> [页码过滤…]` |
| `build-contact-sheet.py` | 把预览拼成 21 页联系表（一眼总览版式） | `python docs/ppt/scripts/build-contact-sheet.py <preview_dir>` |
| `roster-quota-check.py` | 校验 roster 配额与模块规则（`[H]/[1]/[2]/[3]/[F]`、问题页无测量数字、19 px 底线） | `python docs/ppt/scripts/roster-quota-check.py` |

### 再生成成品的完整命令（可复现）

```bash
# 0) 环境：仓库 .venv 需含 python-pptx / Pillow / numpy
# 1) 改内容：编辑 group-meeting-ppt-prompt.md（内容权威）+ scripts/deck_content.py（页面数据）
python docs/ppt/scripts/build-deck-pages.py                       # 重生成 SVG
python docs/ppt/scripts/svg-layout-check.py .agents/projects/gm1013v4_20261013/svg_output
python docs/ppt/scripts/roster-quota-check.py                     # roster 配额自检
python .agents/skills/ppt-master/scripts/svg_quality_checker.py .agents/projects/gm1013v4_20261013 \
       --quick-generate --canonical-authoring --stage final --json     # 技能质量门（须 0 blocking）
python .agents/skills/ppt-master/scripts/svg_to_pptx.py .agents/projects/gm1013v4_20261013 \
       --quick-generate --with-notes -o "docs/ppt/2026-10-14-group-meeting/2026-10-14-group-meeting.pptx"
python docs/ppt/scripts/verify-pptx.py "docs/ppt/2026-10-14-group-meeting/2026-10-14-group-meeting.pptx"
```

> 备注：演讲备注的正文在 `.agents/projects/gm1013v4_20261013/notes/total.md`（由 `total_md_split.py` 按页拆分）。

## 三、跨会议复用材料（本级）

| 文件 | 作用 |
|---|---|
| `framework-selection-brief.md` | 选型主题的英文分页稿（模块选型 + 重难点 + 评测预想）；正式版见 `docs/project/framework-selection.md` |
| `ppt-master-usage-guide.md` | ppt-master 怎么用、提示词怎么写、验收看什么（与具体会议无关） |

## 四、新增一次组会（3 步）

1. 新建 `docs/ppt/<日期>-group-meeting/`；
2. 放入：底稿（outline）、内容权威（prompt md）、决策门、成品 PPTX、当次演示 brief；
3. 更新本索引 + `docs/README.md` 的 ppt 段（并把旧文件夹里只属于那次的材料一并带过去）。
