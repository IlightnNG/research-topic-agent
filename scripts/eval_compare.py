"""Compare two evaluated runs (S17)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lit_agent.config import load_settings  # noqa: E402
from lit_agent.eval.metric_store import collect_report_points, load_points  # noqa: E402
from lit_agent.eval.report_eval import compare_summaries, score_summary, summarize_points  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two runs")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    settings = load_settings()
    for run_id in (args.baseline, args.candidate):
        collect_report_points(settings, run_id)
    base = summarize_points(load_points(settings, args.baseline))
    cand = summarize_points(load_points(settings, args.candidate))
    comparison = compare_summaries(base, cand)
    print(
        json.dumps(
            {
                "baseline": args.baseline,
                "candidate": args.candidate,
                "baseline_score": score_summary(base),
                "candidate_score": score_summary(cand),
                "deltas": comparison.deltas,
                "regressions": comparison.regressions,
                "improvements": comparison.improvements,
                "hard_fail": comparison.hard_fail,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
