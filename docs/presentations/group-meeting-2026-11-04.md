# Group Meeting · 2026-11-04

> Deck source for PPT Master.
> Each slide has **English slide copy** and **Chinese speaker notes**.
> Speaker notes explain why each line exists and what to show.

---

# Slide 1 — Title

## English Copy

- Evidence-Grounded Literature Agent
- Generic Kernel + Specialized Report Workflow
- Demo · Architecture · Current Status · Next Steps

## 中文讲解（speaker notes）

- **Evidence-Grounded Literature Agent**
  - 为什么：一句话说明不是普通聊天 Agent，而是基于论文证据产出报告的系统。
  - 展示：大标题，背景放论文/引用网络抽象图。
- **Generic Kernel + Specialized Report Workflow**
  - 为什么：直接点出本次组会最重要的架构判断——内核通用，Workflow 特制。
  - 展示：标题下方一行副标题，或用两个并列色块。
- **Demo · Architecture · Current Status · Next Steps**
  - 为什么：先给听众路线图，避免一上来陷入实现细节。
  - 展示：四个短标签，下面用细线连接。

---

# Slide 2 — Demo in One Slide

## English Copy

- One request → an evidence-grounded literature review
- 100-paper benchmark: 98 fulltext, 196 claims, 23 sections
- Quality gate passed; LLM audit accepted
- Every factual sentence carries a citation

## 中文讲解（speaker notes）

- **One request → an evidence-grounded literature review**
  - 为什么：用最短路径说明输入输出，先让听众理解 demo 是什么。
  - 展示：左侧 “New Run”，右侧 “Report + citations”，中间箭头。
- **100-paper benchmark: 98 fulltext, 196 claims, 23 sections**
  - 为什么：三个数字分别代表数据规模、证据规模、报告规模，比单说“效果不错”可信。
  - 展示：三个大数字卡片，下面标注 papers / claims / sections。
- **Quality gate passed; LLM audit accepted**
  - 为什么：说明不是“生成完就算”，而是有质量门禁。
  - 展示：绿色 check 标识，旁边写 quality gate / audit。
- **Every factual sentence carries a citation**
  - 为什么：这是系统最核心的可信性主张，也是和普通报告生成的区别。
  - 展示：截一段报告，用高亮标出 `[C#]` 和论文标题链接。

---

# Slide 3 — End-to-End Demo Flow

## English Copy

- Choose source: local corpus / online search / auto
- Five stages: source → evidence → plan → write → finalize
- Live node progress, section progress, paper links
- Reports are inspectable, resumable, and retryable

## 中文讲解（speaker notes）

- **Choose source: local corpus / online search / auto**
  - 为什么：说明系统不是写死本地数据，Agent 可以选择数据来源。
  - 展示：New Run 弹窗截图，圈出 Source 和 Paper limit。
- **Five stages: source → evidence → plan → write → finalize**
  - 为什么：给听众一个可记忆的流程骨架，后面架构页会展开。
  - 展示：横向 5 个节点，节点之间用箭头连接。
- **Live node progress, section progress, paper links**
  - 为什么：强调前端不是只看最终文件，而是能看到 Agent 正在做什么。
  - 展示：Trajectory 页面截图，标出 Node 进度和 section 进度。
- **Reports are inspectable, resumable, and retryable**
  - 为什么：说明工程属性：可检查、可恢复、可局部重试。
  - 展示：三个词做成三个小标签，放在流程下方。

---

# Slide 4 — Why This Is a Real Refactor

## English Copy

- Old chain: four fixed nodes, each calling a scripted `demo.*` tool
- New chain: a generic think → act → observe loop
- Workflow fixes only stage boundaries, not the internal tool sequence
- The Node contract replaces hard-coded orchestration

## 中文讲解（speaker notes）

- **Old chain: four fixed nodes, each calling a scripted `demo.*` tool**
  - 为什么：必须先把“旧版到底是什么”说清楚，否则听众会以为只是改名字。
  - 展示：旧版 4 个节点，每个节点只连一个 `demo.source` / `demo.evidence` / `demo.report` / `demo.finalize`。
- **New chain: a generic think → act → observe loop**
  - 为什么：这是本次重构的核心变化：Node 内部不再写死下一步调用。
  - 展示：循环图：LLM 思考 → 选工具 → 观察结果 → 再思考/修复。
