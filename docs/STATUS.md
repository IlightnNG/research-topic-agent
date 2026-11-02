# STATUS

> 版本：2.1（2026-11-02）
> 用途：AI 长周期交接；每个 phase 收尾必须更新。
> 只写事实，不写计划口吻。

---

## 当前状态

```text
阶段：Phase 4.1 complete；Phase 4.2 S0–S8 done；S9 30 个真实 LLM 简单任务 30/30；复杂 L3 未完成
前端：Vue F1–F6 done；real API mode 已联调
最后测试：112 passed / ruff clean
前端构建：web npm run build passed
全链路 demo：100 papers / 35 fulltext / 186 claims / 13 sections / complete
联调：topics → run → trace → report → paper；chat 基础链路
当前契约：CONTRACTS 2.0 frozen
真实联调：100 篇本地 corpus，fulltext 35/100，186 claims，13 sections，report complete
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
| W Workflow | 特制任务外壳 | 4 Node report demo 已跑通；但 Node 单工具 + DemoOrchestrator 写死 |
| K Kernel | 通用 Agent 内核，可独立完成复杂任务 | S6–S8 硬化完成；30 真实任务 30/30；复杂任务 L3 未完成 |
| T Tools | ToolRuntime + general/domain toolset | S2/S3 done：general tools、toolset、policy、spill |
| V Verification | code + audit | dual Verifier 已接入 runner |
| S Storage | artifact/state/report | 已有 |
| I Interface | API/UI | Vue F1–F6 real API；full-chain 默认 |
| R Research | source/evidence/report tools | report demo tools 已有 |
| E Evaluation | scorecard/judge tools | 已有，未接入 |

---

## 当前阻塞

1. 默认 API 是 4 Node full chain；`LIT_V2_DEMO_CHAIN=single` 才走单 Node 兼容模式；
3. 100 篇本地 corpus fulltext 35/100，其余 65 篇使用 abstract；
4. demo.report 的 overview/synthesis 仍是确定性，10 个 analysis section 由 LLM 写；
5. 前端默认仍用 mock adapter；real mode 已接 topics/trace/report/paper/chat；
6. M5-P02 AI gold 不可用；
7. 真实 Chat 仍是本地检索，不是 LLM 对话。

---

## 下一步

```text
1. S6 Kernel completeness：parallel、checkpoint、retry、context overflow
2. S7 NodeKernelAdapter：最小 Node 入口
3. S8 观察性：metrics / logging / error taxonomy
4. S9 真实 LLM 30+ benchmark + performance gate
5. 门禁通过后才做 report workflow
6. 最后再接 Chat workflow
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
2026-11-02  ARCHITECTURE 2.1：通用 Kernel + 特制 Workflow
2026-11-02  CONTRACTS 2.0 frozen
2026-11-02  Phase 4.2 设计：Kernel/Tools 优先，报告 Workflow 后置
2026-11-01  模块地图改为 W/K/T/V/S/I + R/E + C
2026-11-01  M6-P01 API/UI 完成
2026-11-01  M5-P02 AI gold 抽样分析：不可用
2026-11-02  Phase 4.1.8：100 篇 4 Node 全链路，35 fulltext / 186 claims / 13 sections / complete
2026-11-01  Pause/Resume：线程去重 + Kernel checkpoint 恢复
2026-11-01  Frontend：Trajectory UX / 菜单 / 文档索引收尾
2026-11-01  Phase 4.1.9：删除旧 report workflow / 旧 kernel / 旧 API，contracts 2.0 frozen
```

---

## 交接规则

1. 先读 `docs/ARCHITECTURE.md`；
2. 再读 `docs/KERNEL-WORKFLOW.md`；
3. 再读 `docs/CONTRACTS.md`；
4. 再读 `docs/modules/README.md`；
5. 只改当前平台模块；
6. phase 完成更新 STATUS/TODO；
7. 生成一句话 commit；
8. 不恢复旧代码。
