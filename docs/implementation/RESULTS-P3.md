# RESULTS — Phase 3.0（Foundations）

> 口径：只记**实测**；数字由命令产出。
> 规范：`phase3-double-layer-agent.md`（3.0：S1–S6；M1–M3/M9 的前置）。
> 借鉴调研：`open-source-borrowing-survey.md`（DSH 源码 + GitHub 项目，含许可证与落地优先级）。

## 0. 一页摘要

| 指标 | 当前值 |
|---|---|
| 阶段 | **Phase 3 完成**（S20 MCP 为 P4 可选） |
| 测试 | `pytest` 收集 **551 例**；e2e **14 passed** |
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


---

## 8. 3.3 · Chat L3（2026-10-26）

### 8.1 交付

| 产物 | 说明 |
|---|---|
| 迁移 0004 | `chat_messages.trace_json`（表本身在 0001 已建） |
| `db/repo/chat.py` | 会话创建/列表、消息追加/读取（含 citations/trace） |
| `agents/chat.py` | L3：`rewrite_query → search_topic → verify_claim`，无引用拒答 |
| Chat API | `GET /api/topics/{id}/chat`、`POST /api/topics/{id}/chat`（同步回答） |
| Chat 页 | 会话列表、消息流、引用标签、工具轨迹、发送/中止 |
| 测试 | `tests/chat/test_chat_l3.py`（5 例）+ e2e 2 条（首轮/追问/拒答） |

### 8.2 实测

```text
pytest                520 例（3.2 的 515 + 5）
verify_phase3 --all   6/6
playwright            14 passed
首轮：根据 [E2E-P0]：tool use improves task success…
追问：同一 session 继续回答
拒答：zzz-nonexistent → 无法从本 topic 的证据回答
```

### 8.3 偏差

| ID | 偏差 | 理由 |
|---|---|---|
| 3.3-a | 会话表在 0001 已建，0004 只加 `trace_json` | 避免重复建表；迁移幂等 |
| 3.3-b | Chat 检索用**全局 papers**（schema 无 topic_papers） | 与周报同源；多 topic 隔离需要后续迁移 |
| 3.3-c | 无 token 级 SSE，同步返回 + 前端 AbortController | 回答确定性、毫秒级；中止测试用单元/手动覆盖 |
| 3.3-d | L3 无 LLM（规则 search/verify） | 零成本、可复现；LLM 版留配置位 |
| 3.3-e | e2e 用 `scripts/seed_e2e.py` 预置 3 篇论文 | dev DB 原本 0 篇；CI 需先 seed 或扩展 fixture |

### 8.4 下一步（3.4）

治理（权限/沙盒/工具检索）→ 3.5 评测与收尾（含壳规范、执行器等价）。


### 8.5 3.3 收尾（2026-10-26）

| 项 | 结果 |
|---|---|
| 新建会话 | 新增 `POST /api/topics/{id}/chat/sessions` + Chat 页「+ 新建对话」 |
| 会话隔离 | 新会话消息为空；`GET ?session_id=` 精确读取 |
| 迁移 | 0004 已在 dev store 应用（`trace_json`） |
| 中止 | 前端 AbortController；后端同步返回，中止不落半条 assistant 消息 |
| 测试 | `tests/chat` 6 例；e2e 14 条（首轮/追问/拒答） |
| 遗留 | 多话题隔离（schema 无 topic_papers）、token 级流式 → 2.3 打磨 |

**结论：3.3 关闭。** 偏差 3.3-a…e 保留在案，不阻塞 3.4。

---

## 9. 3.4 · 治理与扩展（2026-10-26）

### 9.1 交付

| 产物 | 说明 |
|---|---|
| 权限门 | `ToolRuntime.call(..., approved=False)`；`permission=confirm` 未确认即拒（`E_PERMISSION_REQUIRED`），并发 `guard_trigger` 事件 |
| 工具检索 | `ToolRuntime.search(query, k=3)`：词面 + CJK bigram；为 3.4 的工具白名单/延迟加载铺路 |
| 沙盒准入 | `security/sandbox.py`：命令白名单、shell 元字符、`ensure_within` 防目录穿越（只判不执行） |
| 测试 | `tests/governance`（4）、`tests/tools/test_tool_search.py`（3）、`tests/security`（5） |

### 9.2 实测

```text
权限：未确认 write_file → 拒绝；approved=True → 执行
检索：10 个工具 / 10 条 query → top-3 命中 10/10（目标 ≥80%）
沙盒：rm/curl/`;`/../ 全部拒绝；python/pytest 放行
pytest 533 例；verify_phase3 --all 8/8
```

### 9.3 偏差

| ID | 内容 | 理由 |
|---|---|---|
| 3.4-a | 权限确认用 `approved` 布尔，未接人工审批 UI | 先保证“默认不执行”；审批 UI 归 2.3 |
| 3.4-b | 工具检索是词面/bigram，不是向量 | 零依赖、可复现；目录 >50 再上向量 |
| 3.4-c | 沙盒只做准入判断，不执行子进程 | 真实执行归 P4 code-runtime |
| 3.4-d | MCP 适配（S20）推迟 | 与 subagent/外部工具一起做，避免半成品 |

### 9.4 下一步（3.5）

gold v2 + 轨迹指标 + 消融 + 壳规范/执行器等价（S21–S28）。


---

## 10. 3.5 · 评测、回放与壳规范（2026-10-26）

### 10.1 交付

