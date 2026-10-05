# 状态机与守卫判决表（设计与实现规范）

> 状态：**v0.1 预想/指导方案**——不是组会材料，而是后续系统完善的实现依据（可直接据此写代码与测试）
> 用途：① 实现依据：状态、迁移、守卫、阈值、动作全部显式化；② 测试依据：每条迁移与守卫都有对应用例；③ 论文附录：Harness Engineering 的核心设计资产
> 关联：`design/architecture-overview.md`（分层与时序）· `design/agent-design-decisions.md` A1–A8/B1（问题与解法）· `implementation/implementation-guide.md` §6/§7/§13（落地位置）· `implementation/evaluation-plan.md` §4.3（自愈指标）
> 说明：所有阈值均为**初始建议值**，须经 §12 的标定流程确定；所有判决必须结构化（不得用自然语言表达"通过了"）。

---

## 1. 设计原则

1. **控制流在状态机，自由度在节点内**：agent 在单个 stage 内可自由调用工具，但**不能跨 stage 跳转**；迁移只由条件边决定。
2. **一切判决结构化**：`GuardVerdict{ok, severity, action, code, reasons[]}`；LLM 只允许出现在"语义判定"这一类守卫内部，且其输出必须落成同一个结构。
3. **有界回退**：每个回退边带最大次数；超限即进入终止分支并**留痕标注**，绝不静默继续。
4. **可回放**：每次迁移、每个判决、每次恢复都写事件；事件表是唯一真相源。
5. **fail-closed**：完整性/引用/预算类守卫失败时，禁止写入图库、证据池与报告。
6. **阈值配置化**：全部阈值来自 `guards.*` 配置，禁止硬编码；配置版本随运行快照记录。

---

## 2. 状态空间总览（三层）

| 层 | 生命周期 | 粒度 | 状态存储 |
|---|---|---|---|
| **L1 Topic 生命周期** | 长期（跨周/跨月） | 业务实体 | SQLite `topics.status` |
| **L2 Run（单次周更）** | 小时级 | 一次执行 | SQLite `runs.state` + LangGraph checkpointer |
| **L3 Stage（流水线阶段）** | 分钟级 | 图节点 | LangGraph 状态 + `run_events` |

三层关系：`Topic(active) → 触发 Run → Run 依次经过 Stage → 产出 Report → 回到 Topic(active)`。

```
L1: [new] → scoping → active ⇄ paused → archived
                              │
                              ▼ 每周/手动触发
L2: queued → running ──────────────────────────────► succeeded
                │  ├─ 任一 stage 失败且不可恢复 → failed
                │  ├─ 守卫判定不可继续       → aborted
                │  ├─ 进程中断（心跳失效）    → interrupted → 可续跑/待重跑
                │  └─ 用户取消              → cancelled
                ▼
L3: S0→S1→S2→S3→S4→S5→S6→S7→S8→S9（含条件回退边）
```

---

## 3. L1 Topic 生命周期状态机

| 状态 | 含义 | 进入条件 | 允许迁移 | 触发者 | 副作用/事件 |
|---|---|---|---|---|---|
| `new` | 刚创建，未定义范围 | 用户创建 | → `scoping` | 用户操作 | `topic_created` |
| `scoping` | 正在确定 scope 与源白名单 | 进入 scoping 或漂移复核 | → `active`（scope 校验通过） | 用户 + scope 校验 | `scope_updated` |
| `active` | 参与周更 | scope 存在且源白名单非空 | ⇄ `paused`；→ `archived`；内部触发 Run | 调度器/用户 | `topic_activated` |
| `paused` | 暂停周更（保留数据） | 用户暂停 | → `active`；→ `archived` | 用户 | `topic_paused` |
| `archived` | 归档（只读） | 用户归档 | → `active`（恢复） | 用户 | `topic_archived` |

**不变量**：① `active` 时必须有 `scope_statement`；② scope 变更必须产生新版本号（`scope_version`）并写入事件；③ 归档后不再被调度器选中。

---

## 4. L2 Run 状态机

