# RESULTS — Phase 3.0（Foundations）

> 口径：只记**实测**；数字由命令产出。
> 规范：`phase3-double-layer-agent.md`（3.0：S1–S6；M1–M3/M9 的前置）。

## 0. 一页摘要

| 指标 | 当前值 |
|---|---|
| 阶段 | **3.0 + 3.1 + 3.2 完成** |
| 测试 | `pytest` 收集 **515 例**（2.2 为 467） |
| 3.x 验证器 | `verify_phase3 --all` **6/6 PASS** |
| 基线 | `verify_phase2_1 13/13`、`verify_phase2 12/12`、`verify_phase1 13/13` |
| 行为变化 | **零**（`micro_enabled=false`，十阶段事件与 2.2 一致） |

---

## 1. 交付

| 模块 | 产物 | 说明 |
|---|---|---|
| NodeGoal | `contracts/goals.py` | 10 个 Goal（name/objective/postconditions/tools/autonomy/max_steps/max_usd），JSON 可序列化 |
| ShellSpec | `contracts/shell.py` | 纯数据壳：canonical JSON + sha256；`default_shell()`（10 Goal） |
| MicroAgent | `runtime/micro_agent.py` | 七相位：`before_request → request → parse → act/after_tool → after_action → replan`；`LoopState` 外置 |
| Tool v2 | `tools/spec.py` | `pre_execute → guard(单调) → execute(超时) → post_execute`；输出 schema 校验/截断；`ToolRuntime` + 3 个新工具 |
| 接线 | `config.pipeline.micro_enabled=False`、`RunContext.shell` | 只挂载，不执行；关闭时行为逐事件一致 |
| 验证 | `scripts/verify_phase3.py --foundations` | H1/H2/H3/H6，输出 `phase3-report.json` |

## 2. 实测

```text
pytest -q                    505 例（exit 0）
verify_phase3 --foundations  4/4 PASS
verify_phase2_1 --all        13/13
verify_phase2_2 --all        8/8
verify_phase2 --offline      12/12
verify_phase1 --online       13/13
ruff                         clean
```

新增测试分布：

| 文件 | 例数 | 覆盖 |
|---|---|---|
| `tests/contracts/test_goals_and_shell.py` | 17 | 10 Goal 合法性、roundtrip、ShellSpec hash/纯度/可删 |
| `tests/runtime/test_micro_agent.py` | 8 | 六路径 + 相位分离 + 状态隔离 |
| `tests/tools/test_protocol_v2.py` | 10 | 四段流水线、超时/截断/校验/预算/事件 |
| `tests/runtime/test_phase3_defaults.py` | 3 | 默认关、十阶段、零 tool_call |

## 3. 关键决策与偏差

| ID | 决策/偏差 | 理由 |
|---|---|---|
| 3.0-a | **ShellSpec 提前到 3.0**（原计划 3.5 / S27） | 契约测试和后续 L2 需要它；纯数据、成本低 |
| 3.0-b | `pipeline.micro_enabled` 新增配置字段（默认 False） | 加法式配置，不改 2.1/2.2 语义，符合 ADR-0007 |
| 3.0-c | 测试台写在测试文件内（未建 `tests/support/scripted.py`） | 目前只有 MicroAgent 用；等 3.1 复用再抽包 |
| 3.0-d | ToolRuntime 与旧 `tools/registry.Tool` 并存 | 旧链路不动，L2 节点逐步迁移；避免一次性替换 |
| 3.0-e | `before_request` 目前只做消息组装 + 可插拔 policy | 压缩/注入在 3.2 接入（先有相位，再有策略） |
| 3.0-f | MicroAgent 的 trace 记录工具 output | 便于 postcondition 与回放；体积可控 |

## 4. 未做（按计划）

- 节点真正启用 L2（3.1 retrieval / 3.2 analysis）；
- `before_request` 的剪枝/摘要策略（3.2）；
- 图执行器 → GoalRunner 的等价迁移（3.5）；
- Chat L3（3.3）。

## 5. 下一步（3.1）

1. retrieval Goal 打开 `autonomy=L2`：`rewrite_query → hybrid_search → postcondition(evidence)`；
2. 用 `ToolRuntime` 注册 `hybrid_search`（包一层现有检索），保持输出 schema；
3. 默认仍关，跑 A/B：L1 vs L2 的 recall/cost/延迟；
4. 若 L2 无增益，保留 L1 并把结论写进论文（负结果也算证据）。


---

## 6. 3.1 · retrieval L2（2026-10-26）

### 6.1 交付

