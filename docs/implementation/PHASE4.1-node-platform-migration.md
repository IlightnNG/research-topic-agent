# Phase 4.1 · Node Platform Migration

> 版本：2.0（2026-11-01）
> 类型：详细迁移方案
> 范围：平台层 + Research 工具包 + Report Node
> 目标：删除旧 M1–M6 流程骨架，按 Node/Tool/Verifier 重写
> 状态：execution；4.1.0 / 4.1.1 / 4.1.2 done；下一 4.1.3
> 依据：`docs/ARCHITECTURE.md` 2.0、`docs/CONTRACTS.md` 2.0 DRAFT

---

## 1. 完成定义

Phase 4.1 完成时：

```text
1. Workflow 就是 Node 链；
2. 每个 Node 通过 Kernel 执行；
3. 所有外部 I/O 只通过 Tool；
4. 每个 Node 有 code + audit 双 Verifier；
5. 100 篇论文可完成 report；
6. classification 默认关闭；
7. report sections 由 report.plan 决定；
8. API/UI 读取新 workflow；
9. 旧 ReportWorkflow / write.py 已删除；
10. 不存在两套 report 生成路径。
```

Demo 硬目标：

```text
papers >= 100
claims per paper >= 1
fulltext >= 30 或显式 abstract-only/degraded
sections:
  overview
  paper_analysis blocks
  synthesis
  paper_index
citation coverage = 1
code verifier pass
audit verifier pass 或显式 degraded
```

---

## 2. 不可违反的约束

```text
不保留兼容层
不在旧 ReportWorkflow 上加 feature flag
不在旧 write.py 上加 if
不构造两套 Workflow
不构造两套 ReportPlan
不把每个 section 拆成 Workflow Node
不让 LLM 直接访问 DB/FS/HTTP
不让 audit 覆盖 code hard fail
```

允许：

```text
迁移期间旧代码暂时留在仓库
但新 composition/API 不 import 旧代码
旧代码只作为回滚参考，最后删除
```

---

## 3. 当前代码基线

```text
src/lit_agent_v2/
  contracts/__init__.py
  contracts/ports.py
  contracts/report.py
  contracts/errors.py
  contracts/events.py
  contracts/version.py

  run_shell.py
  workflow/definition.py
  workflow/runner.py
  workflow/events.py
  workflow/verifier.py

  kernel/loop.py
  kernel/tools.py
  kernel/checkpoint.py
  kernel/llm.py

  storage/db.py
  storage/artifacts.py

  domains/report/*.py
  domains/chat/*.py

  metrics/*.py
  evaluation/*.py

  api/app.py
  cli.py
  composition.py
```

当前问题：

```text
ReportWorkflow._definition() 固定 5 节点
write 节点 deterministic
WriteService.build() 固定章节
ReportWorkflow 依赖 concrete 服务
Kernel 只被 Chat 使用
没有 ToolRegistry
Verifier 只有 CodeVerifier
API 默认 deterministic writer
```

---

## 4. 目标代码结构

```text
src/lit_agent_v2/
  contracts/
    node.py
    tool.py
    verdict.py
    features.py
    artifacts.py
    errors.py
    events.py

  workflow/
    definition.py
    runner.py
    state.py
    definitions/
      report.py

  kernel/
    loop.py
    context.py
    checkpoint.py
    budget.py

  tools/
    spec.py
    registry.py
    packs/
      source.py
      corpus.py
      evidence.py
      claims.py
      report_plan.py
      report.py
      storage.py
      eval.py
      audit.py
    adapters/
      openalex.py
      pdf.py
      http.py
      llm.py

  verify/
    code.py
    audit.py
    verdict.py

  storage/
    db.py
    artifacts.py
    repositories.py
    report_repository.py

  interface/
    api.py
    cli.py
    templates/

  domains/
    research/
      artifacts.py
      prompts/
    evaluation/
      dataset.py
      scorecard.py
      judge.py
      calibration.py

  composition.py
```

