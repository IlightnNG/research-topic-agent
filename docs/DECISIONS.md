# Decisions

> 版本：1.0（2026-10-31）
> 用途：记录不可反复摇摆的架构决定。变更必须新增一条，不覆盖历史。
> 完整背景见 `docs/ARCHITECTURE.md`。

---

## D-001 · 六模块固定

- 日期：2026-10-31
- 状态：accepted
- 决定：系统固定为 M1 Engine / M2 Source / M3 Evidence / M4 Report / M5 Evaluation / M6 Interface。
- 原因：跨模块 phase 导致反复返工；模块化后独立优化。
- 约束：一个 phase 只改一个模块。

## D-002 · 外层 Workflow 固定

- 日期：2026-10-31
- 状态：accepted
- 决定：Workflow 由代码声明，运行时不增删节点。
- 原因：保证可恢复、可测试、可审计。
- 约束：Kernel 只能拆当前节点任务。

## D-003 · 新包不 import 旧包

- 日期：2026-10-31
- 状态：accepted
- 决定：`lit_agent_v2` 不 import `lit_agent`；旧代码已移出。
- 原因：防止旧架构污染。
- 约束：import guard 测试必须存在。

## D-004 · 字数只做 gate

- 日期：2026-10-31
- 状态：accepted
- 决定：1500–3000 words 只作为 gate，不进入质量正分。
- 原因：字数可刷，不能代表质量。
- 约束：评分使用模块分 + 方向分 + 硬门禁。

## D-005 · Report 分方向生成

- 日期：2026-10-31
- 状态：accepted
- 决定：先 ReportPlan，再逐方向生成/校验/追加，最后全局检查。
- 原因：一次性全量 writer 导致覆盖不足、无法局部修复。
- 约束：方向 section 独立重试。

## D-006 · Claim 必须有类型

- 日期：2026-10-31
- 状态：accepted
- 决定：claim 分为 finding/method/dataset/limitation/background；作者列表等拒绝。
- 原因：真实报告出现作者名 claim。
- 约束：purity 只统计 research claim。

## D-007 · 指标不作为唯一优化目标

- 日期：2026-10-31
- 状态：accepted
- 决定：LLM judge + 人工抽检 + 规则门禁共同判断。
- 原因：单一指标会被 gaming。
- 约束：评估集只读。

## D-008 · 错误/日志/指标分离

- 日期：2026-10-31
- 状态：accepted
- 决定：Event / Log / Metric 三类数据分开；错误有统一 code。
- 原因：避免“日志当事件、事件当指标”。
- 约束：见 `ERRORS.md`、`LOGGING.md`。

---

## 变更规则

1. 新决定追加 D-009；
2. 不删除历史；
3. 推翻旧决定必须写 supersedes；
4. 影响接口的决定必须同步模块 README；
5. phase 文档引用相关 D-xxx。


## D-009 · 模块只依赖 contracts/ports

- 日期：2026-10-31
- 状态：accepted
- 决定：M1–M6 之间只允许 import `contracts/` 中的 port/artifact；唯一例外是 `composition.py`。
- 原因：消除 M4/M5/M6 对具体实现的直接依赖。
- 约束：冻结后由 import guard + contract tests 保证；破坏性变更升 major。

## D-010 · 组合根唯一装配

- 日期：2026-10-31
- 状态：accepted
- 决定：新增 `src/lit_agent_v2/composition.py`，只做构造/注入，不写业务逻辑。
- 原因：模块内部不再 new 其他模块实现。
- 约束：M1–M6 不允许 import composition。


## D-011 · Contracts v1.0 frozen

- 日期：2026-10-31
- 状态：accepted
- 决定：冻结 `src/lit_agent_v2/contracts/` 的 port/artifact/error/event 契约，`CONTRACT_VERSION=1.0`。
- Hash：`c13bb3fa8b16263c69c44e6a16adf733074e6016b12147b1bbf23ea781897dc7`
- 约束：
  - contract freeze test 必须通过；
  - 修改任何 contract（除 `version.py`）必须同步更新 hash、版本和本文件；
  - breaking change 升 major；
  - M1–M6 不允许绕过 ports。


## D-012 · Contracts v1.1 (claim type)

- 日期：2026-10-31
- 状态：accepted
- 决定：`Claim` 新增可选字段 `claim_type`，默认 `finding`；`CONTRACT_VERSION=1.1`。
- Hash：`8df591896a40b6efd65780191a9b94ad76f39316cdf06c96274574ab6b8f4f96`
- 原因：M3-P01 必须区分 finding/method/dataset/limitation/background，且不能把作者列表计入 purity。
- 兼容性：additive minor；旧调用不需要改。


## D-013 · Contracts v1.2 (paper authors)

- 日期：2026-10-31
- 状态：accepted
- 决定：`Paper` 新增可选 `authors` 列表，`CONTRACT_VERSION=1.2`。
- Hash：`cf2243febe2d1b924b4ca2c179abee9a341d703ed9945ba1ae579eeb2daf9e90`
- 原因：M2-P01 需要 authors 进入 metadata / paper index，并计算 authors rate。
- 兼容性：additive minor；旧 JSON 缺 authors 时为空列表。
