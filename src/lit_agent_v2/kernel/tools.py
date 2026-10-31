"""Tool registry with schema and timeout."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ToolResult", "ToolSpec", "ToolBox"]


@dataclass
class ToolResult:
    ok: bool
    output: dict[str, Any]
    error: str | None = None
    cost_usd: float = 0.0


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, str] = field(default_factory=dict)
    required: tuple[str, ...] = ()
    timeout_s: float = 30.0
    cost_usd: float = 0.0
    handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None


class ToolBox:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec | str, fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> None:
        if isinstance(spec, str):
            if fn is None:
                raise ValueError("handler required")
            spec = ToolSpec(name=spec, description=spec, handler=fn)
        if spec.handler is None:
            raise ValueError("tool handler required")
        self._tools[spec.name] = spec

    def names(self) -> list[str]:
        return sorted(self._tools)

    def spec(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def _validate(self, spec: ToolSpec, args: dict[str, Any]) -> str | None:
        missing = [key for key in spec.required if key not in args]
        if missing:
            return f"E_TOOL_ARGS: missing {missing}"
        return None

    def call(self, name: str, args: dict[str, Any]) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None or spec.handler is None:
            return ToolResult(False, {}, "E_TOOL_NOT_FOUND")
        problem = self._validate(spec, args)
        if problem:
            return ToolResult(False, {}, problem)
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(spec.handler, args)
        try:
            output = future.result(timeout=spec.timeout_s)
        except FutureTimeout:
            return ToolResult(False, {}, "E_TOOL_TIMEOUT")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(False, {}, f"E_TOOL_ERROR: {type(exc).__name__}")
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        return ToolResult(True, output, cost_usd=spec.cost_usd)