| 状态 | 含义 | 进入条件 | 允许迁移 | 备注 |
|---|---|---|---|---|
| `queued` | 已入队，等待执行 | 调度触发或手动触发 | → `running`；→ `cancelled` | 同 topic 串行（`job_locks`） |
| `running` | 正在执行流水线 | 获得 topic 锁且 worker 可用 | → `succeeded` / `failed` / `aborted` / `interrupted` / `cancelled` | 心跳每 N 秒更新 |
| `succeeded` | 正常完成并产出报告 | S9 完成且报告通过质量门 | 终态 | 写 `reports` + `metrics` |
| `failed` | 不可恢复错误终止 | 错误分类为不可重试且升阶梯耗尽 | → 人工重跑（新 run） | 必须产出失败报告 |
| `aborted` | 守卫判定不应继续（漂移/预算/安全） | 升级阶梯到达 abort | → 人工重跑 | 报告**必须**带 annotate |
| `interrupted` | 进程死亡/心跳失效 | 启动扫描发现 | → 续跑（checkpoint）或待重跑 | 由恢复策略配置 |
| `cancelled` | 用户主动取消 | 协作式取消信号 | → 人工重跑 | 记录取消点 |

**规则**：续跑只允许从 `interrupted` 且 checkpoint 完整时进行；续跑创建的不是新 run，而是在原 run 上追加 `seq`。

---

## 5. L3 周更 Stage 图

```
S0 scope_check ─► S1 plan ─► S2 retrieve ─► S3 ingest_parse ─► S4 map_update
                                                                     │
        ┌──────────────────────────── replan（回退，≤N）──────────────┘
        ▼
     S5 novelty ─► S6 analyze ─► S7 draft ─► S8 critique ─► S9 finalize
                                    ▲              │
                                    └── 重写（≤N）──┘
```

| Stage | 名称 | 输入 | 输出（契约） | 执行者 | 出口条件 | 可回退至 |
|---|---|---|---|---|---|---|
| S0 | scope_check | topic.scope_statement、上期摘要 | `ScopeCheckResult` | 确定性 + LLM 辅助 | scope 有效、源白名单非空 | —（失败直接 abort/请求用户） |
| S1 | plan | scope、上期报告、未决问题 | `PlanOutput`（子任务列表） | plan agent | 子任务非空且均带验收条件 | S0 |
| S2 | retrieve | 子任务、源白名单、游标 | `RetrievalResult`（证据卡列表） | retrieval agent | 证据卡 ≥ 阈值 且越界率 ≤ 阈值 | S1 |
| S3 | ingest_parse | 证据卡 | `IngestResult`（paper_id 列表、解析状态） | 确定性管道 | 解析成功率 ≥ 阈值 | S2 |
| S4 | map_update | paper 元数据 | `MappingResult`（节点/边计数） | 确定性 | MERGE 幂等、无写失败 | S2/S3 |
| S5 | novelty | 图 + 向量 + 上期状态 | `NoveltyResult`（新论文列表） | 确定性 | 计算完成（允许空集） | — |
| S6 | analyze | 新证据 + 图查询结果 | `AnalysisResult`（发现 + 证据引用） | analyst agent | 每条发现带 citation | S4/S5 |
| S7 | draft | AnalysisResult + 大纲模板 | `ReportDraft`（markdown + claims） | reporter agent | schema 校验通过 | S6 |
| S8 | critique | ReportDraft + 语料快照 | `CritiqueResult`（分项分数 + 问题清单） | critic agent（**异源模型**） | 分数 ≥ 阈值或重写次数用尽 | S7 |
| S9 | finalize | Draft/Critique/预算与降级标记 | `Report`（落库） | 确定性 | 写库成功 + 事件完整 | — |

**Stage 内部契约**：每个 stage 的入口处校验输入 schema；出口处校验输出 schema；失败即返回结构化 `Verdict`，由条件边决定去向。

---

## 6. 条件边表

