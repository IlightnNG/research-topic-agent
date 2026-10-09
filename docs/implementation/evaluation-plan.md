# 评测方案与数据集计划（Evaluation & Dataset Plan）

> 状态：**v0.2 指导/预想方案**——用于后续系统完善与工程化的实现依据，不是组会材料
> 与 v0.1 的差别：补齐**数据集规格与样例、构建流程与工作量、指标公式与边界处理、实验设计、执行命令、验收标准**
> 一致性修正：评测技术底座按 `project/framework-selection.md` v0.5 更新为 **DeepEval 外壳 + 自研领域模块**（原 v0.1 写的"自研评测核心"）
> 关联：`design/state-machine-and-guards.md`（守卫与自愈判决）· `design/architecture-overview.md` §3.7/§7（事件与埋点）· `implementation/implementation-guide.md` §12（评测模块落地）· `design/agent-design-decisions.md` J 类（评测闭环问题）

---

## 1. 目标与原则

1. **评测即代码**：数据集、指标、runner 全部文件化、可版本化、可一键复跑——不允许"手工统计一次算完"。
2. **先客观后主观**：客观层（citation-grounding、数值一致性、去重）→ LLM-judge（固定 rubric）→ 人工抽查（校准与背书）。
3. **评测与运行同源**：指标从事件表/metrics 表聚合（运行即埋点），不事后补录。
4. **语料快照锁定**：grounding 必须基于冻结快照回查，保证可复现。
5. **judge 异源**：判读模型与生成模型不同源；rubric 版本化；人工抽查报告一致性（κ）。
6. **数据全本地留存**：可导出论文图表与公开数据集（脱敏后）。

---

> **本轮范围（2026-10-07 决定）**：项目当前只使用**云端 DeepSeek API**；本地模型不测试、不考虑。因此 §2 / §5.4 / §7 中的 local vs cloud 对比与 D7 的 `engine` 因子**保留为后续维度**（见 `phase0-implementation-steps.md` Step 2 注记）。
> **数据侧实测约束（S1/S1b）**：白名单侧 OA 率 **100%** → grounding 可基于**全文**；但白名单记录 `referenced_works` 完整率仅 1.5–14.3% → "引用正确率"类指标需注明**引用覆盖不完整**，且引用图依赖 `cited_by` 反向构边（见 `RESULTS.md` §2.6）。

## 2. 被测维度与指标总览

| 对象 | 核心指标 | 方法 | 数据来源 |
|---|---|---|---|
| 周报 | grounding 支持率、幻觉率、主题相关度、claim 覆盖度 | claim 抽取 → citation 回查 → 三类判定 | `reports` + `run_events` |
| 对话 | 准确率、召回率、引用正确率、拒答恰当性 | 问题集 + judge + gold 比对 | `chat_messages` |
| Agent 行为 | 漂移率、循环/停滞检出、自愈成功率、异常终止率 | 守卫事件统计 + 故障注入 | `run_events` + `metrics` |
| 工程表现 | 时延、token、成本、失败率（local vs cloud） | 配对 A/B | `llm_calls` |
| 消融 | 守卫/折叠的增益 | 因子实验 | 以上全部 |

---

## 3. 数据集清单

| ID | 数据集 | 规模（建议） | 主要用途 | 构建方式 |
|---|---|---|---|---|
| D1 | 测试 topic 集 | 3–5 个 | 固定实验对象 | 人工选定 + scope 撰写 |
| D2 | gold 事实集 | 20–40 条/topic | 召回率与引用正确性基准 | 人工从种子文献提炼 |
| D3 | 对话问题集 | 30–50 问/topic | 对话准确率/召回/拒答 | 由 gold 反写 + 人工设计 |
| D4 | 故障注入场景集 | 8–12 个场景 | 自愈与守卫有效性 | 脚本化 + 人工设计 |
| D5 | 语料快照 | 每战役 1 份 | grounding 可复现 | 自动打点 + tag |
| D6 | 源白名单与种子文献 | 每 topic 10–30 venue + 5–10 种子论文 | 范围约束与 gold 来源 | 人工配置 |
| D7 | 实验配置矩阵 | 4–8 组 | 消融与双引擎对比 | 配置声明 |

### 3.1 D1 测试 topic 集

