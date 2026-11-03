# Group Meeting · 2026-11-04

> Deck source for PPT Master.
> Each slide has **English slide copy** and **Chinese speaker notes**.
> The Chinese notes explain the exact meaning of every line, why it is defensible, what to show, and likely advisor questions.

---

# Slide 1 — Title

## English Copy

- Evidence-Grounded Literature Agent
- Generic Kernel + Specialized Report Workflow
- Demo · Architecture · Current Status · Next Steps

## 中文讲解（speaker notes）

- **Evidence-Grounded Literature Agent**
  - 字面：一个以论文证据为依据、生成文献综述的 Agent。
  - 为什么准确：系统的每条 claim 都来自论文原文 exact quote，报告正文要求带 `[C#]` 引用。
  - 展示：标题 + 论文/引用网络抽象图。
  - 导师可能问：和普通 ChatGPT 写综述有什么区别？
  - 回答：普通生成是“先写再找依据”；这里是“先抽证据，再基于证据写”，并做 citation / quality gate。

- **Generic Kernel + Specialized Report Workflow**
  - 字面：通用 Agent 内核 + 专门为报告任务定制的 Workflow。
  - 为什么准确：`AgentKernel` 不 import report/paper/claim；报告阶段、schema、verifier 都在 Workflow / Node 层。
  - 展示：左右两个色块：Kernel / Workflow。
  - 导师可能问：这是不是一个通用 Workflow？
  - 回答：不是。Kernel 通用，Workflow 特制；“报告 Workflow”只服务报告。

- **Demo · Architecture · Current Status · Next Steps**
  - 字面：本次汇报覆盖 demo、架构、当前状态、下一步。
  - 为什么这样排：先让导师看到结果，再解释架构，最后讨论限制和计划。
  - 展示：四个短标签，下面用细线连接。

---

# Slide 2 — Demo in One Slide

## English Copy

- One request → an evidence-grounded literature review
- 100-paper benchmark: 98 fulltext, 196 claims, 23 sections
- Quality gate passed; LLM audit accepted
- Every factual sentence is required to carry a citation

## 中文讲解（speaker notes）

- **One request → an evidence-grounded literature review**
  - 字面：输入一个研究主题，输出一份有证据的文献综述。
  - 为什么这样写：这是系统最小闭环：New Run → report，不需要人工逐篇整理。
  - 展示：左侧 New Run，右侧 report + citations，中间箭头。
  - 导师可能问：输入只有主题吗？
  - 回答：主题 + 可选 focus + language + source mode + paper limit。

- **100-paper benchmark: 98 fulltext, 196 claims, 23 sections**
  - 字面：100 篇论文中 98 篇有全文，抽出 196 条 exact-quote claim，生成 23 个 section。
  - 为什么用这三个数字：分别代表“数据覆盖”“证据规模”“报告规模”，比“效果不错”可验证。
  - 数据来源：`report.json` 的 `papers/fulltext/claims/sections`。
  - 展示：三个数字卡片。
  - 导师可能问：为什么不是 100 篇全全文？
  - 回答：2 篇 PDF/HTML 下载失败，报告中按 98/100 记录，不伪装成 100。

- **Quality gate passed; LLM audit accepted**
  - 字面：质量门禁通过，LLM audit 接受。
  - 为什么准确：deterministic gate 检查 papers/claims/sections/words/citation；LLM audit 是另一个独立检查。
  - 展示：两个绿色 check。
  - 导师可能问：audit 是模型自己评自己吗？
  - 回答：是独立 LLM audit；明确 reject 会阻止发布，audit 不可用时记录 unavailable，不伪装通过。

- **Every factual sentence is required to carry a citation**
  - 字面：每条事实句都必须带引用；不是“每段随便有一个引用”。
  - 为什么这样写：这是质量门禁和写作 prompt 的共同要求；citation coverage 在最终报告上复算。
  - 展示：报告片段，圈出 `[C#]` 和论文标题链接。
  - 导师可能问：如果一句话没有引用呢？
  - 回答：section checker 会报 no claim citations / unknown refs；失败会 fallback 或导致 finalize 失败。

---

# Slide 3 — End-to-End Demo Flow

## English Copy

- Choose source: local corpus / online search
- Five stages: source → evidence → plan → write → finalize
- Live node progress, section progress, paper links
- Reports are inspectable, resumable, and retryable

## 中文讲解（speaker notes）

- **Choose source: local corpus / online search**
  - 字面：可以读本地 corpus，也可以在线检索。
  - 为什么准确：`source.collect` 读本地 `papers.jsonl + fulltext`；`source.collect_online` 用 OpenAlex 搜索并尝试下载 PDF/HTML。
  - 展示：New Run 的 Source 下拉框；local / online。
  - 导师可能问：自动选择呢？
  - 回答：当前 UI 还保留 auto 选项，但默认可靠路径是 local / online；auto 属于后续优化，不在汇报中夸大。

