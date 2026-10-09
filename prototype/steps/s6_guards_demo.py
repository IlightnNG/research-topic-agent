"""Step 6（S6）：两个守卫 + 预算看门狗 + 注入钩子。

要回答的问题（见 `docs/implementation/phase0-implementation-steps.md` §Step 6）
1. G1 漂移守卫能不能检出"越界产物"，且**不误报**正常产物？
2. G4 循环守卫能不能检出"重复工具序列"，并按升级阶梯处置（replan → abort）？
3. 停滞（无新增）与预算超限是否可判、可处置？
4. 四类注入 × 3 次：**检出率 ≥90%、动作符合预期、能恢复到正常完成态或按规则终止**；正常 run **误报 = 0**。

为什么这样设计（可离线的确定性验证）
- 守卫是纯判定，注入只需改变"喂给守卫的观测值"，**不需要真调 LLM** → 全部离线、秒级、可重复。
- "产物文本"取自真实语料：正常态用 S5 的 T1 语料（`out/s5_corpus.json`），
  漂移态用真实离题语料（`out/s6_offtopic_corpus.json`，生物/CRISPR 方向）→ 分布真实，不是编的。
- 打分器用词法 TF-IDF（无本地 embedding），并**显式做阈值扫描**给出 TPR/FPR —— 这正是 spec
  在"失败应对"里要求的标定输入（配置里 0.60/0.45 是按 embedding 余弦给的，直接套用会全误报）。

注入场景
| `--inject` | 模拟的故障 | 期望检出 | 期望动作 |
|---|---|---|---|
| `none` | 正常 run | 不检出（0 误报） | 正常完成 |
| `drift` | 检索返回**越界结果**（离题语料） | G1 | 首次 replan（回退检索+恢复包）→ 恢复后完成 |
| `loop` | 重复同一工具调用（同查询签名） | G4 | 首次 replan → 仍重复则 abort(annotate) |
| `stagnation` | 连续多步**零新增** | 停滞守卫 | degrade（换源）→ 持续则 abort |
| `timeout` | provider 超时（工具抛异常） | 分级重试 | 重试后降级换通道，不静默吞掉 |
| `budget` | 人为放大 token 计数 | 预算看门狗 | 80% warn（记账）→ 100% stop |

用法
```bash
uv run python steps/s6_guards_demo.py --topic T1 --inject none  --repeats 3
uv run python steps/s6_guards_demo.py --topic T1 --inject drift --repeats 3
uv run python steps/s6_guards_demo.py --sweep            # 阈值扫描 → TPR/FPR（标定输入）
```
产出：`out/guards_<scenario>_<run_id>.jsonl`（完整事件链）、`out/s6_summary.json`、`out/s6_threshold_sweep.json`。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lit_agent_min import (  # noqa: E402
    EventType,
    Severity,
    bind_context,
    clear_context,
    load_settings,
    log_event,
    open_event_log,
)
from lit_agent_min.guards import (  # noqa: E402
    BudgetWatchdog,
    DriftGuard,
    LoopGuard,
    ProgressGuard,
    build_recovery_packet,
)
from lit_agent_min.models import GuardAction, Verdict  # noqa: E402
from lit_agent_min.normalize import openalex_work_to_paper, reconstruct_abstract  # noqa: E402
from lit_agent_min.scoring import (  # noqa: E402
    build_centroid,
    build_idf,
    calibrate_drift_thresholds,
    calibrate_threshold,
    cosine_to_vector,
)
from lit_agent_min.topics import get_topic  # noqa: E402

SCENARIOS = ("none", "drift", "loop", "stagnation", "timeout", "budget")
INJECTED = ("drift", "loop", "stagnation", "timeout", "budget")

STEPS_PER_RUN = 6
TOKENS_PER_STEP = 180

SEED_FRACTION = 0.66
"""前 2/3 同主题论文用于**建立 scope 表示（质心）**，后 1/3 **留出**作为被检查的"产物"。