**要求**：英文、学术事实密集、可核验（便于 gold 构建）、覆盖你的目标方向（CS / 软硬件 / 工科）。
**字段**
```yaml
- topic_id: T1
  name: "Multi-agent LLM orchestration reliability"
  scope_statement: >
    关注 LLM 多智能体系统的编排、长时运行可靠性、失败检测与恢复机制；
    不包含纯单模型 prompt 工程、模型预训练/微调方法。
  out_of_scope_examples:
    - "instruction tuning datasets"
    - "prompt template engineering for single LLM"
  source_whitelist:
    openalex_venues: ["NeurIPS", "ICML", "ICLR", "ACL", "EMNLP"]
    arxiv_categories: ["cs.AI", "cs.LG", "cs.MA", "cs.SE"]
  seed_papers: ["W...", "arXiv:24xx.xxxxx"]
  language: en
```
**构建步骤**：① 选定方向 → ② 写 scope（含反例，反例对守卫 G1/G2 至关重要）→ ③ 列白名单 → ④ 选 5–10 篇种子文献 → ⑤ 自检：能否用一句话判断"某论文是否属于本 topic"。
**质控**：scope 必须可判定（拿 10 篇随机论文自测，判定一致性应 ≥ 90%）。
**工作量**：每个 topic 1.5–2 h。

### 3.2 D2 gold 事实集（核心资产）

**字段与样例**
```yaml
- fact_id: T1-F017
  topic_id: T1
  type: relational          # entity | relational | temporal | survey
  statement: "ReAct 将推理轨迹与工具调用交错生成，成为后续 agent 框架的常见范式。"
  expected_support: ["W2963087533", "arXiv:2210.03629"]
  support_span_hint: "method section, paragraph 2"
  verified_by: "human:zhu"          # 人工复核者
  verified_at: "2026-01-10"
  difficulty: easy                   # easy | medium | hard
```
**类型定义**
| 类型 | 说明 | 判定要点 |
|---|---|---|
| `entity` | 某方法/系统/数据集的提出者、年份、归属 | 单一来源即可支撑 |
| `relational` | A 引用/改进/对比 B | 需要明确关系证据 |
| `temporal` | 领域事件先后、版本演进 | 需要时间证据 |
| `survey` | 综述性结论（多来源支撑） | 至少 2 条独立来源 |

**构建流程（7 步）**：① 读种子文献与已知综述；② 逐条抽取候选事实；③ 标注类型与期望支撑文献；④ 在语料快照中确认可回查；⑤ 第二人复核（或隔日自复核）；⑥ 标难度；⑦ 入库并登记版本。
**质控**：每条必须有 ≥1 个可回查支撑；`survey` 型必须 ≥2 条；表述不得含模糊词（"可能/据说"）。
**工作量**：单条 5–10 min（含复核）→ 30 条/topic ≈ 4–6 h；5 个 topic ≈ 20–30 h。**建议：先做 1 个 topic 的 10 条试点，验证流程与耗时再放量。**

### 3.3 D3 对话问题集

**字段与样例**
```yaml
- qid: T1-Q003
  topic_id: T1
  type: cross_source          # factual | relational | survey | cross_topic | unanswerable
  question: "哪些工作把循环检测显式建模进 agent 的运行时？"
  expected_evidence: ["W1...", "W2..."]     # 期望被引用/覆盖的来源
  expected_gold_facts: ["T1-F017", "T1-F021"]
  scoring: "judge+gold"                       # judge | gold | judge+gold
```
**类型与判定口径**
| 类型 | 期望行为 | 判定 |
|---|---|---|
| `factual` | 给出事实 + 引用 | judge + gold 覆盖 |
| `relational` | 通过关系图回答 | 关系正确性 |
| `survey` | 多来源综合 | 覆盖度 + 不偏 |
| `cross_topic` | 跨 topic 关联 | 关联正确性 |
| `unanswerable` | **明确拒答** | 拒答恰当性（编造即失败） |
**构建步骤**：① 由 gold 反写问题；② 人工设计关系/综述/不可答类型；③ 标注期望证据；④ 组内试答 5 题检查歧义。
**工作量**：8–12 min/题 → 30 题 ≈ 4–6 h/topic。

### 3.4 D4 故障注入场景集