- **Five stages: source → evidence → plan → write → finalize**
  - 字面：五个报告阶段：收集、证据、规划、写作、审核发布。
  - 为什么准确：`build_report_v2_workflow()` 的 5 个 NodeSpec 就是这个顺序。
  - 展示：横向 5 节点流程条。
  - 导师可能问：为什么要分成 5 段？
  - 回答：每段有独立产物、schema、verifier；检索失败不重写报告，单节失败不重跑全篇。

- **Live node progress, section progress, paper links**
  - 字面：前端实时显示 Node 进度、section 进度和论文链接。
  - 为什么准确：SSE `/events` 推送 `node.* / kernel.* / section.written`；报告标题链接到 `#paper-<id>`。
  - 展示：Trajectory 截图 + section progress + 标题点击。
  - 导师可能问：为什么不是刷新页面？
  - 回答：EventSource 持续接收事件，页面实时 append；懒加载时 `trace` 做快照。

- **Reports are inspectable, resumable, and retryable**
  - 字面：报告可检查、可恢复、可局部重试。
  - 为什么准确：JSON artifacts、section 文件、checkpoint、`--resume`、retry section API。
  - 展示：`report.json`、`sections/*.json`、Pause/Resume 按钮。
  - 导师可能问：中断后会不会重复生成？
  - 回答：已提交 Node 从 NodeStore 恢复；section 文件已 ok 会跳过；不会重复 report。

---

# Slide 4 — Why This Is a Real Refactor

## English Copy

- Old chain: four fixed nodes, each calling a scripted `demo.*` tool
- New chain: a generic think → act → observe loop
- Workflow fixes only stage boundaries, not the internal tool sequence
- The Node contract replaces hard-coded orchestration

## 中文讲解（speaker notes）

- **Old chain: four fixed nodes, each calling a scripted `demo.*` tool**
  - 字面：旧版是 4 个固定 Node，每个 Node 只调用一个写死的 `demo.*` 工具。
  - 为什么准确：旧 `DemoOrchestrator` 为每个 Node 返回固定 tool call，`demo.source / demo.evidence / demo.report / demo.finalize`。
  - 展示：旧版 4 Node + 每个 Node 右边挂一个 `demo.*`。
  - 导师可能问：旧版不是也能跑吗？
  - 回答：能跑，但它是“编排出来的 demo”，不是通用 Agent；工具选择不在 LLM。

- **New chain: a generic think → act → observe loop**
  - 字面：新版是通用的“思考 → 行动 → 观察”循环。
  - 为什么准确：`AgentKernel` 每步让 LLM 返回 action，执行工具，把 observation 写回 history，再下一步。
  - 展示：循环图 Thought → Tool → Observation → Thought。
  - 导师可能问：LLM 每一步都能自由决定工具吗？
  - 回答：在 Node 可见 toolset 内自由选择；不能越权调用其他 Node 的工具。

- **Workflow fixes only stage boundaries, not the internal tool sequence**
  - 字面：Workflow 只固定阶段边界，不固定阶段内部的工具调用顺序。
  - 为什么准确：NodeSpec 固定 goal/inputs/toolset/schema/verifier/budget；具体调用哪个工具、参数、是否 retry 由 Kernel LLM 决定。
  - 展示：上面一条固定阶段带，每个阶段内部画“LLM 选择工具”的分叉。
  - 导师可能问：那还不是有固定 Node？
  - 回答：是，阶段固定是特制 Workflow 的职责；重构点在于去掉“阶段内部写死 demo.* 调用”。

- **The Node contract replaces hard-coded orchestration**
  - 字面：Node 契约取代了硬编码编排器。
  - 为什么准确：`DemoOrchestrator` 已从生产 interface 删除；现在 `NodeSpec → KernelTask → AgentKernel`。
  - 展示：删除线 `DemoOrchestrator` → `NodeSpec / KernelTask`。
  - 导师可能问：删除编排器后怎么保证顺序？
  - 回答：`WorkflowRunner` 按 WorkflowDefinition 顺序执行 Node；顺序是 Workflow 的职责，不是 Kernel 的。

---

# Slide 5 — Two-Layer Architecture in Detail

## English Copy

- Kernel is generic: Goal, Plan, Tool, Observation, Memory, Budget, Checkpoint
- Workflow is specialized: stage order, inputs, outputs, toolsets, verifiers, budgets
- Node is the contract between them, not a tool alias
- Tools and verifiers attach at the Node boundary; no domain logic in the Kernel

## 中文讲解（speaker notes）

