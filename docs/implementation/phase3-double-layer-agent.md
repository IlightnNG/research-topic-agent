# Phase 3 —— 双层 Agent：可控 Workflow + 微观 ReAct

> **文档性质**：**规范性文件（冻结契约）**。Phase 3 的"做什么 / 什么算做完 / 按什么顺序"以本文件为唯一判据。
> **版本**：**1.5.0**（2026-10-26，3.0 + 3.1 + 3.2 已落地）
> **前序**：`phase2.2-closeout-and-observability.md`、`phase2.1-wiring-and-contracts.md` v2.0.0、ADR-0006（事件）、ADR-0007（NodeIO/配置）。
> **入口基线**：`verify_phase2_1 13/13`、`pytest 439+`、`e2e 8+`、`verify_phase1 13/13`、`vue-tsc 0 error`。
> **重要度**：**本阶段是项目从"可演示的系统"变成"有研究贡献的系统"的分水岭**，预计投入 2.5–3 周；允许拆成 3.0 → 3.5 六个子阶段独立验收。
> **外部参考**：DeepSeek Harness（DSH）的 turn/step 内核、工具四段流水线、会话日志真源、pre-step 压缩与 subagent seam。**只借机制，不搬框架**（见 §3.5–§3.9 与附录 E）。

---

## 0. 目标、规则与"完成"定义

### 0.1 一句话目标

在**不破坏外层可观测/可续跑/可评测**的前提下，给节点装上**通用的微观运行时（plan + ReAct + 自检）**，让 LLM 在"有目标、有工具、有预算、有验收"的边界内自由发挥；并用**对照实验**证明"双层结构"比"纯 workflow"和"纯 ReAct"都好。

### 0.2 三层结构（本阶段的核心思想）

```
┌─ 编排层（壳）──────────────────────────────────────────────
│  Goal 列表 + 顺序 + postconditions + 预算/checkpoint 放置
│  每个节点 = NodeGoal（配置），不是"一段写死的实现"
└──────────────┬────────────────────────────────────────────
               │ NodeGoal(objective, postconditions, tools, max_steps)
┌──────────────▼────────────────────────────────────────────
│  控制层：MicroAgent（通用兼用卡）
│  before_request → request → act(工具) → after_action(门禁) → replan/stop
│  每步可观测、可预算、可终止；L1 失败才升级到 L2（省成本）
└──────────────┬────────────────────────────────────────────
               │ ToolSpec + 结构化结果
┌──────────────▼────────────────────────────────────────────
│  能力层：工具库（rewrite/retrieve/verify/rewrite_claim/compress…）
│  治理层：预算 · 调用数 · 熔断 · 权限 · 沙盒 · 注入防护
└───────────────────────────────────────────────────────────
横切（不在调用栈里）：**记录层 = 仅追加日志（唯一真源）**，事件分"持久/实时"两域。
内部状态（LoopState）可从日志重建；内存丢了，事实不丢。
```

### 0.3 四条硬规则

| 规则 | 内容 |
|---|---|
| **R1 外层契约不变** | NodeIO、6 类门禁、事件类型（不新增）、checkpoint 语义不动 |
| **R2 逐节点启用** | 内层循环只对 allowlist 节点开启；**默认关闭**，关掉后行为与 2.2 完全一致 |
| **R3 有界自治** | 每节点 `max_steps`、`max_usd`、墙钟上限；总 LLM 调用数硬顶 |
| **R4 可评测** | 任何"更聪明"必须能用 gold/基准/轨迹指标证明，禁止"我觉得更好" |

### 0.4 反向定义

> **Phase 3 结束 ⇔ §10 的 H1–H22 全绿，且 3.5 的消融实验有结论（不是"跑通了"）。**
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

> 命名约定：本节 `§3.x` 是**架构组件**（壳/NodeGoal/微运行时/工具/记录/取消/上下文/治理/断点）；子阶段编号是 `3.0–3.5`（见 §7），两者不是一回事。

### 3.0 壳（Shell）：定义、边界与可生成规范

**一句话**：壳是**任务相关的编排声明**（Goal 列表、顺序、postconditions、自主性、限额、预设），
**不含业务实现、不做 IO、不调 LLM**；内核负责执行，工具负责干活。

#### 3.0.1 四层归属（冻结）

| 层 | 负责 | 归属判断 | 例子 |
|---|---|---|---|
| **内核** | 循环、工具调度、门禁执行、取消、预算计数、日志、提交 | 换任务**不改** | `before_request → request → tools → after_action` |
| **壳** | 有哪几个 Goal、什么顺序、每 Goal 的验收/自主性/限额 | 换任务**要改**，且是**声明** | 周报 10 个 Goal；Chat 1 个 Goal |
| **能力** | 具体动作 | 换任务**可复用** | `hybrid_search`、`verify_claim`、`render_report` |
| **治理** | 预算/权限/沙盒的**数值**（执行在内核） | 按部署/任务配置 | `max_usd=2.0`、`permission=confirm` |

