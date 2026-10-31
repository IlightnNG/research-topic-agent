"""Run a Report through the direct Workflow shell (S1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lit_agent.config import load_settings  # noqa: E402
from lit_agent.runtime.report_shell import run_direct_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a report without the legacy graph")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--focus", default=None)
    args = parser.parse_args()
    result = run_direct_report(
        load_settings(),
        args.topic,
        run_id=args.run_id,
        limit=args.limit,
        focus_hint=args.focus,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
