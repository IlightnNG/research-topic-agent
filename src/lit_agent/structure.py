"""仓库结构与模块深度清单（Phase 1 的结构冻结基线的**可执行版本**）。

用途
- `lit-agent doctor` 与 `scripts/check_structure.py` 共用同一份清单，避免"文档写一套、检查另一套"；
- `DEPTH` 记录每个包在 Phase 1 的交付深度（D-FULL / D-MIN / D-SKEL），
  **收口时必须与 `phase1-implementation-steps.md` §1.4 深度矩阵一致**（SKEL 不得写成已实现）。

改动本文件 = 改结构契约 → 需同步 §3.1 目录树与 §8.4 差异登记。
"""

from __future__ import annotations

__all__ = [
    "DEPTH",
    "PACKAGES",
    "ROOT_FILES",
    "SCHEMA_VERSION",
    "expected_files",
    "missing_files",
]

SCHEMA_VERSION = "1.0"

#: 仓库根下的必需文件（相对仓库根）
ROOT_FILES: tuple[str, ...] = (
    "pyproject.toml",
    "alembic.ini",
    ".python-version",
    ".env.example",
    "README.md",
    "config/config.example.yaml",
    "config/seeds/topics.yaml",
    "migrations/env.py",
    "migrations/script.py.mako",
    "migrations/versions/0001_initial.py",
    "scripts/check_structure.py",
    "scripts/lit-agent.ps1",
)

#: `src/lit_agent/` 下的包目录 → 必需文件
PACKAGES: dict[str, tuple[str, ...]] = {
    ".": (
        "__init__.py",
        "__main__.py",
        "_version.py",
        "cli.py",
        "doctor.py",
        "config.py",
        "logging.py",
        "errors.py",
        "selftest.py",
        "structure.py",
        "py.typed",
    ),
    "models": (
        "__init__.py",
        "_base.py",
        "author.py",
        "paper.py",
        "evidence.py",
        "claim.py",
        "verdict.py",
        "event.py",
        "topic.py",
        "run.py",
        "report.py",
        "results.py",
    ),
    "db": ("__init__.py", "base.py", "session.py", "tables.py"),
    "db/repo": (
        "__init__.py",
        "papers.py",
        "authors.py",
        "citations.py",
        "topics.py",
        "runs.py",
        "events.py",
        "reports.py",
        "claims.py",
        "chunks.py",
        "sync.py",
        "llm_calls.py",
        "locks.py",
    ),
    "stores": ("__init__.py", "files.py", "graph.py", "vector.py", "selftest.py", "rebuild.py"),
    "sources": (
        "__init__.py",
        "base.py",
        "openalex.py",
        "arxiv.py",
        "whitelist.py",
        "normalize.py",
        "dedup.py",
        "sync.py",
    ),
    "parsing": ("__init__.py", "pdf.py", "chunking.py", "pipeline.py"),
    "gateway": ("__init__.py", "llm.py", "cache.py", "metering.py", "policy.py", "breaker.py"),
    "graph": ("__init__.py", "state.py", "pipeline.py", "edges.py", "guards.py", "checkpoint.py"),
    "agents": (
        "__init__.py",
        "base.py",
        "retrieval.py",
        "mapper.py",
        "analyst.py",
        "reporter.py",
        "critic.py",
        "chat.py",
    ),
    "context": ("__init__.py", "budget.py", "folding.py", "slots.py"),
    "tools": ("__init__.py", "registry.py", "mcp_adapter.py"),
    "tools/builtin": ("__init__.py", "openalex_search.py", "paper_pdf.py", "kv_cache.py"),
    "runtime": (
        "__init__.py",
        "events.py",
        "runner.py",
        "jobs.py",
        "budget.py",
        "watchdog.py",
        "scheduler.py",
    ),
    "api": ("__init__.py", "app.py", "schemas.py", "sse.py", "dependencies.py"),
    "api/routes": (
        "__init__.py",
        "topics.py",
        "runs.py",
        "reports.py",
        "chat.py",
        "graph.py",
        "metrics.py",
        "sources.py",
        "health.py",
    ),
    "eval": (
        "__init__.py",
        "metrics.py",
        "export.py",
        "datasets.py",
        "grounding.py",
        "judge.py",
        "faultinject.py",
    ),
}

#: 包 → Phase 1 深度（与 phase1-implementation-steps.md §1.4 对齐）
DEPTH: dict[str, str] = {
    ".": "D-FULL",  # config / logging / errors / doctor / cli
    "models": "D-FULL",
    "db": "D-FULL",
    "db/repo": "D-FULL",
    "runtime": "D-MIN",  # events 已完整，其余骨架
    "api": "D-SKEL",
    "api/routes": "D-SKEL",
    "stores": "D-SKEL",
    "sources": "D-SKEL",
    "parsing": "D-SKEL",
    "gateway": "D-SKEL",
    "graph": "D-SKEL",
    "agents": "D-SKEL",
    "context": "D-SKEL",
    "tools": "D-SKEL",
    "tools/builtin": "D-SKEL",
    "eval": "D-SKEL",
}


def expected_files() -> list[str]:
    """返回相对 `src/lit_agent/` 的全部必需文件路径。"""
    files: list[str] = []
    for package, names in PACKAGES.items():
        prefix = "" if package == "." else f"{package}/"
        files.extend(f"{prefix}{name}" for name in names)
    return sorted(files)


def missing_files(src_root: object) -> list[str]:
    """返回缺失文件（相对 `src/lit_agent/` 的路径）。`src_root` 需是 `pathlib.Path`。"""
    from pathlib import Path

    root = Path(src_root)  # type: ignore[arg-type]
    return [rel for rel in expected_files() if not (root / rel).is_file()]
