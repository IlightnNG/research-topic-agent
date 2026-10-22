# Phase 2 —— 规范、模块判据与实施步骤

> **文档性质**：**规范性文件（冻结契约）**。Phase 2 的"做什么 / 什么算做完 / 按什么顺序做"以本文件为唯一判据。
> **版本**：**3.0.0（已收尾）**（2026-10-21，重构版；替代 0.1.0 首版）｜改动必须升版本并在 §11 记录。
> **前序**：`phase1.1-scope-and-acceptance.md`（收口纪律）、`phase1.2-frontend-spec.md` v1.3.0（已收尾）、`phase1.1-known-gaps.md`（缺口登记册）。
> **入口基线**（Phase 1.2 收尾实测）：`pytest 260 例全绿`、`verify_phase1 --online 13/13`、`vue-tsc 0 error`、`playwright 5 passed`、OpenAPI 21 路径。

---

## 0. 目标、硬规则与"完成"的定义

### 0.1 一句话目标

把 Phase 1 的**线性四阶段骨架**升级为**完整的十节点 Agent 图 + 多角色协作 + 可评测的 grounding**，让"周报"从"证据清单"变成"有抽取、有自查、有分节、可追溯"的交付物。

### 0.2 三条硬规则（沿用 Phase 1.1）

| 规则 | 内容 | 违反后果 |
|---|---|---|
| **R1 范围冻结** | 只做 §7 的 S1–S14；新想法进 §6 backlog | 范围蔓延、判据失效 |
| **R2 红项优先** | 先跑基线，只修 P0；禁止"顺手优化" | 引入回归 |
| **R3 单步可逆** | 每步结束必须：全量 `pytest` 绿 + `ruff` clean + `verify_phase2` 对应断言绿 + 文档更新；否则回滚该步 | 不可回退 |

### 0.3 反向定义（阶段何时结束）

> **Phase 2 结束 ⇔ §9 的 H1–H10 全绿，且 §5 中所有 P0 关闭。**
> 此后新发现的问题：一律登记 → 分级 → 排入 Phase 3 或 1.2.x 打磨，**不重新打开 Phase 2**。
> "未实现"不是缺陷，是 backlog；只有"承诺了却没做到"和"数据/契约错误"才是 P0。

---

## 1. 入口条件（不满足不得开工）

| # | 条件 | 验证 |
|---|---|---|
| E1 | Phase 1.2 已收尾 | `phase1.2-frontend-spec.md` §15 结论为 COMPLETE |
| E2 | 基线全绿 | `pytest -q`、`verify_phase1.py --online 13/13`、`npm run test:e2e` |
| E3 | 有可回退基线 | `git tag phase1.2-rc1`（由负责人执行） |
| E4 | 缺口册已冻结 | `phase1.1-known-gaps.md` 无"未定级"条目 |
| E5 | 密钥/配额就绪（可选但推荐） | OpenAlex key、LLM key；缺失时相关步骤必须能**显式降级**而非跳过验证 |

---

## 2. 基线现状（P2 起点）

| 维度 | 现状 |
|---|---|
| 数据链路 | arXiv 真实抓取 → 去重 → 引用投影 → 证据卡 → 报告（degraded 判定）✅ |
| 图 | 只有 `intake→ingest→curate→report` 线性链；`E1–E13` 常量存在但回退边未实现 |
| Agents | 仅 `base` + `reporter`；5 个角色为显式骨架（`E_FEATURE_DISABLED`） |
| 上下文 | 只有 `truncate` 折叠；注入未物化 |
| 守卫 | 只有 budget + no-progress；其余 13 类为骨架 |
| 运行器 | 异步 202（已建实体）+ abort；pause/resume/inject 为 501；无续跑、无熔断 |
| 检索 | 无 hybrid、无 rerank；`paper_pdf` 为骨架 |
| 评测 | 只有 metrics/export；grounding/judge/datasets/faultinject 为骨架 |
| 前端 | Vue3+TS 三页已完成；十阶段可视化与干预按钮未做 |

