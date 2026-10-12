# ADR 0002: 指标事件契约（`metric{kind}`）与"事件即真相源"的埋点义务

Status: accepted（Phase 0 实测后冻结，Phase 1 沿用）
Date: 2026-10-09
Context:
- S7 的目标是"**只读事件**算出 5 个指标"（口径见 `evaluation-plan.md` §5）。
  实测过程中三次因埋点缺失而算不出指标：
  1. S5 的 `metric` 事件只有 `claims` 总数，没有按 `support` 分级计数 → grounding 支持率/幻觉率算不出；
  2. 主题相关度（§5.1 `mean(cos(claim, scope))`）没有埋点 → 事后无法补算；
  3. 单 run 成本/时延只在 summary 文件里、不在事件里 → 指标必须回头读文件（违背"只读事件"）。
- 另有一处**日志/事件混淆**：S6 的 provider 超时只调用了 `log_event`（写 `logs/app.jsonl`），
  没写事件 → §5.3 的 TPR 里 timeout 族**恒为 0**（假阴性，不报错）。
- 结论：**"日志是给人看的，事件是给指标与回放用的"**，凡是要被指标/回放消费的事实必须写事件。

Decision:
1. `metric` 事件统一携带 `kind` 字段，Phase 0 冻结三种：
   | kind | 产出方 | 必需 payload |
   |---|---|---|
   | `grounding` | S5 报告阶段 | `claims`、`verifiable_claims`、`claims_supported`、`claims_contradicted`、`claims_unsupported`、`claims_dropped_ungrounded`、`distinct_cited_papers`、`ungrounded_citation_count`、`report_chars`、`topicality_mean`、`topic` |
   | `run_summary` | run 收尾 | `cost_usd`、`seconds`、`llm_calls`、`network_calls`、`cache_hits`、`prompt_tokens`、`completion_tokens`、`cost_known`、`topic` |
   | 守卫 run | S6/编排层 | `scenario`、`guard_hits`、`recovered`、`aborted`、`budget` |
2. 事实双写规则：**任何"会被指标或回放消费"的事实，必须同时写事件**；
   `log_event` 只用于人读日志，不得作为唯一落点（本轮 timeout 就是这么漏的）。
3. 错误类事实必须带 `error_code`（事件 payload 与日志行都带），用于 TPR/错误分类学统计。
4. 同一 run 的多次尝试：事件按 `run_id` 累加（见 S4 结论），因此**消费方取"最后一条同类事件"**，
   并把 `metric_events` 计数写入指标行，使重复尝试显式可见（`steps/s7_metrics.py` 已实现）。

Impact:
- 契约：`implementation-guide.md` §2.2 事件表需补 `metric.kind` 约定；`EventType` 不变（仍是 `metric`）。
- 受影响模块：`agents/reporter.py`（grounding 事件）、`runtime/`（run_summary）、`graph/guards.py`（守卫事件）、
  `eval/metrics.py`（消费方，只读事件）。
- 测试：`tests/test_metrics.py`（12 例，含"取最后一条""timeout 靠 error 事件"等回归）。

Migration:
- Phase 0：已按上表实现（S5 5.6/5.7、S6 run_once）。
- Phase 1：事件落 SQLite `run_events`（表加 `payload` JSON 列 + `kind` 索引），本 ADR 的 payload 约定不变。

Verification:
```bash
uv run python steps/s5_walking_skeleton.py --topic T1 --run-id p0-s5-adr2    # 产生 grounding/run_summary 事件
uv run python steps/s7_metrics.py --explain p0-s5-adr2                       # 事件侧即可复算指标
uv run pytest -q tests/test_metrics.py
```
