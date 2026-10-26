"""3.6 / S28：壳消融（10-goal 默认壳 vs 5-goal 精简壳，GoalRunner）。

用法：uv run python scripts/ab_shell.py
输出：表格 + docs/implementation/ab-shell.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.wiring import fetch_events, prepare  # noqa: E402

from lit_agent.contracts.goals import GOALS  # noqa: E402
from lit_agent.contracts.shell import default_shell  # noqa: E402
from lit_agent.eval.metrics import compute_run_metrics  # noqa: E402
from lit_agent.runtime.graph_runner import run_graph  # noqa: E402


def reduced_shell():
    from lit_agent.contracts.shell import ShellSpec

    names = ("retrieval", "analysis", "critique", "report", "evaluate")
    return ShellSpec(name="reduced", goals=tuple(GOALS[name] for name in names))


def run_one(shell, *, papers: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        settings = prepare(Path(tmp), papers=papers)
        out = run_graph(
            settings,
            "ai-agents",
            run_id="ab-shell",
            focus_hint="tool use",
            executor="goal_runner",
            shell=shell,
        )
        metrics = compute_run_metrics(settings, "ab-shell")
        events = fetch_events(settings, "ab-shell")
        stages = [
            e["stage"]
            for e in events
            if e["type"] == "phase_change"
            and e["payload"].get("phase") == "start"
            and e["stage"] != "run"
        ]
        return {
            "shell": shell.name,
            "goals": len(shell.goals),
            "hash": shell.hash,
            "stages": len(set(stages)),
            "claims": metrics.get("claims_total", 0),
            "grounding": metrics.get("grounding_rate", 0.0),
            "tool_calls": metrics.get("tool_calls", 0),
            "duration_ms": metrics.get("duration_ms_total", 0),
            "state": out["state"],
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--papers", type=int, default=3)
    parser.add_argument("--json", default="docs/implementation/ab-shell.json")
    args = parser.parse_args(argv)

    rows = [run_one(default_shell(), papers=args.papers), run_one(reduced_shell(), papers=args.papers)]
    print("\nshell ablation")
    print("-" * 86)
    print(f"{'shell':<12}{'goals':>6}{'stages':>7}{'claims':>7}{'ground':>8}{'tools':>7}{'ms':>8}{'state':>12}")
    for row in rows:
        print(
            f"{row['shell']:<12}{row['goals']:>6}{row['stages']:>7}{row['claims']:>7}"
            f"{row['grounding']:>8}{row['tool_calls']:>7}{row['duration_ms']:>8}{str(row['state']):>12}"
        )
    print("-" * 86)

    out = Path(args.json)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"papers": args.papers, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
