# Phase 2.2 —— 收尾、可观测与前端质量（Closeout · Observability · UX）

> **文档性质**：**规范性文件（冻结契约）**。本阶段"做什么 / 什么算做完 / 按什么顺序"以本文件为唯一判据。
> **版本**：**1.1.0**（2026-10-23，S1–S2 已落地）
> **前序**：`phase2.1-wiring-and-contracts.md` v2.0.0（已收尾）、ADR-0007（NodeIO 与配置冻结）、ADR-0006（事件格式冻结）。
> **入口基线**：`verify_phase2_1 13/13`、`verify_phase2 12/12`、`verify_phase1 13/13`、`pytest 439 例`、`e2e 8 passed`、`ruff clean`、`vue-tsc 0 error`。

---

## 0. 目标、边界与"完成"定义

### 0.1 目标（一句话）

**只做"不会被 Phase 3 节点重构淘汰"的收尾**：把 2.1 遗留的配置/限额/漂移/观测/前端质量补齐，让系统"可配置、可解释、可演示"，**不动节点结构**。

### 0.2 四条硬规则

| 规则 | 内容 | 违反后果 |
|---|---|---|
| **R1 范围冻结** | 只做 §7 的 S1–S8；新想法进 §6 | 范围蔓延 |
| **R2 不重构** | **不改图拓扑、不合节点、不加 plan/MicroAgent、不改阶段契约** | 与 Phase 3 冲突、白干 |
| **R3 单步可逆** | 每步有开关/参数，收尾：`pytest` 全绿 + `ruff` clean + 本阶段断言绿 | 不可回退 |
| **R4 零迁移** | 不新增表/列/迁移（观测用事件/指标表已有列） | 迁移返工 |

### 0.3 反向定义

> **2.2 结束 ⇔ §11 的 H1–H8 全绿，且 §5 的 P0 清零。**
> 此后问题：登记 → 排 2.3 / Phase 3 / Phase 4，**不重开 2.2**。

### 0.4 明确"不做"（避免与 Phase 3 抢工）

| 不做 | 原因 | 归属 |
|---|---|---|
| 节点合并（10→8） | Phase 3 会重排节点 | Phase 3 |
| `plan` 节点 | 属"控制层"，Phase 3 3.0 | Phase 3 |
| `MicroAgent` / ReAct | 同上 | Phase 3 |
| 语义分节（报告） | analysis/report 会被重构 | Phase 3 3.2 |
| `agents.chat` | P3 | Phase 3.3 |
| PDF 真实下载 | 依赖外网与沙盒 | Phase 4 |
| 沙盒 / 权限 | 依赖工具协议 v2 | Phase 3.4 |

---

## 1. 入口条件

| # | 条件 | 验证 |
|---|---|---|
| E1 | Phase 2.1 已收尾 | `phase2.1-wiring-and-contracts.md` §14 = COMPLETE |
| E2 | 基线全绿 | `pytest -q`、`verify_phase2_1 --all`、`verify_phase2`、`verify_phase1 --online`、`npm run test:e2e` |
| E3 | 可回退 | `git tag phase2.1-rc1`（负责人执行） |
| E4 | 缺口清单已冻结 | §6 表无"未定级" |
| E5 | 配置基线可读 | ADR-0007 的配置名/默认值表 |

---

## 2. 现状盘点（2.2 的全部输入）

### 2.1 2.1 遗留的六项偏差

| ID | 偏差 | 证据 | 2.2 处置 |
|---|---|---|---|
| 2.1-a | `limits.max_total_llm_calls` 未接线 | 只有金额预算 | ✅ S2 |
| 2.1-b | `gates.evidence_min_cards` 未使用 | 门禁判 `selected==0` | ✅ S3 |
| 2.1-c | `pipeline.*` 配置未进 `Settings` | 用参数/常量 | ✅ S1 |
| 2.1-d | PDF 真实下载链路 | 只有本地文本缓存 | ⏳ P4 |
| 2.1-e | 漂移检测无产出者 | `drift_*` 无写入 | ✅ S4 |
| 2.1-f | H14 未并入验证器 | 由既有脚本覆盖 | ✅ S8（并入 `--baseline`） |

### 2.2 其他缺口（本阶段可安全关闭）

| ID | 项 | 影响 |
|---|---|---|
| G-17 | 失败态 / 断线 / 并发仅手动验证 | 演示时容易翻车 |
| OBS-1 | 没有阶段耗时 | 无法解释"为什么慢" |
| OBS-2 | 前端看不到单 run 成本/耗时 | 演示缺少"可信感" |
| OBS-3 | 指标 API 无前端消费 | 数据白算 |