| 产物 | 说明 |
|---|---|
| `nodes._retrieval_l2` | L2 循环：`rewrite_query → hybrid_search → postcondition(cards>=1)`；失败回退词面 |
| `pipeline.retrieval_l2` | 开关，默认 `False`（默认仍是 3.0 的 L1） |
| `rewrite_query` 工具 | 规则版：去停用词 + 同义词（确定性，零成本） |
| `hybrid_search` 工具封装 | 复用现有 hybrid，输出 `paper_ids` 可校验 |
| `scripts/ab_retrieval.py` | 同数据、同 hint 跑 L1/L2，输出对比表 + JSON |
| `tests/runtime/test_retrieval_l2.py` | 5 例：默认 L1、两条 tool_call、卡片一致、无 hint 跳过、回退 |
| e2e 回归 | 13 passed（SSE 用例改为 API 建 run，避免重试撞锁） |

### 6.2 A/B 实测（5 篇、focus="tool use"）

| 模式 | 状态 | 策略 | 卡片 | L2 步数 | tool_call | 检索耗时 | 成本 |
|---|---|---|---|---|---|---|---|
| L1 | succeeded | hybrid | 5 | 0 | 0 | 14 ms | $0 |
| L2 | succeeded | l2 | 5 | 2 | 2 | 15 ms | $0 |

**结论**：L2 与 L1 选出的卡片**完全一致**；代价是 +1 次工具调度（约 +1ms），无 LLM 成本。
在"检索已经确定性"的当前数据上，L2 没有质量增益——这是预期结果，也是论文里"L2 只在需要多步时才有价值"的对照基线。

### 6.3 偏差

| ID | 偏差 | 理由 |
|---|---|---|
| 3.1-a | L2 改写用**规则版**，未接 LLM | 保持成本 0、可复现；LLM 改写留配置位，3.2 视需要开 |
| 3.1-b | L2 回退用 `select_cards`（词面）而不是 L1 hybrid | 回退要"最保底"；hybrid 空时词面仍可能命中，避免直接空结果 |

### 6.4 下一步（3.2）

1. analysis 开 L2：`extract_claims → verify_claim → rewrite_claim`（逐条校验-修复）；
2. 用 `rewrite_claim` 降 unsupported 率，对比 grounding/成本；
3. 把 `before_request` 的剪枝/摘要策略接上（长上下文用例）。


---

## 7. 3.2 · analysis L2（2026-10-26）

### 7.1 交付

| 产物 | 说明 |
|---|---|
| `tool_runtime_for(names)` | 工具白名单工厂，避免节点拿到全部工具 |
| `extract_claims` / `rewrite_claim` | 确定性抽取首句 / 改写成片段中可支持的最相关句 |
| `_analysis_l2` | 逐条 `verify_claim → rewrite_claim → 复验`；仍失败丢弃；只改坏 claim |
| `pipeline.analysis_l2` | 开关，默认 `False` |
| `scripts/ab_analysis.py` | L1/L2 × 正常/坏产物 四组对比 |
| `tests/runtime/test_analysis_l2.py` | 5 例：默认 L1、逐条校验、丢弃不可修复、改写转支持、工具注册 |

### 7.2 A/B 实测（3 篇）

| 模式 | 状态 | claims | unsupported | 改写 | 丢弃 | tool_call | grounding |
|---|---|---|---|---|---|---|---|
| L1 | succeeded | 3 | 0 | 0 | 0 | 0 | 1.0 |
| L2 | succeeded | 3 | 0 | 0 | 0 | 3 | 1.0 |
| L1+bad | succeeded | 3 | **1** | 0 | 0 | 0 | 1.0* |
| L2+bad | succeeded | 2 | **0** | 0 | 1 | 3 | 1.0 |

**结论**：坏产物场景下，L2 通过"丢弃不可修复 claim"把 unsupported 从 1 降到 0；
正常场景只多 3 次 verify 调用，无 LLM 成本。
（*L1+bad 的 `grounding` 由 evaluate 口径计算，未计入无引用 claim；所以另列 `unsupported`。）

### 7.3 偏差

| ID | 偏差 | 理由 |
|---|---|---|
| 3.2-a | `rewrite_claim` 用**片段句**替换，未接 LLM | 保证"改写后必被支持"；语义更精细的改写留 LLM 版 |
| 3.2-b | 不可修复 claim **直接丢弃**，不降级整轮 | 报告宁可少一条，也不留无引用断言 |
| 3.2-c | 每条 claim 一次 verify（坏 claim 再 +rewrite+verify） | tool_call 事件随 claims 线性增长，当前规模可接受 |

### 7.4 下一步（3.3）

Chat L3：迁移 0004 + 会话 API + `agents/chat.py`（ReAct 工具白名单、无引用不作答、可中止）+ 前端 Chat 页。
