"""Tune report parameters on a local topic (3.3 / S10).

Safety: without `--execute` this only prints the experiment matrix.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lit_agent.config import load_settings  # noqa: E402
from lit_agent.eval.metrics import compute_run_metrics  # noqa: E402
from lit_agent.runtime.graph_runner import run_graph  # noqa: E402

PRESETS: dict[str, dict[str, Any]] = {
    "baseline": {},
    "token1200": {"max_tokens_card": 1200, "max_tokens_cluster": 300, "max_tokens_synthesis": 1200},
    "strict": {"cluster_threshold": 0.22, "batch_size": 3},
    "cheap": {"max_tokens_card": 900, "batch_size": 8, "max_tokens_synthesis": 700},
}


def _configs(names: list[str]) -> list[tuple[str, dict[str, Any]]]:
    return [(name, PRESETS[name]) for name in names if name in PRESETS]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run report parameter presets")
    parser.add_argument("--topic", default="ai-agents-live")
    parser.add_argument("--preset", action="append", choices=sorted(PRESETS))
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--out", default="out/tune-report.csv")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--execute", action="store_true", help="actually generate reports")
    args = parser.parse_args()

    names = args.preset or ["baseline", "token1200"]
    configs = _configs(names)
    print(json.dumps({"topic": args.topic, "configs": configs, "runs": args.runs}, indent=2))
    if not args.execute:
        print("dry-run: add --execute to generate reports")
        return 0

    base = load_settings()
    rows: list[dict[str, Any]] = []
    for name, overrides in configs:
        for index in range(max(1, args.runs)):
            report_settings = base.report.model_copy(update=overrides)
            settings = base.model_copy(update={"report": report_settings})
            if args.no_llm:
                settings = settings.model_copy(
                    update={"pipeline": settings.pipeline.model_copy(update={"llm": "off"})}
                )
            run_id = f"tune-{name}-{uuid.uuid4().hex[:6]}"
            started = time.monotonic()
            result = run_graph(settings, args.topic, run_id=run_id)
            elapsed = round(time.monotonic() - started, 2)
            if result.get("state") != "succeeded":
                rows.append({"config": name, "run_id": run_id, "state": result.get("state")})
                continue
            metrics = compute_run_metrics(settings, run_id)
            rows.append(
                {
                    "config": name,
                    "run": index + 1,
                    "run_id": run_id,
                    "state": result.get("state"),
                    "papers": metrics.get("papers"),
                    "claims": metrics.get("report_claims"),
                    "sections": metrics.get("report_sections"),
                    "words": metrics.get("report_words"),
                    "fallback_count": metrics.get("report_fallback_count"),
                    "coverage": metrics.get("report_coverage"),
                    "thin": metrics.get("report_thin"),
                    "cache_hit_rate": metrics.get("report_cache_hit_rate"),
                    "cost_usd": metrics.get("cost_usd"),
                    "latency_s": elapsed,
                }
            )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["config"])
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
