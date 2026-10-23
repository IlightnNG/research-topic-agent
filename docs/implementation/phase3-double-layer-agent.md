# Phase 3 —— 双层 Agent：可控 Workflow + 微观 ReAct

> **文档性质**：**规范性文件（冻结契约）**。Phase 3 的"做什么 / 什么算做完 / 按什么顺序"以本文件为唯一判据。
> **版本**：**1.0.0**（2026-10-23）
> **前序**：`phase2.2-closeout-and-observability.md`、`phase2.1-wiring-and-contracts.md` v2.0.0、ADR-0006（事件）、ADR-0007（NodeIO/配置）。
> **入口基线**：`verify_phase2_1 13/13`、`pytest 439+`、`e2e 8+`、`verify_phase1 13/13`、`vue-tsc 0 error`。
> **重要度**：**本阶段是项目从"可演示的系统"变成"有研究贡献的系统"的分水岭**，预计投入 2–2.5 周；允许拆成 3.0 → 3.5 六个子阶段独立验收。

---

## 0. 目标、规则与"完成"定义

### 0.1 一句话目标

在**不破坏外层可观测/可续跑/可评测**的前提下，给节点装上**通用的微观运行时（plan + ReAct + 自检）**，让 LLM 在"有目标、有工具、有预算、有验收"的边界内自由发挥；并用**对照实验**证明"双层结构"比"纯 workflow"和"纯 ReAct"都好。

### 0.2 三层结构（本阶段的核心思想）

```
┌──────────────── 编排层：10 个可见节点（Workflow）────────────────┐
│ 契约 NodeIO · 门禁 postconditions · 事件 · checkpoint · 预算 · 人审  │
│        每个节点 = NodeGoal（配置），不是"一段写死的实现"            │
└───────────────────────────┬──────────────────────────────────────┘
                            │ NodeGoal(objective, postconditions, tools, max_steps)
┌───────────────────────────▼──────────────────────────────────────┐
│ 控制层：MicroAgent（通用兼用卡）                                   │
│  plan → act(工具) → observe → evaluate(门禁) → replan/stop/fail    │
│  每步可观测、可预算、可终止；L1 失败才升级到 L2（省成本）           │
└───────────────────────────┬──────────────────────────────────────┘
                            │ ToolSpec + 结构化结果
┌───────────────────────────▼──────────────────────────────────────┐
│ 能力层：工具库（rewrite/retrieve/verify/rewrite_claim/compress…）  │
│ 治理层：预算 · 调用数 · 熔断 · 权限 · 沙盒 · 注入防护              │
└──────────────────────────────────────────────────────────────────┘
```

### 0.3 四条硬规则

| 规则 | 内容 |
|---|---|
| **R1 外层契约不变** | NodeIO、6 类门禁、事件类型（不新增）、checkpoint 语义不动 |
| **R2 逐节点启用** | 内层循环只对 allowlist 节点开启；**默认关闭**，关掉后行为与 2.2 完全一致 |
| **R3 有界自治** | 每节点 `max_steps`、`max_usd`、墙钟上限；总 LLM 调用数硬顶 |
| **R4 可评测** | 任何"更聪明"必须能用 gold/基准/轨迹指标证明，禁止"我觉得更好" |

### 0.4 反向定义

> **Phase 3 结束 ⇔ §10 的 H1–H16 全绿，且 3.5 的消融实验有结论（不是"跑通了"）。**
> 子阶段可以独立交付；**3.3 结束 = 系统基本完成**；3.5 结束 = 论文实验数据齐备。

---

## 1. 入口条件

| # | 条件 | 验证 |
|---|---|---|
| E1 | Phase 2.2 已收尾 | `phase2.2-*.md` H1–H8 全绿 |
| E2 | 基线全绿 | `pytest`、`verify_phase2_1 --all`、`verify_phase2`、`verify_phase1 --online`、e2e |
| E3 | 可回退 | `git tag phase2.2-rc1` |
| E4 | 评测资产就绪 | gold 20 条 + 检索 20 查询 + 冻结哈希 |
| E5 | 成本可观测 | LLM 调用数/金额有硬顶（2.2 M2） |

---

## 2. 现状与差距

### 2.1 现在每个节点的"微观"是什么

| 节点 | 内部行为 | LLM | 工具 | 循环 |
|---|---|---|---|---|
| intake / scope | 查行、算指纹 | ❌ | ❌ | ❌ |
| retrieval | 一次 hybrid 排序 | ❌ | 1 个函数 | ❌ |
| parse / normalize / mapping | 统计/去重/投影 | ❌ | 内部函数 | ❌ |
| analysis | 一次抽取（有 key 时**一次** `chat_json`） | ✅ 0/1 次 | ❌ | ❌ |
| critique | 规则检查 | ❌ | ❌ | ❌ |
| report | 模板拼装 + 提交 | ❌ | ❌ | ❌ |
| evaluate | SQL 聚合 | ❌ | ❌ | ❌ |

