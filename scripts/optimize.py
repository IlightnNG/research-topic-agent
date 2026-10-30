"""Promotion gate for baseline/candidate summaries (S19).

This is the deterministic promotion step; the experiment runner itself is
driven by an outer loop and remains deliberately out of this script.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lit_agent.config import load_settings  # noqa: E402
from lit_agent.eval.optimizer import Experiment, decide_promotion, save_experiment  # noqa: E402
from lit_agent.eval.report_eval import compare_summaries  # noqa: E402


def _read(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote or reject a candidate")
    parser.add_argument("--baseline-json", required=True)
    parser.add_argument("--candidate-json", required=True)
    parser.add_argument("--dataset", default="local")
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()

    baseline = _read(args.baseline_json)
    candidate = _read(args.candidate_json)
    comparison = compare_summaries(baseline.get("metrics", {}), candidate.get("metrics", {}))
    delta = float(candidate.get("score", 0.0)) - float(baseline.get("score", 0.0))
    promote, reasons = decide_promotion(comparison, score_delta=delta)
    result = {
        "promote": promote,
        "reasons": reasons,
        "score_delta": round(delta, 4),
        "regressions": comparison.regressions,
        "hard_fail": comparison.hard_fail,
    }
    if args.record:
        settings = load_settings()
        experiment_id = save_experiment(
            settings,
            Experiment(
                name="candidate",
                config={"candidate": args.candidate_json},
                dataset=args.dataset,
                baseline_run_id=baseline.get("run_id"),
                candidates=[candidate.get("run_id", "")],
                score=float(candidate.get("score", 0.0)),
                hard_fail=comparison.hard_fail,
                status="promoted" if promote else "rejected",
            ),
        )
        result["experiment_id"] = experiment_id
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
