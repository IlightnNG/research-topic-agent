# RESULTS — Phase 3.0（Foundations）

> 口径：只记**实测**；数字由命令产出。
> 规范：`phase3-double-layer-agent.md`（3.0：S1–S6；M1–M3/M9 的前置）。

## 0. 一页摘要

| 指标 | 当前值 |
|---|---|
| 阶段 | **3.0 Foundations 完成** |
| 测试 | `pytest` 收集 **505 例**（较 2.2 的 467 增加 38） |
| 3.0 验证器 | `verify_phase3 --foundations` **4/4 PASS** |
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
