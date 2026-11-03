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

# Slide 4 — Two-Layer Architecture

## English Copy

- Kernel is generic: it knows Goal, Tool, Observation, Plan, Memory, Budget
- Workflow is specialized: it owns report stages and domain rules
- Node is the contract between them
- Tools and verifiers attach at the edges

## 中文讲解（speaker notes）

- **Kernel is generic...**
  - 为什么：先定义内核边界，避免别人误以为 Kernel 里写了报告逻辑。
  - 展示：左侧 Kernel 色块，只列通用概念，不出现 paper / claim。
- **Workflow is specialized...**
  - 为什么：强调 Workflow 不是通用平台，而是报告任务的特制外壳。
  - 展示：右侧 Workflow 色块，列 source / evidence / plan / write / finalize。
- **Node is the contract between them**
  - 为什么：解释两层如何连接：Workflow 用 Node 把阶段任务交给 Kernel。
  - 展示：中间一个 Node 桥接块，箭头从 Workflow 指向 Kernel。
- **Tools and verifiers attach at the edges**
  - 为什么：说明 Tool 和 Verifier 不是内核领域逻辑，而是挂在 Node 边界。
  - 展示：Node 下方挂 ToolRuntime 和 Verifier 两个小方块。

---

# Slide 5 — Generic Kernel

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

# Slide 6 — Report Workflow: Five Nodes

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

# Slide 7 — Node Contract in Practice

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

# Slide 8 — Tool Layer and Source Choice

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

# Slide 9 — Quality and Observability

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

# Slide 10 — Current Features

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

# Slide 11 — Results

## English Copy

- 100-paper benchmark: 98 fulltext, 196 claims, 23 sections
- 20-paper demo: 19 fulltext, 38 claims, 7 sections
- Citation coverage: 1.0; quality gate: passed
- The report is generated end-to-end by the generic kernel

## 中文讲解（speaker notes）

- **100-paper benchmark...**
  - 为什么：给出完整规模结果，证明不是只跑小样本。
  - 展示：100 / 98 / 196 / 23 四个数字。
- **20-paper demo...**
  - 为什么：给出当前默认 demo 的真实结果，和 benchmark 区分。
  - 展示：20 / 19 / 38 / 7 四个数字。
- **Citation coverage: 1.0; quality gate: passed**
  - 为什么：强调结果不是“看起来像报告”，而是通过硬性检查。
  - 展示：coverage 1.0 + green pass。
- **The report is generated end-to-end by the generic kernel**
  - 为什么：把结果和架构主张连起来，说明不是旧流水线包装。
  - 展示：5 个 Node committed 的 trace 截图。

---

# Slide 12 — Engineering Validation

## English Copy

- 128 tests passing; Ruff clean; frontend build passing
- Failure paths covered: tool error, max steps, audit, resume
- API and CLI share the same five-node workflow
- L3 gate: simple 30/30, complex 12/14, soak 8/8

## 中文讲解（speaker notes）

- **128 tests...**
  - 为什么：用可复现的工程指标支撑“能用”，而不是只展示一个 demo。
  - 展示：测试输出截图，三行命令结果。
- **Failure paths covered...**
  - 为什么：说明失败不是没测，而是有专门的失败路径测试。
  - 展示：测试文件名列表：kernel failures / stress / report v2。
- **API and CLI share the same five-node workflow**
  - 为什么：说明不是只为 CLI 做了一个演示分支。
  - 展示：API 和 CLI 都指向 `build_report_v2_workflow()`。
- **L3 gate...**
  - 为什么：说明内核在报告之外也做过真实任务验证。
  - 展示：30/30、12/14、8/8 三组数字。

---

# Slide 13 — Limitations

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

# Slide 14 — Next Steps

## English Copy

- 4.3: add Qdrant, Kuzu, and a real RAG retrieval path
- Scale evaluation: more topics, larger corpora, retrieval quality
- Chat: reuse the same kernel and retrieval port
- Report UX: quality trends and section-level comparison

## 中文讲解（speaker notes）

- **4.3: add Qdrant, Kuzu...**
  - 为什么：明确下一阶段的技术主线，不是继续堆报告模板。
  - 展示：SQLite / Qdrant / Kuzu 三库示意图。
- **Scale evaluation...**
  - 为什么：说明当前 20/100 只是测试规模，下一步要看泛化。
  - 展示：20 → 100 → larger corpus 的箭头。
- **Chat: reuse the same kernel and retrieval port**
  - 为什么：强调架构复用，不是为 Chat 再写一套 agent。
  - 展示：Kernel 同时连 Report Workflow 和 Chat Workflow。
- **Report UX: quality trends...**
  - 为什么：说明前端下一步不是装饰，而是帮助评估质量。
  - 展示：quality trend 折线图草图。

---

# Slide 15 — Closing

## English Copy

- General kernel, specialized workflows
- A working evidence-grounded report demo
- Honest limits, clear next steps
- Feedback welcome: node granularity, quality thresholds, demo scope

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
  - 展示：三个问题作为结尾：节点粒度是否合理？质量阈值是否合适？demo 范围是否足够？
