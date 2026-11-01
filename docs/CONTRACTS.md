# Contracts

> 版本：2.0 FROZEN（2026-11-01）
> 状态：已冻结
> 依据：`docs/ARCHITECTURE.md` 2.0
> 旧 1.2 契约（M1–M6 ports）已删除。

---

## 1. 契约总览

```text
WorkflowDefinition
  = ordered list[NodeSpec]

NodeSpec
  = goal + tools + inputs + output_schema + verifier + budget

Kernel
  = run(NodeSpec, NodeContext, ToolRegistry, LLM) -> NodeResult

ToolSpec
  = name + schema + side_effect + handler

Verifier
  = code checks + LLM audit -> Verdict
```

契约最小集：

```text
NodeSpec
NodeContext
NodeResult
ToolSpec
ToolCall
ToolResult
Verdict
FeatureProfile
ArtifactEnvelope
```

---

## 2. WorkflowDefinition

```python
@dataclass(frozen=True)
class WorkflowDefinition:
    name: str
    version: str
    nodes: tuple[NodeSpec, ...]
    features: FeatureProfile
```

规则：

- `Workflow` 就是 Node 链；
- 节点顺序由 `nodes` 决定；
- `features` 决定可选节点；
- Node 之间只通过 artifact 传递；
- Node ID 在同一个 workflow 内唯一；
- 运行时不允许 LLM 增删节点。

---

## 3. NodeSpec

```python
@dataclass(frozen=True)
class NodeSpec:
    id: str
    goal: str
    tools: tuple[str, ...]
    inputs: tuple[str, ...]
    output_schema: str
    verifier: VerifierProfile
    max_steps: int = 8
    max_usd: float = 0.20
    max_tokens: int = 4000
    timeout_s: float = 600.0
    optional: bool = False
    enabled: bool = True
```

字段规则：

### goal

- 提示词输入，不是代码流程；
- 可以包含：
  ```text
  目标
  数量要求
  质量要求
  可接受的降级
  停止条件
  ```
- 不包含：
  ```text
  具体 SQL
  具体文件路径
  固定章节顺序
  ```

### tools

- 只能使用 allowlist；
- 工具名全局唯一；
- LLM 不能调用未列出的工具；
- workflow 不直接调用工具。

### inputs

- 引用前序 Node 的 output key；
- 缺失输入时 Node 不能启动，除非 schema 允许 optional；
- 不允许隐式全局变量。

### output_schema

- 必须可 JSON Schema 验证；
- commit 前 CodeVerifier 检查；
- 不符合 schema → Node fail，不进入下一个节点。

### verifier

```python
@dataclass(frozen=True)
class VerifierProfile:
    code: tuple[str, ...] = ("schema",)
    audit: str | None = "default"
    audit_required: bool = True
```

- `code`：代码检查 ID；
- `audit`：LLM 审计 profile；
- 两者都执行；
- code hard fail 不能被 audit 覆盖。

### optional / enabled

```text
enabled=False  → node.skipped，下游必须允许缺省
optional=True  → fail 后可 degraded 继续
```

---

## 4. FeatureProfile

```python
@dataclass(frozen=True)
class FeatureProfile:
    classification: bool = False
    direction_sections: bool = False
    per_paper_sections: bool = True
    synthesis: bool = True
    scorecard: bool = False
    gold_eval: bool = False
    require_fulltext: bool = False
```

用途：

- 生成 WorkflowDefinition；
- 生成 ReportRequirements；
- 控制 `map` / `scorecard` 节点；
- 控制 ReportPlan section 集合。

---

## 5. Kernel 契约

```python
class Kernel(Protocol):
    def run(
        self,
        node: NodeSpec,
        context: NodeContext,
        tools: ToolRegistry,
        llm: LLMClient,
        *,
        checkpoint: KernelCheckpoint | None = None,
    ) -> NodeResult: ...
```

`NodeContext`：

```python
@dataclass
class NodeContext:
    run_id: str
    node_id: str
    goal: str
    features: FeatureProfile
    inputs: dict[str, Any]
    output_schema: dict[str, Any]
```

`NodeResult`：

```python
@dataclass
class NodeResult:
    output: dict[str, Any]
    trace: list[dict[str, Any]]
    usage: LLMUsage
    cost_usd: float
    stop_reason: str
    checkpoint: KernelCheckpoint
```

Kernel 不允许：

```text
修改 WorkflowDefinition
调用未授权工具
访问 DB / 文件 / HTTP 绕过工具
直接调用 domain service
```

Kernel 必须：

```text
记录 tool trace
执行 budget / max_steps / timeout
支持 cancel / resume
每次 tool call 后可 checkpoint
```

---

## 6. Tool 契约

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
    max_retries: int
    retry_on: tuple[str, ...]
    handler: Callable[[dict], dict]
```

`ToolCall`：

```python
@dataclass
class ToolCall:
    tool: str
    args: dict
    call_id: str
```

`ToolResult`：

```python
@dataclass
class ToolResult:
    ok: bool
    output: dict
    error_code: str | None
    retryable: bool
    duration_ms: int
    cost_usd: float