| 边 ID | From | 触发（守卫判决） | To | 最大次数 | 副作用 |
|---|---|---|---|---|---|
| E1 | S0 | `G1 漂移` warn 且可修复 | S0（补 scope 提示） | 1 | 恢复包注入 |
| E2 | S1 | `G1` block / 计划越界 | S0 | 2 | 恢复包 + 记录 |
| E3 | S2 | `G2 检索越界` | S2（收紧查询） | 2 | 查询策略降级 |
| E4 | S2 | `G5 停滞` | S1（重规划） | 2 | 恢复包 |
| E5 | S2/S3 | `G9 provider 故障` | S2（换 provider） | 3 | 熔断降级 |
| E6 | S3 | `G6 schema 失败` | S3（重试）→ 降档 | 2 | 解析器 fallback |
| E7 | S4 | 写失败（`E_DATA_*`） | S4（重放） | 3 | 幂等重放 |
| E8 | S6/S7 | `G7 引用不可回查` | S6（补证）→ S7 | 2 | 标记未证实 |
| E9 | S7 | `G6 报告 schema` 失败 | S7（重写） | 2 | 模板约束加强 |
| E10 | S8 | 质量分 < 阈值 | S7（重写） | 2 | critique 反馈注入 |
| E11 | 任意 | `G4 循环/停滞` block | S1（强制 replan） | 1 | 清局部状态 |
| E12 | 任意 | `G8 预算超限` | S9（提前收尾）或 abort | 1 | 降级标注 |
| E13 | S8 用尽 | critique 仍不达标 | S9（带 annotate 收尾） | — | 标注低置信 |

**全局规则**：任何回退边触发都写 `guard_trigger` + `recovery` 事件；回退次数记入 run 状态，跨 stage 累计超限（默认 6 次）即 abort。

---

## 7. 守卫判决表（核心）

> 字段说明：**信号**＝如何计算；**默认阈值**＝配置项初值；**判决**＝`GuardVerdict`；**动作**＝条件边；**事件**＝埋点类型。

### G1 主题漂移（scope drift）
| 项 | 内容 |
|---|---|
| 触发点 | S1/S2/S6/S7 出口（阶段性产物） |
| 信号 | `cos(embed(summary_of_artifact), embed(scope_statement))`；辅助：越界关键词命中数 |
| 默认阈值 | `< 0.60` → warn；`< 0.45` → block（按嵌入模型标定） |
| 判决 | warn: `action=retry`（携带修复提示）；block: `action=replan` |
| 事件 | `guard_trigger{code=E_GUARD_DRIFT, score, threshold}` |
| 测试要点 | 阈值 ±ε 两侧；同义改写不误报；明显越界样本必触发 |

### G2 检索越界（retrieval out-of-scope share）
| 项 | 内容 |
|---|---|
| 触发点 | S2 出口 |
| 信号 | 越界证据卡数 / 总卡数（越界 = 与 scope 相似度 < 检索阈值或来源不在白名单） |
| 默认阈值 | `> 0.30` → warn；`> 0.50` → block |
| 判决 | warn: `retry`（收紧查询）；block: `replan` |
| 事件 | `guard_trigger{code=E_GUARD_OOS, share}` |
| 测试要点 | 边界样本；白名单外来源必判越界 |

### G3 查询意图（query intent）
| 项 | 内容 |
|---|---|
| 触发点 | S2 入口（每个检索查询） |
| 信号 | 规则（关键词/白名单）+ 轻量分类（本地小模型或 LLM，结果结构化） |
| 默认阈值 | 分类为 `out_of_scope` 即拦截 |
| 判决 | `retry`（改写查询，≤2 次）→ 仍越界则 `replan` |
| 事件 | `guard_trigger{code=E_GUARD_INTENT, query_hash}` |
| 测试要点 | 明显越界查询拦截率；正常查询零误拦 |

### G4 死循环（loop）
| 项 | 内容 |
|---|---|
| 触发点 | 每次工具调用后 |
| 信号 | 工具调用签名（工具名 + 规范化参数哈希）滑动窗口成环；或状态哈希连续重复 |
| 默认阈值 | 窗口 `k=5` 内出现重复环；或同一状态哈希连续 3 次 |
| 判决 | `replan`（清局部子状态）；再次触发且累计超限 → `abort` |
| 事件 | `guard_trigger{code=E_GUARD_LOOP, signature}` |
| 测试要点 | 注入重复序列必触发；正常多步检索不误报 |

