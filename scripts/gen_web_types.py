"""从 OpenAPI 生成前端类型（S12）：`web/src/api/types.gen.ts`。

只生成**组件 schema**（Pydantic 模型）；响应为 `dict` 的端点没有 schema，属于已知限制。
用法：`uv run python scripts/gen_web_types.py`
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "src" / "api" / "types.gen.ts"

_PRIMITIVES = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "null": "null",
}


def ts_type(schema: dict, *, indent: int = 0) -> str:
    if not schema:
        return "unknown"
    if "$ref" in schema:
        return f'components["schemas"]["{schema["$ref"].rsplit("/", 1)[-1]}"]'
    if "anyOf" in schema:
        return " | ".join(ts_type(item) for item in schema["anyOf"])
    if schema.get("type") == "array":
        return f"{ts_type(schema.get('items') or {})}[]"
    if schema.get("type") == "object" and "properties" in schema:
        pad = "  " * (indent + 1)
        lines = [
            f"{pad}{name}{'?' if name not in (schema.get('required') or []) else ''}: {ts_type(value, indent=indent + 1)};"
            for name, value in schema["properties"].items()
        ]
        return "{\n" + "\n".join(lines) + "\n" + "  " * indent + "}"
    if "enum" in schema:
        return " | ".join(json.dumps(item, ensure_ascii=False) for item in schema["enum"])
    return _PRIMITIVES.get(schema.get("type", ""), "unknown")


def main() -> int:
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from lit_agent.api.app import create_app

    schemas = create_app().openapi().get("components", {}).get("schemas", {})
    lines = [
        "// 由 `scripts/gen_web_types.py` 生成，请勿手改。",
        "// 覆盖范围：FastAPI 组件 schema（Pydantic 模型）；dict 端点不在其中。",
        "",
        "export interface components {",
        "  schemas: {",
    ]
    for name, schema in sorted(schemas.items()):
        lines.append(f"    {name}: {ts_type(schema, indent=2)};")
    lines += ["  };", "}", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(schemas)} schemas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