最终删除：

```text
contracts/ports.py
contracts/report.py
run_shell.py
workflow/runner.py（旧）
workflow/verifier.py
kernel/tools.py
domains/report/
```

---

## 5. 迁移顺序

```text
4.1.0 baseline
4.1.1 contracts
4.1.2 workflow
4.1.3 kernel
4.1.4 tools
4.1.5 verify
4.1.6 report node
4.1.7 composition / interface
4.1.8 demo 100
4.1.9 delete old code
```

依赖：

```text
contracts
  → workflow
  → kernel
  → tools
  → verify
  → report node
  → composition/interface
  → demo
  → cleanup
```

每一步必须：

```text
可独立测试
有明确删除/新增文件
有验收
有一句话 commit
```

---

## 6. Step 4.1.0 · Baseline

### 目标

记录迁移前基线，避免“改完不知道坏了什么”。

### 动作

```text
1. 运行 pytest tests/v2
2. 运行 ruff check .
3. 记录当前 100 篇 deterministic report 指标
4. 记录旧 import 清单
5. 记录旧文件 SHA/commit
```

基线应记录：

```text
tests: 77 passed
100 papers:
  dirs 5
  min 7
  max_share 0.27
  claims 174
  fulltext 0/100
  state degraded
```

### 验收

```text
baseline.md 或 RESULTS 文档存在
```

### Commit

```text
docs(W-P00): record pre-migration baseline
```

---

## 7. Step 4.1.1 · Contracts

### 目标

先建立新契约，不让旧 `NodeSpec` 继续扩展。

### 新增

```text
contracts/node.py
  NodeSpec
  NodeContext
  NodeResult
  WorkflowDefinition
  NodeState

contracts/tool.py
  ToolSpec
  ToolCall
  ToolResult

contracts/verdict.py
  VerifierProfile
  CodeCheck
  AuditResult
  Verdict

contracts/features.py
  FeatureProfile
  ReportRequirements

contracts/artifacts.py
  ArtifactEnvelope
  ReportPlan
  SectionArtifact
```

### 删除/替换

```text
contracts/ports.py
contracts/report.py
```

迁移期间可以保留文件，但：

```text
新代码不得 import
旧代码可以暂时 import
```

### 关键定义

```python
NodeSpec(
    id,
    goal,
    tools,
    inputs,
    output_schema,
    verifier,
    max_steps,
    max_usd,
    timeout_s,
    optional,
    enabled,
)
```

```python
ToolSpec(
    name,
    description,
    input_schema,
    output_schema,
    side_effect,
    idempotent,
    timeout_s,
    cost_usd,
    handler,
)
```

```python
Verdict(
    accept,
    code: list[CodeCheck],
    audit: AuditResult,
    reasons,
)
```

### 测试

```text
tests/v2/test_contracts_node.py
  - NodeSpec required fields
  - enabled/optional
  - ToolSpec schema
  - Verdict accept rules

tests/v2/test_contracts_artifacts.py
  - ReportPlan sections
  - SectionArtifact schema
  - ArtifactEnvelope sha
```

### 验收

```text
- 新契约可单独 import；
- 不依赖 workflow/kernel/tools；
- 不 import domain；
- contract tests pass。
```

### Commit

```text
feat(W-P01): add node tool verdict contracts
```

---

## 8. Step 4.1.2 · Workflow

### 目标

用 Node 链替换旧 `ReportWorkflow`。

### 新增

```text
workflow/definition.py
workflow/runner.py
workflow/state.py
workflow/definitions/report.py
```

### 4.1.2.1 definition.py

```python
@dataclass(frozen=True)
class WorkflowDefinition:
    name: str
    version: str
    nodes: tuple[NodeSpec, ...]
    features: FeatureProfile
```

工具：

```python
build_report_workflow(features) -> WorkflowDefinition
```

### 4.1.2.2 runner.py

