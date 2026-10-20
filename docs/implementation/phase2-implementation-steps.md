# Phase 2 实施步骤（首版：范围与出口标准，不含实现）

> **文档性质**：Phase 2 的**规范性骨架**。本文件只定义"做什么、什么算做完"，不写实现细节。
> **前置条件**：`phase1.1-scope-and-acceptance.md` §2 的 G1–G6 全绿（当前已绿：`verify_phase1 --online` 13/13、pytest 全绿）。
> **与 Phase 1.1 的分界**：Phase 1.1 = 收口与冻结（F1–F10）；Phase 2 = **让 Harness 真正跑满 S0–S9 与多角色**。
> **版本**：0.1.0（2026-10-20，首版）｜改动需升版本并在此记录。

---

## 1. 入口条件（不满足则不得开工）

| # | 条件 | 验证 |
|---|---|---|
| E1 | Phase 1.1 全部 P0 关闭 | `phase1.1-known-gaps.md` §2/§3 |
| E2 | 基线绿 | `uv run python scripts/verify_phase1.py --online` → 13/13 |
| E3 | 有可回退基线 | 存在 `phase1-rc` 级 commit/tag（由负责人执行） |
| E4 | 缺口登记册已冻结 | 无"未定级"条目 |

---

## 2. 现状清单：12 个显式骨架（Phase 1 遗留）

这些模块**不是缺陷**，是设计上的未实现：调用即 `E_FEATURE_DISABLED`。

| # | 模块 | FEATURE | 目标阶段 | 依赖 |
|---|---|---|---|---|
| 1 | `agents/retrieval.py` | `agents.retrieval` | P2-2 | 检索工具、上下文预算 |
| 2 | `agents/mapper.py` | `agents.mapper` | P2-2 | 论文图谱、embedding |
| 3 | `agents/analyst.py` | `agents.analyst` | P2-2 | reporter、LLM 网关、grounding |
| 4 | `agents/critic.py` | `agents.critic` | P2-2 | analyst、claims 契约 |
| 5 | `agents/chat.py` | `agents.chat` | P3 | 检索 + 会话记忆 |
| 6 | `gateway/breaker.py` | `gateway.breaker` | P2-5 | 网关、`llm_calls` |
| 7 | `tools/builtin/paper_pdf.py` | `tools.builtin.paper_pdf` | P2-3 | 解析流水线 |
| 8 | `tools/mcp_adapter.py` | `tools.mcp_adapter` | P4 | 工具注册表 |
| 9 | `eval/datasets.py` | `eval.datasets` | P5 | 数据源、快照 |
| 10 | `eval/grounding.py` | `eval.grounding` | P2-2 | claims / citations |
| 11 | `eval/judge.py` | `eval.judge` | P5 | 网关、gold 集 |
| 12 | `eval/faultinject.py` | `eval.faultinject` | P5 | 图、守卫 |

---

## 3. Phase 2 工作流（P2-1 … P2-6）

### P2-1 图：S0–S9 全节点 + E1–E13 全边
- **目标**：把 Phase 1 的四阶段线性链升级为 LangGraph 主干十节点，失败分支走条件边。
- **出口标准（可执行）**
  1. `graph/nodes.py` 每个节点有幂等实现，且单测覆盖"成功 + 失败"两条路径；
  2. `edges.py` 的 E1–E13 全部有路由函数（不再 `E_FEATURE_DISABLED`）；
  3. `pytest -q tests/integration/test_graph_edges.py` 绿（≥13 例，每条边一例）；
  4. 同一输入两次运行：状态轨迹一致（除 LLM 采样差异，用 `input_hash` 断言）；
  5. `verify_phase1.py` 的 `runner` 断言升级为"十节点 + 报告"。
- **禁止**：不得为了"跑通"把失败分支改成 `pass`；不得跳过 checkpoint。

### P2-2 多角色 Agent（retrieval / mapper / analyst / critic）+ 报告升级
- **目标**：四个角色可用，报告由"机械折衷"升级为"抽取 + 自查"。
- **出口标准**
  1. 四角色各有 `inputs/outputs` 契约测试与至少 1 条集成用例；
  2. `reporter` 支持 LLM claim 抽取：**每条 claim 必带 citation**，无引用内容进 `unsupported`；
  3. `eval/grounding.py` 实现"claim ↔ 片段"判定，`grounding_rate` 由它计算（不再只看 `support` 字段）;
  4. critic 能产出 `GuardVerdict` 并驱动至少 1 条回退边（E7 或 E9）；
  5. 成本可归因：`llm_calls` 能按 agent 聚合（`agent` 字段非空）。