- **Kernel is generic: Goal, Plan, Tool, Observation, Memory, Budget, Checkpoint**
  - 字面：Kernel 只认识通用概念：目标、计划、工具、观察、记忆、预算、检查点。
  - 为什么准确：`AgentKernel` 的输入是 `KernelTask`，不 import report/paper/claim。
  - 展示：Kernel 色块，列这些词，不出现论文术语。
  - 导师可能问：Kernel 怎么知道报告要什么？
  - 回答：不知道；Workflow 通过 Node 的 goal + inputs + schema 把领域信息传进来。

- **Workflow is specialized: stage order, inputs, outputs, toolsets, verifiers, budgets**
  - 字面：Workflow 负责阶段顺序、输入输出、工具集、验收和预算。
  - 为什么准确：`report_v2.py` 的 5 个 NodeSpec 明确这些字段。
  - 展示：Workflow 色块，列 5 个 Node。
  - 导师可能问：为什么 Workflow 不能通用？
  - 回答：报告、Chat、评估的阶段和验收完全不同；通用 Workflow 会退化成写死配置。

- **Node is the contract between them, not a tool alias**
  - 字面：Node 是两层之间的契约，不是工具别名。
  - 为什么准确：一个 Node 可以调用多个工具；例如 `report.write` 调 section_status、write_next_section、assemble_v2。
  - 展示：Node 大框内部画 3 个 tool calls。
  - 导师可能问：Node 和 Tool 的边界是什么？
  - 回答：Node 是“阶段 + 验收 + 预算”；Tool 是“一次可执行动作”。

- **Tools and verifiers attach at the Node boundary; no domain logic in the Kernel**
  - 字面：Tool 和 Verifier 挂在 Node 边界，Kernel 不含领域逻辑。
  - 为什么准确：ToolRuntime 按 Node toolset 暴露工具；VerifierProfile 属于 NodeSpec。
  - 展示：Node 下方挂 ToolRuntime / Verifier 两个小方块。
  - 导师可能问：Kernel 怎么保证输出合法？
  - 回答：Kernel 执行 schema 校验；Node 的 verifier 再做领域验收。

---

# Slide 6 — Who Decides What

## English Copy

- Workflow decides: stage order, input/output contracts, toolsets, verifiers, budgets
- LLM decides: which tool, arguments, next step, and whether to repair
- Kernel enforces: loop, cancellation, checkpoint, budget, schema
- This avoids both a fixed script and an unconstrained agent

## 中文讲解（speaker notes）

- **Workflow decides: stage order, input/output contracts, toolsets, verifiers, budgets**
  - 字面：Workflow 决定阶段顺序、输入输出契约、工具集、验收、预算。
  - 为什么准确：这些是 NodeSpec 的字段，不由 LLM 改写。
  - 展示：左列 Workflow 决策项。
  - 导师可能问：LLM 能不能自己加 Node？
  - 回答：不能；Node 是 Workflow 定义的边界，LLM 只在 Node 内行动。

- **LLM decides: which tool, arguments, next step, and whether to repair**
  - 字面：LLM 决定用哪个工具、参数、下一步、是否修复。
  - 为什么准确：Kernel prompt 要求返回 tool/final action；失败后 LLM 收到 observation / verifier 问题再决策。
  - 展示：右列 LLM 决策项。
  - 导师可能问：这不就是让 LLM 控制一切？
  - 回答：不是；它只在 stage 内自由，stage 外由 Workflow 约束。

- **Kernel enforces: loop, cancellation, checkpoint, budget, schema**
  - 字面：Kernel 强制循环、取消、checkpoint、预算、schema。
  - 为什么准确：这些在 `AgentKernel` 主循环里实现，不依赖模型自觉。
  - 展示：中间 Kernel 列。
  - 导师可能问：模型不遵守 JSON 怎么办？
  - 回答：invalid action 计数、repair、最终 `E_KERNEL_INVALID_ACTION` 失败；不会默默继续。

- **This avoids both a fixed script and an unconstrained agent**
  - 字面：避免“完全写死脚本”和“完全自由 Agent”两个极端。
  - 为什么准确：写死脚本没有泛化；完全自由没有阶段验收和可恢复性。
  - 展示：Spectrum：Fixed Script ← Constrained Autonomy → Free Agent。
  - 导师可能问：为什么选中间？
  - 回答：报告需要可复现、可验收、可恢复；同时 Node 内要允许 LLM 处理不确定性。

---

# Slide 7 — Generic Kernel

## English Copy

- Kernel plans, calls tools, observes, and revises
- Checkpoint, resume, compaction, repair, budget are built in
- L3 validation: 30 simple + 14 complex + 8 concurrent tasks
- Kernel imports no report, paper, or claim code

## 中文讲解（speaker notes）