**字段与样例**
```yaml
- scenario_id: F-LOOP-01
  type: loop                  # drift | loop | stagnation | provider | injection | budget
  inject_at: "S2.after_retrieval"
  method: "repeat_tool_calls"  # 具体注入动作
  params: {times: 4, tool: "openalex_search"}
  expected:
    detect: "E_GUARD_LOOP"
    action: "replan"
    recover: true
  repeats: 3                    # 含温度扰动的重复次数
```
**预期处置矩阵**
| 类型 | 期望检出码 | 期望动作 | 期望结果 |
|---|---|---|---|
| drift | `E_GUARD_DRIFT` | replan | 回到 scope 内完成 |
| loop | `E_GUARD_LOOP` | replan | 产生新计划并推进 |
| stagnation | `E_GUARD_STAGNATION` | degrade | 换 provider 后恢复 |
| provider | `E_LLM_*` | degrade | 切备用 provider 完成 |
| injection | `E_PROTO_INJECTION_SUSPECT` | retry | 隔离证据、输出不受影响 |
| budget | `E_BUDGET_*` | abort/annotate | 停止并产出标注报告 |
**约束**：只作用于测试 run 副本（独立数据库/目录），**不得污染生产数据与评测快照**。
**工作量**：场景实现 1–3 h/个（复用 hook 框架后递减）。

### 3.5 D5 语料快照

**组成**：源记录版本（API 响应缓存） + Kuzu 导出 + Qdrant 快照 + 全文文件 + 白名单配置 + 生成参数。
**打点流程**：`snapshot create --tag eval-2026w05` → 校验和清单 → 登记 `snapshots/index.yaml`。
**规则**：评测期间周更继续写"当前库"，评测一律读快照；快照不可变，变更即新 tag。

### 3.6 D6 源白名单与种子文献
每个 topic 的 venue/category 白名单（见 D1）作为**硬过滤**同时用于生产与评测；种子文献用于 gold 构建与 scope 校准。

### 3.7 D7 实验配置矩阵（因子与对照）

| 组 | engine | guards | folding | 用途 |
|---|---|---|---|---|
| A | cloud | on | on | 主基线 |
| B | local | on | on | 双引擎对比 |
| C | cloud | **off** | on | 消融：守卫的价值 |
| D | cloud | on | **off** | 消融：折叠的价值 |
| E（可选） | local | off | off | 下界参照 |

---

## 4. 目录结构与命名规范

```
eval_data/
├─ topics/            T1.yaml …                    # D1
├─ gold/              T1.gold.yaml …               # D2
├─ questions/         T1.questions.yaml …          # D3
├─ faults/            F-LOOP-01.yaml …             # D4
├─ snapshots/         eval-2026w05/{manifest,checksums}.json
├─ campaigns/         p5a/{config.yaml, runs/, results/, charts/}
└─ rubrics/           grounding.v1.md, judge.v1.md # judge 与判定 rubric
```
**命名规范**：`<type>-<topic>-<seq>`（如 `T1-F017`、`T1-Q003`）；rubric 带版本号；campaign 名含阶段（`p5a`）。
**版本化**：数据集与 rubric 提交 Git；campaign 结果同时落 `metrics`/`eval_judgments` 表与 `results/` 文件（双份）。

---

## 5. 指标定义与计算

### 5.1 周报忠实度 / 幻觉
流程：**claim 抽取** → 定位 citation → 快照回查 → 三类判定（支持/矛盾/无支撑）。
```
grounding 支持率 = |supported| / |verifiable_claims|
幻觉率          = (|contradicted| + |unsupported|) / |verifiable_claims|
严重幻觉率      = |contradicted| / |verifiable_claims|        # 分列，论文更好写
主题相关度      = mean(cos(embed(report_section), embed(scope_statement)))
```
### 5.2 对话准确率与召回
```
准确率 = Σ w_type · judge_score(q) / n_questions        # judge_score ∈ {1, 0.5, 0}
召回率 = |正确覆盖的 gold 事实| / |该问题期望覆盖的 gold 事实|
引用正确率 = |citation 与支撑段落真对应| / |citation 总数|        # 抽样
拒答恰当性 = |correct_refusal| / |unanswerable_questions|
```
### 5.3 漂移与自愈
```
漂移率        = 漂移事件数 / run 数
检出率(TPR)   = 被捕获注入数 / 注入总数            # 分故障类型
处置正确率    = 动作符合预期数 / 检出数
自愈成功率    = 恢复到正常完成态的注入数 / 检出数
越界副作用率  = 产生错误入库/错误报告的注入数 / 注入总数   # 安全底线，目标 0
误报率(FPR)   = 正常 run 中触发守卫的 run 数 / 正常 run 数
```
### 5.4 双引擎对比
同一任务集分别在 local / cloud 生成 → **配对比较**：准确率、幻觉率、时延 P50/P95、token、成本、失败率。

