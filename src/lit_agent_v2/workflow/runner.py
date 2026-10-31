"""V2 workflow runner."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from lit_agent_v2.contracts import NodeSpec, NodeState, RunInterrupted, WorkflowDefinition
from lit_agent_v2.storage.artifacts import ArtifactStore
from lit_agent_v2.storage.db import Database
from lit_agent_v2.workflow.events import EventLog
from lit_agent_v2.workflow.verifier import CodeVerifier

__all__ = ["WorkflowRunner"]

Handler = Callable[[dict[str, Any]], dict[str, Any]]


def _now() -> str:
    return datetime.now(UTC).isoformat()


class WorkflowRunner:
    def __init__(
        self,
        db: Database,
        artifacts: ArtifactStore,
        run_id: str,
        *,
        events: EventLog | None = None,
        verifier: CodeVerifier | None = None,
        control: Callable[[], str] | None = None,
    ) -> None:
        self.db = db
        self.artifacts = artifacts
        self.run_id = run_id
        self.events = events
        self.verifier = verifier or CodeVerifier()
        self.control = control
        self._outputs: dict[str, dict[str, Any]] = {}

    @property
    def outputs(self) -> dict[str, dict[str, Any]]:
        return dict(self._outputs)

    def _state(self, node_id: str) -> str | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT state FROM run_nodes WHERE run_id=? AND node_id=?",
                (self.run_id, node_id),
            ).fetchone()
        return str(row[0]) if row else None

    def _load_output(self, node_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT sha256,payload_json FROM run_artifacts WHERE run_id=? AND node_id=?"
                " ORDER BY created_at DESC LIMIT 1",
                (self.run_id, node_id),
            ).fetchone()
        if row is None:
            return None
        payload = row[1]
        if payload and payload != "{}":
            return json.loads(payload)
        return self.artifacts.get(str(row[0]))

    def _commit(self, node: NodeSpec, output: dict[str, Any]) -> str:
        sha = self.artifacts.put(output)
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO run_artifacts(run_id,node_id,kind,sha256,payload_json,created_at)"
                " VALUES (?,?,?,?,?,?)",
                (self.run_id, node.id, node.output_key or "output", sha, "{}", _now()),
            )
            conn.execute(
                "INSERT INTO run_nodes(run_id,node_id,state,attempt,checkpoint_json,"
                "artifact_sha,started_at,finished_at) VALUES (?,?,?,?,?,?,?,?)"
                " ON CONFLICT(run_id,node_id) DO UPDATE SET state=excluded.state,"
                " artifact_sha=excluded.artifact_sha, finished_at=excluded.finished_at",
                (self.run_id, node.id, NodeState.COMMITTED, 1, None, sha, _now(), _now()),
            )
        return sha

    def run(
        self,
        definition: WorkflowDefinition,
        *,
        handlers: dict[str, Handler] | None = None,
        agent_handlers: dict[str, Handler] | None = None,
        resume: bool = False,
    ) -> dict[str, Any]:
        handlers = handlers or {}
        agent_handlers = agent_handlers or {}
        for node in definition.nodes:
            if self.control is not None and self.control() != "running":
                raise RunInterrupted(self.control())
            if resume and self._state(node.id) == NodeState.COMMITTED:
                loaded = self._load_output(node.id)
                if loaded is not None:
                    self._outputs[node.output_key] = loaded
                continue
            inputs = {key: self._outputs[key] for key in node.input_keys if key in self._outputs}
            handler = handlers.get(node.id) if node.kind == "deterministic" else agent_handlers.get(node.id)
            if handler is None:
                raise RuntimeError(f"no handler for {node.id}")
            if self.events:
                self.events.emit("node.started", node_id=node.id)
            try:
                output = handler(inputs)
                verdict = self.verifier.verify(node, output)
                if not verdict.accept:
                    raise RuntimeError(f"verifier: {verdict.reasons}")
                self._commit(node, output)
                self._outputs[node.output_key] = output
                if self.events:
                    self.events.emit("node.finished", node_id=node.id)
            except Exception as exc:  # noqa: BLE001
                with self.db.connect() as conn:
                    conn.execute(
                        "INSERT INTO run_nodes(run_id,node_id,state,attempt,error_code)"
                        " VALUES (?,?,?,?,?) ON CONFLICT(run_id,node_id) DO UPDATE SET state=excluded.state,"
                        " error_code=excluded.error_code",
                        (self.run_id, node.id, NodeState.FAILED, 1, type(exc).__name__),
                    )
                if self.events:
                    self.events.emit("node.failed", node_id=node.id, error=str(exc))
                raise
        return dict(self._outputs)
