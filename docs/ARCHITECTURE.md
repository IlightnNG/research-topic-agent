# Architecture · lit-agent v2

> 版本：2.0（2026-11-01）
> 状态：目标架构；当前代码仍在迁移中
> 范围：`src/lit_agent_v2/`
> 旧 M1–M6 文档是历史阶段记录，不再作为目标模块划分。

---

## 0. 一句话架构

```text
Workflow = 一条 Node 链
Node     = 目标 + 工具白名单 + 输入 artifact + 输出 schema + Verifier
Kernel   = Node 内部的 LLM ReAct 执行器
Tools    = 所有外部交互的唯一入口
Verifier = 代码校验 + LLM 审计，共同决定是否 commit
```

---

## 1. 先统一概念

### 1.1 Workflow 和 Node 不是两层

```text
Workflow 不是 Node 外面的另一个对象
Workflow 就是按顺序组织起来的 Node 链
```

```python
WorkflowDefinition(
    name="report",
    nodes=[
        NodeSpec(...),
        NodeSpec(...),
        NodeSpec(...),
    ],
)
```

所以：

```text
Workflow 负责：节点顺序、依赖、可选性、运行状态、commit/resume
Node  负责：目标、工具、输入、输出、验收、预算
```

不再有“Workflow 契约”和“Node 契约”两套东西。

### 1.2 每个 Node 都调用 Kernel

```text
WorkflowRunner
  → NodeSpec
  → Kernel.run(goal, tools, inputs, verifier)
      → LLM 思考
      → ToolCall
      → Observation
      → 继续 / Final
  → Verifier
  → commit artifact
  → next Node
```

没有 `deterministic node` 作为独立类型。

纯确定性操作，例如：

```text
PDF 解析
quote 校验
计数
写 DB
```

不是“另一种 Node”，而是 **Tool**。

Node 本身始终是：

```text
LLM 决定策略 + 调用工具
```

---

## 2. 设计原则

1. **Node 链可配置**
   - 节点可启用/停用；
   - 可选节点失败可以降级；
   - 章节不是节点，章节是 Node 内的 Plan artifact。

2. **Node 内部由 LLM 主导**
   - 先做什么、调用哪个工具、是否继续、何时 final，由 Kernel/LLM 决定；
   - 代码只提供工具、预算、schema 和不变量。

3. **所有外部交互工具化**
   - HTTP、PDF、文件、DB、LLM、报告落库、评分都通过 Tool；
   - 业务代码不直接 import 领域 service 做副作用。

4. **双 Verifier**
   - 每个 Node 输出都经过代码校验 + LLM 审计；
   - 代码 hard fail 不能被 LLM 覆盖；
   - LLM audit fail 可以触发修复/重写。

5. **Artifact 契约**
   - Node 间只传 artifact；
   - artifact 内容寻址；
   - 不在 Node 间传隐式全局状态。

6. **可恢复**
   - Node commit 后写状态；
   - Kernel step checkpoint；
   - resume 跳过已提交节点；
   - pause 在 Node/step 边界生效。

7. **Feature-first**
   - classification、comparison、scorecard 都是 feature；
   - demo 可以关闭；
   - 不因为高阶功能阻塞基础报告。

---

## 3. 平台分层

```text
Interface
  API / CLI / UI
      │
Workflow
  Node chain / runner / state / commit / resume
      │
Kernel
  ReAct / context / plan / tool calls / budget / checkpoint
      │
Tools
  source / evidence / report / storage / eval / audit
      │
Storage
  artifacts / SQLite / event / metric / report
```

横向：

```text
Verification
  code verifier + LLM audit verifier
  作用于每个 Node 输出
```

模块：

```text
workflow/
kernel/
tools/
verify/
storage/
interface/
domains/        # 领域工具包，不是流程层
composition/    # 唯一装配点
```

---

## 4. Node 契约

```python
@dataclass(frozen=True)
class NodeSpec:
    id: str
    goal: str
    tools: tuple[str, ...]
    inputs: tuple[str, ...]
    output_schema: str
    verifier: VerifierProfile
    max_steps: int
    max_usd: float
    timeout_s: float
    optional: bool = False
    enabled: bool = True
```

### 4.1 goal

`goal` 是提示词的一部分，不是代码流程：

```text
"收集至少 100 篇相关论文。
至少 30 篇 fulltext；如果不足，明确标记 degraded。
先去重，再检查元数据完整性。"
```

### 4.2 tools

Node 只能看到 allowlist：

