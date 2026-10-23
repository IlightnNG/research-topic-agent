# ADR-0007：NodeIO 契约、配置名与门禁清单冻结

> 状态：**Accepted（2026-10-22）**｜适用范围：Phase 2.1 起
> 关联：ADR-0006（事件格式冻结）、`phase2.1-wiring-and-contracts.md`

## 背景

Phase 2.1 要在十节点图上接门禁、回边与指标。若等到实现中途再加字段/改名，
会导致契约测试、事件消费者、前端与文档全量返工。

## 决策

冻结以下四类**接口边界**（不冻结节点内部实现）：

### 1. NodeIO（`src/lit_agent/contracts/nodeio.py`）

- `NodeOutput{stage, artifacts, counters, pending_writes}`——节点只返回**引用与计数**，正文不进 state；
- `GateResult{name, ok, code, action, reasons, details}`——门禁只判决，不写库；
- `Decision{action, target, code, reasons, source, attempt, drop_claim_indexes, deferred}`；
- `PendingWrite{kind ∈ {report, metrics}}`——两阶段提交的声明式写入。

**语义**：`action ∈ {continue, annotate, retry, repair, degrade, replan, abort}`，
顺序即优先级（continue < annotate < retry/repair < degrade < replan < abort）。

### 2. 门禁清单（6 类，名字冻结）

`schema` / `evidence_sufficiency` / `citation_integrity` / `support_ratio` / `budget` / `drift`

### 3. 事件 payload（复用 EventType，**禁止新增类型**）

| 事件 | 必需字段 |
|---|---|
| `phase_change` | `phase ∈ {start,end}`、`attempt:int`（end 另含 `ok`、`action`、`gates`） |
| `guard_trigger` | `gate`、`code`、`action`、`reasons`、`attempt`、`source` |
| `recovery` | `from_stage`、`to_stage`、`attempt`、`reason` |
| `tool_call` | `tool`、`ok`、`duration_ms` |

规则：**只增不改**；消费者必须忽略未知字段。

### 4. 配置名与默认值（`pipeline.*`）

| 配置 | 默认 |
|---|---|
| `gates.enabled` | `true` |
| `gates.evidence_min_cards` | `1`（2.2 起可配；生产建议 3；与 2.1 行为等价） |
| `gates.support_ratio_min` | `0.6` |
| `gates.citation_required` | `true` |
| `limits.max_attempts` | `{analysis:2, retrieval:2, report:1}` |
| `limits.max_total_llm_calls` | `12` |
| `limits.recursion_limit` | `60` |
| `transitions` | `true`（S4 前代码内临时置 false） |
| `hybrid` / `hybrid_alpha` | `true` / `0.6` |
| `llm` | `auto`（有 key 则启用） |
| `pdf_enabled` | `false` |

### 5. 幂等键

`{run_id}:{stage}:{attempt}`；事件用 `{stage}:start:{attempt}` / `{stage}:end:{attempt}`。

## 后果

- ✅ 契约测试可自动生成（`tests/contracts` 参数化 10 节点）；
- ✅ 前端/验证器可只依赖 payload 字段；
- ✅ 自进化（P5）有可校验的接口；
- ⚠️ 改任一命名/字段必须升 `phase2.1` 文档版本并记录；**不得为过测修改**。
