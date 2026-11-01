# STATUS

> 版本：2.0（2026-11-01）
> 用途：AI 长周期交接；每个 phase 收尾必须更新。
> 只写事实，不写计划口吻。

---

## 当前状态

```text
阶段：Phase 4.1.0–4.1.8 done；下一 4.1.9 清理旧代码
前端：Vue F1–F6 done；real API mode 已联调
最后测试：136 passed / ruff clean
前端构建：web npm run build passed
联调：topics → run → trace → report → paper；chat 基础链路
当前契约：代码仍为 1.2；目标契约 CONTRACTS 2.0 DRAFT
真实联调：100 篇本地 corpus，fulltext 0/100，174 claims，13 sections，report degraded
```

---

## 当前代码实际结构

```text
M1 Engine:
  workflow + kernel + storage 混在一起
M4 Report:
  write 节点 deterministic
  write.py 固定章节
  LLM writer 仅在测试/直接调用路径
M5 Evaluation:
  scorecard/judge 可独立运行，未接入 workflow
M6 Interface:
  API/UI 可用，仍走 deterministic writer
```

---

## 目标平台模块

| 模块 | 目标状态 | 当前代码 |
|---|---|---|
| W Workflow | Node 链、可选节点、commit/resume | 4 Node full chain 已跑通；旧 ReportWorkflow 仍在 |
| K Kernel | 每 Node ReAct、tools、checkpoint | 新 Kernel 已有；旧 Kernel 仍给 Chat |
| T Tools | 全量 ToolRegistry | core registry + source/corpus/claims/report + demo packs |
| V Verification | code + audit | dual Verifier 已接入 runner |
| S Storage | artifact/state/report | 已有 |
| I Interface | API/UI | Vue F1–F6 real API；支持 full-chain 模式 |
| R Research | source/evidence/report tools | report demo tools 已有 |
| E Evaluation | scorecard/judge tools | 已有，未接入 |

---

## 当前阻塞

1. 旧 `ReportWorkflow` / `write.py` 仍在仓库，尚未删；
2. 默认 API 是单 Node report demo；`LIT_V2_DEMO_CHAIN=full` 才走 4 Node 链；
3. 100 篇本地 corpus fulltext 0/100，report 明确 degraded；
4. demo.report 目前是确定性 composer，不是 LLM 逐节写作；
5. 前端默认仍用 mock adapter；real mode 已接 topics/trace/report/paper/chat；
6. M5-P02 AI gold 不可用；
7. 旧 M1–M6 模块代码还未清理。

---

## 下一步

```text
1. 4.1.9 删除旧 ReportWorkflow / write.py / run_shell / 旧 kernel
2. 清理旧 contracts/ports 与 domains/report 依赖
3. 加 test_no_legacy_imports
4. 决定 full-chain 是否成为默认 API
5. demo.report 升级为 LLM 逐节写作（可选）
6. 章节拆分 / classification / scorecard
```

Demo 目标：

```text
100 篇
>=30 篇 fulltext 或明确 abstract-only
overview + paper analysis + synthesis + index
每句有引用
API/UI 可读
```

---

## 最近变更

```text
2026-11-01  ARCHITECTURE 2.0：Workflow = Node 链，Node = goal/tools/verifier
2026-11-01  CONTRACTS 2.0 DRAFT
2026-11-01  模块地图改为 W/K/T/V/S/I + R/E + C
2026-11-01  M6-P01 API/UI 完成
2026-11-01  M5-P02 AI gold 抽样分析：不可用
2026-11-01  Phase 4.1.8：100 篇 4 Node 全链路跑通（174 claims / 13 sections / degraded）
2026-11-01  Pause/Resume：线程去重 + Kernel checkpoint 恢复
2026-11-01  Frontend：Trajectory UX / 菜单 / 文档索引收尾
```

---

## 交接规则

1. 先读 `docs/ARCHITECTURE.md`；
2. 再读 `docs/CONTRACTS.md`；
3. 再读 `docs/modules/README.md`；
4. 只改当前平台模块；
5. phase 完成更新 STATUS/TODO；
6. 生成一句话 commit；
7. 不恢复旧代码。
