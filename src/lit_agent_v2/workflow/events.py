"""V2 event writer."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from lit_agent_v2.storage.db import Database

__all__ = ["EventLog"]


class EventLog:
    def __init__(self, db: Database, run_id: str) -> None:
        self.db = db
        self.run_id = run_id
        with db.connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq),0) FROM run_events WHERE run_id=?", (run_id,)
            ).fetchone()
        self._seq = int(row[0]) if row else 0

    def emit(self, event_type: str, *, node_id: str | None = None, **payload: Any) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq),0) FROM run_events WHERE run_id=?", (self.run_id,)
            ).fetchone()
        self._seq = int(row[0]) + 1 if row else 1
        event = {
            "event_id": uuid.uuid4().hex,
            "run_id": self.run_id,
            "seq": self._seq,
            "type": event_type,
            "node_id": node_id,
            "payload": payload,
            "ts": datetime.now(UTC).isoformat(),
        }
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO run_events(id,run_id,seq,type,node_id,payload_json,ts)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    event["event_id"],
                    self.run_id,
                    event["seq"],
                    event_type,
                    node_id,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    event["ts"],
                ),
            )
        return event
