"""L3 gate for the generic AgentKernel.

Reads the simple, complex and soak benchmark JSON files and applies the
documented thresholds. It is intentionally conservative: a failed gate means
Workflow work stays frozen.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_SIMPLE = Path("D:/lit-agent-store/kernel-live-30-priced.json")
DEFAULT_COMPLEX = Path("D:/lit-agent-store/kernel-complex-hard.json")
DEFAULT_SOAK = Path("D:/lit-agent-store/kernel-soak.json")
DEFAULT_OUT = Path("D:/lit-agent-store/l3-gate.json")


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simple", type=Path, default=DEFAULT_SIMPLE)
    parser.add_argument("--complex", type=Path, default=DEFAULT_COMPLEX)
    parser.add_argument("--soak", type=Path, default=DEFAULT_SOAK)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    simple = _read(args.simple)
    complex_data = _read(args.complex)
    soak = _read(args.soak)

    checks = {
        "simple_success": simple["success_rate"] >= 0.90,
        "complex_success": complex_data["success_rate"] >= 0.70,
        "simple_schema": simple.get("schema_ok", 0) == simple.get("cases", 0),
        "audit_accept": complex_data.get("audit_accepted", 0) / max(1, complex_data["cases"]) >= 0.70,
        "audit_repair_used": sum(
            int(row.get("audit_repair_successes", 0)) for row in complex_data["results"]
        )
        > 0,
        "soak_success": soak["success"] == soak["tasks"],
        "cost_measured": simple.get("cost_usd", 0) > 0 and complex_data.get("cost_usd", 0) > 0,
    }
    result = {
        "passed": all(checks.values()),
        "checks": checks,
        "metrics": {
            "simple_success_rate": simple["success_rate"],
            "complex_success_rate": complex_data["success_rate"],
            "audit_accept_rate": complex_data.get("audit_accepted", 0) / max(1, complex_data["cases"]),
            "simple_cost_usd": simple.get("cost_usd", 0),
            "complex_cost_usd": complex_data.get("cost_usd", 0),
            "soak_success": soak["success"],
            "soak_tasks": soak["tasks"],
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