**12 个骨架模块（P2/P3/P5 目标）**：`agents.{retrieval,mapper,analyst,critic,chat}`、`eval.{datasets,grounding,judge,faultinject}`、`gateway.breaker`、`tools.{mcp_adapter,builtin.paper_pdf}`。

---

## 3. 模块目标与验收判据（M1–M8）

> 每个模块给：**目标 / 增量 / 完成判据（可执行）/ 重难点 / 禁止项 / Out-of-Scope / 依赖**。

### M1 图（Graph）—— 十节点主干

| 项 | 内容 |
|---|---|
| **目标** | S0–S9 十节点可跑；E1–E13 条件边可走；失败分支可回退 |
| **增量** | `graph/nodes/` 十个节点（intake/scope/retrieval/parse/normalize/mapping/analysis/critique/report/evaluate）、`edges.py` 全边路由、`checkpoint` 续跑 |
| **完成判据** | ① `pytest -q tests/graph` 绿且**每条边 ≥1 例**（含"不触发"反例）；② 一次 run 覆盖 10 个 `phase_change start`；③ 失败注入后走对应回退边且最终 `failed` 带四要素；④ `verify_phase2.py --graph` PASS |
| **重难点** | 节点幂等（崩溃重跑不重复副作用）；状态只放引用不放正文；条件边不得"沉默降级" |
| **禁止** | 把回退边改成 `pass`；节点内写库后不发事件；共享大 state |
| **OOS** | 子图、并行分支、动态图 |
| **依赖** | 无（P2 第一步） |

### M2 Agents —— 多角色协作

| 项 | 内容 |
|---|---|
| **目标** | retrieval / mapper / analyst / critic 四角色可用；reporter 升级为"抽取 + 自查" |
| **增量** | 四角色实现 + `agent` 维度成本归因；reporter 支持 claim 抽取与引用约束 |
| **完成判据** | ① 每角色有 `inputs/outputs` 契约测试 + 1 条集成用例；② `llm_calls.agent` 非空且可按角色聚合成本；③ **每条 claim 必带 citation**，无引用内容进 `unsupported`；④ critic 能产出 `GuardVerdict` 并驱动至少 1 条回退边；⑤ M7 gold 集上 `grounding ≥ 0.8` |
| **重难点** | 角色间只通过"事件 + 产物"交互；抽取 prompt 的 schema 必须严格（`chat_json` + 校验失败重试一次） |
| **禁止** | 角色共享可变 state；把"没找到证据"写成 supported；用 LLM 自评代替判定器 |
| **OOS** | `agents.chat`（P3）；角色并行（P4） |
| **依赖** | M1、M7 的 gold 集 |

### M3 上下文（Context）—— 折叠与物化

| 项 | 内容 |
|---|---|
| **目标** | 长上下文可压（摘要折叠）；注入内容**物化进事件**，同 run 重放 prompt 逐字节一致 |
| **增量** | `folding.summarize`（先剪枝后摘要）、`slots` 与事件桥接、预算联动 |
| **完成判据** | ① 固定 fixture 折叠后 token 下降 ≥40%，且 gold 集 grounding **不下降**；② 同一 run 回放 prompt `sha` 相同；③ 折叠不得切断 citation 片段；④ `pytest -k "folding or context"` 绿 |
| **重难点** | "便宜的先做"（先 prune 再摘要）；有损但可解释；重试不重做前置阶段 |
| **禁止** | 折叠截断引用片段；注入内容只存在内存 |
| **OOS** | 分层折叠、跨 run 记忆 |
| **依赖** | M2、M6 |

### M4 守卫（Guards）—— 全 15 类 + 动作阶梯

| 项 | 内容 |
|---|---|
| **目标** | 漂移/循环/停滞/超时/预算可检测；阶梯 `retry(提醒) → degrade → replan → abort` |
| **增量** | 13 个守卫 + `GuardRail` 取最重动作 + 提醒式 retry |
| **完成判据** | ① 每个守卫**两条**测试：触发 + 不触发；② 阶梯顺序单测（同一输入不得越级）；③ 守卫只返回判决、不写事件；④ 超时由工具 deadline 产生 `E_SRC_TIMEOUT`，run 不挂死 |
| **重难点** | 误报会打断正常流程（Phase 1 曾把"每步产出 1"误判为停滞）；阈值可配且写进 ADR |
| **禁止** | 守卫内写库/发事件；为通过测试放宽阈值 |
| **OOS** | 学习型阈值 |
| **依赖** | M1 |