### G5 停滞（no progress）
| 项 | 内容 |
|---|---|
| 触发点 | S2/S3/S4/S6 出口 |
| 信号 | 新增"已核实事实/新 paper_id"数量；或证据池信息增益 ≈ 0 |
| 默认阈值 | 连续 2 步增量为 0 → warn；连续 3 步 → block |
| 判决 | warn: `retry`（换查询策略）；block: `degrade`（换 provider）→ 仍无进展 `abort` |
| 事件 | `guard_trigger{code=E_GUARD_STAGNATION, delta}` |
| 测试要点 | 注入无新增状态必触发；正常低产阶段不误报（用历史分布标定） |

### G6 结构化违规（schema）
| 项 | 内容 |
|---|---|
| 触发点 | 每个 stage 出口 |
| 信号 | Pydantic 校验错误列表 |
| 默认阈值 | 任意错误即触发 |
| 判决 | `retry`（1 次，带错误反馈）→ `degrade`（换模型档）→ `abort` |
| 事件 | `guard_trigger{code=E_SCHEMA_STAGE_OUTPUT, errors[]}` |
| 测试要点 | 缺字段/类型错/枚举越界各一例；错误反馈进入下次提示 |

### G7 引用可回查（citation resolvability）
| 项 | 内容 |
|---|---|
| 触发点 | S6/S7 出口 + S9 前 |
| 信号 | 每条 claim 的 citation 是否能在语料快照中定位（paper_id + 片段命中） |
| 默认阈值 | 未解析率 `> 0` 即 warn；`> 0.15` → block（报告不得直接发布） |
| 判决 | warn: 标记"未证实"；block: `retry`（补证或删除该 claim） |
| 事件 | `guard_trigger{code=E_GROUND_UNRESOLVED_CITATION, claim_id}` |
| 测试要点 | 伪造 citation 必被拦截；正确 citation 零误报 |

### G8 预算（budget）
| 项 | 内容 |
|---|---|
| 触发点 | 每次 LLM 调用后 + 定时（看门狗） |
| 信号 | run 级 token/时长/成本累计；stage 级超时 |
| 默认阈值 | token 80% / time 80% / cost 80% → warn；100% → block |
| 判决 | warn: 降级（小模型、缩短检索批）；block: `abort`（提前收尾 + annotate） |
| 事件 | `metric{budget_used}`、`guard_trigger{code=E_BUDGET_*}` |
| 测试要点 | 恰好 80%/100% 边界；超限后确实停止继续调用 |

### G9 provider 健康（circuit breaker）
| 项 | 内容 |
|---|---|
| 触发点 | 每次 LLM/工具调用失败后 |
| 信号 | 连续失败数、错误类型（`E_LLM_*`/`E_SRC_*`） |
| 默认阈值 | 连续 3 次失败或错误率 > 50%（窗口 10 次）→ 打开熔断 |
| 判决 | `degrade`（切备用 provider）；半开成功则恢复 |
| 事件 | `guard_trigger{code=E_LLM_*}` + `recovery{action=degrade}` |
| 测试要点 | 熔断状态迁移；切云/切本地顺序；恢复后不再打故障 provider |

### G10 注入嫌疑（injection suspicion）
| 项 | 内容 |
|---|---|
| 触发点 | S2/S3 证据入池前 |
| 信号 | 指令性模式（"ignore previous instructions"、伪 system 标记）、异常超长隐藏文本、URL/脚本片段 |
| 默认阈值 | 命中模式列表即标记（默认不阻断，隔离入 quarantine） |
| 判决 | `retry`（丢弃该证据）；若关键证据全部被隔离 → `replan` |
| 事件 | `guard_trigger{code=E_PROTO_INJECTION_SUSPECT, source}` |
| 测试要点 | 注入样本必被隔离且不影响后续输出；正常论文摘要不误伤（含"ignore"一词的合理句子） |

### G11 重复证据（duplicate evidence）
| 项 | 内容 |
|---|---|
| 触发点 | S2/S4 入库前 |
| 信号 | `fingerprint(paper)` 已存在，或 chunk 哈希重复，或 arXiv 版本重复 |
| 默认阈值 | 命中即去重（不判失败） |
| 判决 | `continue`（跳过重复，不产生"新进展"） |
| 事件 | `metric{dedup_skipped}` |
| 测试要点 | 重复注入不改进度指标；版本更新记录为 `updated` 而非新论文 |