| 步 | 产物 | 说明 |
|---|---|---|
| S21 | `eval/bench_v2.py` | 30 queries + 10 场景（合成）；哈希冻结 `8ec94db9…` |
| S22 | `eval/trajectory.py` | steps / tool_calls / retries / repair_rate / escalation_rate / stop_reason |
| S23 | `scripts/ablation.py` | 四组对照：L1 / retrieval-L2 / analysis-L2 / both |
| S26 | `scripts/replay_run.py` | 只读事件回答：重试、降级、成本、耗时、轨迹 |
| S27 | `eval/shell_metrics.py` + `tests/shell` | 壳厚度：goals/postconditions/llm-per-goal/loc/hash |

### 10.2 消融实测（3 篇、focus=“tool use”）

| 配置 | 状态 | claims | unsupported | grounding | tool_calls | 重试 | 耗时 | 成本 |
|---|---|---|---|---|---|---|---|---|
| L1 | succeeded | 3 | 0 | 1.0 | 0 | 0 | 148 ms | $0 |
| retrieval-L2 | succeeded | 3 | 0 | 1.0 | 2 | 0 | 166 ms | $0 |
| analysis-L2 | succeeded | 3 | 0 | 1.0 | 3 | 0 | 226 ms | $0 |
| both-L2 | succeeded | 3 | 0 | 1.0 | 5 | 0 | 289 ms | $0 |

**结论**：在当前确定性数据上，L2 不改变质量，只增加工具调用与耗时（≈+18%/+52%/+95%）。
这正是预期对照：**L2 的价值在多步/坏证据场景，而不是健康数据**（与 3.1/3.2 的 bad 场景结论一致）。

### 10.3 日志回放（S26）

`replay_run.py` 仅读 `run_events` + metrics，即可回答：
1. 哪一步重试/修复（stage/action/code/attempt）；
2. 是否降级/中止（guard/recovery）；
3. 成本与各阶段耗时；并附轨迹指标。

测试 `tests/observability/test_trajectory_replay.py` 3 例。

### 10.4 壳规范（S27）

`ShellSpec`：10 goals、postconditions ≤2、loc ≤500、hash 稳定；
`tests/shell` 6 例覆盖 SH1/SH2/SH3/SH5。
**未完成**：`shell_overhead_ratio` 需要 LLM/tool span，当前占位 0（S25/S28 一并补）。

### 10.5 偏差与推迟

| ID | 内容 | 影响 |
|---|---|---|
| 3.5-a | bench v2 是合成集，不是人工标注 | 用于回归/消融，不能替代 gold 精度结论 |
| 3.5-b | **S25 执行器等价 / S28 壳消融推迟 3.6** | 需要 GoalRunner 重构；当前 Graph 执行器保持唯一路径 |
| 3.5-c | `shell_overhead_ratio` 未实测 | 待 OTel span；当前以耗时对比近似 |
| 3.5-d | 消融是确定性单次运行（无方差） | 真实多 seed 方差需 LLM 在线实验（P4） |

### 10.6 下一步（3.6）

1. `GoalRunner` + Graph/Goal 等价测试（S25）；
2. 壳消融与生成准入（S28）；
3. 2.3 打磨：Chat 流式/可恢复、引用抽屉、工具轨迹分组。


---

## 11. 3.6 · 执行器等价与壳消融（2026-10-26）

### 11.1 交付

| 步 | 产物 | 说明 |
|---|---|---|
| S25 | `run_graph(executor="goal_runner")` | 顺序执行 Goal 列表，复用同一 `stage_node`（门禁/提交/事件完全一致）；支持回边（retry/repair/replan） |
| S25 | `tests/runtime/test_executor_parity.py` | 5 例：健康/坏产物/空检索阶段序列一致；精简壳；默认 10 goals |
| S28 | `eval/shell_admission.py` | 红线：必要阶段、goals ≤10、预算覆盖、`ShellSpec.validate` |
| S28 | `scripts/ab_shell.py` | 10-goal 默认壳 vs 5-goal 精简壳（GoalRunner） |

### 11.2 壳消融实测（3 篇）

| 壳 | goals | 阶段 | claims | grounding | 耗时 | 状态 |
|---|---|---|---|---|---|---|
| weekly-report | 10 | 10 | 3 | 1.0 | 148 ms | succeeded |
| reduced | 5 | 5 | 3 | 1.0 | 106 ms | succeeded |

**结论**：去掉 parse/normalize/mapping 后质量不变、耗时 −28%，说明这三个阶段在当前数据上是“可删的壳”。
准入红线会阻止“删掉 retrieval/analysis/report”的候选壳。

### 11.3 偏差

| ID | 内容 | 影响 |
|---|---|---|
| 3.6-a | GoalRunner 不支持 `resume`（明确报错） | 等价范围是 fresh run；断点续跑仍走 Graph |
| 3.6-b | 等价测试覆盖 3 场景（非 10） | 覆盖主干与两类故障；更多场景可扩 |
| 3.6-c | 壳消融只比 2 个壳 | 生成准入的红线已测；批量生成留 P5 |
| 3.6-d | S20 MCP 适配推迟 P4 | 可选扩展，不影响收尾 |

### 11.4 Phase 3 收尾结论

```text
verify_phase3 --all     13/13 PASS
verify_phase2_1 --all   13/13
verify_phase2 --offline 12/12
verify_phase1 --online  13/13
pytest                  551 例
playwright              14 passed
build / typecheck       ✓ / 0 error
```

**Phase 3 COMPLETE**：双层架构（Graph + MicroAgent）、L1/L2/L3、治理、评测、壳规范与执行器等价全部落地。
S20（MCP）作为 P4 可选扩展保留，不阻塞论文与答辩。