```python
class WorkflowRunner:
    def __init__(self, kernel, verifier, store, events): ...
    def run(self, definition, run_id, inputs): ...
```

逻辑：

```text
for node in definition.nodes:
  if not node.enabled:
      emit node.skipped
      continue
  result = kernel.run(node, context)
  verdict = verifier.verify(node, context, result)
  if verdict.accept:
      store.commit(node, result)
      emit node.committed
  elif node.optional:
      emit node.degraded
      continue
  else:
      raise NodeFailed
```

要求：

- 不 import domain；
- 不直接调用工具；
- 不决定章节；
- 支持 resume；
- 支持 pause；
- 支持 node skipped；
- 支持 step checkpoint。

### 4.1.2.3 state.py

```text
NodeState:
  pending
  running
  verifying
  committed
  failed
  skipped

RunState:
  pending
  running
  paused
  succeeded
  degraded
  failed
  aborted
```

### 4.1.2.4 definitions/report.py

```python
def build_report_workflow(features):
    nodes = [
        source_collect_node(features),
        evidence_extract_node(features),
    ]
    if features.classification:
        nodes.append(map_classify_node(features))
    nodes.append(report_generate_node(features))
    if features.scorecard:
        nodes.append(scorecard_node(features))
    nodes.append(finalize_node(features))
    return WorkflowDefinition("report", "2", tuple(nodes), features)
```

### 测试

```text
tests/v2/test_workflow_optional.py
  - node skipped
  - optional fail
  - required fail
  - resume committed
  - pause boundary
```

### 验收

```text
- Node 链可构建；
- map/scorecard 可关闭；
- 旧 ReportWorkflow 不被新代码 import；
- runner 不依赖域服务。
```

### Commit

```text
feat(W-P02): add configurable node chain runner
```

---

## 9. Step 4.1.3 · Kernel

### 目标

Kernel 接收 NodeContext/ToolRegistry，不 import domain。

### 重写

```text
kernel/loop.py
kernel/context.py
kernel/checkpoint.py
kernel/budget.py
```

### 关键接口

```python
Kernel.run(
    node: NodeSpec,
    context: NodeContext,
    tools: ToolRegistry,
    llm: LLMClient,
    checkpoint: KernelCheckpoint | None,
) -> NodeResult
```

Context：

```json
{
  "run_id": "...",
  "node_id": "report.generate",
  "goal": "...",
  "features": {},
  "inputs": {},
  "output_schema": {}
}
```

### 规则

```text
- 只能调用 node.tools
- tool args schema 校验
- tool result 记录 trace
- no-progress 停止
- max_steps / max_usd / timeout
- step checkpoint
- final 输出必须 output_schema
```

### 删除

```text
kernel/tools.py
```

由 `tools/registry.py` 替代。

### 测试

```text
test_kernel_context.py
test_kernel_tool_allowlist.py
test_kernel_budget.py
test_kernel_no_progress.py
test_kernel_resume.py
```

### 验收

```text
- tool 未授权拒绝；
- checkpoint 可恢复；
- budget 停止；
- 无 domain import。
```

### Commit

```text
feat(K-P01): execute nodes through kernel context
```

---

## 10. Step 4.1.4 · Tools

### 目标

所有外部交互统一 ToolSpec。

### 新增

```text
tools/spec.py
tools/registry.py
tools/adapters/openalex.py
tools/adapters/pdf.py
tools/adapters/http.py
tools/adapters/llm.py
tools/packs/source.py
tools/packs/corpus.py
tools/packs/evidence.py
tools/packs/claims.py
tools/packs/report_plan.py
tools/packs/report.py
tools/packs/storage.py
tools/packs/audit.py
tools/packs/eval.py
```

### Tool 命名

```text
source.search
source.fetch_pdf
source.fetch_html
corpus.store
corpus.stats
corpus.dedupe
claims.extract
quote.check
claims.filter
report.plan
report.write_section
report.check_section
report.assemble
report.persist
eval.scorecard
eval.judge
audit.report
```

