"""3.5 / S23：消融实验（L1 / retrieval L2 / analysis L2 / both）。

同一 fixture、同一 focus，比较质量代理（claims/unsupported/grounding）、
成本（cost_usd）与延迟（duration_ms_total）。

用法：uv run python scripts/ablation.py --papers 3
输出：控制台表格 + docs/implementation/ablation.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.wiring import fetch_events, prepare  # noqa: E402

from lit_agent.eval.metrics import compute_run_metrics  # noqa: E402
from lit_agent.runtime.graph_runner import run_graph  # noqa: E402

CONFIGS = [
    ("L1", {}),
    ("retrieval-L2", {"retrieval_l2": True}),
    ("analysis-L2", {"analysis_l2": True}),
    ("both-L2", {"retrieval_l2": True, "analysis_l2": True}),
]


def run_one(*, name: str, flags: dict[str, bool], papers: int, focus: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        settings = prepare(Path(tmp), papers=papers)
        pipeline = settings.pipeline.model_copy(update=flags)
        settings = settings.model_copy(update={"pipeline": pipeline})
        started = time.monotonic()
        out = run_graph(settings, "ai-agents", run_id="ablate", focus_hint=focus)
        wall_ms = int((time.monotonic() - started) * 1000)
        metrics = compute_run_metrics(settings, "ablate")
        events = fetch_events(settings, "ablate")
        tool_calls = len([event for event in events if event["type"] == "tool_call"])
        return {
            "config": name,
            "state": out["state"],
            "claims": metrics.get("claims_total", 0),
            "unsupported": int(metrics.get("claims_total", 0)) - int(metrics.get("claims_supported_db", 0)),
            "grounding": metrics.get("grounding_rate", 0.0),
            "tool_calls": tool_calls,
            "retries": metrics.get("retries_total", 0),
            "stop_reason": metrics.get("stop_reason", ""),
            "duration_ms": metrics.get("duration_ms_total", 0),
            "wall_ms": wall_ms,
            "cost_usd": metrics.get("cost_usd", 0.0),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--papers", type=int, default=3)
    parser.add_argument("--focus", default="tool use")
    parser.add_argument("--json", default="docs/implementation/ablation.json")
    args = parser.parse_args(argv)

    rows = [
        run_one(name=name, flags=flags, papers=args.papers, focus=args.focus)
        for name, flags in CONFIGS
    ]

    print(f"\nablation (papers={args.papers}, focus={args.focus!r})")
    print("-" * 100)
    print(f"{'config':<14}{'state':<12}{'claims':>7}{'unsup':>7}{'ground':>8}{'tools':>7}{'retry':>7}{'ms':>8}{'cost':>7}")
    for row in rows:
        print(
            f"{row['config']:<14}{str(row['state']):<12}{row['claims']:>7}{row['unsupported']:>7}"
            f"{row['grounding']:>8}{row['tool_calls']:>7}{row['retries']:>7}"
            f"{row['duration_ms']:>8}{row['cost_usd']:>7}"
        )
    print("-" * 100)

    out = Path(args.json)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"papers": args.papers, "focus": args.focus, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
