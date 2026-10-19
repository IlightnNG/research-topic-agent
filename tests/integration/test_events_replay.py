"""事件总线验收（D5）：序号连续、幂等不跳号、回放一致、先落库后广播。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from lit_agent.db.repo import runs as run_repo
from lit_agent.db.session import connect
from lit_agent.errors import E_DATA_DUP
from lit_agent.models._base import Severity
from lit_agent.models.event import Event, EventType
from lit_agent.runtime.events import SqliteEventLog


class RecordingBroadcaster:
    def __init__(self, engine: Engine | None = None) -> None:
        self.events: list[Event] = []
        self.visible_at_publish: list[bool] = []
        self._engine = engine

    def publish(self, event: Event) -> None:
        self.events.append(event)
        if self._engine is not None:
            # 广播时必须已经能读到该行（先落库、后广播）
            with connect(self._engine) as conn:
                found = conn.execute(
                    text("SELECT COUNT(*) FROM run_events WHERE run_id=:r AND seq=:s"),
                    {"r": event.run_id, "s": event.seq},
                ).scalar_one()
            self.visible_at_publish.append(int(found) == 1)


def make_log(engine: Engine, run_id: str = "run-0001", **kwargs: object) -> SqliteEventLog:
    return SqliteEventLog(engine, run_id, **kwargs)  # type: ignore[arg-type]


def test_seq_is_contiguous(engine: Engine, committed: str) -> None:
    log = make_log(engine)
    first = log.emit(EventType.PHASE_CHANGE, stage="retrieval", payload={"phase": "start"})
    second = log.emit(
        EventType.TOOL_CALL,
        stage="retrieval",
        dedupe_key="retrieval:openalex:page:1",
        payload={"tool": "openalex"},
    )

    assert first is not None and second is not None
    assert (first.seq, second.seq) == (1, 2)
    assert log.count() == 2


def test_replay_returns_ordered_events(engine: Engine, committed: str) -> None:
    log = make_log(engine)
    log.emit(EventType.PHASE_CHANGE, stage="intake")
    log.emit(EventType.METRIC, stage="intake", payload={"kind": "papers_new", "value": 3})

    replayed = log.replay()
    assert [event.seq for event in replayed] == [1, 2]
    assert [event.type for event in replayed] == [EventType.PHASE_CHANGE, EventType.METRIC]
    assert replayed[1].payload == {"kind": "papers_new", "value": 3}


def test_after_seq_pagination_has_no_gaps_or_duplicates(engine: Engine, committed: str) -> None:
    log = make_log(engine)
    for index in range(5):
        log.emit(EventType.MESSAGE, payload={"n": index})

    page1 = log.replay(after_seq=0, limit=2)
    page2 = log.replay(after_seq=page1[-1].seq, limit=2)
    page3 = log.replay(after_seq=page2[-1].seq, limit=2)

    seqs = [event.seq for event in page1 + page2 + page3]
    assert seqs == [1, 2, 3, 4, 5]


def test_dedupe_hit_does_not_consume_seq(engine: Engine, committed: str) -> None:
    log = make_log(engine)
    log.emit(EventType.TOOL_CALL, stage="retrieval", dedupe_key="retrieval:pdf:W1")
    dup = log.emit(EventType.TOOL_CALL, stage="retrieval", dedupe_key="retrieval:pdf:W1")

    assert dup is not None
    assert dup.type is EventType.ERROR
    assert dup.dedupe_key is None, "去重告警自身不得带 dedupe_key（否则会自我冲突）"
    assert dup.payload["code"] == E_DATA_DUP

    log.emit(EventType.MESSAGE)

    seqs = [event.seq for event in log.replay()]
    assert seqs == [1, 2, 3], "序必须连续：去重命中不能留下空号"
    assert log.count() == 3

    with connect(engine) as conn:
        assert run_repo.get(conn, "run-0001")._mapping["dup_events"] == 1


def test_non_idempotent_events_can_repeat(engine: Engine, committed: str) -> None:
    log = make_log(engine)
    log.emit(EventType.LLM_CALL, payload={"request_sha": "a"})
    log.emit(EventType.LLM_CALL, payload={"request_sha": "a"})
    assert log.count() == 2


def test_broadcast_happens_after_commit(engine: Engine, committed: str) -> None:
    broadcaster = RecordingBroadcaster(engine)
    log = make_log(engine, broadcaster=broadcaster)

    log.emit(EventType.PHASE_CHANGE, stage="retrieval")

    assert len(broadcaster.events) == 1
    assert broadcaster.visible_at_publish == [True]


def test_conn_scoped_emit_defers_broadcast(engine: Engine, committed: str) -> None:
    broadcaster = RecordingBroadcaster()
    log = make_log(engine, broadcaster=broadcaster)

    with connect(engine) as conn:
        event = log.emit(EventType.MESSAGE, payload={"x": 1}, conn=conn)
        assert event is not None
        assert event.seq == 1
        # 事务内可见
        assert conn.execute(text("SELECT COUNT(*) FROM run_events")).scalar_one() == 1

    assert broadcaster.events == [], "调用方事务内的写入不得提前广播"


def test_jsonl_export(engine: Engine, committed: str, tmp_path: Path) -> None:
    log = make_log(engine, jsonl_dir=tmp_path)
    log.emit(EventType.REPORT_WRITTEN, payload={"report_id": "rep-1"})

    exported = tmp_path / "run-0001.jsonl"
    assert exported.is_file()
    lines = exported.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = Event.from_json_line(lines[0])
    assert parsed.type is EventType.REPORT_WRITTEN
    assert parsed.seq == 1


def test_error_event_carries_code(engine: Engine, committed: str) -> None:
    log = make_log(engine)
    event = log.emit(
        EventType.ERROR,
        severity=Severity.ERROR,
        payload={"code": "E_SRC_TIMEOUT", "retryable": True},
    )
    assert event is not None
    replayed = log.replay()[0]
    assert replayed.payload["code"] == "E_SRC_TIMEOUT"


def test_emit_for_unknown_run_raises(engine: Engine) -> None:
    from lit_agent.errors import LitError

    log = make_log(engine, run_id="nope")
    with pytest.raises(LitError):
        log.emit(EventType.MESSAGE)


def test_dump_jsonl(engine: Engine, committed: str, tmp_path: Path) -> None:
    log = make_log(engine)
    log.emit(EventType.PHASE_CHANGE, stage="a")
    log.emit(EventType.PHASE_CHANGE, stage="b")

    target = tmp_path / "dump.jsonl"
    assert log.dump_jsonl(target) == 2
    assert len(target.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_replay_empty_for_fresh_run(engine: Engine, committed: str) -> None:
    assert make_log(engine).replay() == []


def test_event_log_does_not_need_conn_fixture(engine: Engine, committed: str) -> None:
    """确认自带事务路径可用（不依赖调用方连接）。"""
    log = make_log(engine)
    log.emit(EventType.PHASE_CHANGE)
    with connect(engine) as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM run_events")).scalar_one() == 1
