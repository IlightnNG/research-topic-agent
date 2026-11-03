"""Small file-backed NodeStore for CLI and crash/resume tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lit_agent_v2.contracts.verdict import Verdict

__all__ = ["JsonNodeStore"]


class JsonNodeStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str, node_id: str) -> Path:
        safe_run = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in run_id)
        safe_node = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in node_id)
        return self.root / safe_run / f"{safe_node}.json"

    def _read(self, run_id: str, node_id: str) -> dict[str, Any] | None:
        path = self._path(run_id, node_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def state(self, run_id: str, node_id: str) -> str | None:
        payload = self._read(run_id, node_id)
        return str(payload.get("state")) if payload else None

    def load_output(self, run_id: str, node_id: str) -> dict[str, Any] | None:
        payload = self._read(run_id, node_id)
        if not payload or payload.get("state") != "committed":
            return None
        output = payload.get("output")
        return output if isinstance(output, dict) else None

    def commit(
        self,
        run_id: str,
        node_id: str,
        output: dict[str, Any],
        verdict: Verdict,
    ) -> None:
        path = self._path(run_id, node_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "state": "committed",
            "output": output,
            "verdict": verdict.to_dict(),
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, default=str, indent=2),
            encoding="utf-8",
        )

    def degrade(self, run_id: str, node_id: str, reason: str) -> None:
        path = self._path(run_id, node_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"state": "degraded", "reason": reason}, ensure_ascii=False),
            encoding="utf-8",
        )