**三个判断测试**（评审时直接用）：

1. **换任务要不要改？** 要 → 壳；不改 → 内核。
2. **删掉它还能跑吗？** 能跑、只是能力少 → 壳；跑不起来 → 内核。
3. **它是声明还是机制？** 声明（JSON/Goal 列表）→ 壳；机制（循环/门禁执行/提交）→ 内核。

#### 3.0.2 壳的六条硬规则（S1–S6）

| # | 规则 | 违反后果 |
|---|---|---|
| **S1** | 壳里**没有业务实现**（不写抽取/排序/渲染算法） | 壳变厚，换任务要改代码 |
| **S2** | 壳里**没有 IO/DB/LLM 调用**（纯声明 + 纯函数校验） | 不可测、不可生成、不可复现 |
| **S3** | 壳**可序列化**且**哈希稳定**（同 spec 同 hash） | 无法冻结、无法 A/B、无法审计 |
| **S4** | 壳**可整层删除**（内核仍能跑单 Goal） | "薄壳"是假的，删不掉 |
| **S5** | 每 Goal 的 `postconditions ⊆ GATE_NAMES`，**≤ 2 条** | 门禁爆炸、误报率上升 |
| **S6** | 只能引用**已注册**的 tools/gates；新能力走工具层 | 壳偷偷变成实现层 |

#### 3.0.3 `ShellSpec`（可生成、可冻结）

```json
{
  "name": "weekly-report",
  "version": "1.0.0",
  "hash": "sha256:...",
  "kernel_min": "3.0.0",
  "executor": "graph",
  "budget": { "usd": 2.0, "llm_calls": 12, "wall_s": 900 },
  "goals": [
    {
      "id": "retrieval",
      "objective": "找到 >=N 篇与 scope 相关、可引用的证据",
      "postconditions": ["evidence_sufficiency"],
      "tools": ["hybrid_search", "rewrite_query"],
      "autonomy": "L1",
      "max_steps": 2,
      "max_usd": 0.02,
      "escalation": "on_gate_failure"
    },
    {
      "id": "analysis",
      "objective": "抽取可引用结论，且每条 claim 有引用、支持率达标",
      "postconditions": ["citation_integrity", "support_ratio"],
      "tools": ["extract_claims", "verify_claim", "rewrite_claim"],
      "autonomy": "L1",
      "max_steps": 3,
      "max_usd": 0.05,
      "escalation": "on_gate_failure"
    }
  ],
  "notes": "周报预设：固定交付物、强引用约束"
}
```

**加载接口**（壳只是数据，内核负责解释）：

```python
class Shell(Protocol):
    spec: ShellSpec
    def goals(self) -> list[NodeGoal]: ...      # 纯转换，不做 IO
```

**校验规则**：`goals[].id` 唯一；`postconditions` 非空且合法；`tools` 全部已注册；
`autonomy ∈ {L0, L1, L2}`（L3 只允许出现在 Chat 预设）；`hash` 由规范化 JSON 计算。

#### 3.0.4 壳的"厚度"指标（可测）

| 指标 | 公式 | 目标 |
|---|---|---|
| `shell_overhead_ratio` | `(总墙钟 − ΣLLM − Σ工具) / 总墙钟` | **< 5%** |
| `shell_goals` | `len(goals)` | ≤ 10（超过先合并） |
| `shell_postconditions_max` | `max(len(g.postconditions))` | ≤ 2 |
| `shell_llm_calls_per_goal` | `Σ llm_calls / len(goals)` | ≤ 1（L1）/ ≤ 3（L2） |
| `shell_loc` | 壳代码行数（不含工具/内核） | ≤ 500 |
| `gate_false_positive_rate` | 健康 run 中被门禁拦下的次数 / 健康 run 数 | **< 2%** |

这些指标写入 `metrics` 与 `verify_phase3 --shell`，作为"厚/薄"的客观依据。

#### 3.0.5 壳的测试矩阵（S27 创建，后续实现按此建文件）

| ID | 测试 | 文件 | 断言 |
|---|---|---|---|
| SH1 | spec 契约 | `tests/shell/test_shell_spec.py` | 往返一致；hash 稳定；非法 goal/gate 拒绝 |
| SH2 | 纯度 | `tests/shell/test_shell_purity.py` | 静态扫描 + 运行时断言：壳内无 IO/DB/LLM |
| SH3 | 可删 | `tests/shell/test_shell_deletable.py` | 去掉壳，内核仍能跑单 Goal（Chat） |
| SH4 | 等价 | `tests/shell/test_shell_parity.py` | Graph 与 GoalRunner 跑同一壳，结果一致 |
| SH5 | 厚度 | `tests/shell/test_shell_thickness.py` | 六项厚度指标达标 |
| SH6 | 消融 | `tests/shell/test_shell_ablation.py` | 开/关壳的质量、成本、时延对比可复现 |
| SH7 | 生成准入 | `tests/shell/test_generated_shell.py` | 候选壳必须过 SH1–SH5 才能进影子运行 |