**结论**：宏观完备、微观单步；没有"抽→验→修"，没有"查→不够→改写再查"，没有工具选择。

### 2.2 能力缺口

| 缺口 | 说明 |
|---|---|
| 无通用 MicroAgent | 每个节点若要循环，就得各写一份（重复且不可测） |
| 工具协议只有"调用" | 缺：副作用分类、幂等声明、权限、结果校验、工具检索 |
| 无 step 级观测 | 内层循环无法审计（看不到第 2 步干了什么） |
| 无升级策略 | 要么全单步（笨），要么全 ReAct（贵） |
| 无轨迹评测 | pass@k、步数、修复率、升级率都没有 |
| Chat 仍是 501 | 缺会话存储、L3 循环、前端 |

---

## 3. 目标架构（冻结设计）

### 3.1 NodeGoal：节点从"实现"变成"配置"

```python
# contracts/goals.py
@dataclass(frozen=True)
class NodeGoal:
    name: str                       # retrieval / analysis / ...
    objective: str                  # 给人看：这一站要达成什么
    postconditions: tuple[str, ...] # 机器可判：门禁名（必须 ⊆ GATE_NAMES；可多条）
    tools: tuple[str, ...]          # 允许使用的工具（白名单）
    max_steps: int = 3              # 内层最多几步
    max_usd: float = 0.05           # 内层预算
    autonomy: Literal["L1", "L2"] = "L1"
    escalation: Literal["none", "on_gate_failure"] = "on_gate_failure"
    notes: str = ""
```

约束：
- `postconditions` **必须是已有门禁**（schema/evidence/citation/support/budget/drift），否则不允许启用 L2；多条时**全部通过**才算达标；
- 节点只声明"目标 + 工具 + 预算"，**不写循环**；循环由 MicroAgent 提供；
- 需要特殊逻辑的节点（report/evaluate）**继续用普通函数**（逃生舱）。

### 3.2 MicroAgent：通用兼用卡

```python
# runtime/micro_agent.py
class MicroAgent:
    def run(self, goal: NodeGoal, ctx: RunContext, state: dict) -> NodeOutput:
        plan = self.plan(goal, state)                 # 显式计划（≤ max_steps 项）
        trace: list[Step] = []
        for step in range(goal.max_steps):
            self.check_budget(goal, ctx)              # 预算/调用数/墙钟
            action = self.decide(plan, trace, goal)   # 选工具或收尾
            result = self.act(action, ctx)            # 调工具（结构化结果）
            trace.append(step_record(action, result))
            verdict = self.evaluate(goal, trace, state)   # 跑 postconditions 门禁
            if verdict.ok:
                break
            plan = self.replan(plan, trace, verdict)  # 失败 → 改计划
        return self.finalize(goal, trace, state)
```

**终止条件（四选一，先到先停）**：
1. postconditions 全部通过；
2. `max_steps`；
3. 预算/调用数/墙钟超限；
4. 无进展（连续 2 步同一动作且无新产物）。

**replan 规则**：
- 工具失败 → 同工具换参数重试 1 次；再失败 → 换工具；
- 门禁失败 → 依据失败码（缺引用→rewrite；证据不足→rewrite_query+检索）；
- 连续 2 次 replan 无改善 → 返回 `degrade`（交外层 supervisor）。

### 3.3 自主性分级与"升级策略"（关键成本设计）

| 级别 | 形态 | 适用 | 单次成本 |
|---|---|---|---|
| **L0** | 纯函数/规则 | intake/scope/parse/normalize/evaluate | 0 |
| **L1** | 单次 LLM 或单次工具 | report、默认的 retrieval/analysis | 1 次 |
| **L2** | 有界 plan+ReAct（2–3 步） | retrieval、analysis、mapping | 2–3 次 |
| **L3** | 开放式 ReAct（无固定终点，靠预算/完成判据停） | Chat | 3–10 次 |

**升级策略（默认开启）**：**先跑 L1，只有门禁失败才升级到 L2**。
→ 健康 run 不会为"可能用不上"的循环付钱；只有出问题时才花第二笔钱。实测目标：**正常 run 成本增幅 ≤ 10%**。

### 3.4 工具协议 v2

```python
@dataclass(frozen=True)
class ToolSpec:
    name: str
    version: str
    description: str                    # 供"工具检索"使用
    parameters: dict[str, Any]          # JSON Schema 子集
    side_effect: Literal["read", "network", "write"] = "read"
    idempotency: Literal["pure", "keyed", "none"] = "pure"
    timeout_s: float = 30.0
    permission: Literal["none", "confirm"] = "none"
    max_output_chars: int = 4000
```