- **禁止**：角色间共享大 state；每个角色只能通过事件/产物交互。

### P2-3 检索与上下文升级
- **目标**：混合检索（关键词 + 向量）+ 摘要式折叠 + 注入物化。
- **出口标准**
  1. 检索召回在固定查询集上 ≥ Phase 1 基线（记录 recall@10）；
  2. `folding_for("summarize")` 可用，且"折叠后 grounding 不下降"（对照测试）；
  3. 注入上下文**物化进事件**，同 run 重放 prompt 逐字节一致；
  4. `paper_pdf` 工具可下载 + 解析 + 去重（同一 PDF 两次无重复块）。
- **禁止**：折叠时丢失 citation 锚点。

### P2-4 守卫全 15 类 + 提醒式降级
- **目标**：drift / loop / stagnation / timeout / advanced-stagnation 可检测，且动作阶梯完整（`retry(提醒) → degrade → replan → abort`）。
- **出口标准**
  1. 每条守卫有单测：触发条件 + 不触发条件；
  2. loop 守卫对"完全重复的工具调用"先发**提醒**（不改流程），N 次后升级；
  3. 超时由工具级 deadline 产生 `E_SRC_TIMEOUT`，不挂死；
  4. 守卫只返回判决，事件仍由 runner 发（Phase 1 纪律保持）。
- **禁止**：守卫内直接写库/发事件。

### P2-5 运行器升级：异步 + 断点重跑 + 熔断
- **目标**：`POST /run` 立即返回 202 + `run_id`；失败可从 checkpoint 续跑；provider 连续失败触发熔断。
- **出口标准**
  1. `POST /api/topics/{id}/run` → 202（含 `run_id`），状态可轮询；
  2. 中断后续跑：`jobs` 复用同一 `run_id` 不重复写事件（幂等断言）；
  3. `gateway/breaker` 实现半开/闭合三态，连续 N 次失败后 `E_LLM_QUOTA`/降级；
  4. SSE 在异步模式下仍"不重不漏"（沿用 F7 的 5 条契约测试）。
- **禁止**：异步化后丢失 "失败报告四要素"。

### P2-6 前端 Phase 1.2（Vue 3 规范化）
- **目标**：TS + Element Plus + 三独立视图 + 路由 + 浏览器 e2e。
- **出口标准**
  1. `vue-tsc` 无错，`npm run build` 通过；
  2. `/topics`、`/report/:runId`、`/chat` 三条路由可直达（刷新不 404）；
  3. Playwright 走通 `Run → Report` 主路径（截图存档）；
  4. 事件流在页面内实时追加（SSE 客户端重连生效）。
- **禁止**：为了好看而牺牲"事件可见性"。

---

## 4. Phase 2 退出条件（DoD）

| # | 判据 | 命令 |
|---|---|---|
| H1 | 图十节点全绿 | `pytest -q tests/integration/test_graph_edges.py` |
| H2 | 四角色可用 | `pytest -q -k "retrieval or mapper or analyst or critic"` |
| H3 | grounding 由判定器给出 | `pytest -q -k grounding` + 报告字段核对 |
| H4 | 异步 run + 续跑 | `pytest -q -k "async or resume"` |
| H5 | 前端 TS 构建 + e2e | `cd web && npm run build`；`pytest -q tests/e2e` |
| H6 | 基线不回归 | `verify_phase1.py --online` 仍 13/13 |
| H7 | 文档 | 本文件升版 + RESULTS-P2 首版 |

---

## 5. 明确不做（Phase 2）

| 项 | 归属 |
|---|---|
| 多源并行同步与合并口径 | P4 |
| `venue_ids` 解析、OpenAlex 全量回填 | P4 |
| MCP 适配、外部工具生态 | P4 |
| judge / gold 集 / faultinject / datasets | P5 |
| 多用户、鉴权、部署 | 不在论文范围 |

---

## 6. 风险与对策

| 风险 | 对策 |
|---|---|
| 十节点图让调试变慢 | 保留 `--stages intake,ingest,curate,report` 线性回退开关 |
| 多角色引入成本爆炸 | 每角色设 `RunBudget` 份额，超支即 `degrade` |
| grounding 判定器把门槛调松以"通过" | 先冻结 gold 小集（20 条），判定器改动必须重跑同一集 |
| 异步化破坏可观测性 | 所有状态变化仍走 `run_events`，SSE 只做投影 |
