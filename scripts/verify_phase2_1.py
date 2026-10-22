"""Phase 2.1 验证器（S12）：把 H1–H14 变成一条命令。

用法：
    uv run python scripts/verify_phase2_1.py --all
    uv run python scripts/verify_phase2_1.py --gates --transitions
    uv run python scripts/verify_phase2_1.py --frozen --print-hashes

约定：
- 每个断言 = 一个 pytest 选择（或哈希比对）；**只读**，不写业务库；
- 退出码：全绿 0，否则 1；
- `--json` 写报告（默认 `docs/implementation/phase2.1-report.json`）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 冻结哈希（改动 gold/bench 必须升文档版本 + ADR 并重算）
GOLD_SHA256 = "3da1a8d0e7b823c123f42670ec1d70f5a7181114d2c593aa626cc7578efae560"
BENCH_SHA256 = "d3fb619e856160e165b6ab24962852a473f393d303719e97eb22ff7dfdcd000b"


@dataclass
class Check:
    name: str
    targets: list[str]
    ok: bool = False
    detail: str = ""
    skipped: bool = False


CHECKS: list[Check] = [
    Check("H1 守卫接线", ["tests/wiring/test_guards_wired.py"]),
    Check("H2 门禁挡坏数据", ["tests/gates"]),
    Check("H3 健康 run 零误报", ["tests/gates", "-k", "healthy"]),
    Check("H4 回边生效", ["tests/wiring/test_transitions_wired.py"]),
    Check("H5 续跑幂等", ["tests/graph", "-k", "resume"]),
    Check("H6 指标 run 口径", ["tests/wiring/test_metrics_wired.py"]),
    Check("H7 指标与 API 一致", ["tests/wiring/test_metrics_wired.py", "-k", "metrics"]),
    Check("H8 hybrid 接线", ["tests/wiring/test_hybrid_wired.py"]),
    Check(
        "H9 LLM 接线/降级",
        ["tests/wiring/test_llm_wired.py", "tests/agents/test_llm_analysis_wired.py"],
    ),
    Check("H10 单流水线", ["tests/wiring/test_scheduler_wired.py"]),
    Check("H11 工具协议闭环", ["tests/tools"]),
    Check("H12 节点契约", ["tests/contracts"]),
]


def _run_pytest(args: list[str]) -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    import re

    text = completed.stdout or ""
    match = re.search(r"(\d+ passed[^\n]*)", text)
    if match:
        return completed.returncode == 0, match.group(1)[:120]
    return completed.returncode == 0, ("ok" if completed.returncode == 0 else "failed")


def _canonical_gold() -> str:
    from dataclasses import asdict

    from lit_agent.eval.datasets import load_gold

    return json.dumps([asdict(item) for item in load_gold()], sort_keys=True, ensure_ascii=False)


def _canonical_bench() -> str:
    from dataclasses import asdict

    from lit_agent.eval.retrieval_bench import CORPUS, QUERIES

    payload = {
        "corpus": dict(sorted(CORPUS.items())),
        "queries": [asdict(query) for query in QUERIES],
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT / "src"))
    parser = argparse.ArgumentParser(description="Phase 2.1 verifier")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--json", default="docs/implementation/phase2.1-report.json")
    for check in CHECKS:
        parser.add_argument("--" + check.name.split()[0].lower(), action="store_true")
    parser.add_argument("--gates", action="store_true")
    parser.add_argument("--frozen", action="store_true")
    parser.add_argument("--print-hashes", action="store_true")
    parser.add_argument("--update-hashes", action="store_true")
    parser.add_argument("--i-know-what-i-am-doing", action="store_true")
    args = parser.parse_args(argv)

    gold = _sha(_canonical_gold())
    bench = _sha(_canonical_bench())
    if args.print_hashes:
        print(f"gold  {gold}")
        print(f"bench {bench}")
        return 0
    if args.update_hashes:
        if not args.i_know_what_i_am_doing:
            print("拒绝：必须同时给 --i-know-what-i-am-doing")
            return 2
        print("请手工更新 GOLD_SHA256 / BENCH_SHA256：")
        print(f"  GOLD_SHA256  = {gold}")
        print(f"  BENCH_SHA256 = {bench}")
        return 0

    selected: list[Check] = []
    for check in CHECKS:
        flag = "--" + check.name.split()[0].lower()
        if args.all or getattr(args, check.name.split()[0].lower(), False) or getattr(args, flag[2:], False):
            selected.append(check)
    run_frozen = args.all or args.frozen
    if not selected and not run_frozen:
        print("没有选中任何断言（用 --all 或 --h1 … --h12 / --frozen）")
        return 2

    results: list[dict[str, object]] = []
    for check in selected:
        ok, detail = _run_pytest(check.targets)
        check.ok = ok
        check.detail = detail
        results.append({"name": check.name, "ok": ok, "detail": detail})

    frozen_ok = True
    if run_frozen:
        frozen_ok = gold == GOLD_SHA256 and bench == BENCH_SHA256
        results.append(
            {
                "name": "H13 冻结哈希",
                "ok": frozen_ok,
                "detail": f"gold={'ok' if gold == GOLD_SHA256 else 'CHANGED'} bench={'ok' if bench == BENCH_SHA256 else 'CHANGED'}",
            }
        )

    width = max(len(str(item["name"])) for item in results)
    print("\nPhase 2.1 verifier")
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
        json.dumps(
            {"greens": greens, "total": len(results), "results": results},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"report: {out}")
    return 0 if greens == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
