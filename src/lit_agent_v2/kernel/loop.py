"""Minimal v2 kernel."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

__all__ = ["Goal", "Kernel", "KernelResult", "ToolBox", "ToolResult"]


@dataclass
class Goal:
    node_id: str
    objective: str
    max_steps: int = 3
    max_usd: float = 0.05


@dataclass
class ToolResult:
    ok: bool
    output: dict[str, Any]
    error: str | None = None
    cost_usd: float = 0.0


@dataclass
class KernelResult:
    output: dict[str, Any]
    steps: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = "final"


class ToolBox:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}

    def register(self, name: str, fn: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self._tools[name] = fn

    def call(self, name: str, args: dict[str, Any]) -> ToolResult:
        fn = self._tools.get(name)
        if fn is None:
            return ToolResult(False, {}, "E_TOOL_NOT_FOUND")
        try:
            return ToolResult(True, fn(args))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(False, {}, f"{type(exc).__name__}: {exc}")


class Kernel:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def run(
        self,
        goal: Goal,
        toolbox: ToolBox,
        completer: Callable[[list[dict[str, Any]]], dict[str, Any]],
    ) -> KernelResult:
        history: list[dict[str, Any]] = []
        for _step in range(1, goal.max_steps + 1):
            if self.cancelled:
                return KernelResult({}, history, "cancelled")
            action = completer(history)
            if action.get("action") == "final":
                return KernelResult(dict(action.get("outputs") or {}), history, "final")
            name = str(action.get("tool") or "")
            result = toolbox.call(name, dict(action.get("args") or {}))
            history.append({"tool": name, "ok": result.ok, "output": result.output})
            if not result.ok:
                return KernelResult({}, history, "failed")
        return KernelResult({}, history, "max_steps")