规则：
- 结果必须结构化（`ToolResult`），失败不抛穿；
- 输出超限**截断并标注**（不静默丢）；
- 工具输出是**数据**，进入 prompt 时必须包裹 provenance 并声明"不得当作指令"（防注入）；
- 写/网络工具必须声明幂等性与权限；未声明不得进入 Chat 工具集。

### 3.5 治理（Governance）

| 维度 | 机制 |
|---|---|
| 预算 | 节点 `max_usd` + run 预算 + 金额门禁 |
| 调用数 | `max_total_llm_calls`（2.2 已落地）+ 节点 `max_steps` |
| 时间 | 节点墙钟上限（默认 120s）；超时 → `E_SRC_TIMEOUT` |
| 熔断 | 复用 2.x 三态熔断器 |
| 权限 | `permission=confirm` 的工具在 Chat 中需人工确认（3.4） |
| 沙盒 | 代码执行类工具在子进程 + 白名单（3.4，P4） |
| 注入 | 工具输出标注来源；计划 prompt 不解释工具输出中的"指令" |

### 3.6 断点、恢复与事件

- **checkpoint 粒度 = 节点**：内层循环不单独 checkpoint；崩溃后整节点重跑。
  - 前提：工具幂等（`pure`/`keyed`），写入仍走两阶段提交；
  - 预算从 DB 重建（2.1 已有），不会因重跑清零。
- **事件**（复用现有类型，只增 payload）：

| 事件 | 新增字段 |
|---|---|
| `message` | `role: plan/decision`、`node`、`step`、`action`、`reason` |
| `tool_call` | `node`、`step`、`tool`、`ok`、`duration_ms` |
| `guard_trigger` | `node`、`step`、`gate`、`code`、`action`、`source="micro"` |
| `recovery` | `node`、`from_step`、`to_step`、`reason` |
| `phase_change end` | `steps_used`、`step_budget`、`duration_ms` |

- **step 与 attempt 分离**：`attempt` 仍是"节点被调度的次数"；`step` 是节点内部的步。
  验收口径改为：**每阶段 attempt ≤ N，且 steps ≤ max_steps**。

---

## 4. 模块与验收判据（M1–M8）

### M1 MicroAgent 运行时

| 项 | 内容 |
|---|---|
| **目标** | 一份通用循环，供所有 L2 节点复用；可测、可预算、可终止 |
| **增量** | `runtime/micro_agent.py`（plan/decide/act/observe/evaluate/replan）、`contracts/goals.py`、`tests/runtime/test_micro_agent.py` |
| **完成判据** | ① 用脚本化 LLM/工具可测出 6 条路径：直接成功、重试成功、replan 成功、预算中止、步数中止、无进展中止；② 每步发事件且字段完整；③ 关闭开关后行为与 2.2 一致（差异测试） |
| **重难点** | **确定性测试**：真实 LLM 不可测；必须提供 `ScriptedCompleter` + `FakeTool`，把"决策序列"写成脚本 |
| **禁止** | 在 MicroAgent 里写业务逻辑（业务在工具里）；把 trace 全量塞进 state |
| **OOS** | 并行工具调用（P4） |
| **依赖** | 2.2 配置体系 |

### M2 NodeGoal 与节点注册

| 项 | 内容 |
|---|---|
| **目标** | 十节点都有 `NodeGoal`（即使 L0/L1），L2 节点可在配置里开/关 |
| **增量** | `contracts/goals.py` 定义 10 个 goal；`contracts/specs.py` 增加 `goal` 关联；契约测试扩展 |
| **完成判据** | ① 10 个 goal 齐全；② `postconditions ⊆ GATE_NAMES` 且非空；③ `tools ⊆ 工具注册表`；④ 每节点有 `autonomy` 与开关；⑤ `pytest tests/contracts` 全绿 |
| **重难点** | goal 必须可序列化（配置/审计）；不能塞 callable |
| **禁止** | 在 goal 里写 prompt 全文（prompt 属于实现，版本化在代码里） |
| **依赖** | M1 |

### M3 工具协议 v2 + 能力库