---

## 3. 设计原则

1. **配置只加不改**：新配置都有与现状一致的默认值，**默认行为零变化**（否则会破坏 439 例基线）。
2. **观测走已有事件/指标表**：不新增表；`phase_change end` 加 `duration_ms`（只增字段）。
3. **门禁只强化不放松**：`evidence_min_cards` 默认 = 1（与现状一致），生产建议 3；测试显式设 1 或 3。
4. **前端只消费接口**：`GET /runs/{id}/metrics` 已存在，字段只增不改。

---

## 4. 模块与验收判据（M1–M5）

### M1 配置体系落地（Settings.pipeline）

| 项 | 内容 |
|---|---|
| **目标** | 把 ADR-0007 的配置名真正接进 `Settings`，改配置即改行为，**无需改代码** |
| **增量** | `config.py` 新增 `GateSettings / LimitSettings / PipelineSettings`；`Settings.pipeline`；`RunContext.pipeline`；门禁/supervisor/hybrid/transitions/pdf 改读配置 |
| **完成判据** | ① 默认值与现状逐项一致（快照测试）；② 改 `LIT_PIPELINE__GATES__EVIDENCE_MIN_CARDS=3` → 行为变化；③ 非法值（负数/未知动作）启动即报 `E_CONFIG_INVALID`；④ `tests/config/test_pipeline_settings.py` 绿 |
| **重难点** | 环境变量嵌套前缀与现有 `Settings` 机制一致；**默认值必须等于今天的常量**，否则全部测试抖动 |
| **禁止** | 为省事把默认值改成"更合理"的值（属行为变更，另开阶段） |
| **OOS** | 配置热更新、远程配置中心 |
| **依赖** | 无（第一步） |

**冻结字段（与 ADR-0007 对齐）**

```python
class GateSettings(BaseModel):
    enabled: bool = True
    evidence_min_cards: int = 1          # 现状等价；生产建议 3
    support_ratio_min: float = 0.6
    citation_required: bool = True

class LimitSettings(BaseModel):
    max_attempts: dict[str, int] = {"analysis": 2, "retrieval": 2, "report": 1}
    max_total_llm_calls: int = 12
    recursion_limit: int = 60
    max_run_usd: float = 2.0

class PipelineSettings(BaseModel):
    gates: GateSettings = GateSettings()
    limits: LimitSettings = LimitSettings()
    transitions: bool = True
    hybrid_alpha: float = 0.6
    hybrid_min_score: float = 0.15
    llm: Literal["auto", "on", "off"] = "auto"
    pdf_enabled: bool = False
```

### M2 LLM 调用数硬顶（2.1-a）

| 项 | 内容 |
|---|---|
| **目标** | 单 run 的 LLM 调用次数不超过 `max_total_llm_calls`，超限中止 |
| **增量** | `gates.gate_llm_calls`：`SELECT COUNT(*) FROM llm_calls WHERE run_id=:run` ≥ 上限 → `abort E_BUDGET_EXCEEDED`；`RunContext` 暴露 `llm_calls_used` 便于事件记录 |
| **完成判据** | ① 预插 12 条 `llm_calls` → 下一次运行在第 1 个门禁就 abort；② 11 条时仍可再调用 1 次；③ 事件 payload 带 `llm_calls_used`；④ `tests/gates/test_llm_cap.py` 绿 |
| **重难点** | 计数口径：**所有尝试**（含失败）都算，避免"失败重试不计数"被滥用；与金额预算并存，谁先触发谁生效 |
| **禁止** | 用内存计数器（进程重启会丢） |
| **OOS** | 分布式配额 |
| **依赖** | M1 |

### M3 证据阈值生效（2.1-b）

| 项 | 内容 |
|---|---|
| **目标** | `evidence_min_cards` 真正决定"证据够不够" |
| **增量** | `gate_evidence_sufficiency` 改判 `selected < min_cards`；门禁 details 带 `selected/min_cards/repair_target` |
| **完成判据** | ① min_cards=1：选 1 篇即通过；② min_cards=3：选 1 篇 → repair→retrieval（attempt 2）→ 仍不足 → degrade；③ 默认值 1 时全量基线不回归；④ `tests/gates/test_evidence_threshold.py` 绿 |
| **重难点** | **测试夹具**：大量既有用例只有 1 篇论文。方案：`tests/wiring/__init__.prepare()` 显式设 `evidence_min_cards=1`；阈值用例单独构造 3 篇。不要为了过测把生产默认改成 1 后忘记文档说明 |
| **禁止** | 把"没选中"与"少于 N 篇"混为一谈（要能区分） |
| **OOS** | 语义相关性阈值（P3） |
| **依赖** | M1 |

