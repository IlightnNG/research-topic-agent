# STATUS

> 版本：3.0（2026-11-03）
> 用途：AI 长周期交接；每个 phase 收尾必须更新。
> 只写事实，不写计划口吻。

---

## 当前状态

```text
阶段：Phase 4.1 complete；Phase 4.2 complete；L3 gate passed
前端：Vue F1–F6 done；real API mode 已联调
最后测试：128 passed / ruff clean
前端构建：web npm run build passed
全链路 demo：100 papers / 98 fulltext / 196 claims / 23 sections / complete
联调：topics → run → trace → report → paper；chat 基础链路
当前契约：CONTRACTS 2.0 frozen
真实联调：100 篇本地 corpus，fulltext 98/100，196 claims，23 sections，5115 words，report complete
```

---

## 当前代码实际结构

```text
Platform:
  interface/  topics / runs / router / cli
  workflow/       report_v2 + node runner + file store
  kernel/agent/   AgentKernel + checkpoint + audit
  kernel/node/    legacy ReAct loop
  tools/packs/    source / corpus / claims / report / report_v2 / demo
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
| W Workflow | 特制任务外壳 | 5 Node report-v2 CLI/API；Node-level section loop；DemoOrchestrator 已删除 |
| K Kernel | 通用 Agent 内核，可独立完成复杂任务 | L3 gate passed；AgentKernel 已被 API/CLI report 使用 |
| T Tools | ToolRuntime + general/domain toolset | S2/S3 done：general tools、toolset、policy、spill |
| V Verification | code + audit | dual Verifier 已接入 runner |
| S Storage | artifact/state/report | 已有 |
| I Interface | API/UI | 5 Node / section progress / quality badge / failed section retry |
| R Research | source/evidence/report tools | report_v2 tools + exact quote claims |
| E Evaluation | scorecard/judge tools | 已有，未接入 |

---

## 当前阻塞

1. 剩余 2/100 fulltext；
2. LLM audit 基础设施不可用时 fail-open，需监控；
3. RAG / Qdrant / Kuzu 仍 deferred；
4. D 盘 root guard 仍 open；
5. 真实 Chat 仍是本地检索，不是 LLM 对话。

---

## 下一步

```text
1. 4.3 RAG / 三库（deferred）
2. D 盘 root guard
3. Chat workflow
4. 剩余 fulltext / audit 校准
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
2026-11-03  Phase 4.2 complete：5 Node report + Node-level section loop
2026-11-03  Fulltext 98/100，196 claims，23 sections，quality + audit passed
2026-11-03  API pause/resume，quality UI，failed section retry
2026-11-03  DemoOrchestrator / demo package / demo100 CLI removed
2026-11-03  Docs / TODO / phase4.2 收尾
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