### 规则

- Tool 参数先 schema；
- 有副作用工具必须 idempotent 或可回滚；
- 超大结果存 artifact，不塞 tool output；
- adapter 不 import workflow/kernel；
- tool pack 不 import 其他 tool pack。

### 测试

```text
test_tools_schema.py
test_tools_registry.py
test_tools_source.py
test_tools_report.py
```

### 验收

```text
- 所有外部 I/O 可列名；
- 未注册工具拒绝；
- timeout；
- tool result 可审计。
```

### Commit

```text
feat(T-P01): add tool registry and source packs
```

---

## 11. Step 4.1.5 · Verify

### 目标

Node 输出统一双验证。

### 新增

```text
verify/code.py
verify/audit.py
verify/verdict.py
```

### Code checks

```text
schema
paper_id
claim_id
quote exact
citation coverage
count reconciliation
word limit
file exists
budget
```

### Audit

```text
relevance
coverage
readability
synthesis
grounding
```

### 规则

```text
code fail → reject
code pass + audit fail → repair
both pass → accept
```

删除：

```text
workflow/verifier.py
domains/report/audit.py
```

### 测试

```text
test_verify_code.py
test_verify_audit.py
test_verify_combined.py
```

### 验收

```text
- code hard fail 不被 audit 覆盖；
- audit 不接收 producer history；
- verdict 落库。
```

### Commit

```text
feat(V-P01): add code and audit verifier
```

---

## 12. Step 4.1.6 · Report Node

### 目标

删除旧 report workflow/writer，改为一个 agent Node。

### 新增

```text
workflow/definitions/report.py
tools/packs/report_plan.py
tools/packs/report.py
```

### Report Node

```python
NodeSpec(
    id="report.generate",
    goal=REPORT_GOAL,
    tools=(
        "report.plan",
        "report.write_section",
        "report.check_section",
        "report.assemble",
    ),
    inputs=("evidence", "requirements", "features"),
    output_schema="ReportDraft",
    verifier=VerifierProfile(
        code=("schema", "quote", "citation", "count", "word_limit"),
        audit="report_quality",
    ),
)
```

### report.plan

输入：

```json
{
  "papers": 100,
  "claims": 174,
  "features": {
    "classification": false,
    "per_paper_sections": true,
    "synthesis": true
  }
}
```

输出：

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

规则：

- 必需 section 由 requirements；
- 可选 section 可缺；
- 未知 kind 拒绝；
- 每节预算来自 policy。

### 删除

```text
domains/report/workflow.py
domains/report/write.py
domains/report/plan.py
domains/report/llm_writer.py
```

### 测试

```text
test_report_plan_tool.py
  - minimal sections
  - optional section missing
  - unknown kind reject
test_report_generate_node.py
  - per-paper sections
  - citations
  - no classification
test_demo_workflow.py
```

### 验收

```text
- 不写死章节；
- classification=false 可跑；
- 少 section 合法；
- 报告有 citations；
- old ReportWorkflow 不再被 import。
```

### Commit

```text
feat(R-P01): generate reports through a single agent node
```

---

## 13. Step 4.1.7 · Composition / Interface

### 目标

新 composition 只装配新平台；API 不再知道旧 report。

### 新增

```text
composition.py
interface/api.py
interface/cli.py
interface/templates/
```

### composition

```python
build_application(profile="demo"):
  tools = build_tool_registry(...)
  kernel = Kernel(...)
  verifier = Verifier(...)
  workflow = build_report_workflow(features)
  return Application(workflow, ...)
```

规则：

- 唯一 import concrete 的地方；
- 不写业务逻辑；
- demo/full profile 切换。

### API

```text
POST /api/v2/runs
GET  /api/v2/runs/{id}
GET  /api/v2/runs/{id}/events
GET  /api/v2/runs/{id}/report
GET  /api/v2/reports/{id}
GET  /
```