### M4 漂移产出者（2.1-e）

| 项 | 内容 |
|---|---|
| **目标** | 有人真正计算"这轮跑题没有"，让 `drift` 门禁与 `E1/E2` 边不再空转 |
| **增量** | `eval/scope_drift.py`：scope tokens vs claims/证据 tokens 的覆盖率；返回 `{score, verdict: ok|warn|block}`；`analysis` 节点写入 `drift_warn/drift_block` 计数；门禁在 critique/report 读取 |
| **完成判据** | ① scope="protein folding" + agent 论文 → `drift_warn`（score < 0.15）；② 完全不相关 → `drift_block`（score < 0.05）→ run aborted；③ 正常 scope → 0 告警（**健康 run 零误报**）；④ `tests/gates/test_scope_drift.py` 绿 |
| **重难点** | 阈值要可配（`gates.drift_warn_below / drift_block_below`）；确定性词面法对短 scope 敏感，需最小 token 数保护 |
| **禁止** | 把"没有证据"当成"跑题"（两回事） |
| **OOS** | LLM 语义漂移判定（P3 3.4，作为可选工具） |
| **依赖** | M1 |

### M5 可观测 + 前端质量（OBS-1..3、G-17）

| 项 | 内容 |
|---|---|
| **目标** | 能回答"这一步多久、这次花了多少"；失败/断线/连点有自动化保障 |
| **增量** | ① `phase_change end` payload 加 `duration_ms`；② `evaluate` 汇总 `duration_{stage}_ms` 落 `metrics`；③ 指标 API 返回 `duration_by_stage`；④ 前端 run 头部显示 `cost_usd` + 最慢阶段；⑤ e2e 2 条（连点 409、SSE 断线回轮询）+ 组件测试 2 条（FailureCard、ErrorBanner） |
| **完成判据** | ① 一次 run 有 10 条 `duration_ms` 且总和 ≈ 墙钟时间（±20%）；② API `duration_by_stage` 非空；③ 前端显示成本与最慢阶段；④ e2e 10 passed、组件测试 2 passed；⑤ F13 纪律仍 PASS |
| **重难点** | 耗时统计放在 runner（最准），不要放在节点里（节点不感知调度）；前端只读接口，不引入新状态 |
| **禁止** | 为显示方便改事件类型；在页面里写样式（F13） |
| **OOS** | 跨 run 趋势图（2.3） |
| **依赖** | M1（指标字段） |

---

## 5. 缺陷分级与处置

| 级别 | 定义 | 处置 |
|---|---|---|
| **P0** | 出口断言红 / 配置不生效 / 指标错 / 误报 | 本阶段关闭 |
| **P1** | 影响体验或可解释性 | 本阶段尽量 |
| **P2** | 未实现、美化、性能 | §6 backlog |

**纪律**：新增配置必须**默认等价于现状**；任何"顺手改默认值"视为行为变更，须单独评审。

---

## 6. 缺口登记（2.2 起点）

| ID | 项 | 级别 | 归属 |
|---|---|---|---|
| 2.2-01 | 配置体系（M1） | P0 | 本阶段 |
| 2.2-02 | LLM 调用硬顶（M2） | P0 | 本阶段 |
| 2.2-03 | 证据阈值（M3） | P0 | 本阶段 |
| 2.2-04 | 漂移产出者（M4） | P0 | 本阶段 |
| 2.2-05 | 观测 + 前端质量（M5） | P1 | 本阶段 |
| 2.1-d | PDF 真实下载 | P2 | P4 |
| G-24 | 语义分节 | P2 | P3 |
| 2.3-01 | 多话题/定时任务界面 | P2 | 2.3（可选） |

---

## 7. 实施步骤 S1–S8

> 每步：**前置 / 产物 / 门禁 / 回滚点**。每轮只做一个 S；收尾输出三件套。

