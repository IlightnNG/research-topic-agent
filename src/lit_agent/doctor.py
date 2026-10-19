"""`lit-agent doctor`：六类自检 + 模块三态清单（Phase 1 出口标准 D1 的执行体）。

六类检查
1. **结构**：`structure.py` 的包/文件清单（缺失即失败；`--strict` 下同样失败）；
2. **依赖**：核心依赖缺失即失败，可选依赖只告警（骨架阶段允许未装）；
3. **配置**：加载 YAML/env，报告 `config_version` 与校验问题；
4. **路径**：数据根/Kuzu/Qdrant/论文目录的 ASCII 与存在性（ADR-0003）；
5. **存储**：SQLite 的 `store_meta.schema_version` 是否与代码一致（空库哨兵）；
6. **版本**：Python ≥3.11、SQLite ≥3.35（`UPDATE … RETURNING` 需要）。
"""

from __future__ import annotations

import importlib.util
import json
import platform
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lit_agent import structure
from lit_agent._version import __version__
from lit_agent.config import Settings, load_settings
from lit_agent.errors import LitError
from lit_agent.selftest import read_store_meta

__all__ = ["CheckResult", "doctor_report", "main", "run_doctor"]

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "lit_agent"

CORE_DEPS: tuple[str, ...] = (
    "pydantic",
    "pydantic_settings",
    "yaml",
    "structlog",
    "sqlalchemy",
    "alembic",
    "httpx",
    "fastapi",
)
OPTIONAL_DEPS: tuple[str, ...] = (
    "langgraph",
    "litellm",
    "qdrant_client",
    "kuzu",
    "sentence_transformers",
    "numpy",
    "pymupdf",
    "pdfplumber",
    "apscheduler",
    "tiktoken",
    "deepeval",
)

MIN_PYTHON = (3, 11)
MIN_SQLITE = (3, 35)


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    blocking: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": "ok" if self.ok else ("fail" if self.blocking else "warn"),
            "detail": self.detail,
            "extra": self.extra,
        }


def _check_structure() -> CheckResult:
    missing = structure.missing_files(SRC_ROOT)
    missing_root = [rel for rel in structure.ROOT_FILES if not (REPO_ROOT / rel).is_file()]
    total = len(structure.expected_files()) + len(structure.ROOT_FILES)
    absent = len(missing) + len(missing_root)
    depth_counts: dict[str, int] = {}
    for value in structure.DEPTH.values():
        depth_counts[value] = depth_counts.get(value, 0) + 1
    detail = (
        f"{total - absent}/{total} files present"
        f" | packages={len(structure.PACKAGES)}"
        f" | depth={dict(sorted(depth_counts.items()))}"
    )
    if absent:
        sample = (missing + missing_root)[:6]
        detail = f"{detail} | missing={sample}{'…' if absent > 6 else ''}"
    return CheckResult(
        "structure",
        ok=absent == 0,
        detail=detail,
        extra={"missing": missing + missing_root, "expected_total": total},
    )


def _check_deps() -> CheckResult:
    def missing(names: tuple[str, ...]) -> list[str]:
        absent = []
        for name in names:
            try:
                found = importlib.util.find_spec(name) is not None
            except (ImportError, ValueError):
                found = False
            if not found:
                absent.append(name)
        return absent

    missing_core = missing(CORE_DEPS)
    missing_optional = missing(OPTIONAL_DEPS)
    detail = f"core ok ({len(CORE_DEPS)})"
    if missing_core:
        detail = f"core missing={missing_core}"
    elif missing_optional:
        detail = f"{detail} | optional missing={missing_optional}"
    else:
        detail = f"{detail} | optional ok ({len(OPTIONAL_DEPS)})"
    return CheckResult(
        "deps",
        ok=not missing_core,
        detail=detail,
        extra={"missing_core": missing_core, "missing_optional": missing_optional},
    )


def _check_config(settings: Settings) -> CheckResult:
    problems = settings.check()
    codes = [code for code, _ in problems]
    detail = f"config_version={settings.config_version} path={settings.config_path or '<defaults>'}"
    if problems:
        detail = f"{detail} | problems={len(problems)}: {codes}"
    return CheckResult(
        "config",
        ok=not problems,
        detail=detail,
        extra={"problems": [{"code": code, "message": msg} for code, msg in problems]},
    )