要求：

- 不 import `ReportWorkflow`；
- 不 import `WriteService`；
- 不 import `OpenAlex`；
- 错误 envelope；
- SSE replay。

### 删除

```text
api/app.py（旧）
cli.py（旧）
```

### 测试

```text
test_api_demo.py
test_api_errors.py
test_ui_sections.py
```

### Commit

```text
feat(I-P01): wire demo profile through new workflow
```

---

## 14. Step 4.1.8 · Demo 100

### 目标

完整跑通 100 篇。

### 流程

```text
source.collect
  → 100 unique papers
  → >=30 fulltext or explicit abstract-only
  → store corpus

evidence.extract
  → 1-2 claims/paper
  → quote exact

report.generate
  → plan sections
  → write sections
  → assemble

finalize
  → persist
```

### 验收

```text
papers >= 100
unique >= 100
claims >= 100
sections >= 5
citation coverage = 1
uncited facts = 0
duplicate claim rate <= 0.1
code verifier pass
audit pass 或 degraded
```

### 输出

```text
D:\lit-agent-store\v2-demo\
  corpus\
  runs.sqlite
  report.md
  artifacts\
```

### Commit

```text
feat(R-P02): add 100-paper demo profile
```

---

## 15. Step 4.1.9 · Delete old code

### 删除

```text
contracts/ports.py
contracts/report.py
run_shell.py
workflow/runner.py（旧）
workflow/verifier.py
kernel/tools.py
domains/report/
domains/chat/（仅当 Chat 迁移完成）
```

### 检查

```powershell
rg "ReportWorkflow|WriteService|domains.report|contracts.ports" src tests
```

期望：

```text
0 结果
```

### 测试

```text
tests/v2
test_no_legacy_imports
test_demo_workflow
test_api_demo
```

### 验收

```text
- 旧文件删除；
- 无旧 import；
- 77+ tests 新基线；
- 100 demo 可跑；
- contract freeze 新版本。
```

### Commit

```text
refactor(W-P03): delete legacy report workflow
```

---

## 16. 文件处置矩阵

| 旧文件 | 动作 | 新位置 |
|---|---|---|
| `contracts/ports.py` | 删除 | `contracts/node.py` + `tool.py` |
| `contracts/report.py` | 拆分 | `contracts/artifacts.py` + `domains/research/artifacts.py` |
| `run_shell.py` | 删除 | `workflow/runner.py` |
| `workflow/definition.py` | 重写 | `workflow/definition.py` |
| `workflow/runner.py` | 重写 | `workflow/runner.py` |
| `workflow/verifier.py` | 删除 | `verify/` |
| `kernel/loop.py` | 重写 | `kernel/loop.py` |
| `kernel/tools.py` | 删除 | `tools/registry.py` |
| `kernel/checkpoint.py` | 重写 | `kernel/checkpoint.py` |
| `domains/report/workflow.py` | 删除 | `workflow/definitions/report.py` |
| `domains/report/write.py` | 删除 | `tools/packs/report.py` |
| `domains/report/plan.py` | 重写 | `tools/packs/report_plan.py` |
| `domains/report/llm_writer.py` | 重写 | `tools/packs/report.py` |
| `domains/report/map.py` | 重写 | `tools/packs/map.py` |
| `domains/report/persist.py` | 重写 | `storage/report_repository.py` |
| `domains/report/source.py` | 重写 | `tools/packs/source.py` |
| `domains/report/openalex.py` | 迁移 | `tools/adapters/openalex.py` |
| `domains/report/pdf.py` | 迁移 | `tools/adapters/pdf.py` |
| `domains/report/ingest.py` | 重写 | `tools/packs/corpus.py` |
| `domains/report/evidence.py` | 重写 | `tools/packs/evidence.py` |
| `domains/report/claim_extractor.py` | 重写 | `tools/packs/claims.py` |
| `domains/report/audit.py` | 迁移 | `verify/code.py` + `audit.py` |
| `metrics/*` | 迁移 | `domains/evaluation/metrics/` |
| `evaluation/*` | 迁移 | `domains/evaluation/` |
| `composition.py` | 重写 | `composition.py` |
| `api/app.py` | 重写 | `interface/api.py` |
| `cli.py` | 重写 | `interface/cli.py` |

