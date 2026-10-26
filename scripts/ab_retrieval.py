"""3.1 A/B：retrieval L1 vs L2（同数据、同 focus_hint）。

用法：
    uv run python scripts/ab_retrieval.py --papers 5
输出：控制台对比表 + docs/implementation/ab-retrieval.json
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

from lit_agent.runtime.graph_runner import run_graph  # noqa: E402


def run_one(*, l2: bool, papers: int, focus: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        settings = prepare(Path(tmp), papers=papers)
        if l2:
            pipeline = settings.pipeline.model_copy(update={"retrieval_l2": True})
            settings = settings.model_copy(update={"pipeline": pipeline})
        started = time.monotonic()
        out = run_graph(settings, "ai-agents", run_id="ab", focus_hint=focus)
        wall_ms = int((time.monotonic() - started) * 1000)
        events = fetch_events(settings, "ab")
        retrieval_ms = 0
        for event in events:
            if (
                event["type"] == "phase_change"
                and event["stage"] == "retrieval"
                and event["payload"].get("phase") == "end"
            ):
                retrieval_ms = int(event["payload"].get("duration_ms") or 0)
        calls = [event for event in events if event["type"] == "tool_call"]
        stages = out["stages"] or {}
        return {
            "mode": "L2" if l2 else "L1",
            "state": out["state"],
            "strategy": stages.get("strategy"),
            "cards": len(stages.get("paper_ids") or []),
            "l2_steps": stages.get("l2_steps", 0),
            "tool_calls": len(calls),
            "retrieval_ms": retrieval_ms,
            "wall_ms": wall_ms,
            "claims": stages.get("claims", 0),
            "cost_usd": stages.get("cost_usd", 0.0),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--papers", type=int, default=5)
    parser.add_argument("--focus", default="tool use")
    parser.add_argument("--json", default="docs/implementation/ab-retrieval.json")
    args = parser.parse_args(argv)

    rows = [
        run_one(l2=False, papers=args.papers, focus=args.focus),
        run_one(l2=True, papers=args.papers, focus=args.focus),
    ]

    print("\nretrieval A/B")
    print("-" * 96)
    print(f"{'mode':<6}{'state':<12}{'strategy':<14}{'cards':>6}{'steps':>7}{'tool':>6}{'retr_ms':>9}{'cost':>8}")
    for row in rows:
        print(
            f"{row['mode']:<6}{str(row['state']):<12}{str(row['strategy']):<14}"
            f"{row['cards']:>6}{row['l2_steps']:>7}{row['tool_calls']:>6}"
            f"{row['retrieval_ms']:>9}{row['cost_usd']:>8}"
        )
    print("-" * 96)

    out = Path(args.json)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"papers": args.papers, "focus": args.focus, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
