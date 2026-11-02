"""Deterministic orchestration for the 4-Node 100-paper demo.

The report tool still uses a real LLM per analysis group. This adapter only
removes model-level variance from the *control plane* (which tool to call), so
the 100-paper demo can complete reproducibly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = ["DemoOrchestrator"]


class DemoOrchestrator:
    def __init__(self, root: Path, out_dir: Path) -> None:
        self.root = Path(root)
        self.out_dir = Path(out_dir)
        self.calls: dict[str, int] = {}

    def _node(self, messages: list[dict[str, Any]]) -> str:
        system = str(messages[0].get("content") or "")
        for line in system.splitlines():
            if line.startswith("Node: "):
                return line.split("Node: ", 1)[1].strip()
        return ""

    def _tool(self, node_id: str) -> dict[str, Any]:
        if node_id == "source.collect":
            return {
                "id": "call_source",
                "name": "demo.source",
                "args": {"root": str(self.root), "out_dir": str(self.out_dir)},
            }
        if node_id == "evidence.extract":
            return {
                "id": "call_evidence",
                "name": "demo.evidence",
                "args": {
                    "source_path": str(self.out_dir / "source.json"),
                    "out_dir": str(self.out_dir),
                },
            }
        if node_id == "report.generate":
            return {
                "id": "call_report",
                "name": "demo.report",
                "args": {
                    "source_path": str(self.out_dir / "source.json"),
                    "evidence_path": str(self.out_dir / "evidence.json"),
                    "out_dir": str(self.out_dir),
                    "language": "en",
                },
            }
        return {
            "id": "call_finalize",
            "name": "demo.finalize",
            "args": {
                "report_path": str(self.out_dir / "report.json"),
                "out_dir": str(self.out_dir),
            },
        }

    def _final(self, node_id: str) -> dict[str, Any]:
        if node_id == "source.collect":
            payload = json.loads((self.out_dir / "source.json").read_text(encoding="utf-8"))
            papers = len(payload.get("papers") or [])
            fulltext = sum(1 for paper in payload.get("papers") or [] if paper.get("fulltext"))
            return {
                "source_path": str(self.out_dir / "source.json"),
                "papers": papers,
                "fulltext": fulltext,
                "fulltext_ratio": fulltext / papers if papers else 0.0,
                "state": "complete" if fulltext >= papers * 0.3 else "degraded",
            }
        if node_id == "evidence.extract":
            payload = json.loads((self.out_dir / "evidence.json").read_text(encoding="utf-8"))
            return {
                "evidence_path": str(self.out_dir / "evidence.json"),
                "papers": len(payload.get("papers") or []),
                "claims": len(payload.get("claims") or []),
            }
        if node_id == "report.generate":
            report_file = self.out_dir / "report.json"
            if not report_file.exists():
                return {}
            payload = json.loads(report_file.read_text(encoding="utf-8"))
            return {
                "report_path": str(self.out_dir / "report.json"),
                "papers": payload.get("papers", 0),
                "claims": len(payload.get("claims") or []),
                "sections": len(payload.get("sections") or []),
                "word_count": payload.get("word_count", 0),
                "state": payload.get("state", "degraded"),
            }
        payload = json.loads((self.out_dir / "final.json").read_text(encoding="utf-8"))
        return {
            "report_path": payload.get("report_path"),
            "content_sha": payload.get("content_sha"),
            "papers": payload.get("papers", 0),
            "claims": payload.get("claims", 0),
            "state": payload.get("state", "degraded"),
        }

    def chat_json(self, messages, **kwargs):  # noqa: ANN001, ARG002
        node_id = self._node(messages)
        count = self.calls.get(node_id, 0)
        self.calls[node_id] = count + 1
        if count == 0:
            return {"action": "tool", "calls": [self._tool(node_id)]}, None
        return {"action": "final", "outputs": self._final(node_id)}, None
