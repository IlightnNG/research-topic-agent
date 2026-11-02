"""General-purpose tools available to every AgentKernel task."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any, cast

from lit_agent_v2.contracts.tool import ToolContext, ToolSpec
from lit_agent_v2.tools.general.state import GeneralState

__all__ = ["GENERAL_TOOLSET", "build_general_tools"]

GENERAL_TOOLSET = (
    "context.inspect",
    "context.compact",
    "plan.create",
    "plan.update",
    "plan.read",
    "plan.complete_step",
    "memory.write",
    "memory.search",
    "artifact.put",
    "artifact.get",
    "fs.list",
    "fs.read",
    "fs.write",
    "test.run",
    "verify.code",
)


def _state(context: ToolContext) -> GeneralState:
    if context.state is None:
        raise RuntimeError("general tool requires ToolContext.state")
    return cast(GeneralState, context.state)


def _object(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
    }


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def build_general_tools() -> list[ToolSpec]:
    def inspect_context(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        del args
        return _state(context).inspect_context()

    def compact_context(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        return _state(context).compact_context(int(args.get("keep_recent", 6)))

    def plan_create(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        return _state(context).create_plan(str(args["goal"]), list(args["steps"]))

    def plan_update(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        return _state(context).update_plan(str(args["plan_id"]), list(args["steps"]))

    def plan_read(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        return _state(context).plans[str(args["plan_id"])]

    def plan_complete(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        return _state(context).complete_step(str(args["plan_id"]), str(args["step_id"]))

    def memory_write(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        return _state(context).write_memory(
            str(args["key"]), args.get("value"), str(args.get("scope", "run"))
        )

    def memory_search(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        return {
            "results": _state(context).search_memory(
                str(args["query"]), int(args.get("limit", 5))
            )
        }

    def artifact_put(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        path = _state(context).put_artifact(str(args["name"]), str(args["content"]))
        return {"path": path}

    def artifact_get(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        return {"content": _state(context).read_artifact(str(args["path"]))}

    def fs_list(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        root = _state(context).workspace
        target = _state(context).path(str(args.get("path", ".")))
        entries = [
            {
                "name": child.name,
                "path": str(child.relative_to(root)),
                "file": child.is_file(),
                "dir": child.is_dir(),
            }
            for child in sorted(target.iterdir())
        ]
        return {"path": str(target.relative_to(root)), "entries": entries}

    def fs_read(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        path = _state(context).path(str(args["path"]))
        limit = int(args.get("limit", 20000))
        text = path.read_text(encoding="utf-8", errors="replace")
        return {"path": str(path), "text": text[:limit], "truncated": len(text) > limit}

    def fs_write(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        path = _state(context).path(str(args["path"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        content = str(args.get("content", ""))
        path.write_text(content, encoding="utf-8")
        return {"path": str(path), "chars": len(content)}

    def test_run(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        target = str(args.get("target", "tests"))
        timeout = min(float(args.get("timeout_s", 120.0)), 300.0)
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", target],
                cwd=_state(context).workspace,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"returncode": -1, "passed": False, "stdout": "", "stderr": "timeout"}
        return {
            "returncode": completed.returncode,
            "passed": completed.returncode == 0,
            "stdout": completed.stdout[-12000:],
            "stderr": completed.stderr[-4000:],
        }

    def verify_code(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        path = _state(context).path(str(args["path"]))
        problems: list[str] = []
        if not path.exists():
            problems.append("missing file")
        elif path.suffix == ".json" and args.get("required_keys"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for key in args["required_keys"]:
                if key not in payload:
                    problems.append(f"missing key: {key}")
        return {"ok": not problems, "problems": problems, "path": str(path)}

    return [
        ToolSpec(
            "context.inspect",
            "Inspect the current conversation/context size.",
            _object({}),
            _object({"messages": {"type": "integer"}}),
            context_handler=inspect_context,
            namespace="context",
            parallel_safe=True,
        ),
        ToolSpec(
            "context.compact",
            "Compress old tool observations while keeping recent messages.",
            _object(
                {"keep_recent": {"type": "integer"}},
                [],
            ),
            _object({"before": {"type": "integer"}}),
            context_handler=compact_context,
            namespace="context",
            side_effect=True,
        ),
        ToolSpec(
            "plan.create",
            "Create a persistent plan for the current task.",
            _object(
                {
                    "goal": {"type": "string"},
                    "steps": {"type": "array", "items": {"type": "string"}},
                },
                ["goal", "steps"],
            ),
            _object({"plan_id": {"type": "string"}}),
            context_handler=plan_create,
            namespace="plan",
            side_effect=True,
        ),
        ToolSpec(
            "plan.update",
            "Replace the steps of an existing plan.",
            _object(
                {
                    "plan_id": {"type": "string"},
                    "steps": {"type": "array", "items": {"type": "string"}},
                },
                ["plan_id", "steps"],
            ),
            _object({"plan_id": {"type": "string"}}),
            context_handler=plan_update,
            namespace="plan",
            side_effect=True,
        ),
        ToolSpec(
            "plan.read",
            "Read a persistent plan.",
            _object({"plan_id": {"type": "string"}}, ["plan_id"]),
            _object({"plan_id": {"type": "string"}}),
            context_handler=plan_read,
            namespace="plan",
            parallel_safe=True,
        ),
        ToolSpec(
            "plan.complete_step",
            "Mark one plan step complete.",
            _object(
                {"plan_id": {"type": "string"}, "step_id": {"type": "string"}},
                ["plan_id", "step_id"],
            ),
            _object({"plan_id": {"type": "string"}}),
            context_handler=plan_complete,
            namespace="plan",
            side_effect=True,
        ),
        ToolSpec(
            "memory.write",
            "Write a run/node/topic memory entry.",
            _object(
                {
                    "key": {"type": "string"},
                    "value": {},
                    "scope": {"type": "string"},
                },
                ["key", "value"],
            ),
            _object({"key": {"type": "string"}}),
            context_handler=memory_write,
            namespace="memory",
            side_effect=True,
        ),
        ToolSpec(
            "memory.search",
            "Search memory entries by substring.",
            _object(
                {"query": {"type": "string"}, "limit": {"type": "integer"}},
                ["query"],
            ),
            _object({"results": {"type": "array"}}),
            context_handler=memory_search,
            namespace="memory",
            parallel_safe=True,
        ),
        ToolSpec(
            "artifact.put",
            "Write a text artifact and return its path.",
            _object(
                {"name": {"type": "string"}, "content": {"type": "string"}},
                ["name", "content"],
            ),
            _object({"path": {"type": "string"}}),
            context_handler=artifact_put,
            namespace="artifact",
            side_effect=True,
        ),
        ToolSpec(
            "artifact.get",
            "Read a text artifact.",
            _object({"path": {"type": "string"}}, ["path"]),
            _object({"content": {"type": "string"}}),
            context_handler=artifact_get,
            namespace="artifact",
            parallel_safe=True,
        ),
        ToolSpec(
            "fs.list",
            "List a workspace directory.",
            _object({"path": {"type": "string"}}, []),
            _object({"entries": {"type": "array"}}),
            context_handler=fs_list,
            namespace="fs",
            parallel_safe=True,
        ),
        ToolSpec(
            "fs.read",
            "Read a workspace text file.",
            _object({"path": {"type": "string"}, "limit": {"type": "integer"}}, ["path"]),
            _object({"text": {"type": "string"}}),
            context_handler=fs_read,
            namespace="fs",
            parallel_safe=True,
        ),
        ToolSpec(
            "fs.write",
            "Write a workspace text file.",
            _object(
                {"path": {"type": "string"}, "content": {"type": "string"}},
                ["path", "content"],
            ),
            _object({"path": {"type": "string"}}),
            context_handler=fs_write,
            namespace="fs",
            side_effect=True,
        ),
        ToolSpec(
            "test.run",
            "Run pytest in the workspace.",
            _object({"target": {"type": "string"}, "timeout_s": {"type": "number"}}, []),
            _object({"passed": {"type": "boolean"}}),
            context_handler=test_run,
            namespace="test",
            side_effect=True,
        ),
        ToolSpec(
            "verify.code",
            "Run a deterministic file/schema check.",
            _object(
                {
                    "path": {"type": "string"},
                    "required_keys": {"type": "array", "items": {"type": "string"}},
                },
                ["path"],
            ),
            _object({"ok": {"type": "boolean"}}),
            context_handler=verify_code,
            namespace="verify",
            parallel_safe=True,
        ),
    ]
