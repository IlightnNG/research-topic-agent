"""Phase 2.2 验证器：H1–H8 一条命令。

用法：
    uv run python scripts/verify_phase2_2.py --all
    uv run python scripts/verify_phase2_2.py --config --limits --drift
    uv run python scripts/verify_phase2_2.py --observability --ux --baseline

约定：只读；e2e 会启动/复用本地 webServer；退出码 0 表示全绿。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def _pytest(args: list[str]) -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    import re

    match = re.search(r"(\d+) passed[^\n]*", completed.stdout or "")
    return completed.returncode == 0, (match.group(1)[:120] if match else "ok")


def _script(script: str, *args: str) -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    tail = [line for line in (completed.stdout or "").splitlines() if line.startswith("TOTAL")]
    return completed.returncode == 0, (tail[-1] if tail else ("ok" if completed.returncode == 0 else "failed"))


def _npm(script: str) -> tuple[bool, str]:
    env = os.environ.copy()
    env.setdefault("PLAYWRIGHT_BROWSERS_PATH", "D:/lit-agent-store/playwright")
    completed = subprocess.run(
        ["npm", "run", script],
        cwd=str(WEB),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
        env=env,
    )
    text = (completed.stdout or "") + (completed.stderr or "")
    import re

    match = re.search(r"(\d+) passed[^\n]*", text)
    if match:
        return completed.returncode == 0, match.group(1)[:120]
    tail = [line for line in text.splitlines() if line.strip()][-3:]
    return completed.returncode == 0, (" | ".join(tail)[:160] if tail else "failed")


CHECKS: list[tuple[str, str]] = [
    ("H1 配置生效", "config"),
    ("H2 LLM 调用硬顶", "limits"),
    ("H3 证据阈值", "evidence"),
    ("H4 漂移产出", "drift"),
    ("H5 阶段耗时/指标", "observability"),
    ("H6 前端 e2e", "ux"),
    ("H7 基线不回归", "baseline"),
    ("H8 文档", "docs"),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 2.2 verifier")
    parser.add_argument("--all", action="store_true")
    for _name, key in CHECKS:
        parser.add_argument(f"--{key}", action="store_true")
    parser.add_argument("--json", default="docs/implementation/phase2.2-report.json")
    args = parser.parse_args(argv)

    selected = [key for _name, key in CHECKS if args.all or getattr(args, key)]
    if not selected:
        print("没有选中任何断言（--all 或 --config/--limits/...）")
        return 2

    results: list[dict[str, object]] = []
    for name, key in CHECKS:
        if key not in selected:
            continue
        try:
            if key == "config":
                ok, detail = _pytest(["tests/config"])
            elif key == "limits":
                ok, detail = _pytest(["tests/gates/test_llm_cap.py"])
            elif key == "evidence":
                ok, detail = _pytest(["tests/gates/test_evidence_threshold.py"])
            elif key == "drift":
                ok, detail = _pytest(["tests/eval/test_scope_drift.py"])
            elif key == "observability":
                ok, detail = _pytest(["tests/observability"])
            elif key == "ux":
                ok, detail = _npm("test:e2e")
            elif key == "baseline":
                ok2, d2 = _script("verify_phase2.py", "--offline", "--baseline")
                ok1, d1 = _script("verify_phase1.py", "--offline")
                ok = ok1 and ok2
                detail = f"phase2:{d2} phase1:{d1}"
            else:  # docs
                doc = ROOT / "docs/implementation/RESULTS-P2.2.md"
                text = doc.read_text(encoding="utf-8") if doc.exists() else ""
                ok = all(
                    marker in text
                    for marker in ("S1–S8", "H1–H8", "## 8. S7", "## 9. S8", "收尾结论")
                )
                detail = "RESULTS-P2.2 含 S1–S8 / H1–H8 / S7 / S8 / 收尾" if ok else "缺少收尾章节"
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        results.append({"name": name, "ok": ok, "detail": detail})

    width = max(len(str(item["name"])) for item in results)
    print("\nPhase 2.2 verifier")
    print("-" * (width + 60))
    for item in results:
        print(f"[{'PASS' if item['ok'] else 'FAIL'}] {str(item['name']).ljust(width)}  {item['detail']}")
    print("-" * (width + 60))
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
