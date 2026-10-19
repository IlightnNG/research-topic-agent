# DeepSeek Harness 参考对照（补充参考，非契约）

> **定位**：本文件是**参考性**设计笔记，不是冻结契约，也不引入任何依赖。
> 用法：实现 Phase 1 的 P3–P5（上下文/多 Agent/周期化/评测）时，先看本表对应行，
> 再决定"照做 / 改造 / 不采纳"，并把结论写进 `design/agent-design-decisions.md`（新增条目）。
>
> **参考对象**：本机 DSH checkout `D:\DeepseekHarness\deepseek-harness`（TypeScript/pnpm monorepo，
> 40+ 包：`session/`、`compaction/`、`context/`、`guard/`、`subagent/`、`schedule/`、`llm/`、`mcp/`）。
> **读了什么**（2026-10-19）：`docs/agent-lifecycle.md`、`packages/session/README.md`、
> `packages/compaction/README.md`、`packages/context/README.md`、`packages/guard/README.md`。
> 其余包只看了目录名，**未读实现**——因此本文件的结论限定在"架构模式"层面，不含代码细节。
>
> **边界**：DSH 是**面向代码仓库**的 agent harness；本项目是**文献研究** agent。技术栈（TS/Node vs
> Python/uv/LangGraph）不同，**不 fork、不移植、不引入其依赖**。引用/借鉴前须确认其 `LICENSE`
> 与 `THIRD_PARTY_NOTICES.md` 的许可范围。

---

## 0. 一句话结论

> DSH 对我们**有用的是"失败路径与上下文治理"的架构模式**（不是功能，也不是代码）；
> 对**检索/报告质量没有直接帮助**——那由我们的数据源、去重口径、grounding 与评测决定。

| 维度 | 是否有提升 | 依据 |
|---|---|---|
| 鲁棒性（少崩、可恢复、可观测） | **是** | session 的 checkpoint 策略 + 守卫族 + 生命周期顺序保证 |
| 上下文治理（长任务不爆窗、可复现） | **是** | compaction 的"先剪枝后摘要 + 双触发"；注入上下文"物化进历史" |
| 功能完整性（我们缺的模块） | 部分 | projection/format 链、schedule/jobs 有借鉴价值 |
| 检索/报告**效果** | **否** | 那是数据与评测问题，harness 不决定 |

---

## 1. 模式对照表（按采纳优先级排序）

### P0-1 事件双通道：durable log 与 live channel 分离

| | |
|---|---|
| **DSH 做法** | `session/event` 存放**可重放事实**；`agent/*`（status、inbox、assistant-stream chunk）是**实时协调**通道，chunk 帧是瞬态的，"replay 读持久结算结果"。lifecycle 文档明确："SDK 需要可重放数据就消费 `session/event`" |
| **我们现状** | 已同构：`run_events` 是真相源，SSE 只做通知（`runtime/events.py` 的"先落库后广播"） |
| **差距** | 我们的 SSE 尚未实现（1.15）；**没有**"chunk 帧不落库"的显式约定 |
| **建议** | 1.15 实现 SSE 时写死：流式 token 帧**不进** `run_events`，只发最终 `llm_call` 事件（含 usage/cost）；否则事件表会被流式帧撑爆且破坏回放语义 |
| **风险** | 若前端要"打字机"效果，需要独立的内存通道，不能复用事件表 |

### P0-2 三处持久化检查点（比"跑完再存"强）

| | |
|---|---|
| **DSH 做法** | `session-checkpoint-policy`：在**下一个动作之前**，把"模型请求、顶层工具副作用、已完成的 step"落盘 |
| **我们现状** | 阶段边界写 `phase_change`；LLM 调用写 `llm_calls`；但**工具副作用（抓取/PDF 落盘）与事件不在同一事务** |
| **差距** | 崩溃窗口：PDF 已落盘但事件没落 → 重跑时"看不到自己做过什么"（Phase 0 静默错误类） |
| **建议** | 1.12–1.16 接入阶段函数时统一"**副作用 + 事件同事务**"（`emit_event(conn=...)` 已支持）；LLM 调用前先落 `llm_call` 的 request 事实（或至少 request_sha） |
| **风险** | SQLite 单写者下事务变长 → 用"每阶段一个事务"而非"整轮一个事务" |

### P0-3 上下文注入必须"物化进历史"（可复现的关键）