| 步 | 模块 | 目标 | 产物（文件级） | 关键门禁 | 回滚点 | 预估 |
|---|---|---|---|---|---|---|
| **S1** ✅ | M1 | 配置进 Settings | `config.py`、`runtime/context.py`、`graph/gates.py`、`graph/nodes.py`、`graph/transitions.py`、`runtime/graph_runner.py` | 默认快照一致；env 生效；非法值 E_CONFIG_INVALID | 回滚提交 | 4 h |
| **S2** ✅ | M2 | LLM 调用硬顶 | `graph/gates.py`（gate_llm_calls）、事件 `details`、`tests/gates/test_llm_cap.py` | 预插 12 条 → abort（零写入）；11 条可完成；上限可配 | 上限调大即缓解 | 2 h |
| **S3** | M3 | 证据阈值 | `graph/gates.py`、`tests/wiring/__init__.py`（夹具显式 1） | 1 篇通过 / 3 篇修复后降级 | 阈值设 1（等价现状） | 2.5 h |
| **S4** | M4 | 漂移产出 | `eval/scope_drift.py`、`graph/nodes.py`（analysis 写计数）、`gates.py` | 跑题 → warn/block；正常 → 0 | 关闭 `drift.enabled` | 3 h |
| **S5** | M5 | 耗时 + 指标 | `runtime/graph_runner.py`（duration_ms）、`eval/metrics.py`、`api/routes/runs.py` | 10 条 duration；API 非空 | 前端不读即无影响 | 3 h |
| **S6** | M5 | 前端展示 | `RunWorkspace.vue`（成本/最慢阶段）、`types.gen.ts` 重生成 | 显示正确；F13 PASS | 回退组件 | 2 h |
| **S7** | M5 | e2e/组件测试 | `web/e2e/smoke.spec.ts`（+2）、`web/vitest.config.ts`、`web/src/components/__tests__/*`（2）、`package.json` 增 `test:unit` | e2e 10 passed；组件 2 passed | 删除新用例与依赖 | 4 h |
| **S8** | M0 | 收尾 | `RESULTS-P2.2.md`、`verify_phase2_1.py` 加 `--baseline`、known-gaps 更新 | H1–H8 全绿 | —— | 2 h |

**合计 ≈ 22.5 人时（约 2.5–3 个工作日）**

### 7.1 每步 Definition of Done

1. 新增代码有测试，且**先红后绿**（配置/门禁类必须有负例）；
2. `pytest -q` 全绿、`ruff clean`；
3. 本步门禁命令输出贴进 `RESULTS-P2.2.md`；
4. 开关默认值写进文档，并验证"关掉后老测试全绿"；
5. 前端步（S6/S7）另加 `npm run typecheck && npm run build`。

### 7.2 不变量

| # | 不变量 | 原因 |
|---|---|---|
| I1 | 默认配置下行为与 2.1 完全一致 | 否则 439 例基线不可用 |
| I2 | 阈值/上限只从配置读，不硬编码 | 可回退 |
| I3 | 门禁失败零写入（沿用 2.1） | 坏数据不入库 |
| I4 | 漂移判定不能把"空证据"算作漂移 | 语义不同 |
| I5 | 耗时由 runner 记，不由节点记 | 节点不感知调度 |
| I6 | 前端只消费 API，不新增业务判断 | 避免前后端双写逻辑 |
| I7 | 零迁移 | 观测用现有表 |

### 7.3 返工风险登记

| # | 风险 | 规避 |
|---|---|---|
| 1 | 改默认值导致全量抖动 | 默认=现状 + 快照测试 |
| 2 | 证据阈值把 1 篇用例全打红 | 夹具显式设 1，阈值用例单独构造 3 篇 |
| 3 | 漂移误报打断正常 run | "健康 run 零告警"作为 H3 级断言 |
| 4 | 耗时字段改了事件契约 | 只增 `duration_ms`，不改类型 |
| 5 | 前端展示引入页面样式 | F13 检查 + 复用组件 |
| 6 | 与 Phase 3 抢工（重构节点） | R2 明令禁止 |

### 7.4 禁止项

1. 不改图/节点/阶段契约；
2. 不为"更好看"改默认值；
3. 不加迁移；
4. 不跨步提交；
5. 不删测试换绿。

---

## 8. 分批计划

| 批次 | 步骤 | 交付后的状态 |
|---|---|---|
| 批 1（可配置） | S1 → S2 → S3 | 限额与阈值真的生效，且默认不扰民 |
| 批 2（可信） | S4 → S5 | 漂移有人算、耗时有人记 |
| 批 3（可演示） | S6 → S7 → S8 | 前端能看到成本/耗时；失败/断线有测试 |

---

## 9. 前端改动细节（M5/S6/S7）

| 位置 | 改动 | 约束 |
|---|---|---|
| `RunWorkspace.vue` 头部 | `cost_usd` + `slowest_stage`（来自 metrics API） | 只读 props，不新增状态 |
| `TrajectoryTimeline.vue` | 每条 `phase_change end` 显示 `duration_ms` | 已有事件字段，无新接口 |
| `useRunSession.ts` | 加载 metrics（成功 run 时） | 失败不影响主流程 |
| 组件测试 | `FailureCard`：四要素渲染；`ErrorBanner`：错误码→人话 | 需新增 Vitest + @vue/test-utils + `test:unit`（当前只有 Playwright） |
| e2e | 连点两次「开始生成」→ 第二次 409 内联提示；拦截 SSE 响应 → 轮询兜底仍能完成 | 复用 `page.route`，不依赖后端故障注入 |