```text
source.collect:
  source.search
  source.fetch_pdf
  source.fetch_html
  source.store
  corpus.stats
  corpus.dedupe
```

LLM 不能调用未注册工具。

### 4.3 inputs / output_schema

```text
inputs:
  SourceArtifact / EvidenceArtifact / ReportRequirements / ...

output_schema:
  JSON Schema，commit 前必须通过验证
```

### 4.4 verifier

```python
VerifierProfile(
    code=["schema", "quote", "citation", "count", "word_limit", "file_exists"],
    audit="report_quality",
)
```

### 4.5 optional / enabled

```text
enabled=False  → node.skipped
optional=True  → 失败时允许降级继续
```

Node 链可以由 features 生成：

```python
build_workflow(features)
  → source
  → evidence
  → map?            # classification
  → report
  → scorecard?      # evaluation
  → finalize
```

---

## 5. Kernel

Kernel 只做单 Node 内部的事：

```text
接收 NodeContext
  goal
  tools
  inputs
  output schema
  budget
  checkpoint

循环：
  context
  → LLM action
  → tool call
  → observation
  → checkpoint
  → stop / continue
  → final
```

Kernel 不允许：

```text
改 Node 链
访问未授权工具
直接写 DB
直接 import 领域模块
```

Kernel 负责：

```text
tool 参数校验
no-progress
budget
timeout
cancel
step checkpoint
usage / cost
```

---

## 6. Tools

Tool 是唯一副作用边界。

```python
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    side_effect: bool
    idempotent: bool
    timeout_s: float
    cost_usd: float
    handler: Callable
```

工具命名空间：

```text
source.*       搜索、PDF、HTML、存储
corpus.*       统计、去重、范围检查
claims.*       抽取、过滤、quote 校验
report.*       plan、write_section、check、assemble、persist
eval.*         dataset、scorecard、judge
audit.*        质量审计
fs.*           文件
http.*         HTTP
llm.*          LLM 调用
```

规则：

- 领域工具包只暴露 Tool，不暴露 service；
- Node 的工具列表由 Workflow 决定；
- 工具调用记录 input hash、output hash、耗时、错误；
- 有副作用的工具必须幂等或可回滚；
- 下载/HTTP 工具有 allowlist、大小限制、超时。

---

## 7. Verification

每个 Node commit 前：

```text
candidate output
  → CodeVerifier
  → AuditVerifier
  → Verdict
```

### 7.1 CodeVerifier

```text
schema
paper_id / claim_id 存在
quote 原文命中
citation 覆盖
count reconciliation
字数硬上限
文件真实存在
budget / steps
```

这些检查也封装成工具，Kernel 可以主动调用自检。

但最终 Verifier 会**独立重跑**，不信任 Kernel 自检结果。

### 7.2 AuditVerifier

```text
相关性
覆盖度
可读性
综合质量
事实是否有引用支持
```

- 独立 LLM；
- 不接收 producer 的推理链；
- 结构化 JSON；
- 只做质量判断，不替代 quote/count 硬校验。

### 7.3 Verdict

```python
Verdict(
    accept: bool,
    code: CodeResult,
    audit: AuditResult,
    reasons: list[str],
)
```

规则：

```text
code pass + audit pass     → commit
code pass + audit fail     → repair / rewrite
code fail                  → reject，LLM 不能覆盖
```

---

## 8. Workflow 运行

```text
RunShell.prepare
  → WorkflowDefinition
  → for node in nodes:
      if disabled: node.skipped
      context = inputs + feature flags
      result = Kernel.run(node, context)
      verdict = Verifier.verify(node, result)
      if accept: commit artifact
      elif optional: degraded + continue
      else: retry / fail
  → finalize
```

状态：

```text
pending
running
paused
succeeded
failed
degraded
aborted
```

Node 状态：

```text
pending
running
verifying
committed
failed
skipped
```

---

## 9. 领域工具包

领域模块不再直接组成 Workflow。

### 9.1 Research

```text
source.collect
  tools: search, fetch_pdf, fetch_html, store, stats, dedupe
  goal: 100 unique papers, >=30 fulltext or degraded

evidence.extract
  tools: claims.extract, quote.check, claims.filter, evidence.stats

map.classify (optional)
  tools: cluster, name_directions, validate_directions
```

### 9.2 Report

```text
report.generate
  tools:
    report.plan
    report.write_section
    report.check_section
    report.assemble
```

### 9.3 Evaluation

```text
scorecard.build
judge.score
dataset.validate
```

