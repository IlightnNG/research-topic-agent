# 开源 Agent 项目借鉴调研（2026-10-26）

> **目的**：为 Phase 2.3 / 3.4 / 3.5 及最终打磨提供“可落地的借鉴清单”，而不是泛泛的竞品综述。
> **方法**：① 精读本地 DSH（DeepSeek Harness）源码；② 检索并阅读 GitHub 热门项目的 README / 架构文档 / LICENSE；③ 只提炼“设计模式与契约”，不复制实现。
> **边界**：未 clone 仓库、未运行第三方代码；许可证以抓取当日为准，落地前需再核对（尤其 Open WebUI / Phoenix）。项目版本会漂移，接口以调研时点为准。

---

## 0. 结论（TL;DR）

| 判断 | 内容 |
|---|---|
| **最该借的 3 件事** | ① Chat 的**流式 + 可恢复**（LibreChat 的 resumable stream 设计）；② **引用/证据交互**（PaperQA2 的证据分级 + assistant-ui 的 message parts 思路）；③ **评测**（RAGAS 指标 + Pydantic Evals 的轨迹断言） |
| **DSH 最该补的 3 个机制** | ① 工具**协作式超时**（deadline + 结构化 `TOOL_TIMEOUT`）；② **重复调用提醒**（advisory，不否决）；③ 压缩**先剪枝后摘要**（pruner + checkpoint） |
| **不建议** | 引入 React 组件库/新 Agent 框架；复制 ELv2（Phoenix）或带品牌条款（Open WebUI v0.6.6+）的代码；为了“功能多”重写现有图 |
| **预期收益** | Chat 从“能用”到“像产品”；报告可信度可量化；论文多一组“轨迹级”评测证据 |

---

## 1. 调研方法与证据等级

| 等级 | 含义 | 本文用法 |
|---|---|---|
| **A（已读源码）** | 本地 DSH 具体文件 + 行级行为 | 可直接照抄设计 |
| **B（已读官方文档/README）** | 项目自述的架构与能力 | 可借鉴设计，接口需复核 |
| **C（仅检索到）** | 未逐行验证 | 只作候选，不写实现细节 |

本文 DSH 部分全部为 A；GitHub 部分为 B；未标注的推断均写明“需复核”。

---

## 2. DSH 源码深挖：10 个可借机制

DSH 的总体设计已在 `docs/implementation/phase3-double-layer-agent.md` 附录 E 记录（单层内核 + 工具流水线 + 日志真源）。下面是**尚未借鉴、但对当前项目直接有用**的细节。

### 2.1 工具超时：协作式 deadline，而不是“外部杀线程”

**证据**：`packages/guard/timeout-policy/src/index.ts`

```ts
using d = deadline(exec.signal, timeoutMs, TOOL_TIMEOUT)
const upstream = exec.signal
exec.signal = d.signal
try {
  const result = await next()
  if (timeoutOf(d.signal, TOOL_TIMEOUT) !== undefined) return toolTimeoutResult(timeoutMs)
  return result
} finally { exec.signal = upstream }
```

要点：
- 工具声明 `timeoutMs` 并**承诺响应 `exec.signal`**；超时靠 signal 传播，不 race、不抛弃 promise；
- 超时结果替换为**结构化** `TOOL_TIMEOUT`，模型可读、重试/沙盒可路由；
- 外层超时不会被误判成本层超时（按 code 作用域判定）。

**借到哪**：`src/lit_agent/tools/spec.py` 的 `_execute` 目前是 `ThreadPoolExecutor + future.result(timeout)`，线程无法被取消。建议：
1. `ToolSpec` 增加 `cooperative: bool`（默认 False）；
2. 对 `cooperative=True` 的工具传 `signal`（`threading.Event`），超时置位并等待工具退出；
3. 返回 `E_SRC_TIMEOUT` + `meta.stage="execute"`，保持现有错误码。
**成本**：S（半天）。**收益**：长任务不再泄漏线程；取消语义一致。

### 2.2 重复调用提醒：advisory，不否决

**证据**：`packages/guard/repeat-tool-reminder/src/index.ts`

- 阈值默认 `[3, 5, 8]`，只 **enrich post-execute 决策**，不 veto、不改写调用；
- 提醒是带 `source: {kind:'repeat-tool-reminder'}` 的 **user 消息**，避免被当成系统提示；
- 参数预览截断（默认 500 字符），但比较用**完整 canonical 参数**。

**借到哪**：`runtime/micro_agent.py` 现在只有 `no_progress` 终止（repeat>=2 直接停）。建议改为：
- 第 2 次重复：发 `guard_trigger`（severity=warning, code=`E_REPEAT_TOOL`），**注入一条提醒**到下一步上下文；
- 第 3 次：才终止。
**成本**：S。**收益**：少一次“过早失败”，且轨迹可解释。

