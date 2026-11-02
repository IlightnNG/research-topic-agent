"""Tool runtime: visible tool sets, policy, output rendering and spill."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import replace
from typing import Any, Protocol

from lit_agent_v2.contracts.tool import ToolContext, ToolResult, ToolSpec
from lit_agent_v2.tools.registry import ToolRegistry

__all__ = ["ArtifactPort", "ToolRuntime"]


class ArtifactPort(Protocol):
    def put(self, name: str, content: str) -> str: ...


Policy = Callable[[str, dict[str, Any], ToolContext | None], bool | str]


class ToolRuntime:
    """A scoped view over one ToolRegistry.

    The runtime does not replace the registry. It decides which tools are
    visible to a node, applies policy before dispatch, and turns oversized
    rendered content into an artifact reference.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        toolsets: dict[str, Iterable[str]] | None = None,
        default_toolset: str | None = None,
        policy: Policy | None = None,
        artifacts: ArtifactPort | None = None,
    ) -> None:
        self.registry = registry
        self.toolsets = {
            name: tuple(names) for name, names in (toolsets or {}).items()
        }
        self.default_toolset = default_toolset
        self.policy = policy
        self.artifacts = artifacts

    def spec(self, name: str) -> ToolSpec | None:
        return self.registry.spec(name)

    def specs(self, toolset: str | None = None) -> list[ToolSpec]:
        names = self._names(toolset)
        if names is None:
            return [spec for name in self.registry.names() if (spec := self.registry.spec(name))]
        return [spec for name in names if (spec := self.registry.spec(name)) is not None]

    def visible(self, toolset: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.input_schema,
            }
            for spec in self.specs(toolset)
        ]

    def allows(self, name: str, toolset: str | None = None) -> bool:
        names = self._names(toolset)
        return names is None or name in names

    def call(
        self,
        name: str,
        args: dict[str, Any],
        *,
        toolset: str | None = None,
        context: ToolContext | None = None,
    ) -> ToolResult:
        spec = self.registry.spec(name)
        if spec is None:
            return ToolResult(False, error_code="E_TOOL_NOT_FOUND")
        if not self.allows(name, toolset):
            return ToolResult(False, error_code="E_TOOL_NOT_ALLOWED")
        if self.policy is not None:
            decision = self.policy(name, args, context)
            if decision is False or isinstance(decision, str):
                return ToolResult(
                    False,
                    error_code="E_TOOL_POLICY_DENIED",
                    content=str(decision) if isinstance(decision, str) else "",
                )
        result = self.registry.call(name, args)
        if not result.ok:
            return result
        content = result.content or self._render(spec, args, result.output)
        if len(content) > spec.max_output_chars:
            content, refs = self._spill(spec, context, content)
            result = replace(
                result,
                content=content,
                artifact_refs=[*result.artifact_refs, *refs],
                truncated=True,
            )
        elif not result.content:
            result = replace(result, content=content)
        return result

    def _names(self, toolset: str | None) -> tuple[str, ...] | None:
        key = toolset or self.default_toolset
        if key is None:
            return None
        return self.toolsets.get(key, ())

    @staticmethod
    def _render(spec: ToolSpec, args: dict[str, Any], output: dict[str, Any]) -> str:
        if spec.render is not None:
            try:
                return spec.render(args, output)
            except Exception:
                pass
        return json.dumps(output, ensure_ascii=False, default=str)

    def _spill(
        self, spec: ToolSpec, context: ToolContext | None, content: str
    ) -> tuple[str, list[str]]:
        if self.artifacts is None:
            return content[: spec.max_output_chars], []
        name = f"{spec.name}-{(context.call_id if context else 'call')}.txt"
        ref = self.artifacts.put(name, content)
        preview = content[: spec.max_output_chars // 2]
        return (
            f"{preview}\n\n[... output stored in {ref} ...]",
            [ref],
        )
