"""3.5 / S26：日志回放审计（只读 run_events，回答三问）。

用法：
    uv run python scripts/replay_run.py --run <run_id>
输出：JSON（重试、降级、成本、阶段耗时、轨迹指标）。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sqlalchemy import text

from lit_agent.config import load_settings
from lit_agent.db.session import connect, make_engine
from lit_agent.eval.metrics import compute_run_metrics
from lit_agent.eval.trajectory import trajectory_metrics


def replay(settings: Any, run_id: str) -> dict[str, Any]:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            events = conn.execute(
                text(
                    "SELECT type, stage, payload_json FROM run_events"
                    " WHERE run_id = :rid ORDER BY seq"
                ),
                {"rid": run_id},
            ).all()
    finally:
        engine.dispose()

    retries: list[dict[str, Any]] = []
    degradations: list[dict[str, Any]] = []
    for event_type, stage, payload_json in events:
        try:
            payload = json.loads(payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        if event_type == "guard_trigger" and payload.get("action") in {"retry", "repair", "replan"}:
            retries.append(
                {
                    "stage": stage,
                    "action": payload.get("action"),
                    "code": payload.get("code"),
                    "attempt": payload.get("attempt"),
                }
            )
        if event_type in {"guard_trigger", "recovery"} and payload.get("action") in {"degrade", "abort"}:
            degradations.append({"stage": stage, "action": payload.get("action"), "code": payload.get("code")})
        if event_type == "recovery":
            degradations.append({"stage": stage, "action": "recovery", "to": payload.get("to_stage")})

    metrics = compute_run_metrics(settings, run_id)
    trajectory = trajectory_metrics(settings, run_id)
    return {
        "run_id": run_id,
        "retries": retries,
        "degradations": degradations,
        "cost_usd": metrics.get("cost_usd", 0.0),
        "duration_ms_total": metrics.get("duration_ms_total", 0.0),
        "duration_by_stage": metrics.get("duration_by_stage", {}),
        "trajectory": trajectory,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--json", default="")
    args = parser.parse_args(argv)

    payload = replay(load_settings(), args.run)
    text_out = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.json:
        Path(args.json).write_text(text_out, encoding="utf-8")
    print(text_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