---

## 17. 测试矩阵

| Step | 测试 | 门禁 |
|---|---|---|
| 4.1.1 | contract tests | schema |
| 4.1.2 | workflow optional/skip/resume | node chain |
| 4.1.3 | kernel tools/budget/checkpoint | no domain |
| 4.1.4 | tool schema/timeout | registry |
| 4.1.5 | code + audit verdict | dual |
| 4.1.6 | report plan optional sections | no fixed sections |
| 4.1.7 | API/UI | no old import |
| 4.1.8 | demo 100 | E2E |
| 4.1.9 | import guard | no legacy |

---

## 18. 风险

| 风险 | 处理 |
|---|---|
| 100 篇 fulltext 不足 | abstract-only + degraded，不阻塞报告 |
| LLM 长时间不 final | budget/max_steps/no-progress |
| Tool 副作用失败 | idempotent/回滚/错误码 |
| ReportPlan 乱生成 | 允许 kind + max sections + requirements |
| Audit 覆盖代码 | code hard fail 优先 |
| Chat 仍依赖旧 kernel | Phase 4.1 不迁移 Chat；保留 adapter，Phase 5 清理 |
| 双轨运行 | 只允许迁移期；4.1.9 删除旧文件 |

---

## 19. Demo 验收

```text
Workflow:
  source.collect
  evidence.extract
  report.generate
  finalize

Features:
  classification=false
  scorecard=false
  require_fulltext=false

Output:
  100 papers
  >=100 claims
  overview
  paper analyses
  synthesis
  paper_index

Metrics:
  citation_coverage=1
  uncited_facts=0
  duplicate_claim_rate<=0.1
  code_verifier=pass
  audit=pass|degraded
```

---

## 20. Commit 序列

```text
docs(W-P00): record pre-migration baseline
feat(W-P01): add node tool verdict contracts
feat(W-P02): add configurable node chain runner
feat(K-P01): execute nodes through kernel context
feat(T-P01): add tool registry and source packs
feat(V-P01): add code and audit verifier
feat(R-P01): generate reports through a single agent node
feat(I-P01): wire demo profile through new workflow
feat(R-P02): add 100-paper demo profile
refactor(W-P03): delete legacy report workflow
```


---

## 21. 执行记录

### 4.1.0 baseline

```text
docs/implementation/BASELINE-P4.1.md
```

### 4.1.1 contracts

新增：

```text
contracts/node.py
contracts/tool.py
contracts/verdict.py
contracts/features.py
contracts/artifacts.py
```

测试：

```text
tests/v2/test_contracts_node.py
7 passed
```

当前总门禁：

```text
pytest tests/v2   84 passed
ruff              clean
```

旧 1.2 freeze test 已限制为 legacy 文件，不把 2.0 draft 混入冻结 hash。

### 4.1.2 Workflow

新增：

```text
workflow/node/__init__.py
workflow/node/definition.py
workflow/node/runner.py
workflow/node/state.py
workflow/node/ports.py
tests/v2/test_workflow_node_runner.py
```

能力：

```text
Node 链
enabled/skipped
optional/degraded
required failure
resume committed
pause boundary
report workflow with classification disabled
```

说明：

```text
新实现暂放 workflow/node/
旧 workflow/runner.py 仍被旧 ReportWorkflow 使用
4.1.9 清理旧文件后合并到 workflow/
```

当前总门禁：

```text
pytest tests/v2   91 passed
ruff              clean
```

下一 step：

```text
4.1.3 Kernel
```
