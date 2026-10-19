"""并发取号（ADR-0005 V3）：两个 run 并行写事件，各自 seq 必须是 1..N 连续。"""

from __future__ import annotations

import threading

import pytest
from sqlalchemy.engine import Engine

from lit_agent.config import Settings
from lit_agent.db.repo import runs as run_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine
from lit_agent.models.event import EventType
from lit_agent.models.run import RunState
from lit_agent.models.topic import Topic
from lit_agent.runtime.events import SqliteEventLog

EVENTS_PER_RUN = 60


def test_parallel_runs_have_contiguous_disjoint_seqs(engine: Engine, settings: Settings) -> None:
    with connect(engine) as conn:
        for index in (1, 2):
            topic_repo.upsert(
                conn, Topic(id=f"topic-{index}", name=f"topic-{index}", scope_statement="scope")
            )
            run_repo.create(
                conn,
                run_id=f"run-{index}",
                topic_id=f"topic-{index}",
                trigger="manual",
                state=RunState.RUNNING,
            )

    failures: list[BaseException] = []

    def worker(run_id: str) -> None:
        worker_engine = make_engine(settings)
        try:
            log = SqliteEventLog(worker_engine, run_id)
            for index in range(EVENTS_PER_RUN):
                log.emit(EventType.MESSAGE, payload={"n": index})
        except BaseException as exc:  # noqa: BLE001 - 收集后统一断言
            failures.append(exc)
        finally:
            worker_engine.dispose()

    threads = [threading.Thread(target=worker, args=(f"run-{index}",)) for index in (1, 2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)

    assert not failures, f"并发写事件出错：{failures!r}"

    for index in (1, 2):
        replayed = SqliteEventLog(engine, f"run-{index}").replay(limit=10_000)
        seqs = [event.seq for event in replayed]
        assert seqs == list(range(1, EVENTS_PER_RUN + 1)), f"run-{index} seq 不连续：{seqs[:10]}…"


def test_seq_allocation_is_per_run(engine: Engine) -> None:
    with connect(engine) as conn:
        topic_repo.upsert(conn, Topic(id="t", name="t", scope_statement="s"))
        run_repo.create(conn, run_id="a", topic_id="t", trigger="manual")
        run_repo.create(conn, run_id="b", topic_id="t", trigger="manual")
        assert run_repo.allocate_seq(conn, "a") == 1
        assert run_repo.allocate_seq(conn, "b") == 1
        assert run_repo.allocate_seq(conn, "a") == 2


def test_rollback_does_not_consume_seq(engine: Engine) -> None:
    with connect(engine) as conn:
        topic_repo.upsert(conn, Topic(id="t2", name="t2", scope_statement="s"))
        run_repo.create(conn, run_id="c", topic_id="t2", trigger="manual")

    # 事务内取号后回滚：next_seq 必须没变
    with pytest.raises(RuntimeError), connect(engine, immediate=True) as conn:
        assert run_repo.allocate_seq(conn, "c") == 1
        raise RuntimeError("boom")

    with connect(engine) as conn:
        assert run_repo.get(conn, "c")._mapping["next_seq"] == 0