| 项 | 内容 |
|---|---|
| **目标** | 工具可声明、可校验、可检索；能力覆盖"改写/检索/抽取/校验/重写/压缩" |
| **增量** | `tools/spec.py`、`ToolRegistry` 支持 spec；新工具：`rewrite_query`、`hybrid_search`（已有）、`extract_claims`、`verify_claim`、`rewrite_claim`、`compress_context`、`cluster_papers`；`tests/tools` 扩展 |
| **完成判据** | ① 每个工具有 spec 且通过 schema 校验；② 超时/异常/超大输出都有结构化结果；③ 同一输入两次调用结果一致（`pure` 工具）；④ 工具目录可被"检索"（3.4 用） |
| **重难点** | `verify_claim` 要复用 `eval.grounding`（不能两套判定）；`rewrite_claim` 必须保留引用约束 |
| **禁止** | 工具里写业务状态；工具直接写库（写操作必须由节点 commit 层执行） |
| **依赖** | M1 |

### M4 retrieval 升级 L2

| 项 | 内容 |
|---|---|
| **目标** | "查不到就改写再查"，最多 2–3 步，且**健康 run 不额外花钱**（先 L1） |
| **增量** | goal：`objective="找到 ≥N 篇与 scope 相关的证据"`，`tools=(hybrid_search, rewrite_query)`，`max_steps=2`；retrieval 节点接 MicroAgent（开关 `nodes.retrieval.autonomy`） |
| **完成判据** | ① 首次检索达标 → 只跑 1 步（与 2.2 事件数一致）；② 首次不足 → 改写查询再查，最多 2 步；③ 仍不足 → `degrade`（不 abort）；④ 该节点 recall@10 不低于基线；⑤ 成本增幅 ≤ 30%（失败场景） |
| **重难点** | 改写会改变"聚焦"语义，必须保留原 query 作为约束；改写结果要可审计（事件里存改写文本） |
| **禁止** | 改写后丢掉原意图；无限改写 |
| **依赖** | M1–M3 |

### M5 analysis 升级 L2（逐条校验-修复）

| 项 | 内容 |
|---|---|
| **目标** | "抽取 → 逐条校验 → 只重写有问题的 claim"，替代"一次生成、外层门禁兜底" |
| **增量** | goal：`postconditions=("citation_integrity","support_ratio")`，`tools=(extract_claims, verify_claim, rewrite_claim)`，`max_steps=3`；analysis 节点接 MicroAgent |
| **完成判据** | ① 有缺引用的 claim → 只重写该条（其余不动）；② 重写后仍不合格 → 丢弃该条并 `degrade`；③ `grounding_rate` 不低于 2.2；④ 单 run 成本增幅 ≤ 50%；⑤ 报告一致性（`n_claims == claims_total`）保持 |
| **重难点** | 逐条修复要避免"越修越差"：用 `verify_claim` 做前后对比，只接受更优版本；重写不得引入新引用 |
| **禁止** | 用模型自评替代 `verify_claim`；重写时保留原文与新文导致重复 claim |
| **依赖** | M1–M3 |

### M6 critique / mapping / report 的定位

| 项 | 内容 |
|---|---|
| **目标** | 明确"哪些节点不该上 L2"，避免过度自治 |
| **增量** | critique 保持规则（可加 1 个 LLM 仅用于歧义）；mapping 可选 L2（实体消歧，3.4 再做）；report 保持 L1（模板 + 严格引用） |
| **完成判据** | 这三节点默认 `autonomy=L0/L1`；打开 L2 不改变现有验收（可作为后续实验组） |
| **重难点** | 报告生成的可控性优先于灵活性 |
| **禁止** | 为了"看起来 agentic"强行给 report 加循环 |
| **依赖** | M2 |

### M7 Chat（L3 ReAct + 会话）

| 项 | 内容 |
|---|---|
| **目标** | 第三页可用：多轮对话、工具调用、引用、可中断、可评测 |
| **增量** | 迁移 0004（`chat_sessions/chat_messages`）、`agents/chat.py`（L3 循环）、API（会话 CRUD + SSE）、前端 Chat 页（输入框、流式、工具轨迹、引用） |
| **完成判据** | ① 能回答"这个话题最近有什么新进展"并给出论文级引用；② 工具调用可见；③ 可中止；④ 预算可控（默认 3–8 步）；⑤ 多轮保持上下文摘要；⑥ e2e 覆盖首轮/追问/中止 |
| **重难点** | 上下文增长（摘要 + 引用裁剪）；工具误用（白名单 + 权限）；评测（无固定 gold，需要脚本化场景） |
| **禁止** | 把 Chat 写成"直接拼 prompt 不调工具"；允许无引用结论 |
| **OOS** | 多人协作、语音 |
| **依赖** | M1–M3 |

### M8 评测与消融（论文核心）