```

规则：

- 所有外部 I/O 只能通过 Tool；
- Tool 参数先 schema 校验；
- Tool 输出必须 JSON；
- 有副作用的 Tool 必须幂等或可回滚；
- Tool 错误不能静默；
- LLM 可以调用 `check.*` 自检，但最终 Verifier 独立重跑。

---

## 7. Verifier 契约

```python
@dataclass
class CodeCheck:
    check_id: str
    passed: bool
    reason: str = ""

@dataclass
class AuditResult:
    scores: dict[str, float]
    problems: list[str]
    verdict: str

@dataclass
class Verdict:
    accept: bool
    code: list[CodeCheck]
    audit: AuditResult
    reasons: list[str]
```

规则：

```text
code all pass + audit accept  → commit
code all pass + audit fail    → repair
code fail                     → reject
```

代码检查必须包含：

```text
schema
paper_id 存在
claim_id 合法
quote 原文命中
citation 覆盖
count reconciliation
字数硬上限
文件存在
budget / steps
```

Audit 只评：

```text
相关性
覆盖度
可读性
综合质量
引用支持度
```

---

## 8. Artifact 契约

统一 envelope：

```json
{
  "schema_version": 1,
  "artifact_type": "SourceArtifact",
  "run_id": "...",
  "node_id": "source.collect",
  "sha256": "...",
  "payload": {}
}
```

领域 artifact：

```text
SourceArtifact
EvidenceArtifact
MapArtifact
ReportPlan
ReportDraft
ScoreCard
Verdict
```

规则：

- Node 间只传 artifact；
- payload 由 schema 校验；
- `sha256` 由内容计算；
- 大文本放 Artifact Store，不塞事件。

---

## 9. Report 专用契约

### ReportRequirements

```json
{
  "min_words": 1000,
  "max_words": 8000,
  "required_sections": ["overview", "paper_index"],
  "optional_sections": ["synthesis", "comparison", "gaps"],
  "citation_required": true
}
```

### ReportPlan

```json
{
  "sections": [
    {"kind": "overview"},
    {"kind": "paper_analysis", "paper_ids": ["P1", "P2"]},
    {"kind": "synthesis"},
    {"kind": "paper_index"}
  ]
}
```

规则：

- `ReportPlan` 是 `report.plan` 工具产物；
- section 顺序由 plan 决定；
- 必需 section 由 requirements 检查；
- 可选 section 缺失合法；
- 不允许未知 section kind。

### SectionArtifact

```json
{
  "section_id": "paper_analysis_01",
  "kind": "paper_analysis",
  "title": "...",
  "body": "...",
  "claim_ids": ["..."],
  "state": "accepted|repaired|failed"
}
```

---

## 10. 事件契约

```json
{
  "schema_version": 1,
  "event_id": "...",
  "run_id": "...",
  "seq": 1,
  "ts": "...",
  "type": "node.started",
  "node_id": "report.generate",
  "tool": null,
  "severity": "info",
  "payload": {}
}
```

事件：

```text
run.started
node.started
node.skipped
tool.called
tool.result
node.verifying
node.committed
node.failed
section.delta
run.finished
```

---

## 11. 模块边界

| 模块 | 可以依赖 | 禁止 |
|---|---|---|
| `workflow` | kernel/verify/storage contracts | domain service |
| `kernel` | tools contracts | domain service、DB |
| `tools` | storage/external adapters | workflow、kernel |
| `verify` | code checks、audit tool | workflow 内部状态 |
| `domains` | tools contracts | 其他 domain service |
| `interface` | workflow | tools/domain 直接调用 |
| `composition` | all concrete | 业务逻辑 |

唯一组合根：

```text
composition.py
```

---

## 12. 版本与冻结

```text
CONTRACT_VERSION 2.0-draft
SCHEMA_VERSION 1
```

冻结条件：

- NodeSpec 字段稳定；
- ToolSpec 字段稳定；
- Verdict 字段稳定；
- ReportPlan / SectionArtifact 稳定；
- demo workflow 跑通；
- contract tests；
- 旧 1.2 迁移完成。

冻结后：

```text
新增字段 = minor
修改语义 = major
删除 = major
```

---

## 13. Legacy 1.2

旧契约：

```text
M1–M6 ports
LLMClient / ToolSpec / KernelCheckpoint
ReportWorkflow 依赖注入
CONTRACT_VERSION=1.2
```

状态：

```text
代码仍在运行
docs/CONTRACTS.md 2.0 为目标
迁移完成后删除 1.2 描述
```

---

## 14. 迁移检查

```text
[ ] workflow/kernel/tools/verify 独立目录
[ ] NodeSpec goal/tools/verifier
[ ] ToolRegistry 覆盖所有外部交互
[ ] Kernel 不再 import domain
[ ] report.generate 使用 Kernel
[ ] ReportPlan 来自工具
[ ] code + audit 双 Verifier
[ ] demo workflow 无 classification
[ ] 100 篇报告可跑
[ ] contract tests
```