- **Workflow fixes only stage boundaries, not the internal tool sequence**
  - 为什么：澄清“全由 LLM 决定”不是取消阶段，而是取消阶段内部的硬编码；阶段边界仍由特制 Workflow 负责。
  - 展示：一条固定阶段带 + 每个阶段内部由 LLM 自由选择工具。
- **The Node contract replaces hard-coded orchestration**
  - 为什么：说明旧 `DemoOrchestrator` 被 Node + Kernel 契约取代。
  - 展示：删除线划掉 `DemoOrchestrator`，指向 `NodeSpec → KernelTask`。

---

# Slide 5 — Two-Layer Architecture in Detail

## English Copy

- Kernel is generic: Goal, Plan, Tool, Observation, Memory, Budget, Checkpoint
- Workflow is specialized: stage order, inputs, outputs, toolsets, verifiers, budgets
- Node is the contract between them, not a tool alias
- Tools and verifiers attach at the Node boundary; no domain logic in the Kernel

## 中文讲解（speaker notes）

- **Kernel is generic...**
  - 为什么：先定义内核边界，避免别人误以为 Kernel 里写了报告逻辑。
  - 展示：左侧 Kernel 色块，只列通用概念，不出现 paper / claim。
- **Workflow is specialized...**
  - 为什么：强调 Workflow 不是通用平台，而是报告任务的特制外壳。
  - 展示：右侧 Workflow 色块，列 source / evidence / plan / write / finalize。
- **Node is the contract between them, not a tool alias**
  - 为什么：解释两层如何连接：Workflow 用 Node 把阶段任务交给 Kernel。
  - 展示：中间一个 Node 桥接块，箭头从 Workflow 指向 Kernel。
- **Tools and verifiers attach at the Node boundary; no domain logic in the Kernel**
  - 为什么：说明 Tool 和 Verifier 属于领域层，内核只负责调度和执行。
  - 展示：Node 下方挂 ToolRuntime 和 Verifier 两个小方块。

---

# Slide 6 — Who Decides What

## English Copy

- Workflow decides: stage order, input/output contracts, toolset, verifier, budget
- LLM decides: which tool, arguments, next step, and whether to repair
- Kernel enforces: loop, cancellation, checkpoint, budget, schema
- This avoids both a fixed script and an unconstrained agent

## 中文讲解（speaker notes）

- **Workflow decides: stage order, input/output contracts, toolset, verifier, budget**
  - 为什么：说明“特制”体现在哪里：阶段与验收由领域代码决定。
  - 展示：左侧 Workflow 列：Order / Schema / Toolset / Verifier / Budget。
- **LLM decides: which tool, arguments, next step, and whether to repair**
  - 为什么：说明“全由 LLM 思考”发生在 Node 内部，而不是让 LLM 重写整个流程。
  - 展示：右侧 LLM 列：Tool choice / Args / Next step / Repair。
- **Kernel enforces: loop, cancellation, checkpoint, budget, schema**
  - 为什么：强调自由不是失控，内核仍负责硬约束。
  - 展示：中间 Kernel 列：Loop / Cancel / Checkpoint / Budget / Schema。
- **This avoids both a fixed script and an unconstrained agent**
  - 为什么：总结设计取舍：既不是旧式硬编码，也不是完全自由，而是“受约束的自主”。
  - 展示：底部一句话 “Constrained autonomy”。

---

# Slide 7 — Generic Kernel

## English Copy

- Kernel plans, calls tools, observes, and revises
- Checkpoint, resume, compaction, repair, budget are built in
- L3 validation: 30 simple + 14 complex + 8 concurrent tasks
- Kernel imports no report, paper, or claim code

## 中文讲解（speaker notes）

- **Kernel plans, calls tools, observes, and revises**
  - 为什么：用四个动词概括通用 Agent 循环，不展开实现细节。
  - 展示：循环图 Plan → Tool → Observe → Revise。
- **Checkpoint, resume, compaction, repair, budget are built in**
  - 为什么：这些是“能跑长任务”的关键，不只是 demo 装饰。
  - 展示：五个能力做成图标排成一行。
- **L3 validation: 30 simple + 14 complex + 8 concurrent tasks**
  - 为什么：用真实验证数量证明内核不是只跑通一个报告。
  - 展示：三组数字，分别标注 simple / complex / soak。
