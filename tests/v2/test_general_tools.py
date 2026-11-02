"""S3: general tools and ToolRuntime integration."""

from __future__ import annotations

from pathlib import Path

from lit_agent_v2.contracts.tool import ToolContext
from lit_agent_v2.tools.general import GENERAL_TOOLSET, build_general_tools
from lit_agent_v2.tools.general.state import GeneralState
from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.tools.runtime import ToolRuntime


def _runtime(tmp_path: Path) -> tuple[ToolRuntime, GeneralState, ToolContext]:
    state = GeneralState(workspace=tmp_path)
    registry = ToolRegistry(build_general_tools())
    runtime = ToolRuntime(
        registry,
        toolsets={"general": GENERAL_TOOLSET},
        default_toolset="general",
    )
    return runtime, state, ToolContext(run_id="test", node_id="test", state=state)


def test_fs_plan_memory_artifact_tools(tmp_path: Path) -> None:
    runtime, state, context = _runtime(tmp_path)
    assert runtime.call(
        "fs.write",
        {"path": "notes.txt", "content": "hello"},
        context=context,
    ).ok
    assert runtime.call("fs.read", {"path": "notes.txt"}, context=context).output["text"] == "hello"
    assert runtime.call("fs.list", {"path": "."}, context=context).output["entries"]

    plan = runtime.call(
        "plan.create",
        {"goal": "inspect", "steps": ["read", "summarize"]},
        context=context,
    )
    assert plan.ok
    plan_id = plan.output["plan_id"]
    assert runtime.call(
        "plan.complete_step", {"plan_id": plan_id, "step_id": "s1"}, context=context
    ).ok
    assert state.plans[plan_id]["steps"][0]["status"] == "done"

    assert runtime.call(
        "memory.write",
        {"key": "finding", "value": {"text": "hello"}},
        context=context,
    ).ok
    assert runtime.call("memory.search", {"query": "hello"}, context=context).output["results"]

    artifact = runtime.call(
        "artifact.put",
        {"name": "summary.txt", "content": "summary"},
        context=context,
    )
    assert artifact.ok
    assert runtime.call(
        "artifact.get", {"path": artifact.output["path"]}, context=context
    ).output["content"] == "summary"


def test_context_compaction_and_verify(tmp_path: Path) -> None:
    runtime, state, context = _runtime(tmp_path)
    state.history.extend(
        [{"role": "tool", "call_id": f"c{i}", "content": "x" * 100} for i in range(12)]
    )
    compacted = runtime.call("context.compact", {"keep_recent": 2}, context=context)
    assert compacted.ok
    assert state.compaction_count == 1
    assert compacted.output["after"] < compacted.output["before"]

    assert runtime.call(
        "fs.write", {"path": "result.json", "content": '{"ok": true}'}, context=context
    ).ok
    checked = runtime.call(
        "verify.code",
        {"path": "result.json", "required_keys": ["ok"]},
        context=context,
    )
    assert checked.ok
    assert checked.output["ok"] is True
