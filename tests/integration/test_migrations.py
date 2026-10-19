"""迁移验收（D2）：可升、可降、再升，且 schema 与 `metadata` 完全一致。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from sqlalchemy import inspect, text

from lit_agent.config import Settings
from lit_agent.db.session import (
    alembic_config,
    connect,
    make_engine,
    reset_database,
    upgrade_database,
    verify_schema,
)
from lit_agent.db.tables import EXPECTED_TABLES
from lit_agent.structure import SCHEMA_VERSION


def table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows} - {"alembic_version", "sqlite_sequence"}


def test_upgrade_creates_all_tables(settings: Settings) -> None:
    db_path = upgrade_database(settings)

    assert db_path.exists()
    assert table_names(db_path) == set(EXPECTED_TABLES)
    assert len(table_names(db_path)) == 24


def test_schema_matches_metadata(settings: Settings) -> None:
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        report = verify_schema(engine)
    finally:
        engine.dispose()
    assert report["missing_tables"] == []
    assert report["missing_columns"] == {}


def test_store_meta_is_written(settings: Settings) -> None:
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            row = conn.execute(
                text("SELECT schema_version, app_version FROM store_meta WHERE store_name='sqlite'")
            ).first()
    finally:
        engine.dispose()
    assert row is not None
    assert row[0] == SCHEMA_VERSION
    assert row[1] == settings.app_version


def test_wal_and_foreign_keys_enabled(settings: Settings) -> None:
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            mode = conn.execute(text("PRAGMA journal_mode")).scalar_one()
            fk = conn.execute(text("PRAGMA foreign_keys")).scalar_one()
    finally:
        engine.dispose()
    assert str(mode).lower() == "wal"
    assert int(fk) == 1


def test_downgrade_then_upgrade_again(settings: Settings) -> None:
    db_path = upgrade_database(settings)
    command.downgrade(alembic_config(settings), "base")

    remaining = table_names(db_path)
    assert remaining == set(), f"降级后仍有表：{remaining}"

    upgrade_database(settings)
    assert table_names(db_path) == set(EXPECTED_TABLES)


def test_reset_database_rebuilds(settings: Settings) -> None:
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            conn.execute(
                text(
                    "INSERT INTO topics(id,name,scope_statement,created_at,updated_at)"
                    " VALUES ('t1','T1','scope','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')"
                )
            )
    finally:
        engine.dispose()

    reset_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM topics")).scalar_one()
    finally:
        engine.dispose()
    assert int(count) == 0


def test_indexes_are_created(settings: Settings) -> None:
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            paper_indexes = {ix["name"] for ix in inspector.get_indexes("papers")}
            run_indexes = {ix["name"] for ix in inspector.get_indexes("runs")}
            event_indexes = {ix["name"] for ix in inspector.get_indexes("run_events")}
    finally:
        engine.dispose()

    assert "ux_papers_source" in paper_indexes
    assert "ux_runs_one_running" in run_indexes
    assert "ux_run_events_dedupe" in event_indexes
