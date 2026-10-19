"""存储路径与库身份自检（ADR-0003 的可执行部分）。

Phase 0 的四个真实事故在这里固化为断言：
1. Kuzu 路径是**文件**而不是目录 → `reset_store_path` 必须区分 file/dir，且禁止
   `rmtree(..., ignore_errors=True)`（那会静默吞掉 `NotADirectoryError`，留下脏库）；
2. 非 ASCII 路径在 Windows 上 Kuzu 直接打不开 → `assert_ascii_path` 提前报 `E_STORE_PATH_NONASCII`；
3. Kuzu 只在 `Database.close()` 落盘 → `path_size_mb` 的调用方必须在 close 之后测量；
4. 旧库残留会被误当成"本次结果" → `store_is_empty` / `store_meta` 作为空库哨兵。
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from lit_agent.errors import E_STORE_PATH_NONASCII, LitError

__all__ = [
    "assert_ascii_path",
    "path_size_mb",
    "read_store_meta",
    "reset_store_path",
    "sqlite_schema_version",
    "store_is_empty",
]


def assert_ascii_path(path: str | Path, *, label: str = "path") -> Path:
    """非 ASCII 路径直接报错（Kuzu 在 Windows 上无法打开此类路径）。"""
    resolved = Path(path)
    if not str(resolved).isascii():
        raise LitError(
            E_STORE_PATH_NONASCII,
            f"{label} 含非 ASCII 字符：{resolved}",
            context={"label": label, "path": str(resolved)},
        )
    return resolved


def path_size_mb(path: str | Path) -> float:
    """路径占用（MB）。**文件与目录都支持**；不存在返回 0.0。

    注意：Kuzu 必须 `Database.close()` 之后调用，否则读到的是未 checkpoint 的假值。
    """
    target = Path(path)
    if not target.exists():
        return 0.0
    if target.is_file():
        return round(target.stat().st_size / (1024 * 1024), 4)
    total = 0
    for child in target.rglob("*"):
        try:
            if child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    return round(total / (1024 * 1024), 4)


def store_is_empty(path: str | Path) -> bool:
    """库是否为空（不存在 / 0 字节 / SQLite 无 `store_meta` 行都算空）。"""
    target = Path(path)
    if not target.exists():
        return True
    if target.is_file() and target.stat().st_size == 0:
        return True
    if target.is_file() and target.suffix in {".db", ".sqlite", ".sqlite3"}:
        try:
            with sqlite3.connect(target) as conn:
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='store_meta'"
                ).fetchone()
                if row is None:
                    return True
                count = conn.execute("SELECT COUNT(*) FROM store_meta").fetchone()[0]
                return int(count) == 0
        except sqlite3.DatabaseError:
            return True
    # 目录（Qdrant local / 论文目录）：无任何条目即空
    return not any(target.iterdir()) if target.is_dir() else False


def reset_store_path(path: str | Path) -> None:
    """删除库路径：**文件用 unlink、目录用 rmtree**，且不做 `ignore_errors`。

    幂等：路径不存在时直接返回。
    """
    target = Path(path)
    if not target.exists():
        return
    if target.is_file():
        target.unlink()
        return
    shutil.rmtree(target)


def sqlite_schema_version(db_path: str | Path) -> str | None:
    """读取 `store_meta` 中 sqlite 的 schema_version；不存在返回 None。"""
    target = Path(db_path)
    if not target.is_file() or target.stat().st_size == 0:
        return None
    try:
        with sqlite3.connect(target) as conn:
            row = conn.execute(
                "SELECT schema_version FROM store_meta WHERE store_name='sqlite'"
            ).fetchone()
            return str(row[0]) if row else None
    except sqlite3.DatabaseError:
        return None


def read_store_meta(db_path: str | Path) -> dict[str, dict[str, object]]:
    """读取全部 `store_meta` 行（`store_name` → 列字典）；失败返回空 dict。"""
    target = Path(db_path)
    if not target.is_file() or target.stat().st_size == 0:
        return {}
    try:
        with sqlite3.connect(target) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM store_meta").fetchall()
            return {str(row["store_name"]): dict(row) for row in rows}
    except sqlite3.DatabaseError:
        return {}