#### 3.0.6 壳的优化与生成闭环

```text
基线（当前 ShellSpec）
  → 提议（改 Goal 子集/顺序/autonomy/max_steps/预算；不得加新工具或新门禁）
  → 验证（SH1–SH5 + gold 不降 + 成本 ≤ 上限 + 门禁误报 < 2%）
  → 影子（固定语料 N 次，不写生产）
  → 转正（升 version + 记录 ADR + 更新 hash）
```

**允许优化的参数**：Goal 子集与顺序、`autonomy`、`max_steps`、`max_usd`、预算数值、门禁组合（从允许集合里选）。
**不允许**：新增工具/门禁/内核代码；放宽阈值；改 gold；把业务逻辑塞进壳。

**红线**（写进验证器）：候选壳若 `gate_false_positive_rate ≥ 2%` 或 `shell_overhead_ratio ≥ 5%`，直接淘汰。

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
class MicroAgent:                  # 无状态；可变状态全在 LoopState
    def run(self, goal, ctx, state) -> NodeOutput:
        loop = LoopState.new(goal, ctx)            # step / trace / attempt 全在这
        plan = self.plan(goal, state)              # 显式计划（≤ max_steps 项）
        for step in range(goal.max_steps):
            self.check_budget(goal, ctx, loop)     # 预算 / 调用数 / 墙钟

            request = self.before_request(goal, ctx, loop)       # ① pre-step 相位
            reply = self.request(ctx, request)                   # ② 一次模型调用
            actions = self.parse_actions(reply)                  # ③ 只解析，不执行
            for action in actions:
                result = self.act(action, ctx)                   # ④ 工具四段流水线
                self.after_tool(goal, ctx, loop, action, result) # ⑤ post 策略
                loop.trace.append(step_record(action, result))

            verdict = self.after_action(goal, ctx, loop, state)  # ⑥ 门禁 = postcondition
            if verdict.ok:
                break
            plan = self.replan(plan, loop, verdict)  # ⑦ 失败 → 改计划
        return self.finalize(goal, loop, state)
