# Phase 3.6 · Greenfield 重构宪章（删除旧架构）

> **版本**：2.0.0（2026-10-31）
> **性质**：执行宪章，不是增量计划
> **结论**：**不做兼容层、不包旧代码、不保留旧执行路径。**
> **目标**：用全新 `engine/ + domains/ + evaluation/` 替换现有 `graph/ + report/ + runtime/`，每片结束删除旧模块。
> **基线**：648 pytest / 18 e2e / ruff clean（仅作为行为参考，不作为保留旧代码的理由）

---

## 0. 先纠正上一版的问题

上一版仍写着：

- “保留领域算法 / Kernel / WorkflowRunner / Report 工具函数”；
- “保留纯函数”；
- “旧 build_report_bundle 包装”。

这些都会导致**在旧代码上增改**，不是全新重构。

本版规则：

1. **旧代码不移植，只参考行为；**
2. **新代码写入新包，旧包在切片结束删除；**
3. **不写 adapter/wrapper/fallback/feature flag；**
4. **旧测试退役，新测试按新契约重写；**
5. **同一片内完成切换 + 删除，不留双路径。**

---

## 1. 新旧边界

### 1.1 新代码只允许出现在

```text
src/lit_agent/engine/
  run_shell.py
  workflow/
    definition.py
    runner.py
    artifact.py
    verifier.py
    events.py
  kernel/
    loop.py
    tools.py
    context.py
    checkpoint.py
    protocol.py

src/lit_agent/domains/
  report/
    source.py
    evidence.py
    map.py
    write.py
    models.py
  chat/
    answer.py
    stream.py

src/lit_agent/evaluation/
  catalog.py
  store.py
  evaluators.py
  dataset.py
  optimizer.py

src/lit_agent/api/
  routes/runs.py
  routes/report.py
  routes/chat.py
```

### 1.2 旧代码必须删除

```text
src/lit_agent/graph/                     # 整目录
src/lit_agent/runtime/graph_runner.py
src/lit_agent/runtime/micro_agent.py
src/lit_agent/report/                    # 整目录（行为迁入 domains/report，代码重写）
src/lit_agent/agents/chat.py
src/lit_agent/agents/                    # 仅保留 retrieval 等纯工具，其余删除
src/lit_agent/eval/metrics.py
src/lit_agent/eval/report_metrics.py
src/lit_agent/api/routes/graph.py
src/lit_agent/workflow/                  # 原型包，迁入 engine 后删除
src/lit_agent/kernel/                    # 原型包，迁入 engine 后删除
web/src/features/report/10-stage 组件
web/src 旧 Trajectory / stage 常量
scripts/verify_phase3.py
scripts/verify_phase2_1.py
scripts/verify_phase2_2.py
```

### 1.3 旧测试处理

- 旧测试 **不保留** 作为“回归保护”；
- 旧测试只作为**行为样本**，提取后重写为：

```text
tests/engine/
tests/domains/report/
tests/domains/chat/
tests/evaluation/
tests/api/v2/
tests/e2e/v2/
```

- 任何测试若 import 旧模块，删除或重写；
- 不允许“旧测试全绿”作为新架构验收。

### 1.4 数据库

- DB 是数据，不是旧代码；
- 只保留必要的 schema migration；
- 旧表可保留数据，但旧读写代码必须删除；
- 不做双写、不做旧表兼容读取。

---

## 2. 红线

以下任一出现，视为重构失败：

```text
from lit_agent.graph import ...
from lit_agent.report import ...
from lit_agent.runtime.graph_runner import ...
from lit_agent.agents.chat import ...
build_report_bundle(...)
graph_runner.run(...)
10-stage / phase_change(stage="...") 旧阶段
feature flag 切新旧路径
adapter 包旧类
```

新架构只有一条默认路径：

```text
API/CLI
  → engine.run_shell
  → engine.workflow.definition
  → engine.workflow.runner
  → engine.kernel
  → domains.* tools
  → evaluation
```

---

## 3. 全新模块契约

### 3.1 Engine

| 模块 | 职责 |
|---|---|
| `run_shell.py` | prepare → workflow → evaluate → finalize；唯一入口 |
| `workflow/definition.py` | 固定节点声明；拒绝运行时改图 |
| `workflow/runner.py` | 顺序执行、artifact 传递、checkpoint |
| `workflow/verifier.py` | Code Gate + 独立 Verifier |
| `workflow/events.py` | node/step/tool/token 事件 |
| `kernel/loop.py` | 单节点 agent loop |
| `kernel/tools.py` | 工具白名单/超时/预算 |
| `kernel/context.py` | L0–L3 与 handoff |
| `kernel/checkpoint.py` | 可序列化恢复 |

### 3.2 Domains

| 模块 | 职责 |
|---|---|
| `report/source.py` | 真实检索、venue、时间窗、100 篇 |
| `report/evidence.py` | L1/L2/L3、全文精读、quote |
| `report/map.py` | 真实 embedding、聚类、方向 |
| `report/write.py` | outline、deep dive、comparison、gaps |
| `chat/answer.py` | Chat Kernel workflow |
| `chat/stream.py` | token 流 |

### 3.3 Evaluation

| 模块 | 职责 |
|---|---|
| `catalog.py` | 指标定义 |
| `store.py` | points/spans |
| `evaluators.py` | 规则 + judge |
| `dataset.py` | 100 篇冻结集 |
| `optimizer.py` | baseline/candidate/promotion |