- **Kernel plans, calls tools, observes, and revises**
  - 字面：Kernel 自己计划、调工具、观察结果、修正计划。
  - 为什么准确：`AgentKernel` 每步调用 LLM，解析 action，执行工具，写回 history，再下一步。
  - 展示：循环图 Plan → Tool → Observe → Revise。
  - 导师可能问：计划存在哪里？
  - 回答：通用 plan 工具写入 `GeneralState.plans`；Kernel 每步把 plan 注入 prompt。

- **Checkpoint, resume, compaction, repair, budget are built in**
  - 字面：checkpoint、resume、上下文压缩、repair、预算都是内核能力。
  - 为什么准确：`KernelPolicy` / `FileCheckpointStore` / `context.compact` / repair loop / max_usd。
  - 展示：五个能力图标。
  - 导师可能问：checkpoint 粒度是什么？
  - 回答：step / tool 后保存；Node 级别还有 NodeStore committed output。

- **L3 validation: 30 simple + 14 complex + 8 concurrent tasks**
  - 字面：L3 验证包含 30 个简单任务、14 个复杂任务、8 个并发 soak 任务。
  - 为什么准确：这是真实 LLM benchmark 的记录，不是单元测试。
  - 展示：三组数字 + simple/complex/soak 标签。
  - 导师可能问：复杂任务成功率多少？
  - 回答：12/14；audit 13/14；soak 8/8。不要把它说成 100%。

- **Kernel imports no report, paper, or claim code**
  - 字面：Kernel 不 import report/paper/claim 代码。
  - 为什么准确：这是架构守卫，`kernel/agent/` 里没有领域模块依赖。
  - 展示：依赖图，标出 no domain imports。
  - 导师可能问：怎么保证以后不污染？
  - 回答：有 `test_kernel_has_no_report_imports` / 代码审查约束。

---

# Slide 8 — Report Workflow: Five Nodes

## English Copy

- source.collect → evidence.extract → report.plan → report.write → report.audit_finalize
- Each node has goal, inputs, toolset, output schema, verifier, budget
- Failures stay inside one stage
- The workflow is report-specific, not a generic profile

## 中文讲解（speaker notes）

- **source.collect → ... → report.audit_finalize**
  - 字面：报告任务的五阶段链。
  - 为什么准确：`build_report_v2_workflow()` 的 Node 顺序固定。
  - 展示：五节点流程条，每节点下方写产物：source.json / evidence.json / plan.json / draft.json / report.json。
  - 导师可能问：能不能跳过某一步？
  - 回答：核心链路不能；optional Node 是设计能力，但当前报告五段是必需。

- **Each node has goal, inputs, toolset, output schema, verifier, budget**
  - 字面：每个 Node 都有目标、输入、工具集、输出 schema、验收、预算。
  - 为什么准确：NodeSpec 字段直接对应。
  - 展示：NodeSpec 六宫格。
  - 导师可能问：schema 谁来校验？
  - 回答：Kernel 做 output schema；WorkflowRunner 的 Verifier 做 stage verifier。

- **Failures stay inside one stage**
  - 字面：失败被限制在一个阶段内。
  - 为什么准确：每段有独立产物；source 失败不写 report；section 失败只重试该 section。
  - 展示：红色隔离边界。
  - 导师可能问：如果 evidence 错了怎么办？
  - 回答：evidence 有 quote.check / claim 检查；错误可定位到 evidence 阶段并重跑该段。

- **The workflow is report-specific, not a generic profile**
  - 字面：这个 Workflow 是报告专用的，不是通用 Workflow + 报告 profile。
  - 为什么准确：Node 顺序、工具集、verifier 都是报告领域代码。
  - 展示：底部 “No generic report workflow”。
  - 导师可能问：为什么不做一个通用 Workflow？
  - 回答：Chat/评估/报告阶段差异太大；通用 Workflow 最后会变成一堆 if/else。

---

# Slide 9 — Node Contract in Practice

## English Copy

- A Node is a stage, not a tool call
- `report.write` loops section by section
- Each section is checked, retried, and checkpointed
- The Node returns a verifiable artifact

## 中文讲解（speaker notes）

- **A Node is a stage, not a tool call**
  - 字面：Node 是一个阶段，不是一次工具调用。
  - 为什么准确：`report.write` 会调用 section_status、write_next_section、assemble_v2 等多次工具。
  - 展示：Node 大框里放 3 个 tool calls。
  - 导师可能问：那 Node 和 workflow stage 是不是同一个？
  - 回答：是，Node 就是 Workflow 的阶段；Tool 是阶段内动作。

- **`report.write` loops section by section**
  - 字面：写作 Node 逐 section 循环。
  - 为什么准确：`section_status` 返回 next_section，`write_next_section` 每次写一个，直到 remaining=0。
  - 展示：status → write → status → ... → assemble。
  - 导师可能问：为什么不让 LLM 一次写整篇？
  - 回答：整篇难重试、难定位；逐节可检查、可恢复、可局部重写。