### 2.3 压缩：先剪枝（无损）再摘要（有损），且剪枝可回放

**证据**：
- `packages/compaction/compaction-tool-result-pruner/src/index.ts`：`ToolResultPruner` 做 **head/middle/tail** 裁剪，`PRUNE_MARKER` 标记，**replay-safe + model-free**；
- `packages/compaction/compaction/src/checkpoint.ts`：压缩结果以 `compact-checkpoint` source 的 user message 落地，带 `compactionId`，可识别、可恢复；
- `docs/subsystems/compaction.zh.md`：pre-step 先 prune、再测 token、仍超才 summarize。

**借到哪**：`before_request` 目前只组装消息，没有策略。建议：
1. `runtime/context_policy.py`：按字符阈值裁工具结果（保头尾 + 中间省略标记）；
2. 写 `context_pruned` 事件（遮蔽了哪些 seq、省了多少 token）；
3. 再评估是否摘要。
**成本**：M（1 天）。**收益**：长 run/长会话 token 降 40%+，且不破坏引用。

### 2.4 plan mode：状态是日志投影，工具目录保持稳定

**证据**：`packages/plan/plan-mode/src/index.ts`

- `plan/mode` 是 **log-only、非 surface、整值替换**的 SessionEvent；resume/fork 通过 projection fold 恢复；
- 激活时只在请求里加 `plan:policy` 提示词段落；
- `exit_plan_mode` 工具**在非 plan 模式也保持注册**，保证工具目录不随模式变化（对缓存/复现友好）。

**借到哪**：Phase 3 的 `plan` 节点可退化为“Goal + 工具”：
- 计划内容存 `run_events`（payload 加 `plan` 字段），不要新增表；
- 计划模式只影响 prompt 段，不改变可用工具集。
**成本**：S。**收益**：少一个硬编码阶段，且可回放。

### 2.5 子 agent 深度：只增不减

**证据**：`packages/subagent/subagent/src/depth.ts`

```ts
return Math.max(agent.session.header.delegationDepth ?? 0, runtime ?? 0)
```

持久化 header 是权威；resume 时运行时参数**只能加深、不能降低**，防止子 agent 伪装成顶层继续递归。

**借到哪**：Phase 4 的 `subagent` 若实现，必须把 depth 写进会话元数据，并在 resume 时取 max。**成本**：S（设计约束，现在写进契约即可）。

### 2.6 Goal：durable ref + revision CAS + 明确 phase

**证据**：`packages/goal/goal/src/types.ts`

```ts
interface GoalRef { id: GoalId; revision: number }
type GoalPhase = 'active' | 'paused' | 'blocked' | 'complete'
```

- 每次持久化变更 `revision++`；编辑用 **compare-and-set**，避免并发覆盖；
- `blocked` 需要机器可路由的 `code` + 人话 `message`。

**借到哪**：你已有 `runs.state`，但缺“目标级”状态。3.5/Phase 4 若做 GoalRunner：
- `NodeGoal` 增加 `revision`（默认 0），Goal 更新走 CAS；
- `stop_reason` 映射 phase（completed/blocked/aborted）。
**成本**：S。**收益**：为“可暂停/可恢复/可审计”的目标执行打底。

### 2.7 OTel 遥测：显式白名单字段，绝不含 prompt/PII

**证据**：`packages/telemetry/otel/src/event-log.ts`

- `OTelEventRecord` 明确列字段：`eventName` / `body` / `timestamp` / `severityNumber` / `attributes`；
- 注释写明 “never a prompt, response, credential, or file contents”；
- 独立队列、批量、可取消，不阻塞主流程。

**借到哪**：现在 `run_events` 是产品日志；若要接 Langfuse/OTLP：
- 新建 `src/lit_agent/telemetry/otlp.py`，把事件**投影**成 span/log，不要直接发原始 payload；
- 白名单：`stage/attempt/action/error_code/duration_ms/cost_usd`。
**成本**：M。**收益**：论文可用标准 trace 展示，不泄露内容。

### 2.8 审批/沙盒与“计划”解耦

**证据**：`plan-mode/src/index.ts` 注释：

> Sandbox mode and approval policy enforce restrictions independently and do not read or write plan state.

**借到哪**：3.4 治理里，`permission` 只由工具 spec 决定，**不允许**“计划模式=只读”这类隐式耦合，否则会出现“计划里能写、执行时不能写”的裂缝。**成本**：0（设计红线）。