---

## 10. 验证器（`verify_phase2_1.py` 扩展）

| 新增断言 | 内容 |
|---|---|
| `--config` | 默认值与快照一致；env 覆盖生效 |
| `--limits` | LLM 调用上限 / 证据阈值 |
| `--drift` | 跑题告警、正常零告警 |
| `--observability` | duration 字段完整、API 非空 |
| `--ux` | e2e/组件测试通过 |
| `--baseline` | 并联 `verify_phase1/2`（关闭 2.1-f） |

---

## 11. 出口标准 H1–H8

| # | 判据 | 命令 | 期望 |
|---|---|---|---|
| H1 | 配置生效且默认等价 | `pytest -q tests/config`；`verify_phase2_1 --config` | 快照一致；env 覆盖生效 |
| H2 | LLM 调用硬顶 | `verify_phase2_1 --limits` | 12 条即 abort |
| H3 | 证据阈值 | `pytest -q tests/gates -k evidence` | 1/3 两种行为正确 |
| H4 | 漂移产出 | `verify_phase2_1 --drift` | warn/block 可触发，健康 run 0 告警 |
| H5 | 观测 | `verify_phase2_1 --observability` | 10 条 duration；API 有 `duration_by_stage` |
| H6 | 前端质量 | `npm run test:e2e`；`npm run test:unit` | e2e ≥10；组件 ≥2 |
| H7 | 基线不回归 | `verify_phase2_1 --all`；`verify_phase2`；`verify_phase1 --online`；`pytest -q` | 13+/13；12/12；13/13；全绿 |
| H8 | 文档 | 本文件 + `RESULTS-P2.2.md` | 数字与命令一致 |

---

## 12. 经验教训适配

| # | 教训 | 约束 |
|---|---|---|
| 1 | 能力探针绿但生产没用 | 配置/阈值一律用**行为测试**验证生效 |
| 2 | 守卫误报（2.1） | 漂移必须测"不触发" |
| 3 | 零值/缺失不区分 | 空证据 ≠ 漂移 |
| 4 | 指标口径反复 | 耗时定义写死（runner 计时） |
| 5 | 默认值即契约 | 默认=现状 + 快照 |
| 6 | 前端只消费 | 不改接口语义 |

---

## 13. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| 1.1.0 | 2026-10-23 | S1–S2 落地：pipeline 配置进 Settings（默认=现状）、门禁/回边/hybrid/pdf/llm 全部读配置；新增 LLM 调用数硬顶（DB 计数）；`pytest 448 例`，2.1 验证器 13/13 |
| **1.0.0** | 2026-10-23 | 首版：M1–M5、S1–S8、H1–H8；明确"不动节点结构"；关闭 2.1-a/b/c/e/f；G-17 用 2 e2e + 2 组件测试收口（需补 Vitest）；ADR-0007 默认值随本阶段更新 |

---

## 附录 A · 命令速查

```powershell
. .\scripts\env.ps1
uv run pytest -q
uv run ruff check .
uv run python scripts/verify_phase2_1.py --all
uv run python scripts/verify_phase2_1.py --config --limits --drift --observability
uv run python scripts/verify_phase2.py --offline
uv run python scripts/verify_phase1.py --online
cd web; npm run typecheck; npm run build; npm run test:e2e; npm run test:unit
```

## 附录 B · 配置清单（本阶段冻结）

| 配置 | 默认 | 说明 |
|---|---|---|
| `pipeline.gates.enabled` | true | 总开关 |
| `pipeline.gates.evidence_min_cards` | 1 | 与现状等价；生产建议 3（已可配；env 名 `LIT_AGENT_PIPELINE__GATES__EVIDENCE_MIN_CARDS`） |
| `pipeline.gates.support_ratio_min` | 0.6 | 与 critic 一致 |
| `pipeline.gates.drift_warn_below` | 0.15 | 覆盖率低于 → warn |
| `pipeline.gates.drift_block_below` | 0.05 | 低于 → block |
| `pipeline.limits.max_total_llm_calls` | 12 | 超限 abort |
| `pipeline.limits.max_attempts` | analysis/retrieval=2, report=1 | 与 transitions 一致 |
| `pipeline.transitions` | true | 回边总开关 |
| `pipeline.hybrid_alpha` | 0.6 | 关键词/字符权重 |
| `pipeline.pdf_enabled` | false | P4 打开 |
