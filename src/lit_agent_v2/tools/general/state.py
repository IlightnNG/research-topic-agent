"""Runtime state shared by the general tools of one AgentKernel run."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["GeneralState"]


def _safe(root: Path, value: str | Path) -> Path:
    root = root.resolve()
    path = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    if path != root and root not in path.parents:
        raise ValueError("path escapes workspace")
    return path


@dataclass
class GeneralState:
    workspace: Path
    artifacts: Path | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    plans: dict[str, dict[str, Any]] = field(default_factory=dict)
    memory: dict[str, dict[str, Any]] = field(default_factory=dict)
    compaction_count: int = 0

    def __post_init__(self) -> None:
        self.workspace = self.workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.artifacts = (self.artifacts or self.workspace / "artifacts").resolve()
        self.artifacts.mkdir(parents=True, exist_ok=True)

    def path(self, value: str | Path) -> Path:
        return _safe(self.workspace, value)

    def put_artifact(self, name: str, content: str) -> str:
        safe_name = Path(name).name
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
        path = self.artifacts / f"{digest}-{safe_name}"
        path.write_text(content, encoding="utf-8")
        return str(path)

    def read_artifact(self, path: str) -> str:
        target = self.path(path)
        if self.artifacts not in target.parents and target != self.artifacts:
            raise ValueError("artifact outside artifact root")
        return target.read_text(encoding="utf-8")

    def create_plan(self, goal: str, steps: list[str]) -> dict[str, Any]:
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        plan = {
            "plan_id": plan_id,
            "goal": goal,
            "steps": [
                {"id": f"s{index + 1}", "text": step, "status": "pending"}
                for index, step in enumerate(steps)
            ],
        }
        self.plans[plan_id] = plan
        return plan

    def update_plan(self, plan_id: str, steps: list[str]) -> dict[str, Any]:
        plan = self.plans[plan_id]
        plan["steps"] = [
            {"id": f"s{index + 1}", "text": step, "status": "pending"}
            for index, step in enumerate(steps)
        ]
        return plan

    def complete_step(self, plan_id: str, step_id: str) -> dict[str, Any]:
        plan = self.plans[plan_id]
        for step in plan["steps"]:
            if step["id"] == step_id:
                step["status"] = "done"
                return plan
        raise ValueError(f"unknown step: {step_id}")

    def write_memory(self, key: str, value: Any, scope: str = "run") -> dict[str, Any]:
        entry = {"key": key, "value": value, "scope": scope}
        self.memory[f"{scope}:{key}"] = entry
        return entry

    def search_memory(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        needle = query.lower()
        results = []
        for entry in self.memory.values():
            text = json.dumps(entry["value"], ensure_ascii=False, default=str)
            if needle in f"{entry['key']} {text}".lower():
                results.append(entry)
            if len(results) >= limit:
                break
        return results

    def inspect_context(self) -> dict[str, Any]:
        chars = len(json.dumps(self.history, ensure_ascii=False, default=str))
        return {
            "messages": len(self.history),
            "chars": chars,
            "estimated_tokens": chars // 4,
            "compactions": self.compaction_count,
        }

    def compact_context(self, keep_recent: int = 6) -> dict[str, Any]:
        before = len(json.dumps(self.history, ensure_ascii=False, default=str))
        keep = max(1, keep_recent)
        compacted: list[dict[str, Any]] = []
        for index, item in enumerate(self.history):
            if index < len(self.history) - keep and item.get("role") == "tool":
                replacement = dict(item)
                replacement["content"] = "[compacted]"
                compacted.append(replacement)
            else:
                compacted.append(item)
        self.history[:] = compacted
        after = len(json.dumps(self.history, ensure_ascii=False, default=str))
        self.compaction_count += 1
        return {
            "before": before,
            "after": after,
            "messages": len(self.history),
            "compactions": self.compaction_count,
        }
