"""schema 守卫（Phase 0 静默错误 #1 的固化防护）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from lit_agent.config import Settings, StorageSettings
from lit_agent.db.session import (
    assert_empty_or_initialised,
    connect,
    make_engine,
    verify_schema,
)
from lit_agent.errors import E_STORE_NOT_EMPTY, E_STORE_SCHEMA_MISMATCH, LitError


def test_fresh_schema_passes(engine: Engine) -> None:
    report = verify_schema(engine)
    assert report["missing_tables"] == []
    assert report["missing_columns"] == {}


def test_dropped_column_is_detected(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE papers DROP COLUMN abstract")

    with pytest.raises(LitError) as excinfo:
        verify_schema(engine)

    assert excinfo.value.code == E_STORE_SCHEMA_MISMATCH
    assert "papers" in excinfo.value.context["missing_columns"]
    assert "abstract" in excinfo.value.context["missing_columns"]["papers"]


def test_missing_table_is_detected(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE paper_chunks")

    with pytest.raises(LitError) as excinfo:
        verify_schema(engine)
    assert "paper_chunks" in excinfo.value.context["missing_tables"]


def test_dirty_database_without_store_meta_is_rejected(tmp_path: Path) -> None:
    settings = Settings(storage=StorageSettings(data_root=str(tmp_path / "dirty")))
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            conn.exec_driver_sql("CREATE TABLE stray (id INTEGER PRIMARY KEY)")

        with pytest.raises(LitError) as excinfo:
            assert_empty_or_initialised(engine)
        assert excinfo.value.code == E_STORE_NOT_EMPTY
    finally:
        engine.dispose()


def test_empty_database_is_allowed(tmp_path: Path) -> None:
    settings = Settings(storage=StorageSettings(data_root=str(tmp_path / "fresh")))
    engine = make_engine(settings)
    try:
        assert_empty_or_initialised(engine)  # 空库不应报错（首次导入前）
    finally:
        engine.dispose()