### M5 运行器（Runtime）—— 续跑、熔断、干预

| 项 | 内容 |
|---|---|
| **目标** | 异步可控：断点续跑、失败可重试、熔断可降级、人工干预可用 |
| **增量** | `resume`（从 checkpoint）、`breaker`（三态）、`pause/resume/inject` 实装、`jobs` 状态机 |
| **完成判据** | ① 中断后 `resume` 不重复写事件（`seq` 连续、无重复 `phase_change start`）；② 连续 N 次失败 → 熔断打开并降级；③ pause 在阶段边界生效，inject 的提示词进入下一阶段 prompt（事件可见）；④ `pytest -k "resume or breaker or pause"` 绿 |
| **重难点** | 幂等 + 状态机；熔断半开与恢复；干预不能破坏 `input_hash` 可复现性 |
| **禁止** | 用"重跑整轮"冒充续跑；熔断后静默返回空 |
| **OOS** | 多进程 worker、队列中间件 |
| **依赖** | M1、M4 |

### M6 检索与工具 —— hybrid + 全文

| 项 | 内容 |
|---|---|
| **目标** | 关键词 + 向量混合检索、rerank、PDF 全文可用 |
| **增量** | `retrieval` 工具（hybrid + rerank）、`paper_pdf` 实装、`mcp_adapter`（可选） |
| **完成判据** | ① 固定 20 条查询集 `recall@10` ≥ 关键词基线 +10pp；② 3 篇真实 PDF 解析成功且块 token ≤ 预算；③ 同一 PDF 两次入库无重复块；④ `pytest -k "retrieval or paper_pdf"` 绿 |
| **重难点** | 换 embedding 需重建（ADR-0004）；chunk 与 citation 对齐；rerank 成本 |
| **禁止** | 为提升指标换测试集；未重建索引就换模型 |
| **OOS** | 跨语言增强、外部搜索 API |
| **依赖** | M2、M3 |

### M7 评测（Eval）—— 判定器与 gold

| 项 | 内容 |
|---|---|
| **目标** | grounding 由**判定器**给出（不再只看 `support`）；有 gold 集、judge、故障注入 |
| **增量** | `eval/grounding`（claim↔片段判定）、`eval/datasets`（20 条 gold）、`eval/judge`（LLM 评审 + κ）、`eval/faultinject`（3 类） |
| **完成判据** | ① gold 上 grounding precision/recall ≥0.8；② judge 与人工标注一致率 κ ≥0.6；③ 3 类故障（空检索/坏产物/超时）走降级且事件完整；④ `pytest -k "grounding or judge or faultinject"` 绿 |
| **重难点** | **判定器不得为了通过而放宽**（gold 冻结，改动需重跑全量）；judge prompt 稳定性 |
| **禁止** | 改 gold 迁就实现；同一模型既生成又判定而不声明 |
| **OOS** | 大规模人工标注、跨模型矩阵 |
| **依赖** | M2 |

### M8 前端（Web）—— 适配十节点与干预

| 项 | 内容 |
|---|---|
| **目标** | 十阶段可视化；报告按 `sections` 真分节；干预按钮可用；类型由 OpenAPI 生成 |
| **增量** | 阶段条支持 10 阶段；真分节渲染；pause/resume/inject UI；`types.gen.ts` |
| **完成判据** | ① 一次 run 的 10 阶段全部显示且状态正确；② 报告按 `sections` 渲染（不再派生抑制）；③ 干预按钮可用且状态回写；④ `vue-tsc` 0；`npm run test:e2e` ≥8 例；⑤ F13 纪律仍 PASS |
| **重难点** | 阶段多的信息密度；干预后的状态一致性 |
| **禁止** | UI 内做业务判断；为动画破坏可访问性 |
| **OOS** | 移动端、深色主题、i18n |
| **依赖** | M1/M5/M7 |

