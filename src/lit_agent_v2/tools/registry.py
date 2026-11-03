"""Tool registry with schema validation, timeout, retry and allowlist subset."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any

from lit_agent_v2.contracts.tool import ToolContext, ToolResult, ToolSpec
from lit_agent_v2.tools.schema import validate_args, validate_value

__all__ = ["ToolRegistry"]


class ToolRegistry:
    def __init__(
        self,
        specs: Iterable[ToolSpec] = (),
        *,
        on_call: Callable[[str, dict[str, Any], ToolResult], None] | None = None,
    ) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self.on_call = on_call
        for spec in specs:
            self.register(spec)

    def register(self, spec: ToolSpec) -> None:
        if not spec.name:
            raise ValueError("tool name is required")
        if spec.name in self._specs:
            raise ValueError(f"duplicate tool: {spec.name}")
        if spec.handler is None and spec.context_handler is None:
            raise ValueError(f"tool {spec.name} has no handler")
        self._specs[spec.name] = spec

    def names(self) -> list[str]:
        return sorted(self._specs)

    def spec(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def subset(self, names: Iterable[str]) -> ToolRegistry:
        allowed = set(names)
        return ToolRegistry(
            spec for name, spec in self._specs.items() if name in allowed
        )

    def call(
        self, name: str, args: dict[str, Any], *, context: ToolContext | None = None
    ) -> ToolResult:
        spec = self._specs.get(name)
        if spec is None or (spec.handler is None and spec.context_handler is None):
            return ToolResult(False, error_code="E_TOOL_NOT_FOUND")
        problems = validate_args(args, spec.input_schema)
        if problems:
            result = ToolResult(False, error_code="E_TOOL_SCHEMA", output={"problems": problems})
            self._notify(name, args, result)
            return result
        last: ToolResult | None = None
        for _attempt in range(spec.max_retries + 1):
            result = self._call_once(spec, args, context)
            last = result
            if result.ok or not result.retryable:
                break
            if result.error_code not in spec.retry_on:
                break
        assert last is not None
        self._notify(name, args, last)
        return last

    def _call_once(
        self, spec: ToolSpec, args: dict[str, Any], context: ToolContext | None
    ) -> ToolResult:
        started = time.monotonic()
        pool = ThreadPoolExecutor(max_workers=1)
        if spec.context_handler is not None:
            future = pool.submit(spec.context_handler, args, context)  # type: ignore[arg-type]
        else:
            future = pool.submit(spec.handler, args)  # type: ignore[arg-type]
        try:
            output = future.result(timeout=spec.timeout_s)
        except FutureTimeout:
            return ToolResult(
                False,
                error_code="E_TOOL_TIMEOUT",
                retryable=True,
                duration_ms=int((time.monotonic() - started) * 1000),
                cost_usd=spec.cost_usd,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                False,
                error_code=f"E_TOOL_EXCEPTION:{type(exc).__name__}",
                content=f"{type(exc).__name__}: {exc}",
                retryable=False,
                duration_ms=int((time.monotonic() - started) * 1000),
                cost_usd=spec.cost_usd,
            )
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        if not isinstance(output, dict):
            return ToolResult(
                False,
                error_code="E_TOOL_OUTPUT",
                retryable=False,
                duration_ms=int((time.monotonic() - started) * 1000),
                cost_usd=spec.cost_usd,
            )
        output_problems = validate_value("output", output, spec.output_schema)
        if output_problems:
            return ToolResult(
                False,
                error_code="E_TOOL_OUTPUT_SCHEMA",
                output={"problems": output_problems},
                duration_ms=int((time.monotonic() - started) * 1000),
                cost_usd=spec.cost_usd,
            )
        content = spec.render(args, output) if spec.render is not None else ""
        return ToolResult(
            True,
            output=output,
            duration_ms=int((time.monotonic() - started) * 1000),
            cost_usd=spec.cost_usd,
            content=content,
        )

    def _notify(self, name: str, args: dict[str, Any], result: ToolResult) -> None:
        if self.on_call is not None:
            self.on_call(name, args, result)