### 5.4b Phase 0 实测口径映射（S7 落地，2026-10-09）

> 本节是 S7 的验收要求（口径不一致必须回写）。Phase 0 已按 §5.1/§5.3 从**事件**实现自动聚合
> （`steps/s7_metrics.py` → `out/metrics_summary.csv` / `out/metrics_aggregate.json` / `out/metrics_report.md`）。

| §5 指标 | Phase 0 事件来源 | 实测值（S7 campaign） | 与 §5 的差异 |
|---|---|---|---|
| grounding 支持率 | `metric{kind:grounding}.claims_supported / verifiable_claims` | **0.7949**（verifiable=39） | ⚠️ 分子来自**模型自报 support 标签**，非独立核验 |
| 幻觉率 | `(contradicted + unsupported + 被丢弃的不可回查 claim) / verifiable` | **0.2051** | 同上；且按 §5.5 把不可回查 claim 计入 unsupported |
| 严重幻觉率 | `contradicted / verifiable` | 0.0513 | 同上 |
| 主题相关度 | `mean(cos(claim, scope))`，scope 用**语料质心** | 0.0699 | 用词法代理（无 embedding）；Phase 1 换 bge-m3 后需重标定 |
| 漂移率 / 检出率 | `guard_trigger{code}` 计数 + S6 场景映射 | 事件率 0.3333 / **TPR 1.0** | 一致 |
| 处置正确率 / 自愈成功率 | `guard_trigger.action` + `recovery.action` + `metric{recovered}` | 均 **1.0**（abort 类自愈率 0 属设计） | 一致（处置动作含 harness 级 recovery） |
| 误报率 FPR | `scenario=none` 的 run 中触发守卫的比例 | **0.0** | 一致 |
| 越界副作用率 | 报告 run 中 `ungrounded_citation_count > 0` 的比例 | **0.0** | 一致（S5 硬过滤不可回查引用） |
| 单 run 成本/时延 | `metric{kind:run_summary}.cost_usd / seconds` | 均值 **$0.006294**；p50 0.08s / p95 68.35s | 时延含真实网络调用（reasoning 模型） |

**两条必须记住的口径约定（S7 实测确立）**

1. **「claim 无 citation」按 §5.5 计入 `unsupported`**，而不是从分母中丢弃——否则 grounding 率恒为 100%、指标失去意义。
   Phase 0 的做法：报告仍不发布不可回查引用（硬过滤），但**该 claim 计入 `verifiable` 与幻觉率分子**并单独计数。
2. **指标只能在"补埋点之后"的 run 上计算**：埋点（`topicality`、按 support 分级计数、`run_summary`）是随 S5/S6/S7 逐步补的，
   旧 run 缺字段就算不出。同理，**必须按 campaign 圈定 run 集**（每场景最近 N 次 + 明确纳入的 run），
   把全部历史尝试一起算会得到错误结论（实测混入改阈值前的行为后 FPR 0.75 / TPR 0.625）。

### 5.5 边界情况处理（必须预先定义，否则结果不可比）
| 情况 | 处理 |
|---|---|
| claim 无 citation | 计入 `unsupported`（不算"不可核验"） |
| citation 指向的论文不在快照 | 计入 `unsupported`，并单列"越界引用" |
| judge 判"部分正确" | 计 0.5（rubric 中定义何为部分） |
| gold 未覆盖该问题的方面 | 不计入召回分母（分母只算"期望覆盖"） |
| 重复 claim | 先按语义去重再统计 |
| 报告为空/失败 | 记为该 run 失败，不参与质量均值（单列失败率） |
| 生成模型自报 support | Phase 0 只能用自报标签（`support_label_source=llm_self_label`）；**独立核验（P3）前不得把它当 §5.1 结论** |

---

## 6. 评测执行流程