---

## 4. 模块依赖图（决定步骤顺序）

```
M1 图 ──> M3 上下文 ──> M6 检索
  │           │            │
  ├──> M4 守卫 ──> M5 运行器
  │
  └──> M2 Agents ──> M7 评测 ──> M8 前端（最后适配）
```

---

## 5. 缺陷分级与处置（沿用并强化）

| 级别 | 定义 | 处置 |
|---|---|---|
| **P0** | 出口断言红 / 数据错误 / 契约违反 / **指标造假** | 必须修，本阶段关闭 |
| **P1** | 有 workaround，影响体验 | 步骤内选做 |
| **P2** | 未实现功能、性能、美化、重构 | 进 §6 backlog |

**P2 期新增两条纪律**

1. **指标类修复必须附 gold 集重跑结果**（否则视为调参而非修复）；
2. **守卫/边/判定器改动必须同时补"不触发（反例）"测试**（Phase 1 教训：只测触发会放过误报）。

---

## 6. 缺口与 Backlog 登记（P2 起点）

| ID | 项 | 级别 | 归属 |
|---|---|---|---|
| G-17 | F5/F7/F8/F9 仅有手动验证 | P1 | 1.2.x / M8 |
| G-18 | `sections` 为 claims 派生 | P2 | M8（随 M2 落地真分节） |
| G-19 | 前端手写类型（未接 `types.gen.ts`） | P2 | M8 |
| G-20 | 生产部署缺 `try_files` | P2 | 部署清单 |
| P2-01 | 十节点未实现 | — | M1 |
| P2-02 | 五个 agent 骨架 | — | M2 |
| P2-03 | 折叠仅 truncate | — | M3 |
| P2-04 | 13 类守卫未实现 | — | M4 |
| P2-05 | 无续跑/熔断/干预 | — | M5 |
| P2-06 | 无 hybrid 检索、无 PDF 工具 | — | M6 |
| P2-07 | grounding/judge/gold/faultinject 为骨架 | — | M7 |

> **新增缺口流程**：现象/复现命令/影响面 → 定级 → 归属 → 若 P0 立即排入当前批次。

---

## 7. 实施步骤 S1–S14

> 每步"可独立验收 + 可回滚"。**每轮只做一个 S**，结束输出三件套：**门禁结果 / 文件清单 / 一句英文 commit**。

