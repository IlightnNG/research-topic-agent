"""Step 7（S7）：最小指标集与汇总——只从 **JSONL 事件**聚合。

内容要求（见 `docs/implementation/phase0-implementation-steps.md` §Step 7）
1. 五个数字：**grounding 支持率**、**幻觉率**、**漂移检出率**、**循环检出率**、**单 run 成本与时延**；
2. 输出 `out/metrics_summary.csv`（每 run 一行）+ 一页结论（可直接粘进 `RESULTS.md`）；
3. 可选柱状图（本轮不做：matplotlib 未装，且 Phase 0 不要求前端）。

口径来源（**严格对齐 `implementation/evaluation-plan.md` §5，不自行发明**）
| 指标 | 公式（§5.1 / §5.3） | 本脚本实现说明 |
|---|---|---|
| grounding 支持率 | `|supported| / |verifiable_claims|` | 取该 run 最后一条 `metric{kind:grounding}` |
| 幻觉率 | `(|contradicted| + |unsupported|) / |verifiable|` | **外加** S5 因 citation 不可回查而丢弃的 claim（§5.5：claim 无 citation → 计入 unsupported） |
| 严重幻觉率 | `|contradicted| / |verifiable|` | 同上分母 |
| 主题相关度 | `mean(cos(report_section, scope_statement))` | 由 S5 在 5.6 计算的 `topicality_mean` |
| 漂移率 | `漂移事件数 / run 数` | `guard_trigger{code=E_GUARD_DRIFT}` 计数 |
| 检出率(TPR) | `被捕获注入数 / 注入总数`（分故障类型） | 按 S6 场景 → 期望错误码映射统计 |
| 处置正确率 | `动作符合预期数 / 检出数` | 场景→期望动作映射 |
| 自愈成功率 | `恢复到正常完成态的注入数 / 检出数` | S6 `metric{recovered}` |
| 越界副作用率 | `产生错误报告的注入数 / 注入总数` | 报告 run 中 `ungrounded_citation_count > 0` 记为越界（安全底线，目标 0） |
| 误报率(FPR) | `正常 run 中触发守卫的 run 数 / 正常 run 数` | S6 `scenario == none` 的 run |
| 成本与时延 | 单 run 成本/时延 | `metric{kind:run_summary}` 的 `cost_usd` / `seconds` |

设计要点
- **只读事件**：不读 `s5_summary.json` / `s6_summary.json`，这样"指标算不出"就暴露为**埋点缺失**，
  逼着补埋点（spec 的"埋点先于指标"）。本轮就因此给 S5 补了 grounding 分级计数与 topic 相关度埋点。
- **同一 run 多次尝试**：事件按 run_id 累加（S4 已实测），故每个指标取**最后一条**同类事件，
  并把 `metric_events` 计数写进 CSV——重复尝试会显式可见，而不是悄悄把数字算大。
- **纯函数聚合**：`aggregate_run()` / `aggregate_all()` 可单测（`tests/test_metrics.py`）。

用法
```bash
uv run python steps/s7_metrics.py                                   # 读默认事件源，产出 CSV + 报告
uv run python steps/s7_metrics.py --explain p0-s5-008               # 抽查单个 run 的构成事件（手工核对）
uv run python steps/s7_metrics.py --events out/events.jsonl,out/s6/guards_drift_*.jsonl
```
产出：`out/metrics_summary.csv`、`out/metrics_aggregate.json`、`out/metrics_report.md`。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lit_agent_min import read_events  # noqa: E402
from lit_agent_min.models import Event  # noqa: E402

# S6 场景 → (期望错误码, 期望动作)：用于 TPR 与"处置正确率"（口径写在代码里，避免口径漂移）
SCENARIO_EXPECTATIONS: dict[str, tuple[str, str]] = {
    "drift": ("E_GUARD_DRIFT", "replan"),
    "loop": ("E_GUARD_LOOP", "abort"),
    "stagnation": ("E_GUARD_STAGNATION", "abort"),
    "timeout": ("E_PROVIDER_TIMEOUT", "degrade"),
    "budget": ("E_BUDGET_EXCEEDED", "abort"),
    "none": ("", ""),
}

CSV_COLUMNS = [
    "run_id",
    "kind",
    "scenario",
    "topic",
    "status",
    "claims",
    "verifiable_claims",
    "claims_supported",
    "claims_contradicted",
    "claims_unsupported",
    "claims_dropped_ungrounded",
    "grounding_support_rate",
    "hallucination_rate",
    "severe_hallucination_rate",
    "topicality_mean",
    "distinct_cited_papers",
    "ungrounded_citation_count",
    "report_chars",
    "drift_events",
    "loop_events",
    "stagnation_events",
    "budget_events",
    "guard_events",
    "guard_actions",
    "recovery_actions",
    "aborted",
    "recovered",
    "cost_usd",
    "seconds",
    "llm_calls",
    "network_calls",
    "cache_hits",
    "prompt_tokens",
    "completion_tokens",
    "event_count",
    "metric_events",
    "seq_contiguous",
]


# --------------------------------------------------------------------------- #
# 单 run 聚合（纯函数，便于单测）
# --------------------------------------------------------------------------- #
def _last_of(events: Iterable[Event], predicate: Any) -> dict[str, Any] | None:
    found: dict[str, Any] | None = None
    for event in events:
        if predicate(event):
            found = dict(event.payload or {})
    return found


def aggregate_run(run_id: str, events: list[Event]) -> dict[str, Any]:
    """把一个 run 的事件聚合成一行指标（口径见模块 docstring 的映射表）。"""
    events = sorted(events, key=lambda e: e.seq)
    payloads = [dict(e.payload or {}) for e in events]

    grounding = _last_of(events, lambda e: e.payload and e.payload.get("kind") == "grounding")
    run_summary = _last_of(events, lambda e: e.payload and e.payload.get("kind") == "run_summary")
    guard_metrics = [
        dict(e.payload or {})
        for e in events
        if e.type == "metric" and (e.payload or {}).get("recovered") is not None
    ]

    def code_count(code: str) -> int:
        return sum(
            1 for e in events if e.type == "guard_trigger" and (e.payload or {}).get("code") == code
        )

    guard_codes = [str((e.payload or {}).get("code")) for e in events if e.type == "guard_trigger"]
    guard_actions = sorted(
        {str((e.payload or {}).get("action")) for e in events if e.type == "guard_trigger"}
    )
    # harness 级处置（如 timeout → degrade）走 recovery 事件，也要计入"处置正确率"，
    # 否则 timeout 族的处置正确率会恒为 0（S7 实测踩到）
    recovery_actions = sorted(
        {str((e.payload or {}).get("action")) for e in events if e.type == "recovery"}
    )
    all_actions = sorted({*guard_actions, *recovery_actions})
    errors = [str((e.payload or {}).get("error_code")) for e in events if e.type == "error"]
    scenario = ""
    for payload in payloads:
        if payload.get("scenario"):
            scenario = str(payload["scenario"])
            break

    supported = int((grounding or {}).get("claims_supported", 0) or 0)
    contradicted = int((grounding or {}).get("claims_contradicted", 0) or 0)
    unsupported = int((grounding or {}).get("claims_unsupported", 0) or 0)
    dropped = int((grounding or {}).get("claims_dropped_ungrounded", 0) or 0)
    claims = int((grounding or {}).get("claims", 0) or 0)
    # §5.5：无 citation 的 claim 计入 unsupported，而不是从分母里消失
    verifiable = int((grounding or {}).get("verifiable_claims", claims + dropped) or 0)
    hallucinated = contradicted + unsupported + dropped

    def rate(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 4) if denominator else None

    seqs = [e.seq for e in events]
    recovered = guard_metrics[-1].get("recovered") if guard_metrics else None
    aborted = bool(guard_metrics[-1].get("aborted")) if guard_metrics else False

    return {
        "run_id": run_id,
        "kind": "report" if grounding else ("guards" if guard_codes or scenario else "other"),
        "scenario": scenario,
        "topic": str((grounding or run_summary or {}).get("topic", "")),
        "status": "aborted"
        if aborted
        else ("ok" if (run_summary or recovered is not None) else "unknown"),
        "claims": claims,
        "verifiable_claims": verifiable,
        "claims_supported": supported,
        "claims_contradicted": contradicted,
        "claims_unsupported": unsupported + dropped,
        "claims_dropped_ungrounded": dropped,
        "grounding_support_rate": rate(supported, verifiable),
        "hallucination_rate": rate(hallucinated, verifiable),
        "severe_hallucination_rate": rate(contradicted, verifiable),
        "topicality_mean": (grounding or {}).get("topicality_mean"),
        "distinct_cited_papers": int((grounding or {}).get("distinct_cited_papers", 0) or 0),
        "ungrounded_citation_count": int(
            (grounding or {}).get("ungrounded_citation_count", 0) or 0
        ),
        "report_chars": int((grounding or run_summary or {}).get("report_chars", 0) or 0),
        "drift_events": code_count("E_GUARD_DRIFT"),
        "loop_events": code_count("E_GUARD_LOOP"),
        "stagnation_events": code_count("E_GUARD_STAGNATION"),
        "budget_events": code_count("E_BUDGET_EXCEEDED"),
        "guard_events": len(guard_codes),
        "guard_actions": "|".join(guard_actions),
        "recovery_actions": "|".join(recovery_actions),
        "all_actions": "|".join(all_actions),
        "aborted": aborted,
        "recovered": recovered,
        "cost_usd": float((run_summary or {}).get("cost_usd", 0.0) or 0.0),
        "seconds": float((run_summary or {}).get("seconds", 0.0) or 0.0),
        "llm_calls": int((run_summary or {}).get("llm_calls", 0) or 0),
        "network_calls": int((run_summary or {}).get("network_calls", 0) or 0),
        "cache_hits": int((run_summary or {}).get("cache_hits", 0) or 0),
        "prompt_tokens": int((run_summary or {}).get("prompt_tokens", 0) or 0),
        "completion_tokens": int((run_summary or {}).get("completion_tokens", 0) or 0),
        "event_count": len(events),
        "metric_events": sum(1 for e in events if e.type == "metric"),
        "seq_contiguous": seqs == list(range(1, len(seqs) + 1)),
        "simulated_crash": "E_SIMULATED_CRASH" in errors,
        "provider_timeout": "E_PROVIDER_TIMEOUT" in errors,
    }


def aggregate_all(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """跨 run 汇总（§5.1 池化 + §5.3 检出/误报/自愈/越界 + 成本时延）。"""
    reports = [r for r in rows if r["kind"] == "report"]
    guards = [r for r in rows if r["kind"] == "guards"]
    normal = [r for r in guards if r["scenario"] == "none"]

    supported = sum(r["claims_supported"] for r in reports)
    verifiable = sum(r["verifiable_claims"] for r in reports)
    contradicted = sum(r["claims_contradicted"] for r in reports)
    unsupported = sum(r["claims_unsupported"] for r in reports)

    def rate(numerator: float, denominator: float) -> float | None:
        return round(numerator / denominator, 4) if denominator else None

    # 检出率/处置正确率/自愈成功率：分故障类型
    by_fault: dict[str, dict[str, Any]] = {}
    for scenario, (expected_code, expected_action) in SCENARIO_EXPECTATIONS.items():
        family = [r for r in guards if r["scenario"] == scenario]
        if not family:
            continue
        # 检出判定按"故障族的可观测证据"分派：
        # - guard 族（drift/loop/stagnation/budget）：看对应的 guard_trigger 错误码；
        # - timeout 族：**没有 guard_trigger**，证据是 error 事件里的 E_PROVIDER_TIMEOUT
        #   （踩过的坑：把 timeout 也按 guard_events 判 → 检出率恒为 0）。
        if scenario == "timeout":
            hits = [r for r in family if r["provider_timeout"]]
        else:
            hits = [
                r
                for r in family
                if expected_code and r["guard_events"] > 0 and _has_code(r, expected_code)
            ]
        correct = [
            r
            for r in hits
            if expected_action and expected_action in (r["all_actions"] or "").split("|")
        ]
        recovered = [r for r in hits if r["recovered"] is True]
        by_fault[scenario] = {
            "runs": len(family),
            "detected": len(hits),
            "detection_rate": rate(len(hits), len(family)),
            "expected_code": expected_code or None,
            "expected_action": expected_action or None,
            "correct_action": len(correct),
            "action_correct_rate": rate(len(correct), len(hits)) if hits else None,
            "recovered": len(recovered),
            "self_heal_rate": rate(len(recovered), len(hits)) if hits else None,
            "aborted": sum(1 for r in family if r["aborted"]),
        }

    injected = [s for s in by_fault if s != "none"]
    tprs = [by_fault[s]["detection_rate"] for s in injected]
    costs = [r["cost_usd"] for r in reports]
    seconds = [r["seconds"] for r in reports]

    def percentile(values: list[float], q: float) -> float | None:
        """nearest-rank 分位数（样本量小的时候比 int(n*q) 更稳：n=2 时 p50 取小者而非最大者）。"""
        if not values:
            return None
        ordered = sorted(values)
        rank = max(0, min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1))
        return round(ordered[rank], 4)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "runs": {
            "total": len(rows),
            "report": len(reports),
            "guards": len(guards),
            "normal_control": len(normal),
        },
        "metrics": {
            # §5.1（池化：按 claim 数加权，等价于把所有 claim 放一起算）
            "grounding_support_rate": rate(supported, verifiable),
            "hallucination_rate": rate(contradicted + unsupported, verifiable),
            "severe_hallucination_rate": rate(contradicted, verifiable),
            "topicality_mean": round(
                statistics.mean(
                    [r["topicality_mean"] for r in reports if r["topicality_mean"] is not None]
                ),
                6,
            )
            if any(r["topicality_mean"] is not None for r in reports)
            else None,
            "verifiable_claims_total": verifiable,
            "support_label_source": "llm_self_label",
            "citation_resolvable_rate": rate(
                sum(1 for r in reports if r["ungrounded_citation_count"] == 0), len(reports)
            ),
            "support_note": (
                "Phase 0 的 supported/contradicted/unsupported 来自生成模型的**自报标签**；"
                "§5.1 要求的独立核验（claim 抽取 → 快照回查 → 三类判定）需 gold 事实集（D2），属 P3。"
                "citation 可回查性已由 S5 强制校验（不可回查的 claim 计入 unsupported）"
            ),
            # §5.3
            "drift_rate": rate(sum(r["drift_events"] for r in guards), len(guards)),
            "drift_event_rate_per_run": rate(sum(r["drift_events"] for r in guards), len(guards)),
            "loop_rate": rate(sum(r["loop_events"] for r in guards), len(guards)),
            "detection_rate_min_by_fault": min(tprs) if tprs else None,
            "detection_rate_all_faults_ge_0_9": all(t >= 0.9 for t in tprs) if tprs else None,
            "false_positive_rate": rate(
                sum(1 for r in normal if r["guard_events"] > 0), len(normal)
            )
            if normal
            else None,
            "out_of_scope_side_effect_rate": rate(
                sum(1 for r in reports if r["ungrounded_citation_count"] > 0), len(reports)
            ),
            # 成本与时延
            "cost_usd_total": round(sum(r["cost_usd"] for r in rows), 6),
            "cost_usd_mean_per_report": round(statistics.mean(costs), 6) if costs else None,
            "cost_usd_max_per_report": round(max(costs), 6) if costs else None,
            "cost_note": "均值为本次 campaign 观测（含缓存命中的 $0 run）；max 可作冷启动成本上界",
            "seconds_mean_per_report": round(statistics.mean(seconds), 3) if seconds else None,
            "seconds_p50": percentile(seconds, 0.5),
            "seconds_p95": percentile(seconds, 0.95),
            "cache_hit_rate_reports": rate(
                sum(r["cache_hits"] for r in reports), sum(r["llm_calls"] for r in reports)
            )
            if sum(r["llm_calls"] for r in reports)
            else None,
        },
        "by_fault": by_fault,
        "integrity": {
            "all_runs_seq_contiguous": all(r["seq_contiguous"] for r in rows),
            "runs_with_multiple_attempts": sorted(
                r["run_id"] for r in rows if r["metric_events"] > 2
            ),
        },
    }


def _has_code(row: dict[str, Any], code: str) -> bool:
    field = {
        "E_GUARD_DRIFT": "drift_events",
        "E_GUARD_LOOP": "loop_events",
        "E_GUARD_STAGNATION": "stagnation_events",
        "E_BUDGET_EXCEEDED": "budget_events",
    }.get(code)
    if field is None:
        return row["guard_events"] > 0
    return int(row.get(field, 0)) > 0


# --------------------------------------------------------------------------- #
# 读写
# --------------------------------------------------------------------------- #
def load_events(paths: list[Path]) -> dict[str, list[Event]]:
    by_run: dict[str, list[Event]] = {}
    for path in paths:
        matched = (
            sorted(path.parent.glob(path.name)) if any(ch in path.name for ch in "*?[") else [path]
        )
        for single in matched:
            if not single.exists():
                continue
            for event in read_events(single):
                by_run.setdefault(str(event.run_id), []).append(event)
    return by_run


def write_csv(rows: list[dict[str, Any]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (r["kind"], r["run_id"])):
            writer.writerow({key: row.get(key) for key in CSV_COLUMNS})


def render_report(agg: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    m = agg["metrics"]
    lines = [
        "# Phase 0 最小指标集（S7 自动生成）",
        "",
        f"> 生成时间：{agg['generated_at']} · 数据来源：JSONL 事件（**只读事件**，不读 summary 文件）",
        f"> run 统计：共 {agg['runs']['total']}（报告 {agg['runs']['report']} / 守卫 {agg['runs']['guards']} / 正常对照 {agg['runs']['normal_control']}）",
        "",
        "## 1. 五个指标（口径对齐 `evaluation-plan.md` §5）",
        "",
        "| # | 指标 | 公式 | 实测值 |",
        "|---|---|---|---|",
        f"| 1 | grounding 支持率 | `supported/verifiable` | **{m['grounding_support_rate']}**（verifiable={m['verifiable_claims_total']}） |",
        f"| 2 | 幻觉率 | `(contradicted+unsupported)/verifiable` | **{m['hallucination_rate']}** |",
        f"| 2b | 严重幻觉率 | `contradicted/verifiable` | {m['severe_hallucination_rate']} |",
        f"| 2c | 主题相关度 | `mean(cos(claim, scope))` | {m['topicality_mean']} |",
        f"| 3 | 漂移检出率 | `漂移事件/run` + 注入 TPR | 漂移事件率 {m['drift_rate']}；TPR min **{m['detection_rate_min_by_fault']}**（全类 ≥0.9：{m['detection_rate_all_faults_ge_0_9']}） |",
        f"| 4 | 循环检出率 | `循环事件/run` + 注入 TPR | 循环事件率 {m['loop_rate']}；见下表 by_fault |",
        f"| 5 | 成本与时延 | 单 run | 报告均值 **${m['cost_usd_mean_per_report']}** / **{m['seconds_mean_per_report']}s**（p50 {m['seconds_p50']}s / p95 {m['seconds_p95']}s）；单 run 最高 ${m['cost_usd_max_per_report']}；总成本 ${m['cost_usd_total']} |",
        f"| 2d | citation 可回查率 | 报告 run 中无越界引用占比 | {m['citation_resolvable_rate']} |",
        "",
        f"> ⚠️ **口径警示**：{m['support_note']}",
        "> 即：本轮的 grounding/幻觉率是**自报标签**下的数字，可作为「模型自称的有据率」，"
        "**不等于** §5.1 定义的经独立核验的忠实度；后者需要 D2 gold 事实集（P3）。",
        "",
        "## 2. 守卫有效性（§5.3）",
        "",
        "| 场景 | runs | 检出 | 检出率 | 处置正确率 | 自愈率 | abort |",
        "|---|---|---|---|---|---|---|",
    ]
    for scenario, stat in agg["by_fault"].items():
        lines.append(
            f"| {scenario} | {stat['runs']} | {stat['detected']} | {stat['detection_rate']} | "
            f"{stat['action_correct_rate']} | {stat['self_heal_rate']} | {stat['aborted']} |"
        )
    lines += [
        "",
        f"- **误报率 FPR**（正常 run 触发守卫）：**{m['false_positive_rate']}**（安全要求 = 0）",
        f"- **越界副作用率**（报告含不可回查引用）：**{m['out_of_scope_side_effect_rate']}**（安全底线 = 0）",
        f"- 缓存命中率（报告 run）：{m['cache_hit_rate_reports']}",
        "",
        "## 3. 完整性检查",
        "",
        f"- 全部 run 事件 seq 连续：**{agg['integrity']['all_runs_seq_contiguous']}**",
        f"- 含多次尝试的 run（事件会累加，指标取最后一条）：{agg['integrity']['runs_with_multiple_attempts'] or '无'}",
        "",
        "## 4. 每 run 明细（前 12 行）",
        "",
        "| run_id | kind | scenario | claims | grounding | 幻觉率 | 成本$ | 秒 | 守卫事件 | aborted |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in sorted(rows, key=lambda r: (r["kind"], r["run_id"]))[:12]:
        lines.append(
            f"| {row['run_id']} | {row['kind']} | {row['scenario']} | {row['claims']} | "
            f"{row['grounding_support_rate']} | {row['hallucination_rate']} | {row['cost_usd']} | "
            f"{row['seconds']} | {row['guard_events']} | {row['aborted']} |"
        )
    lines += [
        "",
        "> 完整明细见 `out/metrics_summary.csv`；汇总 JSON 见 `out/metrics_aggregate.json`。",
    ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 0 Step 7：最小指标集与汇总")
    parser.add_argument(
        "--events",
        default="out/events.jsonl,out/s6/guards_*.jsonl",
        help="逗号分隔的事件文件/通配符路径",
    )
    parser.add_argument("--out", default="out/metrics_summary.csv")
    parser.add_argument("--aggregate", default="out/metrics_aggregate.json")
    parser.add_argument("--report", default="out/metrics_report.md")
    parser.add_argument("--explain", default=None, help="打印指定 run 的构成事件（手工核对用）")
    parser.add_argument("--only-kind", choices=("report", "guards", "other"), default=None)
    parser.add_argument(
        "--last-per-scenario",
        type=int,
        default=3,
        help="每个注入场景只取最近 N 次（默认 3，与 --repeats 一致）",
    )
    parser.add_argument("--last-reports", type=int, default=2, help="报告 run 只取最近 N 次")
    parser.add_argument(
        "--all-history",
        action="store_true",
        help="不做 campaign 筛选，把事件目录里所有历史 run 都算进去（仅调试用）",
    )
    parser.add_argument(
        "--include-run",
        default="",
        help="额外纳入指定 run（逗号分隔），例如把冷启动 run 纳入以给出真实成本上界",
    )
    return parser.parse_args(argv)


def select_campaign(
    by_run: dict[str, list[Event]], *, last_per_scenario: int, last_reports: int
) -> dict[str, list[Event]]:
    """挑出**本次评测 campaign** 的 run 子集。

    为什么需要：事件目录里会积累大量历史尝试（失败的、改阈值前的、调试用的），
    把"全部历史 run"一起算指标只会得到无意义的数字（实测 92 个 run 里混着修复前的守卫行为）。
    规则（与真实评测一致）：守卫 run 取**每个场景最近 N 次**，报告 run 取**最近 N 次**。
    """
    guards: dict[str, list[tuple[Any, str]]] = {}
    reports: list[tuple[Any, str]] = []
    for run_id, events in by_run.items():
        row = aggregate_run(run_id, events)
        latest = max((e.ts for e in events), default=None)
        if row["kind"] == "report":
            reports.append((latest, run_id))
        elif row["kind"] == "guards":
            guards.setdefault(row["scenario"] or "unknown", []).append((latest, run_id))

    selected: dict[str, list[Event]] = {}
    for _scenario, items in guards.items():
        for _ts, run_id in sorted(items, key=lambda x: (str(x[0]), x[1]))[-last_per_scenario:]:
            selected[run_id] = by_run[run_id]
    for _ts, run_id in sorted(reports, key=lambda x: (str(x[0]), x[1]))[-last_reports:]:
        selected[run_id] = by_run[run_id]
    return selected


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(__file__).resolve().parents[1]

    event_paths = [
        (Path(part) if Path(part).is_absolute() else root / part)
        for part in (p.strip() for p in args.events.split(","))
        if part.strip()
    ]
    all_runs = load_events(event_paths)
    by_run = (
        all_runs
        if args.all_history
        else select_campaign(
            all_runs, last_per_scenario=args.last_per_scenario, last_reports=args.last_reports
        )
    )
    for extra in (part.strip() for part in args.include_run.split(",")):
        if extra and extra in all_runs:
            by_run[extra] = all_runs[extra]
    rows = [aggregate_run(run_id, events) for run_id, events in sorted(by_run.items())]

    if args.explain:
        events = [e for rid, evs in by_run.items() if rid == args.explain for e in evs]
        print(f"=== run {args.explain}：{len(events)} 条事件（手工核对用） ===")
        for event in sorted(events, key=lambda e: e.seq):
            payload = dict(event.payload or {})
            keys = (
                "kind",
                "phase",
                "node",
                "code",
                "action",
                "recovered",
                "aborted",
                "scenario",
                "claims",
                "claims_supported",
                "claims_contradicted",
                "claims_unsupported",
                "claims_dropped_ungrounded",
                "verifiable_claims",
                "distinct_cited_papers",
                "ungrounded_citation_count",
                "cost_usd",
                "seconds",
                "topicality_mean",
                "report_chars",
            )
            shown = {k: payload[k] for k in keys if k in payload}
            print(
                f"  seq={event.seq:3d} {str(event.type):14s} {str(event.stage or '-'):14s} {shown}"
            )
        return 0

    if args.only_kind:
        rows = [r for r in rows if r["kind"] == args.only_kind]

    aggregate = aggregate_all(rows)
    out_csv = root / args.out
    write_csv(rows, out_csv)
    (root / args.aggregate).write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    report_path = root / args.report
    report_path.write_text(render_report(aggregate, rows), encoding="utf-8")

    m = aggregate["metrics"]
    acceptance = {
        "五个指标可算": all(
            m[key] is not None
            for key in (
                "grounding_support_rate",
                "hallucination_rate",
                "drift_rate",
                "loop_rate",
                "cost_usd_mean_per_report",
            )
        ),
        "注入检出率 ≥0.9": m["detection_rate_all_faults_ge_0_9"] is True,
        "正常 run 误报 = 0": m["false_positive_rate"] == 0.0,
        "越界副作用率 = 0": m["out_of_scope_side_effect_rate"] == 0.0,
        "事件 seq 全连续": aggregate["integrity"]["all_runs_seq_contiguous"],
    }
    print(
        f"事件源 {len(event_paths)} 个 → runs={aggregate['runs']['total']}"
        f"（report={aggregate['runs']['report']} guards={aggregate['runs']['guards']}）"
    )
    print(
        f"① grounding 支持率 {m['grounding_support_rate']}  ② 幻觉率 {m['hallucination_rate']} "
        f"（严重 {m['severe_hallucination_rate']}）  主题相关度 {m['topicality_mean']}"
    )
    print(
        f"③ 漂移率 {m['drift_rate']}  ④ 循环率 {m['loop_rate']}  "
        f"注入 TPR min={m['detection_rate_min_by_fault']}"
    )
    print(
        f"⑤ 成本均值 ${m['cost_usd_mean_per_report']} / 时延均值 {m['seconds_mean_per_report']}s "
        f"（p95 {m['seconds_p95']}s）总成本 ${m['cost_usd_total']}"
    )
    print(
        f"FPR={m['false_positive_rate']}  越界副作用率={m['out_of_scope_side_effect_rate']}  "
        f"缓存命中率={m['cache_hit_rate_reports']}"
    )
    print("\n验收:")
    for name, ok in acceptance.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    print(f"\nCSV     {out_csv}")
    print(f"报告    {report_path}")
    print(f"汇总    {root / args.aggregate}")
    return 0 if all(acceptance.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
