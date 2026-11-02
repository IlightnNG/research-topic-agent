"""Tool registry and schema validation."""

from __future__ import annotations

from typing import Any

__all__ = ["validate_args", "validate_value"]


def validate_args(args: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    if not schema:
        return []
    if schema.get("type") not in (None, "object"):
        return ["tool input schema must be an object"]
    if not isinstance(args, dict):
        return ["tool args must be an object"]
    problems: list[str] = []
    required = schema.get("required") or []
    for key in required:
        if key not in args:
            problems.append(f"missing required argument: {key}")
    properties = schema.get("properties") or {}
    for key, value in args.items():
        spec = properties.get(key)
        if spec is None:
            if schema.get("additionalProperties") is False:
                problems.append(f"unknown argument: {key}")
            continue
        problems.extend(_validate_value(key, value, spec))
    return problems


def validate_value(name: str, value: Any, schema: dict[str, Any]) -> list[str]:
    """Validate one JSON value against the small schema subset tools use."""
    return _validate_value(name, value, schema)


def _validate_value(name: str, value: Any, schema: dict[str, Any]) -> list[str]:
    expected = schema.get("type")
    if expected is None and ("properties" in schema or "required" in schema):
        expected = "object"
    if expected is None:
        return []
    if expected == "string" and not isinstance(value, str):
        return [f"{name}: expected string"]
    if expected == "number" and not isinstance(value, (int, float)):
        return [f"{name}: expected number"]
    if expected == "integer" and not isinstance(value, int):
        return [f"{name}: expected integer"]
    if expected == "boolean" and not isinstance(value, bool):
        return [f"{name}: expected boolean"]
    if expected == "array":
        if not isinstance(value, list):
            return [f"{name}: expected array"]
        item_schema = schema.get("items") or {}
        problems: list[str] = []
        for index, item in enumerate(value):
            problems.extend(_validate_value(f"{name}[{index}]", item, item_schema))
        return problems
    if expected == "object":
        if not isinstance(value, dict):
            return [f"{name}: expected object"]
        problems = []
        for key in schema.get("required") or []:
            if key not in value:
                problems.append(f"{name}.{key}: missing")
        for key, item in value.items():
            child = (schema.get("properties") or {}).get(key)
            if child is not None:
                problems.extend(_validate_value(f"{name}.{key}", item, child))
        return problems
    return []