| 步 | 模块 | 目标 | 主要产物 | 关键门禁 | 预估 |
|---|---|---|---|---|---|
| **S1** ✅ | M0 | 基线冻结 | `scripts/verify_phase2.py`（12 探针）、`RESULTS-P2.md`、`phase2-baseline-report.json` | `verify_phase2 --offline` → **3/12 PASS，9 RED**（RED = S2–S12 目标） | 0.5 d |
| **S2** ✅ | M1 | 十节点主干 | `graph/nodes.py`（Phase2Nodes）、`runtime/graph_runner.py`、state 增 3 字段 | 一次 run 覆盖 **10 个 phase_change start/end**；`tests/graph` 35 例绿 | 1.5 d |
| **S3** ✅ | M1 | E1–E13 条件边 | `edges.py`：`EdgeRule` + `RULES`(13) + `route_after` 优先级 + `backoff_edge` 返回动作 | 13 条边**各有触发 + 不触发**用例；E12 优先级最高 | 1.5 d |
| **S4** ✅ | M1 | checkpoint 续跑 + 幂等 | `run_graph(resume=True)`、`SimulatedCrash` 注入、事件 `dedupe_key` | 崩溃后 resume：10 阶段各 1 次 start，无重复 | 1.0 d |
| **S5** ✅ | M2 | retrieval/mapper | `agents/retrieval.py`（词面打分 + hint 过滤）、`agents/mapper.py`（簇 + 孤儿） | 行为探针 PASS；4 例单测 | 1.5 d |
| **S6** ✅ | M2/M7 | analyst/critic + 判定器 + gold + judge | `analyst`（确定性/LLM 双路径）、`critic`、`grounding`、`datasets`(20)、`judge`(κ) | gold **acc=1.00**、κ=1.00；claim 全带引用 | 2.0 d |
| **S7** ✅ | M3 | 摘要折叠 + 注入物化 | `SummarizeFolding`（首句 + 数字/引用句）、`slots.materialize_slots()`（事件落库 + `has_dedupe` 幂等） | 折叠后 token 明显下降且保留数字句；同槽重复 0 新增 | 1.5 d |
| **S8** ✅ | M4 | 15 类守卫 + 阶梯 | `graph/guards.py`：G1–G15 + `GuardRail`（取最重动作）+ `RepeatToolGuard`（先提醒后升级） | 15 类各触发/不触发；阶梯不越级；提醒→replan 升级 | 1.5 d |
| **S9** ✅ | M5 | 续跑/熔断/干预 | `gateway/breaker.py`（三态）、`control` 的 pause/inject、API `pause/resume/inject` 实装、`pause` 在阶段边界生效 | 熔断三态可测；pause→paused→resume→succeeded；inject 写回 `runs.focus_hint` 并留事件 | 2.0 d |
| **S10** ✅ | M6 | hybrid + rerank + PDF | `agents/hybrid.py`（0.6 关键词 + 0.4 char-3gram）、`eval/retrieval_bench.py`（20 查询/40 语料）、`tools/builtin/paper_pdf.py`（分块 + 幂等哈希） | **keyword 0.75 → hybrid 1.00（+25pp）**；同 PDF 二次解析 0 新块 | 1.5 d |
| **S11** ✅ | M7 | judge + faultinject + datasets | `eval/judge.py`（LLM + 回落 + κ）、`eval/faultinject.py`（3 类，检查点触发）、`eval/datasets.py`（20 条 gold 冻结） | **κ=1.00**（90% 正确 judge 仍 ≥0.6）；3 类故障：空检索降级 / 坏产物留痕 / 超时失败 | 1.5 d |
| **S12** ✅ | M8 | 前端适配 | 十阶段时间线（中文标签 + 未开始态）、真实分节（`reports.sections_json` + 迁移 0003）、暂停/继续/注入按钮、`types.gen.ts`（OpenAPI 生成） | **e2e 8 例全绿**、`vue-tsc` 0 error、build ✓ | 1.5 d |
| **S13** ✅ | M5/M7 | 成本归因 + 观测 | `cost_by_agent` / `calls_by_agent` / `agents_used`；`metrics(scope='agent')` 落库 | 两角色各 0.25/0.05 正确归因并落库 | 1.0 d |
| **S14** ✅ | M0 | 收尾 | H1–H10 全跑、`RESULTS-P2.md` 定稿、`verify_phase2` **12/12** | 全绿 + 归档（2026-10-21） | 0.5 d |

**合计约 18.5 人日（≈3.5 周）**，建议 5 批执行（§8）。

### 每步通用门禁

| 层 | 命令 | 期望 |
|---|---|---|
| 后端测试 | `uv run pytest -q` | 全绿（只增不减） |
| 静态 | `uv run ruff check .` | clean |
| 基线 | `verify_phase1.py --online`；`verify_phase2.py --offline` | 13/13；本阶段断言全绿 |
| 前端（M8 起） | `cd web && npm run typecheck && npm run build` | 0 error |
| 文档 | 本文件该步追加"完成记录"一行 | 有日期与证据 |

### 每步禁止项（通用）

1. 不得为"跑通"把失败分支改成 `pass`；
2. 不得调松阈值/换测试集来通过指标；
3. 不得在节点/守卫里重复取数（**数据只有一个入口**，见 §10-1）；
4. 不得跨步提交（一步一个 commit）。

---

## 8. 对话分批计划（执行用）

| 批次 | 步骤 | 轮次 | 说明 |
|---|---|---|---|
| **批 1（图）** | S1 → S2 → S3 → S4 | 4–5 | 先把十节点与边打通 |
| **批 2（角色 + 判定）** | S5 → S6 → S7 | 4–5 | 报告质量来源：角色/抽取/grounding/折叠 |
| **批 3（守卫 + 运行时）** | S8 → S9 | 3–4 | 可打断、可续跑、可熔断 |
| **批 4（检索 + 评测）** | S10 → S11 | 3–4 | hybrid、PDF、judge、故障注入 |
| **批 5（前端 + 收尾）** | S12 → S13 → S14 | 3–4 | 只适配契约，不改后端语义 |