- **Kernel imports no report, paper, or claim code**
  - 为什么：这是架构守卫，防止领域逻辑污染内核。
  - 展示：代码片段或依赖图，标出“no domain imports”。

---

# Slide 8 — Report Workflow: Five Nodes

## English Copy

- source.collect → evidence.extract → report.plan → report.write → report.audit_finalize
- Each node has goal, inputs, toolset, output schema, verifier, budget
- Failures stay inside one stage
- The workflow is report-specific, not a generic profile

## 中文讲解（speaker notes）

- **source.collect → ... → report.audit_finalize**
  - 为什么：这是报告任务的完整阶段链，听众可以直接看到拆分结果。
  - 展示：五节点流程条，节点下方写产物。
- **Each node has goal, inputs, toolset, output schema, verifier, budget**
  - 为什么：说明 Node 不是随便调一个工具，而是完整契约。
  - 展示：NodeSpec 的六个字段做成六宫格。
- **Failures stay inside one stage**
  - 为什么：这是拆分的核心收益——检索失败不重写报告，单节失败不重跑全篇。
  - 展示：在 source / write 节点上画红色隔离边界。
- **The workflow is report-specific, not a generic profile**
  - 为什么：再次强调设计选择，避免被误解为“通用 Workflow + 报告配置”。
  - 展示：底部一句 “No generic report workflow”。

---

# Slide 9 — Node Contract in Practice

## English Copy

- A Node is a stage, not a tool call
- `report.write` loops section by section
- Each section is checked, retried, and checkpointed
- The Node returns a verifiable artifact

## 中文讲解（speaker notes）

- **A Node is a stage, not a tool call**
  - 为什么：纠正常见误解：Node 是阶段边界，不是单个工具的别名。
  - 展示：左侧 Node 大框，里面包含多个 tool calls。
- **`report.write` loops section by section**
  - 为什么：用最复杂的 Node 说明 Node-level loop 如何工作。
  - 展示：section_status → write_next_section → check → next。
- **Each section is checked, retried, and checkpointed**
  - 为什么：说明失败粒度是 section，不是整篇 report。
  - 展示：单个 section 卡片，标 attempts / ok / checkpoint。
