# ADR-0008 · Phase 3 契约冻结：NodeGoal / ShellSpec / ToolSpec v2

- **状态**：Accepted
- **日期**：2026-10-26
- **相关**：ADR-0006（事件契约）、ADR-0007（NodeIO/config 冻结）、`phase3-double-layer-agent.md`

## 背景

Phase 3 要在不改坏 2.2 行为的前提下，把"节点实现"换成"节点声明 + 通用微运行时"。
这要求三类契约先稳定：节点目标（NodeGoal）、任务壳（ShellSpec）、工具协议（ToolSpec v2）。
否则每加一个节点/工具都会牵动运行时与测试。

## 决策

1. **NodeGoal 冻结**：字段 `name/objective/postconditions/tools/max_steps/max_usd/autonomy/escalation/notes`；
   `postconditions` 必须非空、≤2、⊆`GATE_NAMES`；`max_steps ∈ 1..5`。
2. **ShellSpec 冻结**：纯数据（无 IO/DB/LLM）；canonical JSON 的 sha256 前 16 位为 `hash`；
   改壳必须升 `version` 并记录新 hash；`default_shell()` 为周报预设（10 Goal）。
3. **ToolSpec v2 冻结**：四段流水线 `pre_execute → guard(单调) → execute(超时) → post_execute`；
   `output_schema` 必填；`concurrency` 默认 `exclusive`（fail-closed）；参数进入流水线后不可改写。
4. **默认关**：`pipeline.micro_enabled=False`；关闭时节点行为与 2.2 完全一致（十阶段、无 tool_call）。
5. **门禁与工具名的唯一来源**：`graph/gates.GATE_NAMES`、`tools/spec.TOOL_NAMES`。

## 后果

- 改上述字段/语义 = 破坏契约，需修订本 ADR 并升 `shell.version`；
- 壳的 hash 可用于论文复现（同一 hash = 同一编排）；
- L2 节点逐节点开启，可随时回退到 2.2 行为；
- 旧 `tools/registry.Tool` 暂时保留，3.1 起新节点走 `ToolRuntime`。

## 被否决的替代方案

| 方案 | 否决理由 |
|---|---|
| 用 dict 直接描述 Goal | 无类型校验，postcondition 容易写错 |
| 每个节点一个 MicroAgent 子类 | 回到"节点=实现"，无法复用 |
| 一次性替换旧工具注册表 | 风险大，无法逐节点 A/B |