| 项 | 内容 |
|---|---|
| **目标** | 证明"双层结构"的收益，而不是"跑通了" |
| **增量** | gold v2（50 claims / 30 queries / 10 多轮脚本）、轨迹指标（steps、tool_calls、repair_rate、escalation_rate、cost_per_claim）、pass@k、消融脚本 |
| **完成判据** | ① 三组对照（workflow-only / L2 nodes / L3 chat）在质量/成本/时延上可比较；② 报告均值与方差；③ 结论可复述（"L2 把 X 提升 Y%，代价是 Z%"）；④ 冻结哈希 v2 |
| **重难点** | 非确定性：固定种子/温度、重复 k 次；小样本：报告效应量与置信区间，不吹 p 值 |
| **禁止** | 只跑一次就下结论；挑好看的案例 |
| **依赖** | M1–M7 |

---

## 5. 缺陷分级

| 级别 | 定义 |
|---|---|
| **P0** | 契约违反 / 预算失控 / 死循环 / 安全（注入、越权）/ 评测失真 |
| **P1** | 质量或成本明显退化 |
| **P2** | 体验、性能、美化 |

**纪律**：任何 L2 节点上线前必须有：步数上限测试、预算测试、死循环测试、关闭开关的回归测试。

---

## 6. 缺口登记

| ID | 项 | 归属 |
|---|---|---|
| P3-01 | MicroAgent 运行时 | 3.0 |
| P3-02 | 工具协议 v2 + 能力库 | 3.0 |
| P3-03 | retrieval L2 | 3.1 |
| P3-04 | analysis L2 | 3.2 |
| P3-05 | Chat 存储 + L3 | 3.3 |
| P3-06 | 工具检索/权限/沙盒 | 3.4 |
| P3-07 | 评测扩展 + 消融 | 3.5 |
| P3-08 | 语义分节（report） | 3.2 选做 |
| P3-09 | 记忆/长期偏好 | 3.4 选做 |

---

## 7. 子阶段与步骤（S1–S24）

### 7.1 3.0 Foundations（≈2 天）

| 步 | 目标 | 产物 | 关键门禁 | 回滚 | 预估 |
|---|---|---|---|---|---|
| **S1** | NodeGoal 契约 + 10 goal 注册 | `contracts/goals.py`、specs 扩展、契约测试 | 10/10；postconditions 合法 | 开关关闭 | 3 h |
| **S2** | MicroAgent 核心 | `runtime/micro_agent.py` + 6 路径单测 | 6 路径全绿；事件完整 | `micro.enabled=false` | 4 h |
| **S3** | 工具协议 v2 | `tools/spec.py`、registry 升级、3 个新工具 | spec 校验；幂等/超时/截断 | 保留旧调用 | 4 h |
| **S4** | runner 接线（默认关） | `graph_runner` 支持 per-node autonomy | 关闭时行为与 2.2 逐字节一致（事件差异=0） | 同上 | 3 h |
| **S5** | 确定性测试台 | `tests/support/scripted.py`（ScriptedCompleter/FakeTool）、golden trace | 无网络、无睡眠、可重复 | 删除 | 2 h |
| **S6** | 契约、验证器与不变量测试 | `tests/contracts/test_micro_contracts.py`、`scripts/verify_phase3.py`（骨架 + H1/H6/H7） | 全绿；`--foundations` PASS | —— | 3 h |

**3.0 出口**：开/关前后行为等价；MicroAgent 6 路径可测；工具 spec 全覆盖；`verify_phase3 --foundations` PASS。

### 7.2 3.1 retrieval L2（≈1.5 天）

| 步 | 目标 | 产物 | 关键门禁 | 预估 |
|---|---|---|---|---|
| **S7** | retrieval goal + escalation | goal 配置、节点接线 | 健康 run 只 1 步；失败 ≤2 步 | 3 h |
| **S8** | 改写工具 | `rewrite_query`（规则 + 可选 LLM） | 改写保留原意图（人工抽检 10 例） | 3 h |
| **S9** | 基准对比 | recall@10、步数分布、成本 | recall 不降；成本 +≤30% | 2 h |

### 7.3 3.2 analysis L2（≈2 天）

| 步 | 目标 | 产物 | 关键门禁 | 预估 |
|---|---|---|---|---|
| **S10** | 抽取/校验/重写工具 | `extract_claims`、`verify_claim`、`rewrite_claim` | 复用 grounding 判定 | 4 h |
| **S11** | 逐条修复循环 | analysis goal + 接线 | 只改坏 claim；仍坏则丢弃 | 4 h |
| **S12** | 一致性与基准 | 报告一致性、grounding、成本 | 不低于 2.2；+≤50% | 2 h |

### 7.4 3.3 Chat L3（≈4–5 天）

