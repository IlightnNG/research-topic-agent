"""引擎、事务、迁移与 schema 守卫。

关键约定
- **写事务一律 `BEGIN IMMEDIATE`**（通过 `begin` 事件注入）：SQLite 默认的延迟事务在
  "先读后写"时会尝试升级锁，并发下直接 `SQLITE_BUSY`；本仓单写者模型下用 IMMEDIATE 最简单可靠。
- `PRAGMA foreign_keys=ON` 必须每个连接设置（SQLite 默认关闭，否则级联与 FK 校验全部失效）。
- **schema 守卫**：按 `metadata` 逐表比对列名，缺列 → `E_STORE_SCHEMA_MISMATCH`（Phase 0 静默错误 #1 的固化防护）。
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, Engine, create_engine, event, inspect, text

from lit_agent.config import Settings
from lit_agent.db.base import metadata, utcnow_iso
from lit_agent.db.tables import EXPECTED_TABLES
from lit_agent.errors import (
    E_STORE_NOT_EMPTY,
    E_STORE_SCHEMA_MISMATCH,
    LitError,
)
from lit_agent.structure import SCHEMA_VERSION

__all__ = [
    "alembic_config",
    "connect",
    "database_status",
    "make_engine",
    "reset_database",
    "upgrade_database",
    "verify_schema",
]

REPO_ROOT = Path(__file__).resolve().parents[3]


def make_engine(settings: Settings, *, echo: bool = False) -> Engine:
    """创建 SQLite 引擎（WAL + 外键 + 超时 + IMMEDIATE 事务）。"""
    path = settings.storage.sqlite_file
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{path.as_posix()}",
        future=True,
        echo=echo,
        # 允许多线程共享（TestClient / SSE 后台任务），真并发仍由 job_locks + 单写者保证
        connect_args={"check_same_thread": False, "timeout": 5.0},
    )

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()

    return engine


@contextlib.contextmanager
def connect(engine: Engine, *, immediate: bool = False) -> Iterator[Connection]:
    """一次事务（自动 commit / rollback）。

    `immediate=True` 时发 `BEGIN IMMEDIATE`（ADR-0005 §5：事件取号必须先拿写锁）。
    **只对写事务启用**：若给所有连接都加写锁，读请求会互相阻塞，且同进程内
    "先开一个读连接再做内省"会自锁（`database is locked`）。
    """
    conn = engine.connect()
    try:
        if immediate:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Alembic
# --------------------------------------------------------------------------- #
def alembic_config(settings: Settings) -> Any:
    from alembic.config import Config

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{settings.storage.sqlite_file.as_posix()}")
    cfg.attributes["settings"] = settings
    return cfg


def upgrade_database(settings: Settings) -> Path:
    """迁移到 head，并写入库身份行（空库哨兵）。"""
    from alembic import command

    path = settings.storage.sqlite_file
    path.parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(settings), "head")
    ensure_store_meta(settings)
    return path


def reset_database(settings: Settings) -> Path:
    """删除本地库（含 WAL/SHM 旁文件）后重建。"""
    path = settings.storage.sqlite_file
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{path}{suffix}")
        if candidate.exists():
            candidate.unlink()
    return upgrade_database(settings)


def ensure_store_meta(settings: Settings) -> None:
    """写入/刷新 sqlite 的库身份行；已存在则只更新版本与时间。"""
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            row = {
                "store_name": "sqlite",
                "schema_version": SCHEMA_VERSION,
                "app_version": settings.app_version,
                "built_at": utcnow_iso(),
            }
            existing = conn.execute(
                text("SELECT schema_version FROM store_meta WHERE store_name='sqlite'")
            ).fetchone()
            if existing is None:
                conn.execute(
                    text(
                        "INSERT INTO store_meta(store_name, schema_version, app_version, built_at) "
                        "VALUES (:store_name, :schema_version, :app_version, :built_at)"
                    ),
                    row,
                )
            elif str(existing[0]) != SCHEMA_VERSION:
                raise LitError(
                    E_STORE_SCHEMA_MISMATCH,
                    f"store_meta.schema_version={existing[0]} != {SCHEMA_VERSION}",
                    context={"expected": SCHEMA_VERSION, "actual": str(existing[0])},
                )
    finally:
        engine.dispose()


def write_store_identity(
    settings: Settings,
    store_name: str,
    *,
    schema_version: str | None = None,
    model_id: str | None = None,
    model_rev: str | None = None,
    dim: int | None = None,
    active_collection: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """写入/更新某个派生物的库身份行（`kuzu` / `qdrant`；SQLite 由 `ensure_store_meta` 写）。"""
    import json

    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            values = {
                "store_name": store_name,
                "schema_version": schema_version or SCHEMA_VERSION,
                "app_version": settings.app_version,
                "built_at": utcnow_iso(),
                "extra_json": json.dumps(extra, ensure_ascii=False, default=str) if extra else None,
                "model_id": model_id,
                "model_rev": model_rev,
                "dim": dim,
                "active_collection": active_collection,
            }
            existing = conn.execute(
                text("SELECT store_name FROM store_meta WHERE store_name = :name"),
                {"name": store_name},
            ).fetchone()
            if existing is None:
                conn.execute(
                    text(
                        "INSERT INTO store_meta(store_name, schema_version, app_version, model_id,"
                        " model_rev, dim, active_collection, built_at, extra_json)"
                        " VALUES (:store_name, :schema_version, :app_version, :model_id,"
                        " :model_rev, :dim, :active_collection, :built_at, :extra_json)"
                    ),
                    values,
                )
            else:
                conn.execute(
                    text(
                        "UPDATE store_meta SET schema_version = :schema_version,"
                        " app_version = :app_version, model_id = COALESCE(:model_id, model_id),"
                        " model_rev = COALESCE(:model_rev, model_rev),"
                        " dim = COALESCE(:dim, dim),"
                        " active_collection = COALESCE(:active_collection, active_collection),"
                        " built_at = :built_at, extra_json = COALESCE(:extra_json, extra_json)"
                        " WHERE store_name = :store_name"
                    ),
                    values,
                )
    finally:
        engine.dispose()


# --------------------------------------------------------------------------- #
# schema 守卫与状态
# --------------------------------------------------------------------------- #
def verify_schema(engine: Engine) -> dict[str, Any]:
    """比对实际库与 `metadata`：缺表/缺列直接报错，返回明细。"""
    with engine.connect() as conn:
        inspector = inspect(conn)
        actual_tables = set(inspector.get_table_names())
        missing_tables = sorted(EXPECTED_TABLES - actual_tables)
        missing_columns: dict[str, list[str]] = {}
        for table_name in sorted(EXPECTED_TABLES & actual_tables):
            expected_cols = {col.name for col in metadata.tables[table_name].columns}
            actual_cols = {col["name"] for col in inspector.get_columns(table_name)}
            absent = sorted(expected_cols - actual_cols)
            if absent:
                missing_columns[table_name] = absent
    if missing_tables or missing_columns:
        raise LitError(
            E_STORE_SCHEMA_MISMATCH,
            f"schema 不匹配：缺表={missing_tables}，缺列={missing_columns}；"
            "请执行 `lit-agent db reset --yes` 或用 Alembic 迁移",
            context={"missing_tables": missing_tables, "missing_columns": missing_columns},
        )
    return {
        "tables": len(EXPECTED_TABLES),
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
    }


def assert_empty_or_initialised(engine: Engine) -> None:
    """空库哨兵：库里有用户表但无 store_meta 行 → 视为脏库/异库（ADR-0003）。"""
    with engine.connect() as conn:
        tables = set(inspect(conn).get_table_names()) - {"alembic_version"}
        if not tables:
            return
        if "store_meta" not in tables:
            raise LitError(
                E_STORE_NOT_EMPTY,
                "目标库已有表但没有 store_meta（旧库或异库）：请 `lit-agent db reset --yes`",
                context={"tables": sorted(tables)[:8]},
            )
        count = conn.execute(text("SELECT COUNT(*) FROM store_meta")).scalar_one()
        if int(count) == 0:
            raise LitError(
                E_STORE_NOT_EMPTY,
                "目标库已有表但 store_meta 为空（未初始化完成）",
                context={"tables": sorted(tables)[:8]},
            )


def database_status(settings: Settings) -> dict[str, Any]:
    """CLI `db status` 的输出：路径、schema 版本、表数、run/event 计数。"""
    path = settings.storage.sqlite_file
    status: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "size_mb": round(path.stat().st_size / (1024 * 1024), 4) if path.exists() else 0.0,
        "schema_version": None,
        "tables": 0,
        "runs": 0,
        "events": 0,
        "expected_schema_version": SCHEMA_VERSION,
    }
    if not path.exists():
        return status
    engine = make_engine(settings)
    try:
        with engine.connect() as conn:
            try:
                status["schema_version"] = conn.execute(
                    text("SELECT schema_version FROM store_meta WHERE store_name='sqlite'")
                ).scalar_one_or_none()
            except Exception:  # noqa: BLE001 - 库可能尚未迁移
                status["schema_version"] = None
            tables = inspect(conn).get_table_names()
            status["tables"] = len([t for t in tables if t != "alembic_version"])
            if "runs" in tables:
                status["runs"] = int(conn.execute(text("SELECT COUNT(*) FROM runs")).scalar_one())
            if "run_events" in tables:
                status["events"] = int(
                    conn.execute(text("SELECT COUNT(*) FROM run_events")).scalar_one()
                )
    finally:
        engine.dispose()
    return status