def _check_paths(settings: Settings) -> CheckResult:
    rows: list[str] = []
    non_ascii: list[str] = []
    for key, path in settings.paths().items():
        exists = "exists" if Path(path).exists() else "absent"
        ascii_ok = str(path).isascii()
        if not ascii_ok:
            non_ascii.append(key)
        rows.append(f"{key}={path}({exists}{'' if ascii_ok else ',non-ascii'})")
    blocking_problem = any(key in {"kuzu", "data_root"} for key in non_ascii)
    return CheckResult(
        "paths",
        ok=not blocking_problem,
        detail=" | ".join(rows),
        blocking=blocking_problem,
        extra={"non_ascii": non_ascii},
    )


def _check_stores(settings: Settings) -> CheckResult:
    sqlite_path = settings.storage.sqlite_file
    meta = read_store_meta(sqlite_path)
    schema = str(meta.get("sqlite", {}).get("schema_version", "")) if meta else ""
    if not sqlite_path.exists():
        sqlite_detail = "sqlite=absent(created by `db upgrade`)"
        ok = True
    elif not schema:
        sqlite_detail = f"sqlite={sqlite_path} but store_meta missing (legacy/foreign db)"
        ok = False
    else:
        ok = schema == structure.SCHEMA_VERSION
        sqlite_detail = f"sqlite ok schema={schema}"
        if not ok:
            sqlite_detail += f" != expected {structure.SCHEMA_VERSION}"

    kuzu = "exists" if settings.storage.kuzu_file.exists() else "absent"
    qdrant = "exists" if settings.storage.qdrant_dir.exists() else "absent"
    return CheckResult(
        "stores",
        ok=ok,
        detail=f"{sqlite_detail} | kuzu={kuzu} | qdrant={qdrant}",
        extra={"schema_version": schema},
    )


def _check_version() -> CheckResult:
    py = sys.version_info[:3]
    sqlite_ver = sqlite3.sqlite_version_info[:3]
    ok = py >= MIN_PYTHON and sqlite_ver >= MIN_SQLITE
    detail = (
        f"python={platform.python_version()} sqlite={sqlite3.sqlite_version} "
        f"app={__version__} min=py{MIN_PYTHON[0]}.{MIN_PYTHON[1]}/sqlite{MIN_SQLITE[0]}.{MIN_SQLITE[1]}"
    )
    return CheckResult("version", ok=ok, detail=detail, extra={"app_version": __version__})


def run_doctor(*, strict: bool = False) -> tuple[list[CheckResult], bool]:
    """执行六类检查，返回 (结果列表, 是否通过)。`strict` 目前与默认一致（结构缺失都算失败）。"""
    try:
        settings = load_settings()
        config_error: LitError | None = None
    except LitError as exc:  # 配置坏了也要给出其余检查结果
        settings = load_settings(environ={})  # 回落到默认配置
        config_error = exc

    results = [
        _check_structure(),
        _check_deps(),
        _check_config(settings),
        _check_paths(settings),
        _check_stores(settings),
        _check_version(),
    ]
    if config_error is not None:
        results[2] = CheckResult(
            "config", ok=False, detail=f"{config_error.code}: {config_error.message}"
        )
    ok = all(item.ok for item in results if item.blocking)
    if strict:
        ok = ok and not any(not item.ok for item in results)
    return results, ok


def doctor_report(*, strict: bool = False) -> dict[str, Any]:
    results, ok = run_doctor(strict=strict)
    return {
        "ok": ok,
        "checks": [item.to_dict() for item in results],
        "structure_schema": structure.SCHEMA_VERSION,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    strict = "--strict" in args
    as_json = "--json" in args
    report = doctor_report(strict=strict)
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for item in report["checks"]:
            status = item["status"].upper()
            print(f"[{status:<4}] {item['name']:<9} {item['detail']}")
        print(f"doctor: {'OK' if report['ok'] else 'FAILED'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