| 步 | 目标 | 产物 | 关键门禁 | 预估 |
|---|---|---|---|---|
| **S13** | 会话存储与 API | 迁移 0004、会话 CRUD、SSE | 迁移可回滚；API 契约测试 | 5 h |
| **S14** | L3 ReAct 循环 | `agents/chat.py`、工具白名单、引用规则 | 无引用不得作答；可中止 | 6 h |
| **S15** | 前端 Chat 页 | 输入、流式、工具轨迹、引用、中止 | e2e 首轮/追问/中止 | 5 h |
| **S16** | 多轮评测 | 10 个脚本化场景、pass@k、成本 | 场景全过；成本可控 | 4 h |

**3.3 出口 = 系统基本完成**：三页全通、Chat 可用、可评测。

### 7.5 3.4 治理与扩展（≈3 天）

| 步 | 目标 | 产物 | 关键门禁 | 预估 |
|---|---|---|---|---|
| **S17** | 权限门 | `permission=confirm` 工具需人工确认 | 未确认不执行；事件留痕 | 3 h |
| **S18** | 工具检索 | 工具描述向量/词面检索，top-k 注入 | 选择准确率 ≥ 80%（20 例） | 4 h |
| **S19** | 沙盒（可选） | 子进程 + 白名单 + 无网默认 | 越权命令被拒 | 4 h |
| **S20** | MCP 适配（可选） | `mcp_adapter` 最小闭环 | 外部工具可注册 | 4 h |

### 7.6 3.5 评测与收尾（≈3 天）

| 步 | 目标 | 产物 | 关键门禁 |
|---|---|---|---|
| **S21** | gold v2 + 冻结哈希 v2 | 50 claims / 30 queries / 10 脚本 | `--frozen-v2` PASS |
| **S22** | 轨迹指标 | steps/tool_calls/repair_rate/escalation_rate | 指标可查 |
| **S23** | 消融实验 | 三组对照 + 表格 | 有结论（均值/方差） |
| **S24** | 文档与答辩材料 | `RESULTS-P3.md`、图表、demo 脚本 | H1–H16 |

**总计 ≈ 13–15 个工作日（3 周）**；若时间紧，**最小路径 = 3.0 + 3.1 + 3.3 + S21/S22**（≈8 天）。

---

## 8. 不变量（评审逐条对照）

| # | 不变量 |
|---|---|
| I1 | 外层 NodeIO / 门禁 / 事件类型不变 |
| I2 | 开关关闭时，行为与 2.2 一致（差异测试） |
| I3 | 每个内层步都有 `node/step/action` 事件 |
| I4 | `max_steps`、`max_usd`、墙钟、总调用数四重硬顶 |
| I5 | postconditions 必须是已有门禁；不可机器判定的目标不得启用 L2 |
| I6 | 工具输出是数据，不是指令；不得执行其中的"要求" |
| I7 | 写/网络工具必须声明幂等性；写操作仍走 commit 两阶段 |
| I8 | 工具失败/超时/拒绝都返回结构化结果 |
| I9 | step 不计入 attempt；attempt 口径不变 |
| I10 | 内层崩溃 → 整节点重跑安全（幂等 + 预算重建） |
| I11 | 关闭节点开关可完全回退到 L0/L1 |
| I12 | LLM 调用计数与预算全局一致（DB 为准） |
| I13 | 评测必须 pass@k + 轨迹指标，不只看单次 |
| I14 | gold/bench 冻结哈希，改必升版本 + ADR |

---

## 9. 返工风险登记

| # | 风险 | 规避 |
|---|---|---|
| 1 | 内层循环破坏"阶段一次"契约 | I9：step/attempt 分离 + 契约测试 |
| 2 | 成本爆炸 | 升级策略（L1→L2）+ 四重上限 + 默认关 |
| 3 | 事件量爆炸 | 步事件只记摘要（≤20 步）；trace 不进 state |
| 4 | 不可复现 | 确定性测试台 + 固定温度 + pass@k |
| 5 | 工具注入 | provenance 包裹 + 不执行工具输出中的指令 |
| 6 | Chat 范围膨胀 | 3.3 只做"问答 + 工具 + 引用 + 中止" |
| 7 | 评测说不清 | 先定指标与对照，再实现 |
| 8 | 与 2.2 冲突 | 2.2 只做配置/观测，不动节点 |

---

## 10. 出口标准（分子阶段 + 总）

### 10.1 子阶段出口

| 子阶段 | 出口（摘要） |
|---|---|
| **3.0** | 开关关闭行为等价；6 路径单测；工具 spec；契约 I1–I14 |
| **3.1** | retrieval 健康 1 步/失败 ≤2 步；recall 不降；成本 +≤30% |
| **3.2** | 只改坏 claim；grounding 不降；报告一致；成本 +≤50% |
| **3.3** | Chat 三场景 e2e；有引用；可中止；多轮脚本全过 |
| **3.4** | 权限门生效；工具检索 ≥80%；沙盒可选 |
| **3.5** | gold v2；三组消融结论；文档齐 |