Evaluation 是可选 Node，不阻塞报告生成。

---

## 10. Report Node：现在一个，后期拆

### 现在

```text
Node: report.generate
Input:
  EvidenceArtifact
  ReportRequirements
  ReportFeatures
Tools:
  report.plan
  report.write_section
  report.check_section
  report.assemble
Output:
  ReportDraft
```

Kernel：

```text
1. 调 report.plan
2. 得到 ReportPlan
3. 对每个 section 调 report.write_section
4. 每节调 report.check_section
5. 调 report.assemble
```

`ReportPlan` 是工具产物：

```json
{
  "sections": [
    {"kind": "overview"},
    {"kind": "paper_analysis", "paper_ids": ["P1..P5"]},
    {"kind": "synthesis"},
    {"kind": "paper_index"}
  ]
}
```

章节不写死在 Python。

### 后期

```text
report.plan        Node
report.write       Node
report.verify      Node
report.persist     Node
```

或：

```text
foreach section
  → section.writer Node
```

工具契约不变。

---

## 11. Demo 配置

```python
ReportFeatures(
    classification=False,
    direction_sections=False,
    per_paper_sections=True,
    synthesis=True,
    scorecard=False,
    require_fulltext=False,
)
```

Demo Workflow：

```text
source.collect
  → evidence.extract
  → report.generate
  → finalize
```

目标：

```text
100 篇论文
>=30 篇 fulltext 或 abstract-only
每篇有 claim
overview + paper analysis blocks + synthesis + index
每个事实句有引用
API/UI 可读
```

不要求：

```text
5–8 directions
direction F1
scorecard
gold
```

---

## 12. 存储与事件

```text
runs
run_nodes
run_artifacts
run_events
metric_points
reports / report_sections / claims / citations
```

Artifact：

```text
sha256(payload)
metadata: schema, node_id, run_id, created_at
```

事件：

```text
node.started
tool.called
tool.result
node.verifying
node.committed
node.failed
node.skipped
run.finished
```

---

## 13. 模块依赖规则

```text
interface   → workflow
workflow    → kernel, verify, storage contracts
kernel      → tools contracts
tools       → storage / external adapters
verify      → code checks + audit tool
domains     → tools contracts only
composition → all concrete
```

禁止：

```text
workflow 直接 import domain service
kernel 直接 import domain service
domain 直接调用另一个 domain 的 service
工具外部调用绕过 ToolRegistry
```

---

## 14. 当前实现状态

当前代码仍接近旧架构：

```text
M1 Engine:
  workflow + kernel + storage 混在一起
M4 Report:
  write 节点是 deterministic
  report/write.py 固定章节
  LLM writer 只在测试路径
M5 Evaluation:
  scorecard/judge 可独立运行，未接入 workflow
M6 Interface:
  API/UI 已可用，使用 deterministic writer
```

已经具备：

```text
Kernel ReAct
ToolBox
Step checkpoint
LLM writer
API/UI
```

尚未完成：

```text
Workflow 可选节点
Node goal/tools/verifier 契约
ToolRegistry 全量工具化
Report Node 的 plan 工具
双 Verifier
模块重排
```

---

## 15. 迁移顺序

```text
1. 抽 Workflow / Kernel / Tools / Verify 模块
2. NodeSpec 增加 goal/tools/verifier/optional
3. ToolRegistry 包装现有 service
4. report.generate 改为 agent node
5. report.plan 产出 sections
6. 双 Verifier 接入
7. demo profile 跑 100 篇
8. 再拆 report.plan / report.write / section nodes
9. 启用 classification / scorecard
```

---

## 16. 非目标

- 不把每个 section 都做成 Workflow Node；
- 不让 LLM 直接访问 DB/文件/HTTP；
- 不让 LLM retry 覆盖代码 hard fail；
- 不用 AI-only gold 声称 human gold；
- 不为 demo 引入生产级前端。

---

## 17. 相关文档

- `docs/CONTRACTS.md`：Node / Tool / Verifier 契约
- `docs/modules/README.md`：新平台模块与旧 M1–M6 映射
- `docs/STATUS.md`：当前实现与迁移状态
- `docs/DECISIONS.md`：架构决定
- `docs/modules/research/REPORT-POLICY.md`：报告 sizing / demo 质量策略
- `docs/implementation/PHASE4.1-node-platform-migration.md`：迁移方案
- `docs/archive/implementation/PHASE4-report-end-to-end.md`：历史 Phase 4 计划
