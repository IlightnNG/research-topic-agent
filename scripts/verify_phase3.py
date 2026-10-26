"""Phase 3 验证器（3.0 Foundations 子集；后续子阶段继续扩展）。

用法：
    uv run python scripts/verify_phase3.py --foundations
    uv run python scripts/verify_phase3.py --all
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECKS: list[tuple[str, str, list[str]]] = [
    ("H1 MicroAgent 六路径 + 相位", "micro", ["tests/runtime/test_micro_agent.py"]),
    ("H2 NodeGoal / ShellSpec", "goals", ["tests/contracts/test_goals_and_shell.py"]),
    ("H3 工具协议 v2", "tools", ["tests/tools/test_protocol_v2.py"]),
    ("H4 retrieval L2", "retrieval", ["tests/runtime/test_retrieval_l2.py"]),
    ("H5 analysis L2", "analysis", ["tests/runtime/test_analysis_l2.py"]),
    ("H6 默认关闭等价", "defaults", ["tests/runtime/test_phase3_defaults.py"]),
    ("H7 Chat L3", "chat", ["tests/chat"]),
]


def _pytest(paths: list[str]) -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *paths],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    import re

    match = re.search(r"(\d+) passed[^\n]*", completed.stdout or "")
    return completed.returncode == 0, (match.group(1)[:80] if match else "ok")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 3 verifier")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--foundations", action="store_true")
    for _name, key, _paths in CHECKS:
        parser.add_argument(f"--{key}", action="store_true")
    parser.add_argument("--json", default="docs/implementation/phase3-report.json")
    args = parser.parse_args(argv)

    selected = [
        key
        for _name, key, _paths in CHECKS
        if args.all or args.foundations or getattr(args, key)
    ]
    if not selected:
        print("没有选中断言（--all 或 --micro/--goals/--tools/--defaults）")
        return 2

    results: list[dict[str, object]] = []
    for name, key, paths in CHECKS:
        if key not in selected:
            continue
        ok, detail = _pytest(paths)
        results.append({"name": name, "ok": ok, "detail": detail})

    width = max(len(str(item["name"])) for item in results)
    print("\nPhase 3 verifier (3.0 Foundations)")
    print("-" * (width + 50))
    for item in results:
        print(f"[{'PASS' if item['ok'] else 'FAIL'}] {str(item['name']).ljust(width)}  {item['detail']}")
    print("-" * (width + 50))
    greens = sum(1 for item in results if item["ok"])
    print(f"TOTAL: {greens}/{len(results)}")

    out = Path(args.json)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"greens": greens, "total": len(results), "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"report: {out}")
    return 0 if greens == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