> 每轮开始先跑基线（约 30 秒），结束输出三件套；跨批次不合并。

---

## 9. 出口标准 H1–H10

| # | 判据 | 命令 | 期望 |
|---|---|---|---|
| H1 | 十节点全绿 | `pytest -q tests/graph` | 全绿，含每条边两例 |
| H2 | 四角色可用 | `pytest -q -k "retrieval or mapper or analyst or critic"` | 全绿 |
| H3 | grounding 由判定器给出 | `verify_phase2.py --grounding` | gold 上 P/R ≥0.8 |
| H4 | 续跑与熔断 | `pytest -q -k "resume or breaker"` | 全绿 |
| H5 | 干预可用 | `pytest -q -k "pause or inject"`；e2e | 全绿 |
| H6 | 检索提升 | `verify_phase2.py --retrieval` | recall@10 ≥ 基线+10pp |
| H7 | 评测闭环 | `pytest -q -k "judge or faultinject or datasets"` | κ ≥0.6；3 类故障通过 |
| H8 | 前端适配 | `cd web && npm run typecheck && npm run build`；`npm run test:e2e` | 0 error；≥8 例 |
| H9 | 基线不回归 | `verify_phase1.py --online`；`pytest -q` | 13/13；全绿 |
| H10 | 文档 | 本文件 §11 + `RESULTS-P2.md` | 数字与命令一致 |

---

## 10. 经验教训适配（来自 Phase 1 / 1.2 的真实踩坑）

> 本节是**硬约束**，评审时逐条对照代码。

| # | 教训（真实发生过） | 本阶段约束 |
|---|---|---|
| 1 | `focus_hint` 只在 stage 过滤，`_persist_report` 又各自 `_load_cards()` → **功能半生效** | **单一取数入口**：同一份数据只能有一个加载函数，下游一律传参 |
| 2 | 异步 202 先返回、run 行在线程里才建 → **幽灵 run** | **先建实体再异步**：202 时 run 必须可查；锁冲突在请求线程内判 |
| 3 | `jobs.start` 在 `try` 外 → 异常时**锁不释放** | 资源获取与释放必须在同一 `try/finally` |
| 4 | 迁移 `add_column` 碰上 `create_all` → **duplicate column** | 迁移必须**幂等**（先 `inspect` 再 ALTER） |
| 5 | 守卫拿"单步新增"比较 → **误报停滞** | 守卫必须定义"增长"口径，并测"不触发" |
| 6 | 报告 `n_claims` 与指标 `claims` 不一致（claims 未落表） | **一致性门**：报告 claims 数必须等于 `metrics.claims_total` |
| 7 | e2e 报 31s 超时，实为"报告永不加载" | **SSE 必须能降级**（轮询兜底）；失败先看截图 |
| 8 | 前端 1 MB 单包、页面样式各自为政 | 按需引入 + 令牌/工具类；页面 ≤300 行、style ≤80 行 |
| 9 | 中文文件被 PowerShell 管道写坏；`.pth` 用 UTF-8 路径致解释器崩溃 | 中文文件只用 `write`/`edit`；venv 路径暴露用 **ASCII junction + ASCII `.pth`** |
| 10 | 缓存/浏览器/模型默认落 C:（空间不足） | `UV_CACHE_DIR`/`HF_HOME`/`PLAYWRIGHT_BROWSERS_PATH`/`TEMP` 全在 D: |

---

