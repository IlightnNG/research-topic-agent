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
