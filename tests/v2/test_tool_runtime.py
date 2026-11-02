"""Phase 4.2 S1/S2: tool contracts and ToolRuntime."""

from __future__ import annotations

from typing import Any

from lit_agent_v2.contracts.tool import ToolContext, ToolSpec
from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.tools.runtime import ToolRuntime


def _spec(**overrides: Any) -> ToolSpec:
    values: dict[str, Any] = {
        "name": "demo.echo",
        "description": "echo",
        "input_schema": {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
        "output_schema": {"type": "object", "required": ["value"]},
        "handler": lambda args: {"value": args["value"]},
    }
    values.update(overrides)
    return ToolSpec(**values)


def test_tool_spec_parallel_defaults() -> None:
    assert _spec().effective_parallel_safe is True
    assert _spec(side_effect=True).effective_parallel_safe is False
    assert _spec(side_effect=True, parallel_safe=True).effective_parallel_safe is True


def test_registry_validates_output_schema() -> None:
    registry = ToolRegistry(
        [_spec(handler=lambda _args: {"wrong": True})],
    )
    result = registry.call("demo.echo", {"value": "x"})
    assert not result.ok
    assert result.error_code == "E_TOOL_OUTPUT_SCHEMA"


def test_runtime_limits_visible_tools() -> None:
    registry = ToolRegistry([_spec()])
    runtime = ToolRuntime(
        registry,
        toolsets={"echo": ("demo.echo",)},
        default_toolset="echo",
    )
    assert [spec.name for spec in runtime.specs()] == ["demo.echo"]
    assert runtime.allows("demo.echo")
    assert not runtime.allows("demo.missing")


def test_runtime_blocks_tools_outside_toolset() -> None:
    registry = ToolRegistry([_spec()])
    runtime = ToolRuntime(registry, toolsets={"other": ("other.tool",)})
    result = runtime.call("demo.echo", {"value": "x"}, toolset="other")
    assert not result.ok
    assert result.error_code == "E_TOOL_NOT_ALLOWED"


def test_runtime_policy_denial() -> None:
    registry = ToolRegistry([_spec()])
    runtime = ToolRuntime(
        registry,
        toolsets={"echo": ("demo.echo",)},
        policy=lambda _name, _args, _context: "blocked by policy",
    )
    result = runtime.call("demo.echo", {"value": "x"}, toolset="echo")
    assert not result.ok
    assert result.error_code == "E_TOOL_POLICY_DENIED"
    assert result.content == "blocked by policy"


def test_runtime_renders_and_spills() -> None:
    class Artifacts:
        def __init__(self) -> None:
            self.values: dict[str, str] = {}

        def put(self, name: str, content: str) -> str:
            self.values[name] = content
            return f"artifact://{name}"

    registry = ToolRegistry(
        [
            _spec(
                max_output_chars=10,
                render=lambda _args, _output: "x" * 100,
            )
        ]
    )
    artifacts = Artifacts()
    runtime = ToolRuntime(
        registry,
        toolsets={"echo": ("demo.echo",)},
        artifacts=artifacts,
    )
    result = runtime.call(
        "demo.echo",
        {"value": "x"},
        toolset="echo",
        context=ToolContext(call_id="call_1"),
    )
    assert result.ok
    assert result.truncated
    assert result.artifact_refs == ["artifact://demo.echo-call_1.txt"]
    assert "demo.echo-call_1.txt" in artifacts.values


def test_runtime_unknown_toolset_has_no_tools() -> None:
    registry = ToolRegistry([_spec()])
    runtime = ToolRuntime(registry, toolsets={"echo": ("demo.echo",)})
    assert runtime.specs("missing") == []
