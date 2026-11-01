# STATUS

> 版本：2.0（2026-11-01）
> 用途：AI 长周期交接；每个 phase 收尾必须更新。
> 只写事实，不写计划口吻。

---

## 当前状态

```text
阶段：Phase 4.1 complete（4.1.0–4.1.9）；下一 Phase 4.2
前端：Vue F1–F6 done；real API mode 已联调
最后测试：84 passed / ruff clean
前端构建：web npm run build passed
全链路 demo：100 papers / 174 claims / 13 sections / degraded
联调：topics → run → trace → report → paper；chat 基础链路
当前契约：代码仍为 1.2；目标契约 CONTRACTS 2.0 DRAFT
真实联调：100 篇本地 corpus，fulltext 0/100，174 claims，13 sections，report degraded
```

---

## 当前代码实际结构

```text
Platform:
  interface/  topics / runs / router / cli
  workflow/node/  NodeRunner + definitions
  kernel/node/    ReAct loop
  tools/packs/    source / corpus / claims / report / demo
  verify/         code + audit
  research/       corpus / claims / pdf / openalex
  storage/        db + report_store
  domains/chat/   local retrieval chat
  evaluation/     standalone evaluation tools

Legacy:
  domains/report/ removed
  contracts/ports.py removed
  run_shell.py removed
  old kernel/workflow removed
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

1. 默认 API 是单 Node report demo；`LIT_V2_DEMO_CHAIN=full` 才走 4 Node 链；
3. 100 篇本地 corpus fulltext 0/100，report 明确 degraded；
4. demo.report 目前是确定性 composer，不是 LLM 逐节写作；
5. 前端默认仍用 mock adapter；real mode 已接 topics/trace/report/paper/chat；
6. M5-P02 AI gold 不可用；
7. 真实 Chat 仍是本地检索，不是 LLM 对话。

---

## 下一步

```text
1. Phase 4.2 决定 full-chain 是否成为默认 API
2. demo.report 升级为 LLM 逐节写作
3. 章节拆分 / classification / scorecard
4. Chat 接入真实 LLM 与 streaming
5. 评估模块接入 platform workflow
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
2026-11-01  Phase 4.1.9：删除旧 report workflow / 旧 kernel / 旧 API，contracts 2.0 frozen
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