```
① 周更留痕（P2 起）        run_events / llm_calls / metrics 实时写入
② 冻结快照                snapshot create --tag <campaign>
③ 跑评测 runner           eval run --campaign p5a --datasets T1,T2 --config A
④ 客观层                  grounding / 一致性 / 去重（无 LLM）
⑤ judge 层                DeepEval 外壳 + 领域自定义 metric（异源模型）
⑥ 人工抽查                ≥10% 或每类 ≥20 条 → 计算 κ
⑦ 聚合导出                eval aggregate → metrics 表 + results/*.csv
⑧ 出图                    eval export charts → 论文图表
```
**命令示例**
```bash
uv run python -m lit_agent.eval.run --campaign p5a --config configs/A.yaml --weeks 4
uv run python -m lit_agent.eval.aggregate --campaign p5a --out eval_data/campaigns/p5a/results
uv run python -m lit_agent.eval.export --campaign p5a --charts faithfulness,drift,engine_compare
uv run python -m lit_agent.eval.faultinject --scenario F-LOOP-01 --repeats 3
```

---

## 7. 实验设计与统计口径

- **单元**：一个 run = 一个 topic × 一周；一次 campaign = 3–5 topic × ≥4 周 = 12–20 run/组。
- **配对**：A/B 组同 topic 同周次 配对比较（消除 topic 难度差异）。
- **重复**：LLM 非确定性 → 关键指标跑 2–3 次取中位数（记录采样参数）。
- **报告项**：中位数 + 四分位距（样本小不强行报显著性）；差异同时给绝对值与相对值。
- **消融**：C/D 组分别回答"守卫值多少""折叠值多少"，是论文亮点。
- **盲评**：judge 不知分组（engine/guards）以降低偏差。

---

## 8. 质量保证与风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| gold 构建成本高 | P5 延期 | 先做 1 topic 试点 10 条，验证后再放量；难度分级，先易后难 |
| judge 偏差/漂移 | 指标可信度 | 异源 judge + rubric 版本化 + 人工 κ + 抽样复判 |
| 快照与应用库漂移 | 不可复现 | 快照不可变 + 校验和 + 评测只读快照 |
| 过拟合评测集 | 论文结论虚高 | 保留一份"留出 topic"不参与调参 |
| 注入污染生产 | 数据损坏 | 独立库/目录 + 测试专用 run 标记 + 事后校验 |
| 采样参数未记录 | 无法复现 | 每次调用记录 temperature/seed/模型版本（§2.2 事件） |

---

## 9. 验收标准（一次评测 campaign 合格的清单）

- [ ] 快照已 tag 并校验和入库，评测只读快照；
- [ ] 数据集齐备：D1–D4 全部 versioned，rubric versioned；
- [ ] 样本量达标：≥3 topic × ≥4 周/组，关键指标 ≥2 次重复；
- [ ] 客观层与 judge 层结果同时留存；人工抽查比例达标并报告 κ；
- [ ] 消融（守卫/折叠）与双引擎对比均有数据；
- [ ] 一键复跑脚本可复现相同结论（中位数差异在容差内）；
- [ ] 图表与原始数据（metrics/eval_judgments + 事件）全部导出可交付。

---

## 10. 里程碑与埋点时间线

| 阶段 | 评测相关工作 |
|---|---|
| P2 | 事件/计量埋点落地；fault-injection hook 可用；D4 首批场景 + D2 试点 10 条 |
| P3 | 折叠/守卫 A/B 小规模试跑；D3 试点问题集；runner 骨架 |
| P4 | 周更连续运行（数据自然积累）；快照打点流程固化 |
| P5 | 正式 campaign：D1–D7 齐备，≥4 周 × 多组，人工抽查与 κ |
| P6 | 图表定稿、数据集整理成可交付物、论文第 5 章撰写 |

---

## 11. 关联与待确认

- 守卫判决与阈值：`design/state-machine-and-guards.md`（自愈指标口径与其 §12 标定目标一致）；
- 落地实现：`implementation/implementation-guide.md` §12（`eval/` 组件与接口）；
- 技术底座：DeepEval 外壳 + 自研领域模块（`project/framework-selection.md` 模块10）；
- 待确认：① gold 事实人工量为 20–30 h 是否可接受（或缩减到 3 topic × 20 条）；② 是否纳入"无守卫/无折叠"两组消融；③ 是否保留一个留出 topic；④ 未来是否加第三引擎（Jetson 本地后端）作扩展维度。
