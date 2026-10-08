"""Step 4（S4）：长跑恢复验证（LangGraph checkpoint 断点续跑）。

要回答的问题（见 `docs/implementation/phase0-implementation-steps.md` Step 4）
1. 进程被**硬杀**后，重启用同一 `thread_id` 能否从 checkpoint 续跑（而不是从头重跑）？
2. **恢复粒度**是什么：节点边界 / 超级步边界 / 更细？
3. 崩溃点所在节点会**重跑**吗（at-least-once）？已完成节点会不会被重复执行？
4. 事件序列跨进程是否**连续且不重复**（我们自己维护的 per-run seq 能否与框架 checkpoint 配套）？
5. 带**不同输入**重启时，框架用的是 checkpoint 里的状态还是新输入？（守卫设计输入）
6. 对**已完成**的 run 再次触发会怎样（重复触发语义 / 幂等风险）？
7. checkpoint 的落盘形态与体积增长。

设计要点（为什么这样测才可信）
- **崩溃确定性**：不用"掐时间 Ctrl+C"（有竞态、不可复现），而是用**一次性崩溃臂文件**：
  节点开始后检查臂文件，命中则先写 `E_SIMULATED_CRASH` 事件再 `os._exit(9)`
  —— `os._exit` 跳过一切清理与 flush，等价于被 SIGKILL，且崩溃点永远在同一位置。
- **零网络零 LLM**：3 节点小图（`fetch → transform → emit`）+ 可配置短 sleep，纯本地 sqlite。
- **小数据集**：状态只有 topic/步骤列表，无外部数据；单次运行 < 2 s。
- **证据分层**：调用前先落盘"调用前 checkpoint 快照"（pre），因此即使进程随后被杀，
  也能证明"恢复点 = 该节点"；事件写入 `out/events_s4.jsonl`（跨进程按 run_id 续写 seq）。

用法（每个 mode 都是一次独立进程；`crash` 预期非零退出）
```bash
# 场景 A：不崩溃，作为对照
uv run python steps/s4_checkpoint_spike.py --mode baseline --run-id p0-s4-a --label baseline
# 场景 B：在 transform 崩溃 → 重启续跑
uv run python steps/s4_checkpoint_spike.py --mode crash   --run-id p0-s4-b --label 1-crash
uv run python steps/s4_checkpoint_spike.py --mode resume  --run-id p0-s4-b --label 2-resume
# 场景 C：连续两次崩溃（transform → emit）
uv run python steps/s4_checkpoint_spike.py --mode crash   --run-id p0-s4-c --label 1-crash
uv run python steps/s4_checkpoint_spike.py --mode resume  --run-id p0-s4-c --label 2-crash --crash-at emit --arm
uv run python steps/s4_checkpoint_spike.py --mode resume  --run-id p0-s4-c --label 3-resume
# 场景 D：带不同 topic 重启（输入漂移语义）
uv run python steps/s4_checkpoint_spike.py --mode crash   --run-id p0-s4-d --topic T1 --label 1-crash
uv run python steps/s4_checkpoint_spike.py --mode resume  --run-id p0-s4-d --topic T2-CHANGED --label 2-resume
# 场景 E：对已完成的 run 再次触发
uv run python steps/s4_checkpoint_spike.py --mode baseline --run-id p0-s4-e --label 1-first --fresh
uv run python steps/s4_checkpoint_spike.py --mode baseline --run-id p0-s4-e --label 2-dup
# 汇总校验
uv run python steps/s4_checkpoint_spike.py --mode verify
```
产出：`out/s4/*.json`（调用前/后状态快照）、`out/events_s4.jsonl`（事件）、`out/s4_summary.json`（校验结论）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from operator import add
from pathlib import Path
from typing import Annotated, Any, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lit_agent_min import (  # noqa: E402
    EventType,
    JsonlEventLog,
    Severity,
    bind_context,
    clear_context,
    load_settings,
    log_event,
    open_event_log,
    read_events,
    setup_logging,
)

NODES = ("fetch", "transform", "emit")
SCENARIOS = {
    "p0-s4-a": "baseline（不崩溃，对照组）",
    "p0-s4-b": "单次崩溃于 transform → 重启续跑",
    "p0-s4-c": "连续两次崩溃（transform → emit）→ 三次进程完成",
    "p0-s4-d": "带不同 topic 重启（输入漂移语义）",
    "p0-s4-e": "对已完成的 run 再次触发（重复触发语义 / 幂等风险）",
    "p0-s4-f": "正确续跑姿势：invoke(None) 从断点继续（不重跑已完成节点）",
}


class S4State(TypedDict):
    """最小状态：只有 topic/时长/观测记录，无外部依赖。"""

    topic: str
    sleep_s: float
    steps_done: Annotated[list[str], add]
    topic_seen: Annotated[list[str], add]


# --------------------------------------------------------------------------- #
# 事件与快照
# --------------------------------------------------------------------------- #
def events_path(settings: Any) -> Path:
    return settings.paths.out_dir / "events_s4.jsonl"


def s4_dir(settings: Any) -> Path:
    path = settings.paths.out_dir / "s4"
    path.mkdir(parents=True, exist_ok=True)
    return path


def arm_path(settings: Any) -> Path:
    return s4_dir(settings) / "crash_arm.flag"


def arm_crash(settings: Any, node: str) -> None:
    """布置一次性崩溃臂：节点读到自己的名字才崩，崩前删除臂（保证只崩一次）。"""
    arm_path(settings).write_text(node, encoding="utf-8")


def take_arm(settings: Any, node: str) -> bool:
    """命中本节点的崩溃臂才消费它（否则不崩、且不能误删别的节点的臂）。

    踩过的坑：第一版写成"见到臂文件就删"，结果 `fetch` 先执行时把 "transform" 的臂吃掉，
    崩溃点永远不会触发 —— 这类"臂被提前消费"的静默失效，靠最终状态一致性才能发现。
    """
    flag = arm_path(settings)
    if not flag.exists():
        return False
    target = flag.read_text(encoding="utf-8").strip()
    if target != node:
        return False
    flag.unlink()
    return True


def dump(settings: Any, name: str, payload: dict[str, Any]) -> Path:
    path = s4_dir(settings) / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# 图定义
# --------------------------------------------------------------------------- #
def build_graph(saver: Any, log: JsonlEventLog, settings: Any, node_label: str) -> Any:
    from langgraph.graph import END, START, StateGraph

    def make_node(name: str) -> Any:
        def run(state: S4State) -> dict[str, Any]:
            payload = {
                "node": name,
                "label": node_label,
                "pid": os.getpid(),
                "topic_arg": state.get("topic"),
            }
            log.emit(
                EventType.PHASE_CHANGE,
                stage=name,
                agent="single",
                payload={**payload, "phase": "start"},
            )
            log_event(Severity.INFO, "s4_node_started", f"节点 {name} 开始", **payload)

            time.sleep(float(state.get("sleep_s", 0.0)))

            # 崩溃点：节点"做到一半"（尚未返回状态）被杀 → 该节点必须重跑
            if take_arm(settings, name):
                log.emit(
                    EventType.ERROR,
                    stage=name,
                    agent="single",
                    severity=Severity.ERROR,
                    payload={
                        **payload,
                        "phase": "crash",
                        "error_code": "E_SIMULATED_CRASH",
                        "note": "os._exit(9) 模拟硬杀，不经任何清理",
                    },
                )
                log_event(
                    Severity.ERROR,
                    "s4_simulated_crash",
                    f"模拟硬杀于节点 {name}",
                    error_code="E_SIMULATED_CRASH",
                    **payload,
                )
                os._exit(9)

            log.emit(
                EventType.PHASE_CHANGE,
                stage=name,
                agent="single",
                payload={**payload, "phase": "end"},
            )
            return {"steps_done": [name], "topic_seen": [state.get("topic", "")]}

        return run

    graph = StateGraph(S4State)
    for name in NODES:
        graph.add_node(name, make_node(name))
    graph.add_edge(START, "fetch")
    graph.add_edge("fetch", "transform")
    graph.add_edge("transform", "emit")
    graph.add_edge("emit", END)
    return graph.compile(checkpointer=saver)


# --------------------------------------------------------------------------- #
# 单次进程：跑图（baseline / crash / resume 共用）
# --------------------------------------------------------------------------- #
def run_once(args: argparse.Namespace) -> int:
    from langgraph.checkpoint.sqlite import SqliteSaver

    settings = load_settings()
    setup_logging(settings)
    log = open_event_log(events_path(settings), run_id=args.run_id)
    clear_context()
    bind_context(run_id=args.run_id, stage="S4_checkpoint", agent="single")

    if args.mode == "crash" or args.arm:
        arm_crash(settings, args.crash_at)
    log_event(
        Severity.INFO,
        "s4_invocation_started",
        "S4 进程启动",
        mode=args.mode,
        label=args.label,
        topic=args.topic,
        crash_at=args.crash_at if (args.mode == "crash" or args.arm) else None,
        event_seq_before=log.seq,
    )

    ckpt = Path(args.ckpt).expanduser()
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    if args.mode == "baseline" and args.fresh and ckpt.exists():
        ckpt.unlink()

    with SqliteSaver.from_conn_string(str(ckpt)) as saver:
        saver.setup()
        graph = build_graph(saver, log, settings, args.label)
        config = {"configurable": {"thread_id": args.run_id}}

        before = graph.get_state(config)
        pre = {
            "run_id": args.run_id,
            "label": args.label,
            "mode": args.mode,
            "topic_arg": args.topic,
            "pid": os.getpid(),
            "checkpoint_db": str(ckpt),
            "checkpoint_db_bytes_before": ckpt.stat().st_size if ckpt.exists() else 0,
            "event_seq_before": log.seq,
            "state_before": before.values,
            "next_before": list(before.next),
            "has_checkpoint": bool(before.values or before.next),
            "at": datetime.now(UTC).isoformat(),
        }
        pre_path = dump(settings, f"{args.run_id}.{args.label}.pre", pre)
        print(
            f"[{args.label}] run_id={args.run_id} mode={args.mode} "
            f"checkpoint_events_before={log.seq} next_before={list(before.next)} "
            f"state_before={before.values}"
        )

        # 续跑判定：已有 checkpoint 且有待执行节点 → 这是"恢复"，不是"重跑"
        if pre["has_checkpoint"]:
            log.emit(
                EventType.RECOVERY,
                stage="harness",
                agent="single",
                severity=Severity.WARNING,
                payload={
                    "resumed": True,
                    "next_before": list(before.next),
                    "state_before": before.values,
                    "label": args.label,
                    "note": "从 checkpoint 续跑；已完成的超步不会重放",
                },
            )

        final = graph.invoke(
            {
                "topic": args.topic,
                "sleep_s": args.sleep_s,
                "steps_done": [],
                "topic_seen": [],
            }
            if args.input_mode == "fresh"
            else None,
            config,
        )
        after = graph.get_state(config)
        post = {
            **{k: pre[k] for k in ("run_id", "label", "mode", "topic_arg", "pid")},
            "event_seq_after": log.seq,
            "checkpoint_db_bytes_after": ckpt.stat().st_size if ckpt.exists() else 0,
            "state_after": final,
            "next_after": list(after.next),
            "at": datetime.now(UTC).isoformat(),
        }
        post_path = dump(settings, f"{args.run_id}.{args.label}.post", post)
        print(
            f"[{args.label}] 完成：steps_done={final['steps_done']} "
            f"event_seq_after={log.seq} next_after={list(after.next)}"
        )

    log_event(
        Severity.INFO,
        "s4_invocation_finished",
        "S4 进程正常结束",
        mode=args.mode,
        label=args.label,
        event_seq_after=log.seq,
    )
    print(f"  pre={pre_path.name} post={post_path.name} ckpt={ckpt}")
    clear_context()
    return 0


# --------------------------------------------------------------------------- #
# 校验
# --------------------------------------------------------------------------- #
def node_attempts(events: list[Any]) -> dict[str, list[str]]:
    """按节点收集所有 start 事件（含进程 label），用于判断是否重跑。"""
    out: dict[str, list[str]] = {name: [] for name in NODES}
    for event in events:
        if str(event.type) != "phase_change":
            continue
        payload = event.payload or {}
        if payload.get("phase") == "start" and payload.get("node") in out:
            out[payload["node"]].append(str(payload.get("label")))
    return out


def seq_report(events: list[Any]) -> dict[str, Any]:
    seqs = [e.seq for e in events]
    expected = list(range(1, len(seqs) + 1))
    return {
        "count": len(seqs),
        "min": min(seqs) if seqs else None,
        "max": max(seqs) if seqs else None,
        "contiguous_from_1": sorted(seqs) == expected,
        "duplicates": sorted({s for s in seqs if seqs.count(s) > 1}),
        "monotonic_in_file_order": seqs == sorted(seqs),
    }


def verify(args: argparse.Namespace) -> int:
    settings = load_settings()
    path = events_path(settings)
    all_events = read_events(path)
    by_run: dict[str, list[Any]] = {}
    for event in all_events:
        by_run.setdefault(str(event.run_id), []).append(event)

    summary: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "events_file": str(path),
        "scenarios": {},
        "checks": {},
    }
    for run_id, desc in SCENARIOS.items():
        events = by_run.get(run_id, [])
        pre_files = sorted(s4_dir(settings).glob(f"{run_id}.*.pre.json"))
        post_files = sorted(s4_dir(settings).glob(f"{run_id}.*.post.json"))
        summary["scenarios"][run_id] = {
            "desc": desc,
            "events": len(events),
            "seq": seq_report(events),
            "node_attempts": node_attempts(events),
            "crash_events": [
                e.payload.get("error_code")
                for e in events
                if e.payload and e.payload.get("error_code") == "E_SIMULATED_CRASH"
            ],
            "recovery_events": [
                {"label": e.payload.get("label"), "next_before": e.payload.get("next_before")}
                for e in events
                if str(e.type) == "recovery"
            ],
            "invocations": [
                {
                    "file": f.name,
                    "label": json.loads(f.read_text(encoding="utf-8"))["label"],
                    "topic_arg": json.loads(f.read_text(encoding="utf-8"))["topic_arg"],
                    "next_before": json.loads(f.read_text(encoding="utf-8"))["next_before"],
                    "has_checkpoint": json.loads(f.read_text(encoding="utf-8"))["has_checkpoint"],
                    "seq_before": json.loads(f.read_text(encoding="utf-8"))["event_seq_before"],
                }
                for f in pre_files
            ],
            "final_states": [
                {
                    "label": json.loads(f.read_text(encoding="utf-8"))["label"],
                    "state_after": json.loads(f.read_text(encoding="utf-8"))["state_after"],
                    "next_after": json.loads(f.read_text(encoding="utf-8"))["next_after"],
                    "ckpt_bytes": json.loads(f.read_text(encoding="utf-8"))[
                        "checkpoint_db_bytes_after"
                    ],
                }
                for f in post_files
            ],
        }

    checks = summary["checks"]
    a = summary["scenarios"].get("p0-s4-a", {})
    b = summary["scenarios"].get("p0-s4-b", {})
    c = summary["scenarios"].get("p0-s4-c", {})
    d = summary["scenarios"].get("p0-s4-d", {})
    e = summary["scenarios"].get("p0-s4-e", {})
    f = summary["scenarios"].get("p0-s4-f", {})

    def final_of(scenario: dict[str, Any]) -> dict[str, Any]:
        states = scenario.get("final_states") or [{}]
        return states[-1].get("state_after") or {}

    checks["A_baseline_completes"] = final_of(a).get("steps_done") == list(NODES)
    # B：带"完整输入"重启 —— 实测会从 START 重跑已完成节点（陷阱，见 F 的正确姿势）
    checks["B_fresh_input_reruns_completed_fetch"] = (
        len((b.get("node_attempts") or {}).get("fetch", [])) == 2
    )
    checks["B_transform_rerun_once"] = len((b.get("node_attempts") or {}).get("transform", [])) == 2
    checks["B_emit_not_rerun"] = len((b.get("node_attempts") or {}).get("emit", [])) == 1
    checks["B_resume_point_is_node_boundary"] = all(
        inv.get("next_before") == ["transform"] for inv in (b.get("invocations") or [])[1:]
    )
    checks["B_resume_seen"] = bool(b.get("recovery_events"))
    checks["C_three_invocations"] = len(c.get("invocations") or []) == 3
    checks["C_two_crashes"] = len(c.get("crash_events") or []) == 2
    checks["C_final_contains_all_nodes"] = set(final_of(c).get("steps_done") or []) == set(NODES)
    checks["D_topics_seen"] = final_of(d).get("topic_seen")
    checks["D_final_topic"] = final_of(d).get("topic")
    checks["E_reinvoke_duplicates_work"] = len(final_of(e).get("steps_done") or []) == 2 * len(
        NODES
    )
    # F：正确姿势 —— invoke(None) 从断点续跑：已完成节点不重跑，且最终状态与对照组完全一致
    checks["F_fetch_not_rerun"] = len((f.get("node_attempts") or {}).get("fetch", [])) == 1
    checks["F_transform_rerun_once"] = len((f.get("node_attempts") or {}).get("transform", [])) == 2
    checks["F_emit_not_rerun"] = len((f.get("node_attempts") or {}).get("emit", [])) == 1
    checks["F_final_state_equals_baseline"] = final_of(f) == final_of(a)
    checks["all_seq_contiguous"] = all(
        s["seq"]["contiguous_from_1"] and not s["seq"]["duplicates"]
        for s in summary["scenarios"].values()
    )

    out = settings.paths.out_dir / "s4_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== 场景 ===")
    for run_id, s in summary["scenarios"].items():
        attempts = {k: len(v) for k, v in s["node_attempts"].items()}
        print(
            f"  {run_id:12s} events={s['events']:3d} seq_ok={s['seq']['contiguous_from_1']} "
            f"attempts={attempts} crashes={len(s['crash_events'])} "
            f"invocations={len(s['invocations'])}"
        )
    print("\n=== 校验 ===")
    for name, ok in checks.items():
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}: {ok}")
    print(f"\nsummary: {out}")
    # D_topics_seen / D_final_topic 是"记录型"检查（呈现框架行为），不参与通过/失败判定
    verdict = all(v is True for k, v in checks.items() if not k.startswith("D_"))
    return 0 if verdict else 1


# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 0 Spike S4：断点续跑验证")
    parser.add_argument("--mode", choices=("baseline", "crash", "resume", "verify"), required=True)
    parser.add_argument("--run-id", default="p0-s4-b")
    parser.add_argument("--label", default="1-run")
    parser.add_argument("--topic", default="T1")
    parser.add_argument("--sleep", dest="sleep_s", type=float, default=0.2)
    parser.add_argument("--crash-at", choices=NODES, default="transform")
    parser.add_argument("--arm", action="store_true", help="本次调用前布置崩溃臂")
    parser.add_argument(
        "--input-mode",
        choices=("fresh", "none"),
        default="fresh",
        help="fresh=带完整输入 invoke（会从 START 重跑已完成节点）；none=invoke(None) 真正从断点续跑",
    )
    parser.add_argument("--ckpt", default=None)
    parser.add_argument("--fresh", action="store_true", help="baseline 前删除 checkpoint 库")
    args = parser.parse_args(argv)
    if args.ckpt is None:
        args.ckpt = f"out/data/s4_{args.run_id.replace('p0-s4-', '')}.db"
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "verify":
        return verify(args)
    return run_once(args)


if __name__ == "__main__":
    raise SystemExit(main())
