"""校验仓库结构是否与 §3.1 结构冻结基线一致（Phase 1 出口标准 D1）。

用法：
    python scripts/check_structure.py [--json]

退出码：0 = 完整；1 = 有缺失。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from lit_agent import structure  # noqa: E402


def collect() -> dict[str, object]:
    src_root = ROOT / "src" / "lit_agent"
    missing_src = structure.missing_files(src_root)
    missing_root = [rel for rel in structure.ROOT_FILES if not (ROOT / rel).is_file()]
    expected_total = len(structure.expected_files()) + len(structure.ROOT_FILES)
    absent = len(missing_src) + len(missing_root)
    depth: dict[str, int] = {}
    for value in structure.DEPTH.values():
        depth[value] = depth.get(value, 0) + 1
    return {
        "expected_total": expected_total,
        "present": expected_total - absent,
        "missing_src": missing_src,
        "missing_root": missing_root,
        "missing": absent,
        "extra_allowed": True,
        "depth": dict(sorted(depth.items())),
        "schema_version": structure.SCHEMA_VERSION,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    report = collect()
    if "--json" in args:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"structure: {report['present']}/{report['expected_total']} present "
            f"(missing={report['missing']}) depth={report['depth']}"
        )
        for rel in report["missing_root"]:  # type: ignore[union-attr]
            print(f"  missing (repo): {rel}")
        for rel in report["missing_src"]:  # type: ignore[union-attr]
            print(f"  missing (src):  {rel}")
    return 0 if report["missing"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
