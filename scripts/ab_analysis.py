"""3.2 A/B：analysis L1 vs L2（含 bad_artifact 故障）。

用法：
    uv run python scripts/ab_analysis.py --papers 3
输出：控制台对比表 + docs/implementation/ab-analysis.json
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

from lit_agent.eval.faultinject import inject  # noqa: E402
from lit_agent.runtime.graph_runner import run_graph  # noqa: E402


def run_one(*, l2: bool, papers: int, bad: bool) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        settings = prepare(Path(tmp), papers=papers)
        if l2:
            pipeline = settings.pipeline.model_copy(update={"analysis_l2": True})
            settings = settings.model_copy(update={"pipeline": pipeline})
        started = time.monotonic()
        with inject("bad_artifact") if bad else _null():
            out = run_graph(settings, "ai-agents", run_id="ab", focus_hint="tool use")
        wall_ms = int((time.monotonic() - started) * 1000)
        events = fetch_events(settings, "ab")
        calls = [event for event in events if event["type"] == "tool_call"]
        stages = out["stages"]
        claims = json.loads(stages.get("claims_json") or "[]")
        unsupported = sum(1 for claim in claims if claim.get("support") == "unsupported")
        return {
            "mode": ("L2" if l2 else "L1") + ("+bad" if bad else ""),
            "state": out["state"],
            "claims": len(claims),
            "unsupported": unsupported,
            "rewritten": (stages.get("repair") or {}).get("claims_rewritten", 0),
            "dropped": (stages.get("repair") or {}).get("claims_dropped", 0),
            "tool_calls": len(calls),
            "wall_ms": wall_ms,
            "grounding": stages.get("grounding_rate", 0.0),
        }


class _null:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> None:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--papers", type=int, default=3)
    parser.add_argument("--json", default="docs/implementation/ab-analysis.json")
    args = parser.parse_args(argv)

    rows = [
        run_one(l2=False, papers=args.papers, bad=False),
        run_one(l2=True, papers=args.papers, bad=False),
        run_one(l2=False, papers=args.papers, bad=True),
        run_one(l2=True, papers=args.papers, bad=True),
    ]

    print("\nanalysis A/B")
    print("-" * 92)
    print(f"{'mode':<9}{'state':<12}{'claims':>7}{'unsup':>7}{'rewrite':>8}{'drop':>6}{'tool':>6}{'ground':>8}")
    for row in rows:
        print(
            f"{row['mode']:<9}{str(row['state']):<12}{row['claims']:>7}{row['unsupported']:>7}"
            f"{row['rewritten']:>8}{row['dropped']:>6}{row['tool_calls']:>6}{row['grounding']:>8}"
        )
    print("-" * 92)

    out = Path(args.json)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"papers": args.papers, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
