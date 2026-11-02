"""Tool-call scheduler: parallel-safe calls overlap, exclusive calls barrier."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from lit_agent_v2.contracts.tool import ToolContext, ToolResult
from lit_agent_v2.tools.runtime import ToolRuntime

__all__ = ["schedule_tool_calls"]


def schedule_tool_calls(
    runtime: ToolRuntime,
    calls: list[dict[str, Any]],
    *,
    toolset: str,
    context_for: Callable[[dict[str, Any]], ToolContext],
    max_parallel: int = 4,
) -> list[ToolResult]:
    """Execute in model order, overlapping consecutive parallel-safe calls."""
    results: list[ToolResult] = []
    index = 0
    while index < len(calls):
        call = calls[index]
        spec = runtime.spec(call["name"])
        if spec is None or not spec.effective_parallel_safe:
            results.append(
                runtime.call(
                    call["name"],
                    call["args"],
                    toolset=toolset,
                    context=context_for(call),
                )
            )
            index += 1
            continue
        group: list[dict[str, Any]] = []
        while index < len(calls):
            next_call = calls[index]
            next_spec = runtime.spec(next_call["name"])
            if next_spec is None or not next_spec.effective_parallel_safe:
                break
            group.append(next_call)
            index += 1
        if len(group) == 1:
            results.append(
                runtime.call(
                    group[0]["name"],
                    group[0]["args"],
                    toolset=toolset,
                    context=context_for(group[0]),
                )
            )
            continue
        with ThreadPoolExecutor(max_workers=min(max_parallel, len(group))) as pool:
            futures = [
                pool.submit(
                    runtime.call,
                    item["name"],
                    item["args"],
                    toolset=toolset,
                    context=context_for(item),
                )
                for item in group
            ]
            results.extend(future.result() for future in futures)
    return results
