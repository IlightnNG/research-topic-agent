# Modules · 模块地图

> 版本：2.1（2026-11-02）
> 目的：按**平台职责**拆分，不再按业务阶段 M1–M6 拆分。
> 旧 M1–M6 文档保留为历史 phase 记录；目标架构见 `docs/ARCHITECTURE.md`。

---

## 1. 平台模块

| ID | 模块 | 目录（目标） | 职责 |
|---|---|---|---|
| **W** | Workflow | [docs/modules/workflow/](workflow/README.md) | 特制任务外壳；阶段拆分、约束、验收、commit/resume |
| **K** | Kernel | [docs/modules/kernel/](kernel/README.md) | 通用 Agent Kernel；可独立完成复杂任务 |
| **T** | Tools | [docs/modules/tools/](tools/README.md) | ToolRuntime；general/domain toolset；参数/输出校验 |
| **V** | Verification | [docs/modules/verify/](verify/README.md) | CodeVerifier + LLM AuditVerifier + Verdict |
| **S** | Storage | [docs/modules/storage/](storage/README.md) | artifacts、SQLite、events、metrics、report repository |
| **I** | Interface | [docs/modules/interface/](interface/README.md) | API、SSE、CLI、UI |

## 2. 领域工具包

| ID | 模块 | 目录（目标） | 职责 |
|---|---|---|---|
| **R** | Research | [docs/modules/research/](research/README.md) | source/evidence/report 工具包 |
| **E** | Evaluation | [docs/modules/evaluation/](evaluation/README.md) | dataset、scorecard、judge、calibration |

## 3. 组合层

| ID | 模块 | 目录 | 职责 |
|---|---|---|---|
| **C** | Composition | [docs/modules/composition/](composition/README.md) | 唯一装配点；可 import 所有 concrete |

---

## 4. 依赖方向

```text
Interface
  ↓
Workflow
  ↓
Kernel
  ↓
Tools
  ↓
Storage

Verification 横向作用于 Node 输出

Domains → Tools contracts
Composition → all concrete
```

规则：

- Workflow 不 import domain service；
- Kernel 不 import domain service；
- 所有外部 I/O 只能通过 Tool；
- Domains 之间不互相调用 service；
- Interface 不绕过 Workflow 直接写 DB；
- Composition 是唯一允许 import 所有模块的地方。

---

## 5. Kernel 与 Workflow

```text
Kernel = 通用 Agent 发动机
         可独立完成复杂任务
         不知道 report/paper/claim

Workflow = 特制任务外壳
           拆解阶段、约束 Kernel、验收中间产物
           报告/Chat/研究各自不同

Node = Workflow 的一个阶段
       NodeSpec → KernelTask
```

详见 [`docs/KERNEL-WORKFLOW.md`](../KERNEL-WORKFLOW.md)。

Node 不是“另一个层级”，而是 Workflow 的元素。

一个 Node：

```text
goal
tools allowlist
input artifacts
output schema
code verifier + audit verifier
budget
optional / enabled
```

---

## 6. 旧 M1–M6 映射

| 旧 | 新归属 |
|---|---|
| M1 Engine | W + K + S（部分 V） |
| M2 Source | R：source tools |
| M3 Evidence | R：evidence tools |
| M4 Report | R：report tools；一个 `report.generate` node |
| M5 Evaluation | E：eval tools；可选 scorecard node |
| M6 Interface | I |

旧模块文档：

```text
D:\lit-agent-store\legacy-archive-20261101\docs-modules\m1-engine\
D:\lit-agent-store\legacy-archive-20261101\docs-modules\m2-source\
D:\lit-agent-store\legacy-archive-20261101\docs-modules\m3-evidence\
D:\lit-agent-store\legacy-archive-20261101\docs-modules\m4-report\
D:\lit-agent-store\legacy-archive-20261101\docs-modules\m5-evaluation\
D:\lit-agent-store\legacy-archive-20261101\docs-modules\m6-interface\
```

状态：**历史阶段记录**，不是目标模块划分。

---

## 7. Phase 命名

目标模块使用新 ID：

```text
W-P01-workflow-optional-nodes.md
K-P02-kernel-tool-checkpoint.md
T-P01-tool-registry.md
V-P01-dual-verifier.md
R-P01-report-node-agent.md
E-P01-scorecard-node.md
I-P01-report-api.md
```

格式：

```text
^(W|K|T|V|S|I|R|E|C)-P\d{2}-[a-z0-9-]+\.md$
```

旧 `M1-P01` 文件保留，不再新增。

---

## 8. Commit 标准

```text
<type>(<module>-P<nn>): <summary>
```

示例：

```text
feat(W-P01): add optional node execution
feat(K-P01): add node goal and tool registry context
feat(T-P01): wrap source adapters as tools
feat(V-P01): add code and audit verdict
feat(R-P01): add report generate agent node
```

---

## 9. 迁移原则

- 一次只迁一个平台模块；
- 先工具化，再 agent 化；
- 不删除旧代码，先加新入口；
- 旧 M1–M6 phase 文档只读；
- 新 phase 文档写在新模块目录；
- 契约变更走 `docs/CONTRACTS.md`。