- **Each section is checked, retried, and checkpointed**
  - 字面：每个 section 都检查、重试、checkpoint。
  - 为什么准确：`write_one_section` 最多 3 次；section 文件 `ok/attempts`；已 ok 可跳过。
  - 展示：section 卡片：attempts / ok / fallback / path。
  - 导师可能问：重试 3 次还失败呢？
  - 回答：section 标记 failed，assemble 会拒绝；不会把空 section 当成功。

- **The Node returns a verifiable artifact**
  - 字面：Node 返回可验收的产物。
  - 为什么准确：draft.json 有 sections / word_count / citation_coverage；Node verifier 校验 schema。
  - 展示：draft.json / sections/*.json。
  - 导师可能问：自然语言结果不算吗？
  - 回答：最终 report 是 artifact；中间自然语言只作为 draft 内容，必须通过 schema / quality。

---

# Slide 10 — Tool Layer and Source Choice

## English Copy

- One ToolRuntime, scoped toolsets per Node
- Local corpus and online OpenAlex/PDF paths
- Parallel-safe tools overlap; exclusive tools form barriers
- Default demo size: 20 papers; benchmark: 100 papers

## 中文讲解（speaker notes）

- **One ToolRuntime, scoped toolsets per Node**
  - 字面：所有 Node 共用一个 ToolRuntime，但每个 Node 只能看自己的 toolset。
  - 为什么准确：`ToolRuntime.visible(task.toolset)` 决定模型可见工具；registry 是统一注册表。
  - 展示：中心 ToolRuntime，向外连 5 个 Node toolset。
  - 导师可能问：为什么不让 Agent 看全部工具？
  - 回答：减少误用和越权；Node 的 toolset 是领域约束。

- **Local corpus and online OpenAlex/PDF paths**
  - 字面：本地 corpus 和在线 OpenAlex/PDF 两条来源。
  - 为什么准确：`source.collect` 读本地；`source.collect_online` 搜索 OpenAlex 并尝试下载 PDF/HTML。
  - 展示：Local / Online 两条分支汇聚到 source artifact。
  - 导师可能问：在线下载失败怎么办？
  - 回答：记录失败；只用摘要；state=degraded；不伪造全文。

- **Parallel-safe tools overlap; exclusive tools form barriers**
  - 字面：并行安全工具可重叠执行；独占工具形成屏障。
  - 为什么准确：`ToolSpec.parallel_safe` / `side_effect`；调度器按顺序分组。
  - 展示：两条并行箭头 + 一条 barrier。
  - 导师可能问：并行会不会写乱文件？
  - 回答：有副作用的工具默认不并行；并行只用于读/无副作用工具。

- **Default demo size: 20 papers; benchmark: 100 papers**
  - 字面：默认 demo 20 篇；benchmark 100 篇。
  - 为什么准确：API/CLI/New Run 默认 limit=20；100 篇是完整 benchmark。
  - 展示：20 / 100 两个数字。
  - 导师可能问：为什么降到 20？
  - 回答：组会演示成本低、迭代快；20 篇仍能跑完整链路，质量门禁动态适配。

---

# Slide 11 — Quality and Observability

## English Copy

- Dynamic quality gate: thresholds follow the requested paper count
- Section metrics: citations, claim refs, empty sections, duplicates
- LLM audit: explicit reject blocks; unavailable is recorded
- SSE events expose tool calls, thinking summaries, and progress

## 中文讲解（speaker notes）

- **Dynamic quality gate: thresholds follow the requested paper count**
  - 字面：质量门禁不是固定 100，而是跟随请求的论文数量。
  - 为什么准确：`target_papers` 来自 source `limit`；min_papers / min_claims / min_sections 动态计算。
  - 展示：20 篇阈值 vs 100 篇阈值。
  - 导师可能问：会不会降低标准？
  - 回答：阈值随规模缩放，但 citation coverage / empty section / reference safety 仍是硬条件。

- **Section metrics: citations, claim refs, empty sections, duplicates**
  - 字面：逐 section 统计引用、claim 引用、空 section、重复句。
  - 为什么准确：`report.quality.check` 从 report + evidence 重算，不信任 writer 自报。
  - 展示：section metrics 表格。
  - 导师可能问：duplicate sentences 为什么不 hard fail？
  - 回答：它目前是质量信号，不是硬门禁；避免误杀正常综述复述。

- **LLM audit: explicit reject blocks; unavailable is recorded**
  - 字面：LLM audit 明确拒绝会阻止发布；audit 不可用会记录，但不冒充通过。
  - 为什么准确：`E_REPORT_AUDIT`；`audit.status = unavailable`。
  - 展示：三态：accepted / rejected / unavailable。
  - 导师可能问：unavailable 为什么还发布？
  - 回答：先保证流程可跑；但记录得很清楚，后续可以把 unavailable 改成 hard fail。

- **SSE events expose tool calls, thinking summaries, and progress**
  - 字面：SSE 事件暴露工具调用、思考摘要、进度。
  - 为什么准确：`/events` 流；`kernel.tool_called` / `thinking.summary` / `section.written`。
  - 展示：EventSource 事件列表。
  - 导师可能问：思考是模型原始 chain-of-thought 吗？
  - 回答：不是；是模型给出的短 `thought` 或 reasoning 摘要，用于解释性展示，不是完整内部推理。

---

# Slide 12 — Current Features

## English Copy

- Local or online source selection
- Paper titles are clickable and open a paper tab
- Markdown reports with citations, lists, tables, and code
- Pause, resume, section retry, and failure visibility

## 中文讲解（speaker notes）

- **Local or online source selection**
  - 字面：用户可以选择本地 corpus 或在线检索。
  - 为什么准确：New Run 有 Source 下拉框；API 支持 `source_mode`。
  - 展示：New Run 截图，圈出 Source。
  - 导师可能问：在线检索有质量保证吗？
  - 回答：没有承诺；在线结果取决于 OpenAlex / PDF 可用性，报告会记录 fulltext 覆盖率。

- **Paper titles are clickable and open a paper tab**
  - 字面：报告中的论文标题可以点击，打开 Paper tab。
  - 为什么准确：backend 生成 `[Title](#paper-<id>)`；ReportBody 拦截 `#paper-*` 点击。
  - 展示：点击标题 → Paper tab 截图。
  - 导师可能问：和 citation 点击有什么区别？
  - 回答：标题打开论文；`[C#]` 打开对应 claim / paper 证据。

- **Markdown reports with citations, lists, tables, and code**
  - 字面：报告是标准 Markdown，支持引用、列表、表格、代码块。
  - 为什么准确：`marked + DOMPurify` 渲染。
  - 展示：报告片段。
  - 导师可能问：为什么不用纯文本？
  - 回答：综述需要结构；Markdown 是 LLM 可生成、前端可安全渲染的折中。

- **Pause, resume, section retry, and failure visibility**
  - 字面：可暂停、恢复、单 section 重试，失败可见。
  - 为什么准确：API pause/resume；retry endpoint；UI failed section。
  - 展示：Pause/Resume + Retry failed section。
  - 导师可能问：暂停后会不会丢已完成 section？
  - 回答：section 文件 + checkpoint；resume 跳过已 committed / ok 的部分。

---

# Slide 13 — Results and Engineering Validation

## English Copy

- 100-paper benchmark: 98 fulltext, 196 claims, 23 sections
- 20-paper demo: 19 fulltext, 38 claims, 7 sections
- Citation coverage 1.0; quality gate passed; audit accepted
- 128 tests; Ruff clean; frontend build passing; L3 gate passed

## 中文讲解（speaker notes）

- **100-paper benchmark...**
  - 字面：100 篇完整 benchmark 的结果。
  - 为什么准确：report.json 记录 papers/fulltext/claims/sections；这是历史 benchmark 运行。
  - 展示：100 / 98 / 196 / 23。
  - 导师可能问：100 篇现在还是默认吗？
  - 回答：不是；默认 demo 已降到 20；100 是 benchmark 规模。

- **20-paper demo...**
  - 字面：当前默认 20 篇 demo 的结果。
  - 为什么准确：最新 20 篇 run 的 report.json。
  - 展示：20 / 19 / 38 / 7。
  - 导师可能问：20 篇够不够支撑综述？
  - 回答：够演示闭环，但不足以做领域结论；它是 demo 规模，不是研究规模。

- **Citation coverage 1.0; quality gate passed; audit accepted**
  - 字面：引用覆盖 1.0；质量门禁通过；audit 接受。
  - 为什么准确：finalize 时复算，不信任 writer。
  - 展示：coverage 1.0 + green pass。
  - 导师可能问：coverage 1.0 是否代表内容正确？
  - 回答：不代表；它只说明每个正文 section 有引用，事实正确性还需人工/更强 audit。

- **128 tests; Ruff clean; frontend build passing; L3 gate passed**
  - 字面：128 个测试、ruff、前端构建、L3 门禁都通过。
  - 为什么准确：当前仓库实际执行结果。
  - 展示：四行命令/结果。
  - 导师可能问：L3 是什么？
  - 回答：Kernel 的真实任务门禁：30 simple / 14 complex / 8 soak；不是报告测试。

---

# Slide 14 — Limitations

## English Copy

- RAG, Qdrant, and Kuzu are not implemented yet
- Chat is still local retrieval, not a full LLM chat workflow
- 2 of 100 fulltext downloads still fail
- LLM audit is fail-open when the auditor itself is unavailable

## 中文讲解（speaker notes）

- **RAG, Qdrant, and Kuzu are not implemented yet**
  - 字面：RAG、Qdrant、Kuzu 还没实现。
  - 为什么准确：当前 report 使用 SQLite + 文件 corpus + exact quote，不是向量 RAG。
  - 展示：三个灰色未完成模块。
  - 导师可能问：没有 RAG 还能叫文献 Agent 吗？
  - 回答：当前是 evidence-grounded report demo，不是完整 RAG；RAG 是 4.3 计划。

- **Chat is still local retrieval...**
  - 字面：Chat 仍是本地检索，不是完整 LLM 对话 Workflow。
  - 为什么准确：当前 chat 是基础链路，未接完整 Chat Workflow。
  - 展示：Chat 页面 + local retrieval 标签。
  - 导师可能问：为什么不先做 Chat？
  - 回答：报告是主任务；Chat 需要独立 Workflow 和检索质量，后置。

- **2 of 100 fulltext downloads still fail**
  - 字面：100 篇里仍有 2 篇全文下载失败。
  - 为什么准确：enrichment 从 35 提升到 98；剩余 2 个失败。
  - 展示：35 → 98 → 2 failures。
  - 导师可能问：为什么不能 100%？
  - 回答：PDF/HTML 源可能失效、付费墙、解析失败；报告按 degraded 记录，不伪造。

- **LLM audit is fail-open...**
  - 字面：audit 基础设施不可用时，fail-open。
  - 为什么准确：`strict_audit` 只在明确 reject 时失败；unavailable 记录后继续。
  - 展示：audit 三态图。
  - 导师可能问：这样质量门禁可靠吗？
  - 回答：deterministic gate 仍是 hard；audit 是第二层，fail-open 是当前工程折中。

---

# Slide 15 — Future Hard Problems

## English Copy

- High-quality paper retrieval: coverage, precision, PDF parsing, paywalls
- Real RAG: chunking, embeddings, hybrid search, reranking, traceable evidence
- Three-database collaboration: SQLite + Qdrant + Kuzu consistency and ingestion
- Report format: making the LLM follow a stable template and citation contract

## 中文讲解（speaker notes）

- **High-quality paper retrieval: coverage, precision, PDF parsing, paywalls**
  - 字面：高质量论文检索涉及覆盖率、精确率、PDF 解析、付费墙。
  - 为什么难：OpenAlex 不一定有全文；PDF 解析会失败；query 召回不全；长尾论文缺失。
  - 展示：检索漏斗 query → candidates → dedupe → fulltext → usable。
  - 导师可能问：现在 retrieval 的瓶颈是什么？
  - 回答：fulltext 可用性和 query/recall，不是单纯“有没有 API”。

- **Real RAG: chunking, embeddings, hybrid search, reranking, traceable evidence**
  - 字面：真正的 RAG 需要 chunk、embedding、混合检索、重排、可追溯证据。
  - 为什么难：相似度不等于证据支持；chunk 粒度、embedding 模型、rerank 都会影响引用质量。
  - 展示：chunk → embed → hybrid → rerank → citation。
  - 导师可能问：为什么不直接上向量库？
  - 回答：当前 20/100 篇用 exact quote 已能跑；先验证报告质量，再引入 RAG，避免同时改两个变量。

- **Three-database collaboration: SQLite + Qdrant + Kuzu consistency and ingestion**
  - 字面：三库协作要解决 SQLite / Qdrant / Kuzu 的一致性和 ingestion。
  - 为什么难：三份数据要同步；Qdrant/Kuzu 可重建但不能成为唯一事实源；D 盘存储。
  - 展示：三库图 + ingestion outbox。
  - 导师可能问：为什么需要三个数据库？
  - 回答：SQLite 元数据/事务，Qdrant 语义检索，Kuzu 作者/引用图；职责不同，不是为了堆技术。

- **Report format: making the LLM follow a stable template and citation contract**
  - 字面：报告格式难点是让 LLM 稳定遵守模板和引用契约。
  - 为什么难：模型会偏离模板、漏标题、堆 quote；prompt 只能降低概率，不能保证。
  - 展示：prompt → draft → schema/quality → fallback。
  - 导师可能问：现在怎么保证格式？
  - 回答：模板 + 后处理 + section checker + fallback；还不是完全模型自遵守。

---

# Slide 16 — Proposed Report Template

## English Copy

- Current: At a Glance → Papers N-M → Cross-Paper Synthesis → Paper Index
- Proposed: add Scope, Method, Evidence Notes, Open Problems, Limitations
- Every section has a job, a citation rule, and a target length
- The template should be a contract, not only a prompt

## 中文讲解（speaker notes）

- **Current: At a Glance → Papers N-M → Cross-Paper Synthesis → Paper Index**
  - 字面：当前模板是概览、分批论文分析、综合、索引。
  - 为什么准确：`REPORT_TEMPLATE` 和 `plan_report` 的 section 结构。
  - 展示：当前 4 类 section 简图。
  - 导师可能问：当前模板缺什么？
  - 回答：缺方法、范围、证据说明、开放问题、局限性；更像“论文摘要集合”。

- **Proposed: add Scope, Method, Evidence Notes, Open Problems, Limitations**
  - 字面：建议增加范围、方法、证据说明、开放问题、局限性。
  - 为什么：让报告从“论文列表”升级为“有判断的综述”。
  - 展示：提议模板全文。
  - 导师可能问：这些 section 是否必要？
  - 回答：这是本次想请导师判断的核心问题。

- **Every section has a job, a citation rule, and a target length**
  - 字面：每个 section 都有职责、引用规则、目标长度。
  - 为什么：格式统一不能靠模型自觉，要变成可检查契约。
  - 展示：section card：Goal / Citation / Length / Verifier。
  - 导师可能问：长度怎么定？
  - 回答：按 section kind 给 target_words；当前用总 word gate，后续可做 per-section。

- **The template should be a contract, not only a prompt**
  - 字面：模板应该是契约，不只是 prompt。
  - 为什么：prompt 是软约束；contract 才能被 verifier 检查、fallback 修复。
  - 展示：prompt → schema → verifier → fallback。
  - 导师可能问：具体怎么落地？
  - 回答：section schema + section checker + quality gate + deterministic fallback。

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
  - 字面：哪些 section 是报告真正需要的？
  - 为什么问：当前模板是工程视角，不确定导师/读者真正关心的内容。
  - 展示：当前模板 + 提议模板并排。
  - 导师可能问：你自己觉得呢？
  - 回答：我倾向 Scope / Method / Synthesis / Open Problems 是核心；但想先听导师判断。

- **What balance...**
  - 字面：paper-by-paper 和 cross-paper synthesis 的比例多少？
  - 为什么问：报告可能太像论文列表，也可能综合过度、失去证据。
  - 展示：Paper list ↔ Synthesis 光谱。
  - 导师可能问：现在比例多少？
  - 回答：当前 20 篇有 4 个 paper sections + overview + synthesis + index；综合篇幅仍偏少。

- **What is the minimum evidence...**
  - 字面：最低证据和引用标准是什么？
  - 为什么问：citation coverage、exact quote、abstract-only 的允许程度会直接影响质量门禁。
  - 展示：coverage / quote / abstract-only 三指标。
  - 导师可能问：abstract-only 能接受吗？
  - 回答：当前允许但会标记 degraded；是否允许作为最终依据，需要导师定标准。

- **Should we prioritize RAG / three databases...**
  - 字面：下一步优先 RAG/三库，还是报告深度？
  - 为什么问：资源有限；两条路线成本和收益不同。
  - 展示：两条路线对比。
  - 导师可能问：你建议哪个？
  - 回答：建议先报告深度 + 检索质量，再上三库；三库是规模化基础设施，不是当前 demo 瓶颈。

---

# Slide 18 — Closing

## English Copy

- General kernel, specialized workflows
- A working evidence-grounded report demo
- Honest limits, clear next steps
- Feedback welcome: node granularity, quality thresholds, report scope

## 中文讲解（speaker notes）

- **General kernel, specialized workflows**
  - 字面：内核通用，Workflow 特制。
  - 为什么：这是全篇最重要的架构结论。
  - 展示：双层架构缩略图。
  - 导师可能问：一句话总结创新点？
  - 回答：把通用 Agent 能力和报告领域约束分开，Node 内部自主，Node 边界可验收。

- **A working evidence-grounded report demo**
  - 字面：有一个可运行的证据驱动报告 demo。
  - 为什么：本次交付物是 demo，不是概念图。
  - 展示：报告截图 + 5 Node trace。
  - 导师可能问：现在能稳定跑吗？
  - 回答：20 篇默认链路可跑；100 篇 benchmark 已跑过；仍有 2/100 fulltext 失败等边界。

- **Honest limits, clear next steps**
  - 字面：诚实说明限制，给出清晰下一步。
  - 为什么：避免过度承诺，让讨论聚焦真正问题。
  - 展示：Limitations / Next 两列。
  - 导师可能问：最大的风险是什么？
  - 回答：检索质量和报告质量评估；RAG/三库是工程复杂度风险。

- **Feedback welcome: node granularity, quality thresholds, report scope**
  - 字面：希望反馈节点粒度、质量阈值、报告范围。
  - 为什么：这三个决定架构和 demo 的下一步方向。
  - 展示：三个问题结尾。
  - 导师可能问：为什么是这三个？
  - 回答：节点粒度决定可恢复性；阈值决定质量；范围决定 demo 是否有说服力。