### 10.2 Phase 3 总出口 H1–H16

| # | 判据 | 命令 | 期望 |
|---|---|---|---|
| H1 | 双层运行时可用 | `pytest tests/runtime` | 6 路径绿 |
| H2 | 节点目标化 | `pytest tests/contracts` | 10 goal + 契约 |
| H3 | 工具协议 | `pytest tests/tools` | spec/幂等/超时/截断 |
| H4 | retrieval L2 | `verify_phase3 --retrieval` | recall 不降、成本 ≤+30% |
| H5 | analysis L2 | `verify_phase3 --analysis` | grounding 不降、+≤50% |
| H6 | 默认关闭等价 | `pytest tests/runtime -k disabled` | 事件差异 = 0 |
| H7 | 预算/步数/死循环 | `pytest tests/runtime -k limits` | 四重上限生效 |
| H8 | 事件完整 | `verify_phase3 --events` | 每步有 node/step/action |
| H9 | Chat 可用 | e2e | 首轮/追问/中止 |
| H10 | 引用约束 | `pytest -k chat_citation` | 无引用不作答 |
| H11 | 多轮评测 | `verify_phase3 --chat-eval` | 10 场景全过 |
| H12 | 权限/沙盒 | `verify_phase3 --governance` | 未确认不执行 |
| H13 | 工具检索 | `verify_phase3 --tool-selection` | ≥80% |
| H14 | 轨迹指标 | `verify_phase3 --trajectory` | 五项指标可查 |
| H15 | 消融 | `verify_phase3 --ablation` | 三组表格 + 结论 |
| H16 | 基线不回归 | `verify_phase2_1`、`verify_phase1`、`pytest` | 全绿 |

---

## 11. 评测设计（论文的"证据链"）

### 11.1 确定性测试台（先有它，才敢写循环）

```python
# tests/support/scripted.py
class ScriptedCompleter:
    """按脚本返回：第 1 次返回工具调用，第 2 次返回最终答案…"""
class FakeTool:
    """可注入成功/失败/超时/超大输出"""
```

用途：把"循环行为"变成**可单测的确定性逻辑**，不依赖真实模型。

### 11.2 指标

| 指标 | 定义 |
|---|---|
| `pass@1 / pass@3` | 同一场景重复 3 次，至少 1 次满足 postconditions 的比例 |
| `steps_used` | 每节点实际步数（分布，不只均值） |
| `repair_rate` | 需要重写的 claim 占比 |
| `escalation_rate` | L1 失败升级 L2 的比例（越低越省钱） |
| `cost_per_claim` | 总成本 / 有效 claim 数 |
| `citation_coverage` | 有引用 claim 占比（已有） |

### 11.3 消融实验（三组）

| 组 | 配置 | 目的 |
|---|---|---|
| A. workflow-only | 全 L0/L1（2.2 现状） | 基线 |
| B. L2 nodes | retrieval+analysis 开 L2 | 证明"微观循环"的收益/代价 |
| C. L3 chat | Chat 用 ReAct | 证明"开放式自治"适合问答、不适合报告 |

报告口径：**质量（grounding/recall）× 成本（$） × 时延（s） × 可解释性（步数/工具调用）**，均值 ± 方差，样本不足时只报效应量。

### 11.4 gold v2

- 50 条 claim（覆盖 5 个主题）、30 条检索查询、10 个多轮脚本；
- 冻结哈希 v2 写进 `verify_phase3 --frozen-v2`；
- 改动必须升版本 + ADR。

---

## 12. 自进化接口（P5 预览，不在本阶段实现）

3.x 的产物已足够支撑 Phase 5：
- `NodeGoal` = 可替换的"策略配置"；
- `ToolSpec` = 可组合的能力；
- 验证器 + gold = 候选的裁判；
- 消融脚本 = 候选的 A/B 平台。

P5 只做"参数/配置层自优化"，**不自动生成节点**；生成节点的前提是 3.5 的评测足够稳。

---

## 13. AI 实施建议（按子阶段）

### 3.0
1. **先写测试台**（ScriptedCompleter/FakeTool），再写 MicroAgent；
2. 先实现"直接成功"路径，再依次加 retry/replan/budget/max_steps/no-progress；
3. runner 接线**先默认关**，跑一次全量对比事件差异（应为 0）；
4. 坑：不要在内层用真实 LLM 做单测；不要把 trace 放进 state。

### 3.1
1. 先实现"L1 一次 + 失败升级"的薄路径，确认健康 run 事件不变；
2. `rewrite_query` 先用规则（去停用词/加同义词），LLM 版本作为可选；
3. 坑：改写后丢掉原 query 的约束 → 必须把原 query 作为不可变上下文。

