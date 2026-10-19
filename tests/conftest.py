"""测试公共夹具：临时配置 + 真实 SQLite 引擎（不联网、不建 Kuzu/Qdrant）。"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Connection, Engine
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

import lit_agent.db.tables  # noqa: F401  (注册全部表)
from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.db.base import metadata, utcnow_iso
from lit_agent.db.repo import runs as run_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine
from lit_agent.db.tables import t_store_meta
from lit_agent.models.run import RunState
from lit_agent.models.topic import Topic
from lit_agent.structure import SCHEMA_VERSION


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    """所有路径都落在 pytest 临时目录（其在 D: 上，纯 ASCII）。"""
    return Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        logging=LoggingSettings(console=False),
    )


@pytest.fixture()
def engine(settings: Settings) -> Iterator[Engine]:
    eng = make_engine(settings)
    metadata.create_all(eng)
    with connect(eng, immediate=True) as conn:
        conn.execute(
            sqlite_insert(t_store_meta)
            .values(
                store_name="sqlite",
                schema_version=SCHEMA_VERSION,
                app_version=settings.app_version,
                built_at=utcnow_iso(),
            )
            .on_conflict_do_nothing(index_elements=[t_store_meta.c.store_name])
        )
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture()
def conn(engine: Engine) -> Iterator[Connection]:
    with connect(engine) as connection:
        yield connection


@pytest.fixture()
def seeded(conn: Connection) -> Connection:
    """已建好一个 topic + 一个 running run 的连接。"""
    seed_topic_and_run(conn)
    return conn


@pytest.fixture()
def committed(engine: Engine) -> str:
    """已提交的 topic + running run；返回 run_id。

    事件写入器自开事务，若 seed 仍持有写锁会互相阻塞，故这里必须先提交。
    """
    with connect(engine) as conn:
        seed_topic_and_run(conn)
    return "run-0001"


def seed_topic_and_run(
    conn: Connection,
    *,
    topic_id: str = "ai-agents",
    run_id: str = "run-0001",
    state: RunState = RunState.RUNNING,
) -> None:
    """建一个 topic + 一个 run（多数仓储/事件用例的前置）。"""
    topic_repo.upsert(
        conn,
        Topic(id=topic_id, name=topic_id, scope_statement="llm agents and tool use"),
    )
    run_repo.create(
        conn,
        run_id=run_id,
        topic_id=topic_id,
        trigger="manual",
        config_snapshot={"model": "deepseek-flash"},
        input_hash="hash-1",
        app_version="0.1.0",
        state=state,
    )