### G12 证据矛盾（contradiction）
| 项 | 内容 |
|---|---|
| 触发点 | S6 分析阶段（可选/后续启用） |
| 信号 | 同一事实存在支持与反驳证据；数值冲突 |
| 默认阈值 | 分值差异 > 阈值且来源权威性接近 |
| 判决 | `continue` + **必须显式呈现分歧**（不得取平均）；高影响矛盾 → `annotate` + 人工复核标记 |
| 事件 | `guard_trigger{code=E_GUARD_CONTRADICTION, claim_id}` |
| 测试要点 | 矛盾样本出现在报告中；无矛盾样本不产生噪声 |

### G13 降级产物质量（degraded output quality）
| 项 | 内容 |
|---|---|
| 触发点 | S9 前（若 run 中出现过降级） |
| 信号 | 降级步骤占比、降级路径产出的 claim 占比、critic 分数 |
| 默认阈值 | 降级占比 > 30% 或 critic 分低于阈值 |
| 判决 | `annotate`（报告标记低置信，**不阻断**）；评测中分桶统计 |
| 事件 | `metric{degraded_ratio}` + `report_written{degraded=true}` |
| 测试要点 | 降级 run 的报告带标记；正常 run 不带 |

---

## 8. 判决动作语义与升级阶梯

| 动作 | 语义 | 是否消耗回退预算 | 典型来源 |
|---|---|---|---|
| `continue` | 继续下一步 | 否 | 全部通过、G11 去重 |
| `retry` | 同 stage 重做（可带修复提示） | 是 | G1 warn、G6、G7 |
| `degrade` | 换 provider/模型档/解析器后重做 | 是 | G5、G9 |
| `replan` | 回退到 S1（清局部状态） | 是 | G2 block、G4 |
| `abort` | 立即终止，产出 annotated 报告 | — | G1 block 超限、G4 超限、G8 block |
| `annotate` | 继续但在产物上打标 | 否 | G12、G13 |

**升级阶梯（统一）**：`retry(≤2) → degrade(≤2) → replan(≤1) → abort(annotate)`；同级失败即升一级；全程写事件；abort 时必须包含：失败 stage、错误码、已产出内容、建议动作。

**severity 约定**：`info`（仅记录，如 G11）→ `warn`（可修复，继续尝试）→ `block`（必须改变策略或终止）。

---

## 9. 恢复包（Recovery Packet）规范

每次 retry/degrade/replan 前，由 harness 生成并注入 **system 槽**：

```json
{
  "failed_stage": "S2",
  "failure_code": "E_GUARD_OOS",
  "what_happened": "本次检索 62% 的结果落在 scope 之外（越界占比 > 50% 阈值）",
  "trusted_state": {
    "verified_facts": 12,
    "evidence_papers": ["W123", "arXiv:2401.00001"],
    "open_questions": ["缺少 edge 部署成本数据"]
  },
  "constraints_next_attempt": [
    "仅在白名单 venue 内检索",
    "不得重复使用上次失败查询",
    "优先补充 open_questions 中的缺口"
  ],
  "budget_remaining": {"tokens": 42000, "minutes": 21, "usd": 0.83}
}
```

**规则**：① 不得把原始失败对话整段回灌；② `constraints` 必须具体可执行；③ 恢复包本身写入 `recovery` 事件（可回放审计）。

---

## 10. 状态字段与事件映射

| 状态字段 | 类型 | 说明 |
|---|---|---|
| `run_id / topic_id` | int | 关联 |
| `stage` | enum | 当前 stage |
| `scope` | str + version | 当前 scope 快照 |
| `evidence` | list[EvidenceCard] | 证据池（结构化摘要，非正文） |
| `verified_facts` | list[Fact] | 已核实事实（供 G5 判进度） |
| `counters` | dict | retries / replan / degrade / loop 计数 |
| `budget` | dict | tokens / seconds / usd 已用 |
| `artifacts` | dict | 各 stage 产物（结构化） |
| `flags` | dict | degraded / annotated / quarantined |