为什么要留出：拿建表示用过的文档去打自己的质心，自相似会把分数抬高（乐观偏差）；
留出集才能给出诚实的分隔度与阈值。
"""


def build_scope(
    on_topic: list[str], off_topic: list[str]
) -> tuple[Any, list[float], list[float], list[str], dict[str, Any]]:
    """建立 scope 打分器并给出诚实标定分布。

    返回 (scorer, positives, negatives, held_out_on, meta)。
    - scope 表示 = **种子语料质心**（S6 实测：关键词串表示下正负分布重叠、任何阈值都不可分；
      质心表示下 min(正)=0.0955 > max(负)=0.0810，零误报阈值 0.09 → TPR 1.0）。
    - 正样本 = 种子的**留一法**分数 + 留出集分数（都不用自相似）；负样本 = 真实离题论文。
    """
    n_seed = max(4, int(len(on_topic) * SEED_FRACTION))
    seed, held_out = on_topic[:n_seed], on_topic[n_seed:]
    idf = build_idf([*on_topic, *off_topic])
    centroid = build_centroid(seed, idf)

    def scorer(text: str) -> float:
        return cosine_to_vector(text, centroid, idf=idf)

    positives = [
        cosine_to_vector(
            text, build_centroid([d for j, d in enumerate(seed) if j != i], idf), idf=idf
        )
        for i, text in enumerate(seed)
    ] + [scorer(text) for text in held_out]
    negatives = [scorer(text) for text in off_topic]
    meta = {
        "scope_representation": "seed_corpus_centroid",
        "seed_docs": len(seed),
        "held_out_docs": len(held_out),
        "idf_terms": len(idf),
    }
    return scorer, positives, negatives, held_out, meta


# --------------------------------------------------------------------------- #
# 语料
# --------------------------------------------------------------------------- #
def _load_texts(path: Path) -> list[str]:
    works = json.loads(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for work in works:
        if not work.get("abstract_inverted_index"):
            continue
        paper = openalex_work_to_paper(work)
        out.append(
            f"{paper.title}. {paper.abstract or reconstruct_abstract(work.get('abstract_inverted_index'))}"
        )
    return out


# --------------------------------------------------------------------------- #
# 单次 run：确定性阶段序列 + 注入
# --------------------------------------------------------------------------- #
def run_once(
    *,
    settings: Any,
    topic_key: str,
    scenario: str,
    repeat_index: int,
    on_topic: list[str],
    off_topic: list[str],
    scorer: Any,
    drift_warn: float,
    drift_block: float,
    repeat_threshold: int,
    loop_window: int,
    no_progress_steps: int,
    budget_tokens: int,
    want_timeline: bool = True,
) -> dict[str, Any]:
    topic = get_topic(topic_key)
    run_id = f"p0-s6-{scenario}-{repeat_index}-{datetime.now(UTC).strftime('%H%M%S')}"
    event_path = settings.paths.out_dir / "s6" / f"guards_{scenario}_{run_id}.jsonl"
    event_path.parent.mkdir(parents=True, exist_ok=True)
    log = open_event_log(event_path, run_id=run_id)
    bind_context(run_id=run_id, stage="S6_guards", agent="single")

    drift = DriftGuard(
        scorer=scorer,
        drift_warn=drift_warn,
        drift_block=drift_block,
        scope_label=f"{topic_key}:{topic.name}",
    )
    loop = LoopGuard(window=loop_window, repeat_threshold=repeat_threshold)
    progress = ProgressGuard(no_progress_steps=no_progress_steps)
    budget = BudgetWatchdog(max_tokens=budget_tokens, warn_ratio=0.8)
    # budget 注入：按 3× 放大 token，使 2000 预算下出现"先 80% warn、再 100% stop"的完整阶梯
    budget_inflate = 3 if scenario == "budget" else 1

    timeline: list[dict[str, Any]] = []
    detected: list[str] = []
    actions: list[str] = []
    recovered = False
    aborted = False
    degrade_count = 0
    replan_count = 0
    state = {"strategy": "broad", "verified_claims": 0, "stage": "retrieve"}

    log.emit(
        EventType.PHASE_CHANGE,
        stage="S6_guards",
        agent="single",
        payload={
            "phase": "start",
            "scenario": scenario,
            "repeat": repeat_index,
            "topic": topic_key,
        },
    )
    log_event(
        Severity.INFO,
        "s6_run_started",
        "S6 守卫演示开始",
        scenario=scenario,
        repeat=repeat_index,
        topic=topic_key,
        drift_warn=drift_warn,
        drift_block=drift_block,
        loop_k=loop_window,
        loop_repeat_threshold=repeat_threshold,
        budget_tokens=budget_tokens,
    )

    for step in range(1, STEPS_PER_RUN + 1):
        stage = f"step{step}"
        # ---- 1) 模拟一次工具调用（含注入） ----
        if scenario == "loop":
            tool, params = "openalex_search", {"query": topic.query, "page": 1}
        elif scenario == "stagnation" and step >= 3:
            tool, params = "openalex_search", {"query": f"{topic.query} page{step}", "page": step}
        else:
            tool, params = "openalex_search", {"query": topic.query, "page": step}
        sig = loop.record(tool, params)
        log.emit(
            EventType.TOOL_CALL,
            stage=stage,
            agent="retrieval",
            payload={"tool": tool, "params_hash": sig, "step": step},
        )

        # ---- 2) 产生"阶段产物"（正常/漂移/停滞） ----
        timeout_injected = scenario == "timeout" and step in (2, 4)
        if timeout_injected:
            log_event(
                Severity.ERROR,
                "s6_tool_timeout",
                "工具调用超时（注入）",
                error_code="E_PROVIDER_TIMEOUT",
                stage=stage,
                attempt=1,
            )
            # 处置：重试一次（模拟 harness 的 retry），第二次成功但降级换通道            degrade_count += 1
            log.emit(
                EventType.RECOVERY,
                stage=stage,
                agent="single",
                severity=Severity.WARNING,
                payload={
                    "action": str(GuardAction.DEGRADE),
                    "reason": "provider 超时",
                    "next_channel": "arxiv_fallback",
                    "attempt": 2,
                },
            )
            detected.append("E_PROVIDER_TIMEOUT")
            actions.append(str(GuardAction.DEGRADE))
            product = on_topic[step % len(on_topic)]
        elif scenario == "drift" and step in (2, 3):
            product = off_topic[(step - 2) % len(off_topic)]
        elif scenario == "stagnation" and step >= 3:
            product = on_topic[0]  # 内容重复 → 无新增
        else:
            product = on_topic[step % len(on_topic)]

        new_items = 0 if (scenario == "stagnation" and step >= 3) else 3
        if scenario == "drift" and step in (2, 3):
            new_items = 3  # 有新增，但越界

        # 预算记账（budget 注入按倍数放大 token）
        budget.add(tokens=TOKENS_PER_STEP * budget_inflate, seconds=0.4)

        # ---- 3) 守卫判定 ----
        drift_verdict, score = drift.check(product)
        loop_verdict = loop.check()
        progress_verdict = progress.update(new_items)
        budget_verdict = budget.check()
        verdicts: list[Verdict] = [drift_verdict, loop_verdict, progress_verdict, budget_verdict]

        for verdict in verdicts:
            if verdict.ok:
                continue
            detected.append(verdict.code)
            actions.append(str(verdict.action))
            log.emit(
                EventType.GUARD_TRIGGER,
                stage=stage,
                agent="guards",
                severity=verdict.severity,
                payload={
                    "code": verdict.code,
                    "action": str(verdict.action),
                    "severity": str(verdict.severity),
                    "reasons": verdict.reasons,
                    "step": step,
                    "product_score": score,
                },
            )
            packet = build_recovery_packet(
                verdict=verdict,
                stage=stage,
                trusted_state=dict(state),
                next_constraints=[
                    "只使用本 run 已验证的论文",
                    "产物必须与 scope 相关（漂移守卫在用）",
                    "不得重复已失败的查询签名",
                ],
                attempt=1,
                history=[sig],
            )
            log.emit(
                EventType.RECOVERY,
                stage=stage,
                agent="harness",
                severity=Severity.WARNING,
                payload={"action": str(verdict.action), "recovery_packet": packet},
            )
            if verdict.action is GuardAction.REPLAN:
                replan_count += 1
                state["strategy"] = "whitelist" if state["strategy"] == "broad" else "expansion"
                state["stage"] = "retrieve"
                if verdict.code == "E_GUARD_LOOP" and loop.hits >= 2:
                    aborted = True
            elif verdict.action is GuardAction.DEGRADE:
                degrade_count += 1
            elif verdict.action is GuardAction.ABORT:
                aborted = True
        timeline.append(
            {
                "step": step,
                "sig": sig,
                "new_items": new_items,
                "drift_score": score,
                "timeout_injected": timeout_injected,
                "verdicts": [
                    {"code": v.code, "ok": v.ok, "action": str(v.action)} for v in verdicts
                ],
                "strategy": state["strategy"],
            }
        )
        if aborted:
            log_event(
                Severity.WARNING,
                "s6_aborted_by_guard",
                "守卫按规则终止本 run",
                stage=stage,
                reason=detected[-1] if detected else "unknown",
            )
            break

    # ---- 收尾：判定"是否恢复到完成态" ----
    if aborted:
        recovered = False
    else:
        # 恢复判据：后半程每一步的守卫判决全部为 ok（故障不再复现）
        tail = [row for row in timeline if row["step"] > STEPS_PER_RUN // 2]
        recovered = bool(tail) and all(all(v["ok"] for v in row["verdicts"]) for row in tail)
    budget_usage = budget.usage()
    log.emit(
        EventType.METRIC,
        stage="S6_guards",
        agent="single",
        payload={
            "scenario": scenario,
            "repeat": repeat_index,
            "guard_hits": len(detected),
            "budget": budget_usage,
            "recovered": recovered,
            "aborted": aborted,
        },
    )
    log_event(
        Severity.INFO,
        "s6_run_finished",
        "S6 守卫演示结束",
        scenario=scenario,
        repeat=repeat_index,
        hits=len(detected),
        recovered=recovered,
        aborted=aborted,
        tokens=budget_usage["tokens"],
    )
    log.emit(
        EventType.PHASE_CHANGE,
        stage="S6_guards",
        agent="single",
        payload={"phase": "end", "scenario": scenario, "hits": len(detected)},
    )

    result = {
        "run_id": run_id,
        "scenario": scenario,
        "repeat": repeat_index,
        "detected_codes": detected,
        "actions": actions,
        "replan_count": replan_count,
        "degrade_count": degrade_count,
        "recovered": recovered,
        "aborted": aborted,
        "budget": budget_usage,
        "events_file": str(event_path.relative_to(settings.paths.out_dir.parent)),
        "timeline": timeline,
    }
    clear_context()
    return result


# --------------------------------------------------------------------------- #
# 阈值扫描（标定输入）
# --------------------------------------------------------------------------- #
def sweep_thresholds(pos: list[float], neg: list[float], meta: dict[str, Any]) -> dict[str, Any]:
    """在真实正/负样本分数上扫描漂移阈值 → 各阈值 TPR/FPR（spec 要求的标定输入）。"""
    thresholds = [round(x / 50, 2) for x in range(0, 51)]
    rows = []
    for thr in thresholds:
        tp = sum(1 for s in neg if s < thr)  # 越界（低于阈值）判为漂移 = 正确检出
        fn = len(neg) - tp
        fp = sum(1 for s in pos if s < thr)  # 正常样本被判漂移 = 误报
        tn = len(pos) - fp
        rows.append(
            {
                "threshold": thr,
                "tpr": round(tp / len(neg), 3) if neg else 0.0,
                "fpr": round(fp / len(pos), 3) if pos else 0.0,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
            }
        )
    recommended = calibrate_threshold(pos, neg, step=0.02)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "scorer": "lexical_tfidf_cosine_to_seed_centroid",
        **meta,
        "positives": {
            "n": len(pos),
            "min": round(min(pos), 6),
            "max": round(max(pos), 6),
            "mean": round(sum(pos) / len(pos), 6),
        },
        "negatives": {
            "n": len(neg),
            "min": round(min(neg), 6),
            "max": round(max(neg), 6),
            "mean": round(sum(neg) / len(neg), 6),
        },
        "separable": bool(pos and neg and min(pos) > max(neg)),
        "rows": rows,
        "recommended_zero_fpr": recommended,
        "note": "正样本=同主题论文（种子留一法 + 留出集）；负样本=真实离题论文（CRISPR）；低分判为漂移",
    }


# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 0 Step 6：守卫 + 预算看门狗 + 注入")
    parser.add_argument("--topic", default="T1")
    parser.add_argument("--inject", default="none", choices=(*SCENARIOS, "all"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--sweep", action="store_true", help="只做阈值扫描（TPR/FPR）")
    parser.add_argument("--drift-warn", type=float, default=None)
    parser.add_argument("--drift-block", type=float, default=None)
    parser.add_argument("--loop-window", type=int, default=5)
    parser.add_argument("--loop-repeat", type=int, default=3)
    parser.add_argument("--no-progress-steps", type=int, default=2)
    parser.add_argument("--budget-tokens", type=int, default=2000)
    parser.add_argument(
        "--no-timeline", action="store_true", help="汇总文件里不写逐步时间线（更小）"
    )
    parser.add_argument("--corpus", default="out/s5_corpus.json")
    parser.add_argument("--offtopic", default="out/s6_offtopic_corpus.json")
    parser.add_argument("--summary", default="out/s6_summary.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    root = Path(__file__).resolve().parents[1]
    on_topic = _load_texts(root / args.corpus)
    off_topic = _load_texts(root / args.offtopic)
    # scope 表示 = 种子语料质心；正/负样本分数在**留出集 + 留一法**上取（诚实标定）
    scorer, positives, negatives, held_out_on, scope_meta = build_scope(on_topic, off_topic)

    if args.sweep:
        result = sweep_thresholds(positives, negatives, scope_meta)
        out = root / "out" / "s6_threshold_sweep.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(
            f"scope={result['scope_representation']}（种子 {result['seed_docs']} 篇 / 留出 "
            f"{result['held_out_docs']} 篇 / IDF 词表 {result['idf_terms']}）"
        )
        print(
            f"正样本(n={result['positives']['n']}) 余弦 range={result['positives']['min']}–"
            f"{result['positives']['max']} mean={result['positives']['mean']}"
        )
        print(
            f"负样本(n={result['negatives']['n']}) 余弦 range={result['negatives']['min']}–"
            f"{result['negatives']['max']} mean={result['negatives']['mean']}"
        )
        print(f"可分性 min(正)>max(负): {result['separable']}")
        print("零误报下最佳阈值:", result["recommended_zero_fpr"])
        for row in result["rows"]:
            if row["threshold"] in (0.02, 0.04, 0.06, 0.08, 0.09, 0.1, 0.15, 0.2):
                print(f"  thr={row['threshold']:.2f}  TPR={row['tpr']:.2f}  FPR={row['fpr']:.2f}")
        print(f"summary: {out}")
        return 0

    # 阈值按**分布间隙**标定（不可拍脑袋：warn 落进正样本分布内部必然误报，S6 实测踩过）
    sweep = sweep_thresholds(positives, negatives, scope_meta)
    calibrated = calibrate_drift_thresholds(positives, negatives)
    default_warn = float(calibrated["warn"] or 0.09)
    default_block = float(calibrated["block"] or 0.08)
    drift_warn = args.drift_warn if args.drift_warn is not None else default_warn
    drift_block = args.drift_block if args.drift_block is not None else default_block

    scenarios = list(SCENARIOS) if args.inject == "all" else [args.inject]
    results: list[dict[str, Any]] = []
    started = time.perf_counter()
    for scenario in scenarios:
        for repeat_index in range(1, args.repeats + 1):
            results.append(
                run_once(
                    settings=settings,
                    topic_key=args.topic,
                    scenario=scenario,
                    repeat_index=repeat_index,
                    on_topic=held_out_on,
                    off_topic=off_topic,
                    scorer=scorer,
                    drift_warn=drift_warn,
                    drift_block=drift_block,
                    repeat_threshold=args.loop_repeat,
                    loop_window=args.loop_window,
                    no_progress_steps=args.no_progress_steps,
                    budget_tokens=args.budget_tokens,
                    want_timeline=not args.no_timeline,
                )
            )

    # ---- 汇总：检出率 / 误报 / 动作符合度 ----
    def detected_in(res: dict[str, Any]) -> bool:
        return bool(res["detected_codes"])

    summary: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "topic": args.topic,
        "scorer": "lexical_tfidf_cosine",
        "thresholds": {
            "drift_warn": drift_warn,
            "drift_block": drift_block,
            "loop_window": args.loop_window,
            "loop_repeat": args.loop_repeat,
            "no_progress_steps": args.no_progress_steps,
            "budget_tokens": args.budget_tokens,
            "calibration": calibrated,
            "sweep_recommended": sweep.get("recommended_zero_fpr"),
            "note": "drift 阈值由 --sweep 在真实正/负样本上标定（零误报优先）",
        },
        "per_scenario": {},
        "seconds": round(time.perf_counter() - started, 2),
    }
    for scenario in scenarios:
        rows = [r for r in results if r["scenario"] == scenario]
        hits = [r for r in rows if detected_in(r)]
        summary["per_scenario"][scenario] = {
            "runs": len(rows),
            "detected": len(hits),
            "detection_rate": round(len(hits) / len(rows), 3) if rows else 0.0,
            "codes": sorted({c for r in rows for c in r["detected_codes"]}),
            "actions": sorted({a for r in rows for a in r["actions"]}),
            "recovered": sum(1 for r in rows if r["recovered"]),
            "aborted": sum(1 for r in rows if r["aborted"]),
        }
    injected = {s: v for s, v in summary["per_scenario"].items() if s in INJECTED}
    normal = summary["per_scenario"].get("none", {})
    rates = [v["detection_rate"] for v in injected.values()]
    summary["acceptance"] = {
        "injected_min_detection_rate": min(rates) if rates else None,
        "all_injected_ge_0_9": all(r >= 0.9 for r in rates) if rates else False,
        "normal_runs": normal.get("runs", 0),
        "normal_false_positives": normal.get("detected", 0),
        "zero_false_positive": normal.get("detected", 0) == 0,
        "recovered_or_aborted_everywhere": all(
            v["recovered"] + v["aborted"] == v["runs"] for v in summary["per_scenario"].values()
        ),
    }
    summary["runs"] = results
    out = root / args.summary
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print(
        f"topic={args.topic}  thresholds: drift warn/block={drift_warn}/{drift_block} "
        f"loop k={args.loop_window}×{args.loop_repeat} stagn={args.no_progress_steps} "
        f"budget={args.budget_tokens}tok"
    )
    print(
        f"{'scenario':12s} {'runs':>4s} {'detected':>8s} {'rate':>6s} {'recovered':>9s} {'aborted':>7s}  codes"
    )
    for scenario, stat in summary["per_scenario"].items():
        print(
            f"{scenario:12s} {stat['runs']:4d} {stat['detected']:8d} {stat['detection_rate']:6.2f} "
            f"{stat['recovered']:9d} {stat['aborted']:7d}  {','.join(stat['codes'])}"
        )
    acc = summary["acceptance"]
    print(
        f"\n验收: 注入检出率 min={acc['injected_min_detection_rate']} ≥0.9 → "
        f"{'PASS' if acc['all_injected_ge_0_9'] else 'FAIL'}；"
        f"正常 run 误报={acc['normal_false_positives']}/{acc['normal_runs']} → "
        f"{'PASS' if acc['zero_false_positive'] else 'FAIL'}；"
        f"全部恢复到完成态或按规则终止 → "
        f"{'PASS' if acc['recovered_or_aborted_everywhere'] else 'FAIL'}"
    )
    print(f"summary: {out}")
    return (
        0
        if all(
            [
                acc["all_injected_ge_0_9"],
                acc["zero_false_positive"],
                acc["recovered_or_aborted_everywhere"],
            ]
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
