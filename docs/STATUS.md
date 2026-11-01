# STATUS

> 版本：2.0（2026-11-01）
> 用途：AI 长周期交接；每个 phase 收尾必须更新。
> 只写事实，不写计划口吻。

---

## 当前状态

```text
阶段：Phase 4.1.0–4.1.6 done；下一 4.1.7 Composition / Interface
最后测试：134 passed / ruff clean
当前契约：代码仍为 1.2；目标契约 CONTRACTS 2.0 DRAFT
真实联调：100 篇 OpenAlex，fulltext 0/100，report degraded
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
| W Workflow | Node 链、可选节点、commit/resume | 旧 ReportWorkflow 固定 5 节点 |
| K Kernel | 每 Node ReAct、tools、checkpoint | 已有 Kernel；report 未使用 |
| T Tools | 全量 ToolRegistry | 仅 Kernel ToolBox，未全量工具化 |
| V Verification | code + audit | CodeVerifier + 独立 judge；未合并 |
| S Storage | artifact/state/report | 已有 |
| I Interface | API/UI | 已有，deterministic writer |
| R Research | source/evidence/report tools | 旧 M2/M3/M4 服务 |
| E Evaluation | scorecard/judge tools | 已有，未接入 |

---

## 当前阻塞

1. `report.generate` 不是 agent node；
2. `write.py` 章节写死；
3. 默认 API/CLI 使用 deterministic writer；
4. fulltext 0/100，report state degraded；
5. classification 方向质量不稳定；
6. 双 Verifier 未接入 Node；
7. M5-P02 AI gold 不可用；
8. 平台模块还未从 M1–M6 重排。

---

## 下一步

```text
1. 抽 workflow / kernel / tools / verify 目录
2. NodeSpec 增加 goal/tools/verifier/optional
3. ToolRegistry 包装 source/evidence/report
4. report.generate 改为 agent node
5. report.plan 产出 sections
6. 双 Verifier
7. demo profile 跑 100 篇
8. 章节拆分 / classification / scorecard
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