| Stage 事件 | 进入 | 出口成功 | 出口失败 |
|---|---|---|---|
| 全部 | `phase_change{stage, phase=enter}` | `phase_change{phase=exit, ok=true}` | `error{code, stage}` 或 `guard_trigger` |
| 幂等键 | `(run_id, stage, attempt)` | — | — |
| checkpoint 边界 | stage 出口（含状态快照） | — | — |

---

## 11. 预算与看门狗规范

| 级别 | 项目 | 默认值（可配） | 检查频率 | 超限处置 |
|---|---|---|---|---|
| Run | 总 token | 300k | 每次调用后 | warn 80% → degrade；100% → abort+annotate |
| Run | 总时长 | 90 min | 30 s | 同上 |
| Run | 总成本 | $2.00 | 每次调用后 | 同上 |
| Stage | 单 stage 超时 | 15 min（检索类 25 min） | 10 s | retry 1 次 → degrade → abort |
| Run | 回退总次数 | 6 | 每次回退 | 超限 abort |
| Run | 心跳 | 30 s 间隔 | 启动扫描 | 过期 → `interrupted` |

---

## 12. 阈值标定方法（预想）

1. **数据**：≥10 次正常 golden run（记录全部信号值）+ ≥30 条注入样本；
2. **扫描**：对每个守卫阈值做网格扫描，计算 `检出率(TPR)` 与 `误报率(FPR)`；
3. **选点**：在 FPR ≤ 5% 的约束下取 TPR 最大的阈值；单目标不可兼得时按严重度分级（warn/block 双阈值）；
4. **固化**：标定结果写入 `config.yaml` 并在事件里记录 `guards_config_version`；
5. **复标定触发**：更换嵌入模型、更换生成模型、scope 模板大改、语料结构变化。

**验收目标（初值，待标定确认）**：注入集检出率 ≥ 0.90（漂移/循环/停滞/超时/幻觉诱导各自）、正常样本误报率 ≤ 0.05、可恢复类自愈成功率 ≥ 0.80、abort 100% 带 annotate。

---

## 13. 测试与验收

**单元测试（每个守卫必测）**
- 阈值 ±ε 两侧行为；空输入/超大输入；`severity` 与 `action` 映射正确；恢复包结构合法。

**状态机测试**
- 每条条件边可达性（构造触发条件走到目标）；回退次数上限；跨 stage 累计上限；无"死状态"（每个状态都有出口）。

**集成测试（注入集）**
| 注入 | 预期事件链 |
|---|---|
| 越界检索 | `guard_trigger(E_GUARD_OOS)` → `recovery(retry)` → 收紧查询 → `phase_change(exit, ok)` |
| 重复工具序列 | `guard_trigger(E_GUARD_LOOP)` → `recovery(replan)` → 新计划 |
| 无新增状态 | `guard_trigger(E_GUARD_STAGNATION)` → `recovery(degrade)` |
| provider 超时 | `guard_trigger(E_LLM_TIMEOUT)` → 熔断 → `recovery(degrade)` 切备用 provider |
| 伪造引用 | `guard_trigger(E_GROUND_UNRESOLVED_CITATION)` → claim 标记/重写 |
| 预算超限 | `metric(budget_used)` → `guard_trigger(E_BUDGET_*)` → annotated 报告 |

**端到端验收**
- 连续 3 次正常 run：误报率 ≤ 5%，无 abort，报告 grounding 支持率 ≥ 基线；
- 注入集全跑：检出率/处置正确率/恢复成功率达标（§12），越界副作用率 = 0。

---

## 14. 开放问题与待标定项

1. G1 scope 相似度的嵌入模型选择（bge-m3 vs 专用句向量）与阈值需实测；
2. G3 查询意图分类用规则 vs 小模型 vs 云 LLM——成本与准确率权衡；
3. G12 矛盾检测是否进首版（会引入额外成本与误报）；
4. 回退预算的全局次数（6 次）与单边次数需按真实 run 分布调整；
5. "降级占比 > 30%" 的阈值是否合理，需评测分桶数据支撑；
6. 恢复包注入是否会干扰后续模型输出（需 A/B 验证）。
