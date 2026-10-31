"""V2 RunShell."""

from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from lit_agent_v2.contracts import RunInterrupted, RunRequest, RunState, WorkflowDefinition
from lit_agent_v2.storage.artifacts import ArtifactStore
from lit_agent_v2.storage.db import Database
from lit_agent_v2.workflow.events import EventLog
from lit_agent_v2.workflow.runner import Handler, WorkflowRunner

__all__ = ["RunShell"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


class RunShell:
    def __init__(self, db: Database, artifacts: ArtifactStore) -> None:
        self.db = db
        self.artifacts = artifacts

    def prepare(self, request: RunRequest) -> str:
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO runs(id,topic_id,workflow,request_json,state,created_at,started_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    run_id,
                    request.topic_id,
                    request.workflow,
                    json.dumps(dataclasses.asdict(request), ensure_ascii=False),
                    RunState.RUNNING,
                    _now(),
                    _now(),
                ),
            )
        return run_id

    def run(
        self,
        run_id: str,
        definition: WorkflowDefinition,
        *,
        handlers: dict[str, Handler],
        agent_handlers: dict[str, Handler] | None = None,
        resume: bool = False,
    ) -> dict[str, Any]:
        with self.db.connect() as conn:
            conn.execute("UPDATE runs SET state=? WHERE id=?", (RunState.RUNNING, run_id))
        events = EventLog(self.db, run_id)
        runner = WorkflowRunner(
            self.db,
            self.artifacts,
            run_id,
            events=events,
            control=lambda: self._state(run_id),
        )
        events.emit("run.started")
        try:
            outputs = runner.run(
                definition,
                handlers=handlers,
                agent_handlers=agent_handlers,
                resume=resume,
            )
        except RunInterrupted:
            events.emit("run.paused")
            return runner.outputs
        except Exception:
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE runs SET state=?, finished_at=? WHERE id=?",
                    (RunState.FAILED, _now(), run_id),
                )
            events.emit("run.failed")
            raise
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE runs SET state=?, finished_at=? WHERE id=?",
                (RunState.SUCCEEDED, _now(), run_id),
            )
        events.emit("run.finished")
        return outputs


    def _state(self, run_id: str) -> str:
        with self.db.connect() as conn:
            row = conn.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()
        return str(row[0]) if row else "failed"

    def pause(self, run_id: str) -> None:
        with self.db.connect() as conn:
            conn.execute("UPDATE runs SET state=? WHERE id=? AND state=?",
                         (RunState.PAUSED, run_id, RunState.RUNNING))

    def resume(self, run_id: str) -> None:
        with self.db.connect() as conn:
            conn.execute("UPDATE runs SET state=? WHERE id=? AND state=?",
                         (RunState.RUNNING, run_id, RunState.PAUSED))

    def abort(self, run_id: str) -> None:
        with self.db.connect() as conn:
            conn.execute("UPDATE runs SET state=?, finished_at=? WHERE id=?",
                         (RunState.ABORTED, _now(), run_id))


    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None