```

**相位表（冻结）**

| 相位 | 做什么 | 对应 DSH |
|---|---|---|
| `before_request` | 剪枝/压缩上下文、注入计划状态、接纳 steering；**只读+确定性** | `agent/pre-step` |
| `request` | 一次模型调用（请求不可变、冻结） | step 的 request |
| `act` / `after_tool` | 工具四段流水线 + post 策略 | `tools/*` |
| `after_action` | 跑 `postconditions` 门禁，决定继续/重试/收尾 | gate / guard |
| `replan` | 改计划（不重新 pre-step） | turn 内下一 step |

> **pre-step ≠ ReAct**：pre-step 是"请求前对上下文/输入的确定性处理"，ReAct 是"模型决定下一步动作"的循环。
> 两者在同一个 step 内共存：pre-step 管"带什么进去"，ReAct 管"出来做什么"。

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
    description: str                     # 供"工具检索"使用
    parameters: dict[str, Any]           # JSON Schema 子集
    output_schema: dict[str, Any]        # 必填：结果必须可校验
    side_effect: Literal["read", "network", "write"] = "read"
    idempotency: Literal["pure", "keyed", "none"] = "pure"
    timeout_s: float = 30.0
    permission: Literal["none", "confirm"] = "none"
    concurrency: Literal["exclusive", "parallel"] = "exclusive"  # fail-closed
    max_output_chars: int = 4000
```

**四段流水线（冻结，借鉴 DSH）**

```text
tools/pre_execute   allow / deny / ask（权限、脱敏、审计）
  → guard           单调否决：只能 deny，不能 force-allow
  → tools/execute   超时/重试包装；signal 贯穿到工具实现
  → tools/post_execute  accept / replace / block（结果校验与修正）
  → tools/result    冻结快照（事件/回放只读这份）
```

规则：
- 结果必须结构化（`ToolResult`），失败不抛穿；
- 参数进入流水线后**不可改写**（历史、审计、执行必须一致）；
- 并发按 `concurrency` 分类：`exclusive` 形成屏障，`parallel` 进有界滚动池，结果按模型顺序提交；
- 取消：未启动的调用跳过并标记 `ABORTED_BEFORE_DISPATCH`；已启动的 drain 后返回结构化结果；
- 输出超限**截断并标注**（不静默丢）；
- 工具输出是**数据**，进入 prompt 时必须包裹 provenance 并声明"不得当作指令"（防注入）；
- 写/网络工具必须声明幂等性与权限；未声明不得进入 Chat 工具集。

### 3.5 记录层：日志唯一真源与双域事件

三条原则（借鉴 DSH 的 session log）：

1. **模型可见即已记录**：进入 prompt 的上下文、工具结果、计划状态，都必须能从 run log 重建；
2. **日志只追加**：报告、指标、评测都从日志派生；禁止"内存里算完就丢"；
3. **双域事件**：持久事件（`phase_change`/`tool_call`/`report_written`/`error`）用于回放与审计；实时事件（SSE 投影）只服务 UI，不落库。

约束：

- **不新增 EventType**（ADR-0006），只加 payload 字段：`node`/`step`/`action`/`attempt`/`phase`；
- `LoopState`（step 计数、trace、plan）是**可重建的缓存**，不是真源；
- 崩溃恢复后，最多重跑当前节点；已提交事实（报告/claims/metrics）不丢。

**判据**：只给日志，不看代码，能回答"为什么这一步重试/降级/花了多少钱"；删除内存状态后 replay 得到同一 `content_sha`。

### 3.6 取消、冻结与提交边界

四个相位各自定义取消语义（借鉴 DSH 的"取消不提交"）：

| 取消发生在 | 期望行为 | 不得发生 |
|---|---|---|
| `before_request` | 丢弃本次请求，不写任何消息 | 写入半截上下文 |
| `request`（流式） | 不提交 assistant message；记录 `assistant/attempt` 等价事件 | 把半截输出当结论 |
| `after_action`（工具） | 未启动→`ABORTED_BEFORE_DISPATCH`；已启动→drain 后结构化返回 | 留下无结果的 tool_call |
| `commit` | 幂等提交已完成；取消不再回滚已提交事实 | 重复写/部分写 |

规则：

- 请求对象**不可变**（消息、参数、工具 schema 一次冻结）；
- 工具实现必须持有并转发 `signal`；未声明 signal 的工具**不得**进入 L2；
- 写操作仍走两阶段提交（2.1 已有），取消发生在 commit 前 = 零写入。

**判据**：四相位取消矩阵测试全绿；每个相位取消后 DB 无部分写入，事件流能解释原因。

### 3.7 上下文：before_request 的"先剪枝、后摘要"

借鉴 DSH 的 compaction 位置与顺序（`agent/pre-step`，先 prune 再 summarize）：

```text
before_request:
  1) prune 过期/超大工具输出（便宜、无损可回放）
  2) 重新测量 token
  3) 仍超预算 → 摘要（贵、有损，事件记录摘要与遮蔽范围）
  4) 注入 plan 状态 / steering（最后做，保证最新）
```

规则：

- **只在 `before_request` 做一次**，不允许 analysis/retrieval 各自写一套压缩；
- 引用片段（`Citation.snippet`）**不得**被压缩截断（2.1 规则）；
- 摘要/剪枝必须发事件（遮蔽了哪些 seq、省了多少 token），可回放；
- 阈值来自 `pipeline.limits`，可配置。

**判据**：长 run（≥50 篇）token 峰值降 ≥40%，引用完整率不降；压缩次数与耗时进指标。

### 3.8 治理（Governance）

| 维度 | 机制 |
|---|---|
| 预算 | 节点 `max_usd` + run 预算 + 金额门禁 |
| 调用数 | `max_total_llm_calls`（2.2 已落地）+ 节点 `max_steps` |
| 时间 | 节点墙钟上限（默认 120s）；超时 → `E_SRC_TIMEOUT` |
| 熔断 | 复用 2.x 三态熔断器 |
| 权限 | `permission=confirm` 的工具在 Chat 中需人工确认（3.4） |
| 沙盒 | 代码执行类工具在子进程 + 白名单（3.4，P4） |
| 注入 | 工具输出标注来源；计划 prompt 不解释工具输出中的"指令" |

### 3.9 断点、恢复与执行器可替换

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

#### 执行器可替换（GraphExecutor vs GoalRunner）

壳要能"删得掉"，前提是**执行器可替换**：

```python
class Executor(Protocol):
    def run(self, goals: list[NodeGoal], ctx: RunContext) -> RunResult: ...
```

- `GraphExecutor`：沿用 Phase 2 的十节点图（3.0–3.2 用它跑）；
- `GoalRunner`：按 Goal 列表顺序执行，不依赖图拓扑（3.5 引入）；
- **等价测试**：同一份 Goal 列表，两种执行器必须产出**相同的阶段顺序、门禁结果、指标**（只允许时间戳/耗时不同）；连续 3 轮 × 10 场景通过后，才允许把 Graph 降级为 legacy adapter。

## 4. 模块与验收判据（M1–M9）

> **3.0 状态（2026-10-26）**：S1–S6 完成；`pytest 505 例`、`verify_phase3 --foundations 4/4`。
> 3.0 只落"可测的骨架"，不改变任何节点行为（`micro_enabled=false`）。

> **能力三件套**（借 DSH 的 seam 写法）：每个新能力先写清 **定义（接口）/ 实现（provider）/ 消费者（工具或节点）**，再写代码。新增能力放哪层见附录 G。

### M1 MicroAgent 运行时

| 项 | 内容 |
|---|---|
| **目标** | 一份通用循环，供所有 L2 节点复用；可测、可预算、可终止 |
| **增量** | `runtime/micro_agent.py`（plan/decide/act/observe/evaluate/replan）、`contracts/goals.py`、`tests/runtime/test_micro_agent.py` |
| **完成判据** | ① 6 条路径单测：直接成功、重试成功、replan 成功、预算中止、步数中止、无进展中止；② **相位分离可测**：`before_request` 只做上下文、`after_action` 只跑门禁（互不写对方状态）；③ 每步发事件且字段完整；④ 关闭开关后行为与 2.2 一致（差异测试） |
| **重难点** | **确定性测试**：真实 LLM 不可测；必须提供 `ScriptedCompleter` + `FakeTool`，把"决策序列"写成脚本 |
| **禁止** | 在 MicroAgent 里写业务逻辑（业务在工具里）；把 trace 全量塞进 state |
| **OOS** | 并行工具调用（P4） |
| **依赖** | 2.2 配置体系 |

### M2 NodeGoal / ShellSpec 与节点注册

| 项 | 内容 |
|---|---|
| **目标** | 十节点都有 `NodeGoal`（即使 L0/L1），L2 节点可在配置里开/关 |
| **增量** | `contracts/goals.py` 定义 10 个 goal；`contracts/shell.py` 定义 `ShellSpec`（可序列化/哈希）；契约测试扩展 |
| **完成判据** | ① 10 个 goal 齐全；② `postconditions ⊆ GATE_NAMES` 且非空、每 Goal ≤2；③ `tools ⊆ 工具注册表`；④ 每节点有 `autonomy` 与开关；⑤ **`ShellSpec` 可序列化、hash 稳定、可整层删除**；⑥ `pytest tests/contracts tests/shell` 全绿 |
| **重难点** | goal 必须可序列化（配置/审计）；不能塞 callable |
| **禁止** | 在 goal 里写 prompt 全文（prompt 属于实现，版本化在代码里） |
| **依赖** | M1 |

### M3 工具协议 v2 + 能力库

| 项 | 内容 |
|---|---|
| **目标** | 工具可声明、可校验、可检索；能力覆盖"改写/检索/抽取/校验/重写/压缩" |
| **增量** | `tools/spec.py`、`ToolRegistry` 支持 spec；新工具：`rewrite_query`、`hybrid_search`（已有）、`extract_claims`、`verify_claim`、`rewrite_claim`、`compress_context`、`cluster_papers`；`tests/tools` 扩展 |
| **完成判据** | ① 每个工具有 spec 且通过 schema 校验（含 `output_schema`/`concurrency`）；② 四段流水线可测：deny/ask/guard 否决/post 替换各有用例；③ 超时/异常/超大输出/取消都有结构化结果；④ 同一输入两次调用结果一致（`pure`）；⑤ 工具目录可被"检索"（3.4 用） |
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


### M9 记录层与执行器（Log & Executor）

| 项 | 内容 |
|---|---|
| **目标** | 日志是唯一真源；执行器可替换（图 → GoalRunner）且行为等价 |
| **增量** | `runtime/log.py`（append-only + 派生视图）、`runtime/executor.py`（`Executor` 协议 + `GoalRunner`）、replay/等价测试 |
| **完成判据** | ① 仅凭日志能回答一次 run 的"重试/降级/成本"三问；② 删除内存状态后 replay 得到同一 `content_sha`；③ 同一 Goal 列表在两种执行器下：阶段顺序、门禁结果、指标一致（3 轮 × 10 场景）；④ 取消矩阵 4 相位零部分写入 |
| **重难点** | 日志与 DB 的双写一致性：先写日志再提交，还是先提交再写日志？（选"先日志后提交 + 幂等"） |
| **禁止** | 在内存里维护"日志之外的事实"；为等价测试放宽断言 |
| **依赖** | M1–M3 |

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

## 7. 子阶段与步骤（S1–S26）

### 7.1 3.0 Foundations（≈2 天）

| 步 | 目标 | 产物 | 关键门禁 | 回滚 | 预估 |
|---|---|---|---|---|---|
| **S1** ✅ | NodeGoal 契约 + 10 goal 注册 | `contracts/goals.py`、`contracts/shell.py`（提前落地）、契约测试 | 10/10；postconditions 合法且 ≤2；`ShellSpec` 可哈希 | 开关关闭 | 3 h |
| **S2** ✅ | MicroAgent 核心（相位化） | `runtime/micro_agent.py`（7 相位 + `LoopState` 外置） | 6 路径 + 相位分离 + 状态隔离测试全绿（8 例） | `micro.enabled=false` | 5 h |
| **S3** ✅ | 工具协议 v2 | `tools/spec.py`（pre/guard/execute/post）、3 个新工具（rewrite/verify/compress） | 10 例：deny/guard/post/超时/截断/校验/预算/事件 | 旧 `tools.registry` 不动 | 5 h |
| **S4** ✅ | runner 接线（默认关） | `ctx.shell` + `pipeline.micro_enabled`；per-node autonomy 执行留给 3.1 | 关闭时仍十阶段、无 tool_call、指标不变（3 例） | 同上 | 3 h |
| **S5** ✅ | 确定性测试台 | 测试内 `Scripted` completer + `FakeTool`（不新增 support 包，记偏差 3.0-c） | 无网络、无睡眠、可重复 | 删除 | 2 h |
| **S6** ✅ | 契约、验证器与不变量测试 | `tests/contracts/test_goals_and_shell.py`、`scripts/verify_phase3.py`（H1/H2/H3/H6） | `--foundations` **4/4 PASS** | —— | 3 h |

**3.0 出口**：开/关前后行为等价；MicroAgent 6 路径可测；工具 spec 全覆盖；`verify_phase3 --foundations` PASS。

### 7.2 3.1 retrieval L2（≈1.5 天）

| 步 | 目标 | 产物 | 关键门禁 | 预估 |
|---|---|---|---|---|
| **S7** ✅ | retrieval goal + L2 接线 | `_retrieval_l2`（rewrite → hybrid → postcondition），`retrieval_l2` 开关默认关 | 健康 run 2 步；默认 L1 事件不变（5 例） | 3 h |
| **S8** ✅ | 改写工具 | `rewrite_query`（规则版，确定性；LLM 版留配置位）+ `hybrid_search` 工具封装 | 停用词/同义词生效；A/B 卡片一致 | 3 h |
| **S9** ✅ | 基准对比 | `scripts/ab_retrieval.py`（L1 vs L2，同数据同 hint） | 卡片数一致；检索耗时 +1ms；成本 0 | 2 h |

### 7.3 3.2 analysis L2（≈2 天）

| 步 | 目标 | 产物 | 关键门禁 | 预估 |
|---|---|---|---|---|
| **S10** ✅ | 抽取/校验/重写工具 | `extract_claims`、`verify_claim`、`rewrite_claim` + `tool_runtime_for` 白名单 | 复用 grounding；坏 claim 可被改写/丢弃 | 4 h |
| **S11** ✅ | 逐条修复循环 | `_analysis_l2`（verify → rewrite → 仍坏丢弃），`analysis_l2` 开关默认关 | 只改坏 claim；5 例全绿 | 4 h |
| **S12** ✅ | 一致性与基准 | `scripts/ab_analysis.py`（L1/L2 × 正常/坏产物） | L2 把 unsupported 从 1 降到 0；成本 0 | 2 h |

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

### 7.6 3.5 评测、壳规范、执行器等价与收尾（≈5 天）

| 步 | 目标 | 产物 | 关键门禁 |
|---|---|---|---|
| **S21** | gold v2 + 冻结哈希 v2 | 50 claims / 30 queries / 10 脚本 | `--frozen-v2` PASS |
| **S22** | 轨迹指标 | steps/tool_calls/repair_rate/escalation_rate | 指标可查 |
| **S23** | 消融实验 | 三组对照 + 表格 | 有结论（均值/方差） |
| **S24** | 文档与答辩材料 | `RESULTS-P3.md`、图表、demo 脚本 | H1–H22 |
| **S25** | **执行器等价** | `GoalRunner` + 等价测试（同一 Goal 列表、两种执行器） | 阶段顺序/门禁/指标一致（3 轮 × 10 场景） |
| **S26** | **日志真源审计** | replay 脚本：仅凭日志回答重试/降级/成本 | 三问可答；删除内存后 `content_sha` 一致 |
| **S27** | **壳规范与厚度** | `ShellSpec` + `tests/shell` + `verify_phase3 --shell` | SH1–SH5 全绿；六项厚度达标 |
| **S28** | **壳消融与生成准入** | 开/关壳对照 + 候选壳准入（SH7） | 质量/成本/时延表；候选壳不得越过红线 |

**总计 ≈ 16–18 个工作日（3.5 周）**；若时间紧，**最小路径 = 3.0 + 3.1 + 3.3 + S21/S22**（≈9 天）。

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
| I15 | **日志是唯一真源**：模型可见的上下文/工具结果/计划都必须可从日志重建 |
| I16 | 取消发生在 commit 前 → 零写入；四相位取消语义各有测试 |
| I17 | guard 单调：只能否决，不能把已拒绝的调用放行 |
| I18 | 工具并发 fail-closed：只有显式 `parallel` 才并行，其余独占 |
| I19 | `before_request` 只做上下文（不调工具、不写业务表），且必须发事件 |
| I20 | 执行器等价：同一 Goal 列表，Graph 与 GoalRunner 的阶段/门禁/指标一致 |
| I21 | 壳内无业务实现：抽取/排序/渲染/校验算法都在工具，不在壳 |
| I22 | 壳内无 IO/DB/LLM；壳可序列化且哈希稳定 |
| I23 | 壳可整层删除：移除壳后内核仍能跑单 Goal（Chat 预设） |

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
| 9 | `before_request` 与门禁混淆 | 明确"入口/出口"分工：前者不调工具，后者不碰上下文；测试分开 |
| 10 | 日志不是唯一真源 | I15 + replay 测试；禁止内存里维护第二份事实 |
| 11 | 执行器迁移半途而废 | 双执行器并存 + 等价测试兜底，最后才删 Graph |

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

### 10.2 Phase 3 总出口 H1–H22

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
| H17 | 日志真源 | `verify_phase3 --replay` | 仅凭日志可答三问；replay sha 一致 |
| H18 | before_request 生效 | `pytest -q -k before_request` | 压缩/注入可观测，且不写业务表 |
| H19 | 取消矩阵 | `pytest -q -k cancel` | 4 相位零部分写入 |
| H20 | 执行器等价 | `verify_phase3 --executor-parity` | 3 轮 × 10 场景一致 |
| H21 | 壳可删/可替换 | `pytest -q tests/shell -k deletable` | 去掉壳仍能跑单 Goal |
| H22 | 壳厚度达标 | `verify_phase3 --shell` | 六项指标全部达标 |

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
| `before_request_interventions` | 剪枝/摘要/注入次数与省下的 token（衡量上下文治理） |
| `cancelled_before_commit` | 在 commit 前取消、且零写入的次数（安全阀） |
| `executor_parity` | 两种执行器在同一 Goal 列表下的差异项数（应为 0） |
| `shell_overhead_ratio` | 壳固定开销占比（目标 <5%） |
| `shell_goals` / `shell_postconditions_max` | 壳的规模（目标 ≤10 / ≤2） |
| `gate_false_positive_rate` | 健康 run 门禁误报率（目标 <2%） |

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

### 子阶段 3.0
1. **先冻结日志字段与相位**（`before_request`/`after_action`/`step`/`action`），再写代码——字段后补会牵动所有测试；
2. **先落 `ShellSpec`（纯数据）与 SH1/SH2 测试**，再写运行时——壳先可测，才谈得上生成与优化；
3. **先写测试台**（ScriptedCompleter/FakeTool），再写 MicroAgent；
4. 先实现"直接成功"路径，再依次加 retry/replan/budget/max_steps/no-progress；
5. runner 接线**先默认关**，跑一次全量对比事件差异（应为 0）；
6. 坑：不要在内层用真实 LLM 做单测；不要把 trace 放进 state。

### 子阶段 3.1
1. 先实现"L1 一次 + 失败升级"的薄路径，确认健康 run 事件不变；
2. `rewrite_query` 先用规则（去停用词/加同义词），LLM 版本作为可选；
3. 坑：改写后丢掉原 query 的约束 → 必须把原 query 作为不可变上下文。

### 子阶段 3.2
1. 先做 `verify_claim`（复用 grounding），再做 `rewrite_claim`；
2. 修复循环要"逐条"，不要整篇重写；
3. 坑：重写引入新引用/重复 claim → 用 `text_sha` 去重 + 引用白名单校验。

### 子阶段 3.3
1. 先做会话存储与 API（可空跑），再做 L3 循环，最后前端；
2. Chat 的工具白名单**默认只读**；写工具需权限门（3.4）；
3. 坑：上下文无限增长 → 每轮摘要 + 只保留最近引用。

### 子阶段 3.4
1. 权限门先做（最容易出事）；
2. 工具检索先用词面/向量混合，别上复杂 rerank；
3. 沙盒/MCP 可选，时间不够就登记 backlog。

### 子阶段 3.5
0. **先写执行器等价测试（S25）**，再写 GoalRunner——测试先行才敢换执行器；
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
| 1.5.0 | 2026-10-26 | **3.2 analysis L2 落地**：逐条 verify→rewrite→drop、`analysis_l2` 开关、A/B 脚本；偏差 3.2-a/3.2-b 见 `RESULTS-P3.md` |
| 1.4.0 | 2026-10-26 | **3.1 retrieval L2 落地**：`rewrite_query → hybrid_search` 两步循环、`retrieval_l2` 开关（默认 L1）、A/B 脚本；偏差 3.1-a/3.1-b 见 `RESULTS-P3.md` |
| 1.3.0 | 2026-10-26 | **3.0 Foundations 落地**：NodeGoal/ShellSpec（提前）、MicroAgent 七相位、ToolSpec v2 四段流水线、默认关接线、验证器骨架；偏差与结果见 `RESULTS-P3.md` |
| 1.2.0 | 2026-10-26 | **新增壳规范**：§3.0 定义壳/内核/能力/治理四层、S1–S6 硬规则、`ShellSpec`（可序列化/哈希/可删）、六项厚度指标、SH1–SH7 测试矩阵、壳优化与生成闭环；新增 I21–I23、H21–H22、S27/S28、附录 H |
| 1.1.0 | 2026-10-26 | **借鉴 DSH 内核**：MicroAgent 相位化（before_request/after_action）、工具四段流水线 + 单调 guard + 并发分类、日志唯一真源与双域事件、取消/冻结/提交边界、pre-step 压缩（先剪枝后摘要）、执行器可替换与等价测试；新增 M9、I15–I20、H17–H20、S25/S26、附录 E–G |
| **1.0.0** | 2026-10-23 | 首版：双层架构、NodeGoal/MicroAgent/ToolSpec、L0–L3 与升级策略、3.0–3.5 六子阶段（S1–S24）、I1–I14、H1–H16、评测与消融设计、AI 实施建议 |

---

## 附录 A · 命令速查

```powershell
. .\scripts\env.ps1
uv run pytest -q
uv run python scripts/verify_phase3.py --all
uv run python scripts/verify_phase3.py --retrieval --analysis --events
uv run python scripts/verify_phase3.py --ablation --trajectory
uv run python scripts/verify_phase3.py --shell          # 六项厚度指标
uv run python scripts/verify_phase3.py --shell-ablation # 开/关壳对照
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

## 附录 E · DSH 借鉴清单（只借机制，不搬框架）

| DSH 机制 | 我们借鉴为 | 落点 | 判据 |
|---|---|---|---|
| `agent/pre-step`（waterfall） | `MicroAgent.before_request`：剪枝/摘要/注入/steering | §3.2 / §3.7 / M1 / M9 | H18 |
| 会话日志唯一真源 | run log append-only + 派生视图 | §3.5 / M9 | H17 |
| 工具四段流水线 | `pre → guard → execute → post` | §3.4 / M3 | M3 判据 |
| 单调 guard（只能 deny） | 权限/安全策略不可被后续监听器放行 | §3.4 / M3 | I17 |
| 工具并发分类 + 滚动池 | `exclusive/parallel`（fail-closed）+ 有序提交 | §3.4 / Phase 4 | I18 |
| 取消不提交 / 不可变请求 | 四相位取消矩阵 + 冻结请求 | §3.6 | H19 |
| compaction 在 pre-step、先剪枝后摘要 | `before_request` 压缩顺序 | §3.7 | H18 |
| subagent seam（schema/depth/取消/清理） | Phase 4 扇出接口 | Phase 4 | —— |
| plan 模式 = 提示词段落 + 工具 | `plan` 可退化为 Goal + 工具，而非硬编码阶段 | 3.2/3.3 | —— |
| workflow-as-code（模型写脚本扇出） | Phase 4/5 的可选扇出方式 | Phase 4/5 | —— |
| 能力 seam（定义/实现/消费者） | 每个新能力先写三件套再实现 | 本文档 §4 | 评审清单 |
| "新行为归属位置"表 | 见附录 G | 附录 G | —— |

**不借鉴**：Cordis 插件树/热更新、多代会话格式迁移、纯单循环做周报（无阶段契约）。

## 附录 F · 执行器等价测试（删图的前提）

```text
准备：同一份 Goal 列表（10 个 NodeGoal）+ 同一份 fixture（DB/工具/脚本化 LLM）
执行：GraphExecutor.run(...) 与 GoalRunner.run(...)
比较：
  1) 阶段顺序与 attempt/step 计数（忽略时间戳/耗时）
  2) 每个门禁的 (name, ok, code) 序列
  3) 报告 content_sha、claims 数、metrics 关键字段
  4) 事件类型序列（payload 只比冻结字段）
通过：3 轮 × 10 场景（健康/坏产物/证据不足/预算超限/取消）
之后：Graph 降级为 legacy adapter，再过 1 个迭代删除
```

## 附录 G · 新行为应该加在哪一层

| 想加什么 | 加在哪 | 例子 |
|---|---|---|
| 新的阶段/目标 | 壳（`ShellSpec` 的 Goal 列表） | 增加"检索扩充"目标 |
| 新能力 | 工具（`ToolSpec`） | `verify_claim`、`sectionize` |
| 新验收标准 | 门禁（postcondition） | 引用覆盖率 ≥ 0.8 |
| 新安全/预算策略 | guard（单调） | 写操作需确认 |
| 新横切拦截 | `before_request` 或工具 pre/post | 脱敏、审计、注入防护 |
| 新执行模式 | `Executor` 实现 | 并行、扇出、批处理 |
| 新事实记录 | run log 事件（只增字段） | `step`/`action`/`duration_ms` |

## 附录 H · `ShellSpec` 生成模板

给后续"生成壳"的最小输入与输出约定（Phase 5 用它做候选）：

**输入**（人给或自动推导）：

```json
{
  "task": "weekly-report",
  "goal_ids": ["intake", "scope", "retrieval", "parse", "normalize", "mapping", "analysis", "critique", "report", "evaluate"],
  "allowed_tools": ["hybrid_search", "rewrite_query", "extract_claims", "verify_claim", "rewrite_claim", "render_report"],
  "allowed_gates": ["schema", "evidence_sufficiency", "citation_integrity", "support_ratio", "budget"],
  "budget": {"usd": 2.0, "llm_calls": 12, "wall_s": 900}
}
```

**输出**：一份通过 SH1–SH5 的 `ShellSpec`（见 §3.0.3）+ 一份变更说明（改了哪些 goal/顺序/限额及理由）。

**准入**：候选壳必须先过 `tests/shell` 全部用例、gold 不降、成本不超、门禁误报 <2%、壳开销 <5%，
才允许进入影子运行；转正必须升 version 并记录 hash。