## 11. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| 3.0.0 | 2026-10-21 | **阶段收尾**：S12/S13/S14 完成；生产入口切到十节点图；真实分节落库（迁移 0003）；成本按 agent 归因；`verify_phase2` **12/12**、e2e **8/8**、pytest **354 例**全绿 |
| 2.4.0 | 2026-10-21 | S10/S11 完成：混合检索（+25pp recall）、PDF 工具幂等、judge/κ、故障注入接入图；修掉"条件边被后续节点覆盖"与"timeout 在进入时抛"两个缺陷；`verify_phase2` **11/12**（仅剩 S12 前端） |
| 2.3.0 | 2026-10-21 | S8/S9 完成：15 类守卫（含提醒式 retry）、熔断器三态、pause/resume/inject 实装；`verify_phase2` 8/12 → **11/12**（剩 S10 hybrid、S12 前端） |
| 2.2.0 | 2026-10-21 | S5/S6/S7 完成：四角色（行为探针）、grounding/judge/gold（acc 1.00, κ 1.00）、摘要折叠与注入物化；修掉 artifacts 覆盖缺陷；`verify_phase2` 5/12 → **8/12** |
| 2.1.0 | 2026-10-21 | S2/S3/S4 完成：十节点图、E1–E13 条件边、断点续跑；`verify_phase2` 由 3/12 → **5/12**。偏差：生产入口仍走四阶段 `run_topic`，十节点 `run_graph` 并行存在，计划 S9 切换 |
| 2.0.1 | 2026-10-21 | S1 完成：落地 `verify_phase2.py` 能力基线（3 PASS / 9 RED）与 `RESULTS-P2.md`；后续步骤只能通过实现能力把 RED 变 GREEN |
| 0.1.0 | 2026-10-20 | 首版：入口条件、12 骨架清单、P2-1…P2-6、7 条 DoD |
| **2.0.0** | 2026-10-21 | **重构**：改为"模块（M1–M8）× 步骤（S1–S14）"双轴；每模块补**可执行判据 / 禁止项 / OOS / 依赖**；新增 §5 指标与反例纪律、§6 缺口登记、§8 分批计划、§9 H1–H10、**§10 十条经验教训适配**；总工期 18.5 人日 |

---

## 附录 A · 命令速查

```powershell
. .\scripts\env.ps1
uv run pytest -q
uv run ruff check .
uv run python scripts/verify_phase1.py --online
uv run python scripts/verify_phase2.py --offline
uv run python scripts/verify_phase2.py --online
cd web; npm run typecheck; npm run build; npm run test:e2e
```

## 附录 B · 骨架清单（P2 目标映射）

| 模块 | FEATURE | 目标 |
|---|---|---|
| `agents/retrieval.py` | `agents.retrieval` | M2 / S5 |
| `agents/mapper.py` | `agents.mapper` | M2 / S5 |
| `agents/analyst.py` | `agents.analyst` | M2 / S6 |
| `agents/critic.py` | `agents.critic` | M2 / S6 |
| `agents/chat.py` | `agents.chat` | P3 |
| `eval/grounding.py` | `eval.grounding` | M7 / S6 |
| `eval/datasets.py` | `eval.datasets` | M7 / S11 |
| `eval/judge.py` | `eval.judge` | M7 / S11 |
| `eval/faultinject.py` | `eval.faultinject` | M7 / S11 |
| `gateway/breaker.py` | `gateway.breaker` | M5 / S9 |
| `tools/mcp_adapter.py` | `tools.mcp_adapter` | P4（可选） |
| `tools/builtin/paper_pdf.py` | `tools.builtin.paper_pdf` | M6 / S10 |

---

## 12. 收尾结论（2026-10-21）

**Phase 2 COMPLETE。**

```text
verify_phase2 --offline   12/12 PASS
verify_phase1 --online    13/13 PASS
pytest -q                 354 例全绿
ruff                      clean
vue-tsc / vite build      0 error / ✓ built
playwright                8 passed
```

H1–H10 全部满足；剩余项（F5/F7/F8/F9 的手动验证、真实语义检索、`agents.chat`、`mcp_adapter`）已登记 backlog，不阻塞本阶段。

> 此后新问题：登记 → 分级 → 排入 Phase 3，**不重开 Phase 2**。

> **后续**：Phase 2.1（接线、门禁与契约）见 `phase2.1-wiring-and-contracts.md`（v1.0.0）；它只修"实现了但没生效"，不新增节点。