| | |
|---|---|
| **DSH 做法** | `context/` 组把 workspace 指令、`@file` 引用等**作为 user-role 消息写进会话历史**，"因此能持久、重放、像普通内容一样被压缩" |
| **我们现状** | `context/slots.py` 规划为"槽位注入"，但**未决定是否落库** |
| **差距** | 若注入是"运行时拼进 prompt"，同一 run 重跑时 prompt 可能不同 → F8（缓存即复现性）失效 |
| **建议** | P3 实现上下文时：**注入内容先成为 `run_events` 里的 `message` 事件（或 artifact 记录），再由事件组装 prompt**；报告脚注可引用注入来源 |
| **风险** | 事件体积增大 → 注入内容只存引用（文件路径/片段 hash），正文放文件 |

### P1-1 compaction：先剪枝、后摘要、双触发、原地重试

| | |
|---|---|
| **DSH 做法** | 三条流水线：① `tool-result-pruner` **先**裁掉超大工具输出（便宜）；② `compaction-basic` 把旧历史压成摘要；③ 触发有两处——`agent/pre-step`（请求构造前的 token 水位）与 `agent/request-error`（provider 报上下文溢出）；**恢复在当前 step 内重试，且不重复 pre-step / 用户准入 / assembly**，只有当"替换代次前进"时才重试 |
| **我们现状** | `context/budget.py` 只有 `fit()` 截断；无摘要、无双触发、无"重试不重做" |
| **差距** | 长对话/长报告会硬截断丢证据；上下文溢出只能整轮失败 |
| **建议** | 1.13 按此顺序实现：`prune(snippets) → fit() → summarize()`；两个触发点：①阶段开始前按 token 水位预压；②`E_LLM_5XX` 且 provider 声称 context overflow 时降级重试一次（`max_tokens` 不变、历史摘要版） |
| **风险** | 摘要有损 → 必须保留 "citation 锚点"（我们已在 Phase 0 定过：别截掉引用片段） |

### P1-2 守卫：先"提醒"，再"改策略"

| | |
|---|---|
| **DSH 做法** | `guard/repeat-tool-reminder`：发现**完全重复的工具调用**时，**提醒模型换方法或收尾**（advisory），而不是直接终止；`timeout-policy`：给声明了时限的工具调用设**截止时间**，超时返回**明确错误给模型**而非挂死 |
| **我们现状** | `NoProgressGuard` 直接给 `degrade`；`LoopGuard`（P2）设计为 `replan→abort`；超时只由网关超时兜底 |
| **差距** | 我们的动作偏"重"：一次重复就 degrade，可能误伤；缺少"把超时作为可读错误回给模型"的通道 |
| **建议** | P2 实现 loop 守卫时增加一档 `retry(带提醒)` 再升级到 `replan`；工具层为每个工具加 `timeout_s` 声明，超时产生 `tool_call(ok=false, error_code=E_SRC_TIMEOUT)` 事件而不是抛异常中断整轮 |
| **风险** | 提醒会多花一次 token；需在评测里量化"提醒是否真的让模型换策略" |

### P1-3 投影（projection）：事件 → 当前值 + 投影缓存

| | |
|---|---|
| **DSH 做法** | `session-projection`：把事件折叠成"当前整体值"（stats、turn outline 等），并有 `session-projection-cache` 持久化检查点，冷读时跳过全量日志 |
| **我们现状** | `reports`/`claims`/`metrics` 是直接落表；`/api/metrics/summary` 计划现场聚合 |
| **差距** | 现场聚合在 P5 会变慢；且"事件→指标"的口径散落在查询里 |
| **建议** | P5 把 5 项指标做成**投影**（输入 `run_events`，输出 `metrics` 行，可重算=幂等 replace），并加 `projection_cache`（key=run_id+metric，value+generation） |
| **风险** | 多一层缓存 = 多一处一致性风险；沿用 ADR-0005 的 `metrics` 幂等约束 |

### P2-1 格式版本链（frozen adjacent migrations）

| | |
|---|---|
| **DSH 做法** | `session-format-v0→v1→v2→v3→v4`，**每个已发布版本有冻结解码器 + 相邻迁移**，不跳版本 |
| **我们现状** | `run_events.schema_version = "1.0"`，`store_meta.schema_version = "1.0"`，**没有迁移链设计** |
| **差距** | P5 要"回放 4 周前的 run"时，旧事件可能解析失败；P2 加字段会重演 Phase 0 的 schema 漂移 |
| **建议** | 定一条纪律：**任何事件/表结构变更 → 新 schema_version + 冻结旧解码器 + 相邻迁移函数**（可用 `migrations/` + `event_codec/` 小模块，不引入 alembic 之外的东西）；至少在 ADR 里写清"如何读旧事件" |
| **风险** | 硕士项目里做 4 个版本过度设计——**先只定"v1 冻结 + v2 变更流程"** 两个格 |

### P2-2 生命周期顺序：一个权威准入闸门 + 有界并发