---

## 4. 切片

### S0 · Greenfield 冻结

**目标**：停止在旧代码上加功能。

- 建 `legacy-freeze` 清单；
- 统计旧 import；
- 提取行为样本，不复制代码；
- 关闭 OI-017（stale）；
- 确定新包边界。

**删除**：无（只冻结）。

**验收**：

- 旧代码不再被修改；
- 新代码只允许写 `engine/domains/evaluation`；
- 删除清单签字。

---

### S1 · Engine Core（从零）

**目标**：新引擎可跑一个最小 Workflow。

**新建**：

```text
engine/run_shell.py
engine/workflow/*
engine/kernel/*
```

**删除**：

- 不删旧 graph（尚未切换）；
- 但禁止新代码 import 旧模块。

**验收**：

- 一个 fake workflow 端到端；
- checkpoint/resume；
- 事件；
- 无旧 import。

---

### S2 · RunShell 接管 + 删除 graph

**目标**：API/CLI 只走新引擎。

**新建**：

- `api/routes/runs.py` 调 `run_shell`；
- CLI 调 `run_shell`；
- 新 Workflow timeline。

**删除**：

```text
src/lit_agent/graph/
src/lit_agent/runtime/graph_runner.py
src/lit_agent/api/routes/graph.py
10-stage 前端/事件
旧 CLI run-topic
```

**验收**：

- 全仓库无 graph import；
- `/run` 只走 RunShell；
- e2e 走新 timeline；
- 旧 10 阶段测试已删除。

---

### S3 · Report Domain（从零）

**目标**：Report 不依赖旧 `report/`。

**新建**：

```text
domains/report/{source,evidence,map,write,models}.py
```

**删除**：

```text
src/lit_agent/report/
```

**验收**：

- 20/50/100 篇；
- L1/L2/L3；
- 真实 embedding；
- 1500–3000 字；
- comparison 正文；
- 无旧 report import。

---

### S4 · Chat Domain（从零）

**目标**：Chat 不再依赖旧 `agents/chat.py`。

**新建**：

```text
domains/chat/{answer,stream}.py
```

**删除**：

```text
src/lit_agent/agents/chat.py
```

**验收**：

- 引用/拒答；
- token 流；
- 与 Report 共用 Kernel；
- 无旧 chat import。

---

### S5 · 流式 + 运行控制

**目标**：长任务可见、可停、可续。

**新建**：

- section/token 事件；
- SSE 断线恢复；
- pause/resume/abort；
- 序列化 checkpoint；
- 停滞检测。

**删除**：

- 旧 graph 控制；
- 旧 SSE 映射；
- 旧“10 阶段”UI。

**验收**：

- kill 后 resume 不重复；
- pause/resume 一致；
- section/token 可见。

---

### S6 · Evaluation v2

**目标**：指标可信、可复跑。

**新建**：

```text
evaluation/{catalog,store,evaluators,dataset,optimizer}.py
```

**删除**：

```text
src/lit_agent/eval/metrics.py
src/lit_agent/eval/report_metrics.py
旧 fixture/扁平 metrics
```

**验收**：

- 100 篇 × 3 topic 冻结集；
- 每个指标公式/单位/版本；
- NULL 与 0 分离；
- 评估集只读；
- baseline/candidate。

---

### S7 · 100 篇报告调优

**目标**：用 S6 指标把 S3 调到科研级。

- 参数网格；
- Pareto；
- experiments；
- 硬指标回退即拒绝。

**验收**：

- 100 篇端到端；
- 6–8 方向；
- ≥80 篇 claim；
- 引用 100%；
- 成本/时间预算内。

---

### S8 · Source / Ingest / Ops

**目标**：产品闭环。

**覆盖**：

- OI-001 Source AI；
- OI-014 报告前 ingest；
- OI-002 Run 删除；
- OI-007 卡住清理；
- OI-013 设置。

**删除**：

- 手填 venue 旧流程；
- 旧 run 列表；
- 旧 source 同步脚本。

---

### S9 · Research Workspace UI

**目标**：报告可读可用。

**覆盖**：

- OI-003 Outline/Citations；
- OI-004 双 Tab；
- OI-005 PDF；
- OI-006 图谱；
- OI-010 成本；
- OI-011 metadata。

**删除**：

- 旧右侧面板；
- 旧成本逻辑；
- 旧 metadata 兼容。

---

### S10 · 删除与收尾

**目标**：仓库只剩新架构。

**删除**：

```text
旧 graph/
旧 report/
旧 agents/chat.py
旧 runtime/graph_runner.py
旧 workflow/ 原型
旧 kernel/ 原型
旧 eval metrics
旧 10-stage UI
旧 verify 脚本
过时 docs/ADR
```

**验收**：

- 全仓库无 legacy import；
- 只有一条执行路径；
- 统一 verify；
- pytest/e2e 全绿；
- 文档只描述新架构。

---

## 5. 执行规则

1. **先删后写**：切片内先移除旧入口，再写新入口；
2. **不写兼容层**；
3. **不保留旧测试作为绿灯**；
4. **不并行切片**；
5. 每片结束必须：

```text
旧模块删除
新模块可用
端到端验收
无 legacy import
```

---

## 6. 起手

从 **S0 + S1** 开始：

- S0 冻结旧代码；
- S1 从零写 `engine/`；
- S2 接管并删除 graph。

确认后执行 S0。