- **The Node returns a verifiable artifact**
  - 为什么：强调阶段产物必须可验收，而不是只返回一段自然语言。
  - 展示：draft.json / sections/*.json 文件名。

---

# Slide 10 — Tool Layer and Source Choice

## English Copy

- One ToolRuntime, scoped toolsets per Node
- Local corpus and online OpenAlex/PDF paths
- Parallel-safe tools overlap; exclusive tools form barriers
- Default demo size: 20 papers; benchmark: 100 papers

## 中文讲解（speaker notes）

- **One ToolRuntime, scoped toolsets per Node**
  - 为什么：说明工具不是散落各处，而是统一运行时 + 节点可见性。
  - 展示：ToolRuntime 中心，向外连 5 个 Node toolset。
- **Local corpus and online OpenAlex/PDF paths**
  - 为什么：回应用户需求：既能读本地已有论文，也能在线检索下载。
  - 展示：Local / Online 两条分支，汇聚到 source artifact。
- **Parallel-safe tools overlap; exclusive tools form barriers**
  - 为什么：说明调度不是简单 for 循环，能安全并行、也能顺序隔离。
  - 展示：两条并行箭头 + 一个 barrier 竖线。
- **Default demo size: 20 papers; benchmark: 100 papers**
  - 为什么：说明当前测试成本和完整 benchmark 的区别，避免误解规模。
  - 展示：20 / 100 两个数字，分别标 demo / benchmark。

---

# Slide 11 — Quality and Observability

## English Copy

- Dynamic quality gate: thresholds follow the requested paper count
- Section metrics: citations, claim refs, empty sections, duplicates
- LLM audit: explicit reject blocks; unavailable is recorded
- SSE events expose tool calls, thinking summaries, and progress

## 中文讲解（speaker notes）

- **Dynamic quality gate...**
  - 为什么：解释 20 篇 demo 不会被 100 篇硬阈值卡住。
  - 展示：target 20 → thresholds 20；target 100 → thresholds 100。
- **Section metrics...**
  - 为什么：说明质量不是只看总字数，而是逐节检查引用和引用问题。
  - 展示：section metrics 表格截图，圈出 citations / problems。
- **LLM audit: explicit reject blocks; unavailable is recorded**
  - 为什么：说明 audit 是硬门禁，但基础设施失败时不会伪装成通过。
  - 展示：accepted / rejected / unavailable 三个状态。
- **SSE events expose tool calls, thinking summaries, and progress**
  - 为什么：说明前端实时更新和可解释性来自事件流，不是轮询截图。
  - 展示：EventSource 事件列表或浏览器 Network 截图。

---

# Slide 12 — Current Features

## English Copy

- Local / online / auto source selection
- Paper titles are clickable and open a paper tab
- Markdown reports with citations, lists, tables, and code
- Pause, resume, section retry, and failure visibility

## 中文讲解（speaker notes）

- **Local / online / auto source selection**
  - 为什么：展示当前用户可以实际选择数据来源，而不是只能走固定 demo。
  - 展示：New Run 的 Source 下拉框。
- **Paper titles are clickable...**
  - 为什么：说明报告不是纯文本，标题和引用都能回到证据/论文。
  - 展示：报告页点击标题打开 Paper tab 的截图。
- **Markdown reports...**
  - 为什么：说明格式已从手写解析升级为标准 Markdown 渲染。
  - 展示：带列表、表格、代码块的报告片段。
- **Pause, resume, section retry...**
  - 为什么：说明失败和中断是可操作的，不是只能重跑。
  - 展示：Pause/Resume 按钮 + Retry failed section。

---

# Slide 13 — Results and Engineering Validation

## English Copy

- 100-paper benchmark: 98 fulltext, 196 claims, 23 sections
- 20-paper demo: 19 fulltext, 38 claims, 7 sections
- Citation coverage 1.0; quality gate passed; audit accepted
- 128 tests; Ruff clean; frontend build passing; L3 gate passed

## 中文讲解（speaker notes）

- **100-paper benchmark...**
  - 为什么：给出完整规模结果，证明不是只跑小样本。
  - 展示：100 / 98 / 196 / 23 四个数字。
- **20-paper demo...**
  - 为什么：给出当前默认 demo 的真实结果，和 benchmark 区分。
  - 展示：20 / 19 / 38 / 7 四个数字。
- **Citation coverage 1.0; quality gate passed; audit accepted**
  - 为什么：强调结果不是“看起来像报告”，而是通过硬性检查。
  - 展示：coverage 1.0 + green pass。
- **128 tests; Ruff clean; frontend build passing; L3 gate passed**
  - 为什么：用可复现的工程指标支撑“能用”，而不只是展示一次 demo。
  - 展示：四行命令/结果，底部写 30/30、12/14、8/8。

---

# Slide 14 — Limitations

## English Copy

- RAG, Qdrant, and Kuzu are not implemented yet
- Chat is still local retrieval, not a full LLM chat workflow
- 2 of 100 fulltext downloads still fail
- LLM audit is fail-open when the auditor itself is unavailable

## 中文讲解（speaker notes）

- **RAG, Qdrant, and Kuzu are not implemented yet**
  - 为什么：主动划清边界，避免把当前报告 demo 说成完整 RAG 系统。
  - 展示：三个灰色未完成模块。
- **Chat is still local retrieval...**
  - 为什么：说明 Chat 不是本次重点，当前仍是基础链路。
  - 展示：Chat 页面和“local retrieval”标签。
- **2 of 100 fulltext downloads still fail**
  - 为什么：诚实展示数据质量边界，不把 98/100 说成 100/100。
  - 展示：95→98 的提升和剩余 2 个失败。
- **LLM audit is fail-open...**
  - 为什么：说明质量策略的取舍：保证流程可跑，但记录 unavailable。
  - 展示：audit 状态三态图。

---

# Slide 15 — Future Hard Problems

## English Copy

- High-quality paper retrieval: coverage, precision, PDF parsing, paywalls
- Real RAG: chunking, embeddings, hybrid search, reranking, traceable evidence
- Three-database collaboration: SQLite + Qdrant + Kuzu consistency and ingestion
- Report format: making the LLM follow a stable template and citation contract

## 中文讲解（speaker notes）

- **High-quality paper retrieval...**
  - 为什么：当前 demo 只用本地 corpus 或简单在线检索，真实场景要先解决论文覆盖率和质量。
  - 展示：检索漏斗：query → candidates → dedupe → fulltext → usable papers；标出 paywall / parsing / long tail。
- **Real RAG...**
  - 为什么：当前是 exact-quote 证据，不是完整向量 RAG；要说明下一步的技术难点。
  - 展示：chunk → embedding → hybrid retrieval → rerank → citation；强调“可追溯证据”比“相似度”更重要。
- **Three-database collaboration...**
  - 为什么：SQLite / Qdrant / Kuzu 各自解决不同问题，但一致性、重建和 D 盘存储是工程难点。
  - 展示：三库图：SQLite 元数据、Qdrant 向量、Kuzu 关系；中间放 ingestion / outbox。
- **Report format...**
  - 为什么：LLM 仍然会偏离模板，报告格式和模板需要变成可验收契约，而不只是 prompt。
  - 展示：prompt → draft → post-check → fallback 的闭环；标出“模板不是提示词，是契约”。

---

# Slide 16 — Proposed Report Template

## English Copy

- Current: At a Glance → Papers N-M → Cross-Paper Synthesis → Paper Index
- Proposed: add Scope, Method, Evidence Notes, Open Problems, Limitations
- Every section has a job, a citation rule, and a target length
- The template should be a contract, not only a prompt

## 中文讲解（speaker notes）

- **Current: At a Glance → ... → Paper Index**
  - 为什么：先承认当前模板已经能产出报告，但结构还比较“论文清单式”。
  - 展示：当前 5 类 section 的简图。
- **Proposed: add Scope, Method, Evidence Notes, Open Problems, Limitations**
  - 为什么：让报告从“论文摘要集合”升级为“有研究判断的综述”。
  - 展示：提议模板全文（下方）。
- **Every section has a job, a citation rule, and a target length**
  - 为什么：格式统一不能靠模型自觉，必须把 section 变成可验收契约。
  - 展示：一个 section card：Goal / Citation / Length / Verifier。
- **The template should be a contract, not only a prompt**
  - 为什么：这是未来报告质量的关键方向，也是想请导师给意见的地方。
  - 展示：prompt → schema → verifier → fallback。

### Proposed template (English, on slide)

```text
# <Report title>

## Executive Summary
## Scope and Method
## Research Landscape
## Paper-by-Paper Analysis
## Cross-Paper Synthesis
## Evidence and Citation Notes
## Open Problems
## Limitations
## Paper Index
```

---

# Slide 17 — Questions for the Advisor

## English Copy

- Which sections are essential for this report to be useful?
- What balance do you expect: paper-by-paper vs cross-paper synthesis?
- What is the minimum evidence and citation standard?
- Should we prioritize RAG / three databases, or report depth first?

## 中文讲解（speaker notes）

- **Which sections are essential...**
  - 为什么：当前模板是工程视角，不确定导师/读者真正需要的章节。
  - 展示：当前模板 + 提议模板并排，留出批注空间。
- **What balance...**
  - 为什么：报告可能太像论文列表，也可能过度综合；需要导师定义“综述感”。
  - 展示：两个极端：Paper list ↔ Synthesis；中间标理想比例。
- **What is the minimum evidence...**
  - 为什么：引用覆盖、quote 长度、允不允许 abstract-only，会直接影响质量门禁。
  - 展示：citation coverage / exact quote / abstract-only 三个指标。
- **Should we prioritize RAG / three databases...**
  - 为什么：下一步资源有限，需要导师判断先补检索基础设施还是先提升报告深度。
  - 展示：两条路线：RAG/3DB vs report depth；标出时间成本。

---

# Slide 18 — Closing

## English Copy

- General kernel, specialized workflows
- A working evidence-grounded report demo
- Honest limits, clear next steps
- Feedback welcome: node granularity, quality thresholds, report scope

## 中文讲解（speaker notes）

- **General kernel, specialized workflows**
  - 为什么：用一句话回收全篇最重要的架构结论。
  - 展示：标题居中，下方放双层架构缩略图。
- **A working evidence-grounded report demo**
  - 为什么：明确本次组会交付物是“可运行 demo”，不是概念图。
  - 展示：报告截图 + 5 Node trace。
- **Honest limits, clear next steps**
  - 为什么：让听众知道哪些没做，避免过度承诺。
  - 展示：Limitations / Next 两列。
- **Feedback welcome...**
  - 为什么：把组会变成讨论，而不是单向汇报。
  - 展示：三个问题作为结尾：节点粒度是否合理？质量阈值是否合适？报告范围是否足够？