### 2.9 Session log 是唯一真源，projection 是派生

**证据**：`session-query`、`goal`、`plan-mode` 都以 `SessionEvent` + projection fold 实现状态；`compaction` 也以 checkpoint message 落地。

**借到哪**：你已有 `run_events`，但 Chat 的“工具轨迹/引用”存在 `chat_messages.trace_json/citations_json`，属于**第二份事实**。建议：
- 长期：Chat 也发 `chat_tool_call` 事件，消息表只存最终内容 + 引用 id；
- 短期：至少保证 `trace_json` 可从事件重建（导出脚本验证）。
**成本**：M（渐进）。

### 2.10 能力 seam 的文档规范

**证据**：`docs/architecture.zh.md` 每节固定写 **Service Definition / Provider / Consumer**，并给“新行为归属位置”表。

**借到哪**：`phase3` 附录 G 已借一半；建议新工具/新门禁的 PR 模板强制填“定义/实现/消费者”。**成本**：0。

---

## 3. GitHub 横向对比（已读 README / LICENSE）

> 许可证为抓取当日核对；**未标“已核对”的需落地前复核**。

| 项目 | 类别 | 许可证 | 架构/设计要点 | 值得借 | 不要借 |
|---|---|---|---|---|---|
| [PaperQA2](https://github.com/Future-House/paper-qa) | 科学文献 RAG | **Apache-2.0**（README 徽章，已核对） | 三阶段：Search → Gather Evidence（embed/rank/**scored summary**/LLM 重排）→ Generate Answer；`evidence_relevance_score_cutoff`、`answer_max_sources`；支持 agentic 循环 | **证据分级 + 相关性 cutoff + “证据不足”处理**；`gather_evidence` 工具化 | 整套 Docs/索引实现（重） |
| [assistant-ui](https://github.com/assistant-ui/assistant-ui) | Chat 前端 | **MIT**（README，已核对） | 原语化（Thread/Message/Composer/ThreadList/ActionBar）；runtime 适配（AI SDK / LangGraph / 自定义 data-stream）；内置 streaming、auto-scroll、retry、markdown、tool UI、branch picker | **message parts 模型**、流式/自动滚动/重试的 UX 细节、tool call 卡片 | React 组件（你是 Vue）；云端 thread 存储 |
| [LibreChat](https://github.com/danny-avila/LibreChat) | Chat 平台 | **MIT**（LICENSE，已核对） | **Resumable Streams**：generation job 记录每个 delta；断线重连先回放已流内容，再单条 sync 事件续传；单机内存 / Redis 两模式。Trace Viewer、fork message、context usage | **可恢复流协议**（job id + 已流内容 + sync）；工具活动/推理分组展示；fork/分支 | 全家桶（MCP、多 provider、RBAC） |
| [Open WebUI](https://github.com/open-webui/open-webui) | Chat 平台 | **BSD-3 + 品牌条款**（v0.6.6+，[官方说明](https://docs.openwebui.com/license/)） | 自托管 Chat；多模型；RAG；插件；用户/权限 | 交互取舍（侧栏、引用、停止/重新生成） | **代码**（品牌条款；且体量大） |
| [RAGAS](https://github.com/explodinggradients/ragas) | 评测 | **Apache-2.0**（README，已核对） | 指标库 + **测试集生成**；LLM-based 与经典指标并存；`DiscreteMetric` 可自定义 judge | **faithfulness / context precision / answer relevance 的定义**；测试集生成思路 | 直接依赖（你已有 metrics，重实现定义即可） |
| [Langfuse](https://github.com/langfuse/langfuse) | 可观测 | **MIT（ee 目录除外）**（README，已核对） | trace/session、prompt 管理、evals、datasets；OTel 集成 | **trace/session 数据模型**；prompt 版本化；评估集 | 自托管全家桶（ClickHouse 等） |
| [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) | Agent 框架 | **MIT**（需复核 LICENSE 文件） | Agent = instructions + tools + guardrails + handoffs；Sessions 管理历史；Tracing 内建；input/output guardrails | **guardrail 分层**（输入/输出）、handoff 语义、session 抽象 | 新运行时（你已有 LangGraph） |
| [PydanticAI](https://github.com/pydantic/pydantic-ai) | Agent 框架 | **MIT**（需复核） | 类型化依赖注入、结构化输出、**capability 组合**、`defer_loading` 按需加载、Pydantic Evals 评轨迹、OTel 原生 | **capability 组合 + 延迟加载**（正好用于 3.4 工具检索）；**轨迹评测** | 替换现有 Agent 循环 |
| [Letta (MemGPT)](https://github.com/letta-ai/letta) | 记忆 | **Apache-2.0**（需复核） | 有状态 agent、memory blocks、自编辑记忆 | 长期记忆的“块”抽象（Chat 跨会话） | 运行时（重） |
| [Phoenix](https://github.com/Arize-ai/phoenix) | 可观测 | **ELv2**（LICENSE，已核对） | trace/eval UI、OTel | 只可参考 UI/指标设计 | **代码/实现**（ELv2 限制托管服务） |
| [OpenTelemetry GenAI SemConv](https://opentelemetry.io/docs/specs/semconv/gen-ai/) | 规范 | 规范文本 | `gen_ai.*` 属性、span 命名、token 计量 | 统一字段名，便于接任意后端 | —— |

---

## 4. 落地清单（按优先级）

> 每项都给出：参考 → 改动点 → 验收 → 成本。默认**不改现有图结构**，全部走开关。

### P0-1 Chat 流式 + 可恢复（最大体验短板）

- **参考**：LibreChat Resumable Streams（job 记录 delta；重连回放 + sync）；assistant-ui 的 streaming/auto-scroll/retry。
- **设计（简化版，单机）**：
  - 新增 `chat_stream_jobs`（内存 dict 即可，落库后期）：`job_id → {message_id, deltas[], done, error}`；
  - `POST /topics/{id}/chat` 返回 `job_id`，后台线程跑 L3；`GET /chats/{id}/stream?job_id=&after=` 发 SSE；
  - 重连：先发 `sync`（已累积全文），再续发新 delta；结束发 `end`；
  - 前端 `AbortController` 停止 = 调 `POST /chats/jobs/{job_id}/cancel`，后端置 cancel 并结束流。
- **改动**：`api/routes/chat.py`、`agents/chat.py`（改成 generator）、`web/src/stores/chat.ts`、`TopicChatView.vue`；迁移 0005 可后置。
- **验收**：e2e 断线重连不丢字；停止后不落半条消息；`pytest` 不回归。
- **成本**：2–3 天。**风险**：并发/取消边界，需复用 3.0 的取消矩阵。

### P0-2 引用交互：内联锚点 + 证据抽屉

- **参考**：PaperQA2 的 `paper_id + pages + quote`；assistant-ui message parts。
- **设计**：回答文本用 `[[P1]]` 占位；后端返回 `citations[]`（paper_id/snippet/page?）；前端渲染为可点击 chip，打开右侧抽屉显示原文片段与来源。
- **改动**：`agents/chat.py`（生成带锚点文本）、`TopicChatView.vue`（chip + drawer）、`ReportViewer` 复用。
- **验收**：每个 `[[P#]]` 都能定位到 citation；无引用的回答不允许出现锚点。
- **成本**：1 天。

### P0-3 工具轨迹按 step 分组

- **参考**：LibreChat Trace Viewer 的“model → tool → model”分组；assistant-ui tool UI。
- **设计**：`trace` 从扁平 list 改为 `steps: [{step, tool, args_preview, result_preview, ok, duration_ms}]`；前端折叠展示。
- **改动**：`runtime/micro_agent.py`、`chat_messages.trace_json` 结构（兼容旧格式）。
- **验收**：Chat 与周报轨迹都能按 step 展开；事件仍可回放。
- **成本**：0.5 天。

### P1-1 证据分级 + “不可回答”判定

- **参考**：PaperQA2 的 `evidence_relevance_score_cutoff`、`answer_max_sources`。
- **设计**：`_retrieval_l2` 输出每条证据 `relevance ∈ [0,1]`；低于 cutoff 不进 analysis；无证据时 Chat 直接拒答（已做），报告标记 `degraded=insufficient_evidence`（已有类似）。
- **改动**：`agents/hybrid.py` 暴露 scored；`graph/nodes.py` 过滤；`eval/metrics.py` 增 `evidence_precision`。
- **验收**：gold 上 recall 不降；坏证据不再进报告。
- **成本**：1–2 天。

### P1-2 评测：RAGAS 风格指标 + 轨迹断言

- **参考**：RAGAS（faithfulness / context precision / answer relevancy）；Pydantic Evals（tool-call trajectory）。
- **设计**：
  - `eval/judge.py`：LLM-as-judge（可选，无 key 时跳过），带 **校准集**（人工 20 条）；
  - `tests/eval/test_trajectory.py`：断言“检索→校验→报告”关键工具序列；
  - `verify_phase3 --eval` 输出 `faithfulness/context_precision/answer_relevance`。
- **改动**：`eval/`、`scripts/verify_phase3.py`、`docs/implementation/RESULTS-P3.md`。
- **验收**：同一 run 可重复打分；judge 与人工一致率 ≥0.7（小样本）。
- **成本**：2–3 天。

### P1-3 OTel 导出（可选）

- **参考**：Langfuse 数据模型 + OTel GenAI semconv。
- **设计**：`telemetry/otlp.py` 把 `phase_change/tool_call` 投影为 span（白名单字段），`OTEL_EXPORTER_OTLP_ENDPOINT` 开启。
- **验收**：本地 collector 能看到 run→stage→tool 三层 span；不含 prompt。
- **成本**：1–2 天。

### P2-1 重复调用提醒（DSH 2.2）

- 改动 `micro_agent.replan`：warning + 注入提醒，第 3 次才停。**成本**：0.5 天。

### P2-2 压缩剪枝（DSH 2.3）

- 新增 `context_policy`，在 `before_request` 裁工具结果（头尾保留），发 `context_pruned` 事件。**成本**：1 天。

### P2-3 工具延迟加载 / 检索（PydanticAI `defer_loading`）

- `ToolSpec.defer_loading` + `search_tools`；3.4 的“工具检索”直接用。**成本**：1–2 天。

### P2-4 Goal / Subagent 治理（DSH 2.5/2.6）

- `NodeGoal.revision` + CAS；subagent depth 只增不减。**成本**：设计 0.5 天，实现留给 Phase 4。

---

## 5. 许可证与“不借清单”

| 项目 | 许可证 | 结论 |
|---|---|---|
| PaperQA2 | Apache-2.0 | 可借设计；若复制代码需保留 NOTICE |
| assistant-ui / LibreChat / Langfuse / OpenAI SDK / PydanticAI | MIT | 可借设计；复制需版权声明 |
| RAGAS / Letta | Apache-2.0 | 同上 |
| Open WebUI v0.6.6+ | BSD-3 + 品牌条款 | **不复制代码**；只借交互 |
| Phoenix | ELv2 | **不复制**；仅参考 UI/指标 |
| DSH | 本地参考 | 不复制代码；借设计 |

**通用红线**：
1. 不引入新 Agent 框架（LangGraph 已是既定选型）；
2. 不把 React 组件搬进 Vue；
3. 不为“像竞品”增加无测试的功能；
4. 所有借鉴在文档里标注来源与许可证。

---

## 6. 与现有路线图的整合

| 时间点 | 做什么 | 对应 |
|---|---|---|
| **现在（3.4）** | 治理：权限/沙盒/`search_tools`；借 PydanticAI 的 capability 延迟加载 | S16–S19 |
| **3.5** | 评测收尾：RAGAS 指标 + 轨迹断言 + 执行器等价 | S21–S26 |
| **2.3 打磨冲刺**（建议 2 天） | P0-1/2/3：流式、引用抽屉、轨迹分组 | 本文 §4 |
| **P4** | 子 agent / 并行 / 记忆块 | DSH 2.5/2.6 + Letta |

> 建议顺序：**先 3.4/3.5 保完整性，再做 2.3 打磨**；P0 三项可在 3.5 之后两天内完成，直接提升 demo 观感。

---

## 7. 参考链接

**DSH（本地源码）**
- `packages/guard/timeout-policy/src/index.ts`
- `packages/guard/repeat-tool-reminder/src/index.ts`
- `packages/compaction/compaction-tool-result-pruner/src/index.ts`
- `packages/compaction/compaction/src/checkpoint.ts`
- `packages/plan/plan-mode/src/index.ts`
- `packages/subagent/subagent/src/depth.ts`
- `packages/goal/goal/src/types.ts`
- `packages/telemetry/otel/src/event-log.ts`

**GitHub（已读 README/LICENSE）**
- [PaperQA2](https://github.com/Future-House/paper-qa) · [assistant-ui](https://github.com/assistant-ui/assistant-ui) · [LibreChat](https://github.com/danny-avila/LibreChat) · [Resumable Streams](https://www.librechat.ai/docs/features/resumable_streams)
- [Open WebUI License](https://docs.openwebui.com/license/) · [RAGAS](https://github.com/explodinggradients/ragas) · [Langfuse](https://github.com/langfuse/langfuse)
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) · [PydanticAI](https://github.com/pydantic/pydantic-ai) · [Letta](https://github.com/letta-ai/letta) · [Phoenix](https://github.com/Arize-ai/phoenix)
- [OTel GenAI SemConv](https://opentelemetry.io/docs/specs/semconv/gen-ai/)

---

## 8. 变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| 1.0.0 | 2026-10-26 | 首版：DSH 10 个机制 + 11 个 GitHub 项目对比 + P0/P1/P2 落地清单 |