### 3.2
1. 先做 `verify_claim`（复用 grounding），再做 `rewrite_claim`；
2. 修复循环要"逐条"，不要整篇重写；
3. 坑：重写引入新引用/重复 claim → 用 `text_sha` 去重 + 引用白名单校验。

### 3.3
1. 先做会话存储与 API（可空跑），再做 L3 循环，最后前端；
2. Chat 的工具白名单**默认只读**；写工具需权限门（3.4）；
3. 坑：上下文无限增长 → 每轮摘要 + 只保留最近引用。

### 3.4
1. 权限门先做（最容易出事）；
2. 工具检索先用词面/向量混合，别上复杂 rerank；
3. 沙盒/MCP 可选，时间不够就登记 backlog。

### 3.5
1. 先扩 gold，再跑消融（顺序反了会返工）；
2. 每组跑 3 次，记均值/方差；
3. 坑：只挑成功案例 → 必须报告失败率。

---

## 14. 经验教训适配（2.x → 3.x）

| # | 教训 | 约束 |
|---|---|---|
| 1 | 探针绿但生产没用 | 所有 L2 验收走"事件/指标"行为证据 |
| 2 | 守卫误报 | 内层 stop 条件必须有"不触发"测试 |
| 3 | 指标口径反复 | 轨迹指标定义先冻结 |
| 4 | 双路径漂移 | 内层开关默认关 + 差异测试 |
| 5 | 幂等/去重坑 | 工具 `idempotency` 声明 + 写工具键 |
| 6 | 契约冻结 | NodeGoal/ToolSpec 先冻结再实现 |
| 7 | 成本失控 | L1→L2 升级 + 四重上限 |
| 8 | 不可复现 | 确定性测试台 + pass@k |

---

## 15. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| **1.0.0** | 2026-10-23 | 首版：双层架构、NodeGoal/MicroAgent/ToolSpec、L0–L3 与升级策略、3.0–3.5 六子阶段（S1–S24）、I1–I14、H1–H16、评测与消融设计、AI 实施建议 |

---

## 附录 A · 命令速查

```powershell
. .\scripts\env.ps1
uv run pytest -q
uv run python scripts/verify_phase3.py --all
uv run python scripts/verify_phase3.py --retrieval --analysis --events
uv run python scripts/verify_phase3.py --ablation --trajectory
uv run python scripts/verify_phase2_1.py --all
cd web; npm run typecheck; npm run build; npm run test:e2e
```

## 附录 B · NodeGoal 示例

```python
RETRIEVAL_GOAL = NodeGoal(
    name="retrieval",
    objective="找到 ≥N 篇与 scope 相关、可引用的证据",
    postcondition="evidence_sufficiency",
    tools=("hybrid_search", "rewrite_query"),
    max_steps=2,
    max_usd=0.02,
    autonomy="L1",
    escalation="on_gate_failure",
)

ANALYSIS_GOAL = NodeGoal(
    name="analysis",
    objective="抽出可引用结论，且每条 claim 都有引用、支持率达标",
    postconditions=("citation_integrity", "support_ratio"),
    tools=("extract_claims", "verify_claim", "rewrite_claim"),
    max_steps=3,
    max_usd=0.05,
    autonomy="L1",
    escalation="on_gate_failure",
)
```

## 附录 C · 工具目录（3.x）

| 工具 | 副作用 | 幂等 | 用途 |
|---|---|---|---|
| `hybrid_search` | read | pure | 混合检索 |
| `rewrite_query` | read | pure | 改写查询 |
| `extract_claims` | read | pure | 抽取 claims |
| `verify_claim` | read | pure | 引用/支持判定 |
| `rewrite_claim` | read | pure | 重写单条 claim |
| `compress_context` | read | pure | 上下文压缩 |
| `cluster_papers` | read | pure | 论文簇 |
| `paper_pdf` | network | keyed | PDF 解析 |
| `sectionize` | read | pure | 报告分节（3.2 选做） |
| `search_tools` | read | pure | 工具检索（3.4） |

## 附录 D · 与相邻阶段边界

| 阶段 | 本阶段做 | 不做 |
|---|---|---|
| 2.2 | 配置/限额/漂移/观测/前端 e2e | 任何节点重构 |
| 3.0–3.2 | 运行时 + retrieval/analysis L2 | Chat |
| 3.3 | Chat L3 + 会话 | 多 agent 协作 |
| 3.4 | 权限/沙盒/工具检索/MCP | 自进化 |
| 3.5 | 评测与消融 | 新功能 |
| P4 | 并行、MCP 完整、PDF 下载 | 评测重写 |
| P5 | 契约内自优化 | 自动生成节点 |