| | |
|---|---|
| **DSH 做法** | 每个 step：claim 输入 → assemble prompt → `agent/pre-step`（**权威** accept/reject）→ 请求 → 工具分类（`executionMode`）→ **barriers + bounded rolling pool**（有界滚动并发，启动前重新分类）→ 结算 → `step/end` |
| **我们现状** | `runner` 逐阶段执行，无准入闸门、无工具并发控制 |
| **差距** | 阶段失败时没有"准入即拒绝"的早期拦截；未来并发抓取可能打爆源 API |
| **建议** | 1.12+ 给每个阶段加 `admit(ctx) -> bool`（守卫裁决前置）；抓取/解析并发用**信号量 + 有界批次**（我们已有 `per_page`/限速） |
| **风险** | 过度抽象；P1 阶段只需"开始前跑一次 GuardRail + 信号量"即可 |

---

## 2. 明确**不采纳**的（避免范围膨胀）

| DSH 项 | 不采纳原因 |
|---|---|
| Cordis 插件体系 / 服务-提供者-消费者分层 | 绑定 TS/Node 运行时；我们用 FastAPI + 显式模块，收益不抵迁移成本 |
| `session-format` 多版本链（4 个版本） | 我们只有 1 个消费方（自己），先冻 v1 + 变更流程即可 |
| telemetry / OTel 上报 | 单机单人项目，`logs/app.jsonl` + `run_events` 足够；P5 再谈 |
| session 标题（LLM 生成） | 与文献 agent 无关 |
| 图片 offload / browser-use / computer-use | 域外功能 |
| 把 DSH 当底座 fork | 技术栈不兼容、许可与论文原创性风险、时间不允许 |

---

## 3. 采纳路线（与 Phase 1 排期对齐）

| 优先级 | 动作 | 落点 | 预估 |
|---|---|---|---|
| **P0-1** | SSE 流式帧不落事件表；只落结算事件 | 1.15 | 0.5 h（设计已定） |
| **P0-2** | 阶段"副作用 + 事件同事务"；LLM 调用前落 request 事实 | 1.12–1.16 | 每阶段 0.5 h |
| **P0-3** | 注入上下文物化进事件历史再组装 prompt | P3 | 2 h（含回放测试） |
| **P1-1** | compaction 三段式 + 双触发 | 1.13 | 4–6 h |
| **P1-2** | loop 守卫加 `retry(提醒)` 档；工具级 timeout 声明 | P2 | 3 h |
| **P1-3** | 指标做成可重算投影 + 投影缓存 | P5 | 3 h |
| **P2-1** | "v1 冻结 + 变更流程" 两条纪律进 ADR | 1.19 收口 | 1 h（写文档） |
| **P2-2** | 阶段准入闸门 + 有界并发 | 1.12+ | 2 h |

> **时间盒**：本轮（Phase 1 剩余）只做 P0-1/P0-2 与 P2-1 的**文档纪律**；
> P0-3 / P1-* 属于 P2–P5，**现在不做**（否则 1.12–1.19 做不完）。

---

## 4. 对论文的用法（合规且加分）

- **Related work 写法**："我们的 harness 设计借鉴了生产级 coding agent 的若干模式（durable log 与 live channel 分离、checkpoint-before-next-action、prune-then-summarize 的上下文压缩），并针对**文献研究**场景做了三点改造：①领域化的证据锚点保留；②周期化 run 的幂等重放；③面向 grounding 的引用不可丢失约束。"
- **可做的对照实验**：同一批 topic 上，`budget-only` 与 `prune→summary` 两种上下文策略的 grounding/成本对比（P5 评测的一行）。
- **不要写**："基于 DeepSeek Harness 构建"——我们**没有**使用其代码；写了反而不实。

---

## 5. 已知未验证（诚实边界）

1. 本文件只读了 5 份 README/生命周期文档，**未读实现**，因此"DSH 怎么做"的细节以文档表述为准；
   若后续要照搬某个具体策略（如 compaction 的摘要选择算法），需再读对应包源码并在此追加 §6。
2. DSH 的 `LICENSE` / `THIRD_PARTY_NOTICES.md` 未逐条核对；**若计划引用代码片段，必须先确认许可**。
3. 上述"预估工时"是经验值，未实测。

---

## 6. 后续追加区（读源码后再补）

- [ ] `packages/compaction/compaction-basic`：摘要选择算法（保留什么、丢弃什么）
- [ ] `packages/guard/repeat-tool-reminder`：重复判定键（是否含参数）
- [ ] `packages/session/session-projection`：投影单位契约与 generation 语义
- [ ] `packages/subagent`：输入输出契约与隔离边界（P3 用）
- [ ] `packages/schedule` + `jobs`：定时去重与补偿（P4 用）
