"""Evaluate a completed run (S17)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lit_agent.config import load_settings  # noqa: E402
from lit_agent.eval.metric_store import collect_report_points, load_points, seed_definitions  # noqa: E402
from lit_agent.eval.report_eval import score_summary, summarize_points  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate one run")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--seed", action="store_true", help="seed metric definitions")
    args = parser.parse_args()

    settings = load_settings()
    if args.seed:
        seed_definitions(settings)
    collect_report_points(settings, args.run_id)
    points = load_points(settings, args.run_id)
    summary = summarize_points(points)
    print(json.dumps({"run_id": args.run_id, "score": score_summary(summary), "metrics": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
