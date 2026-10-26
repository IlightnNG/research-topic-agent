"""3.0 / S3 验收：ToolSpec v2 四段流水线 + guard + 超时/截断/校验。"""

from __future__ import annotations

import time

from lit_agent.errors import E_BUDGET_COST, E_SCHEMA_STAGE_OUTPUT, E_SRC_TIMEOUT
from lit_agent.models.event import EventType
from lit_agent.tools.registry import ToolResult
from lit_agent.tools.spec import ToolRuntime, ToolSpec, default_runtime


def make_runtime(fn, **kwargs) -> ToolRuntime:
    runtime = ToolRuntime()
    runtime.register(
        ToolSpec(
            name="t",
            description="test",
            output_schema=kwargs.pop("output_schema", {"type": "object"}),
            **kwargs,
        ),
        fn,
    )
    return runtime


def test_pre_execute_can_deny() -> None:
    runtime = make_runtime(lambda **_: {"ok": True})
    runtime.add_pre(lambda spec, args: {"decision": "deny", "code": "E_FEATURE_DISABLED"})
    result = runtime.call("t")
    assert result.ok is False
    assert result.error_code == "E_FEATURE_DISABLED"
    assert result.meta["stage"] == "pre_execute"


def test_guard_denies_monotonically() -> None:
    runtime = make_runtime(lambda **_: {"ok": True})
    runtime.add_pre(lambda spec, args: None)  # 放行
    runtime.add_guard(lambda spec, args: "危险操作")
    result = runtime.call("t")
    assert result.ok is False
    assert result.meta["stage"] == "guard"
    assert "危险操作" in str(result.meta["reason"])


def test_post_execute_can_replace() -> None:
    runtime = make_runtime(lambda **_: {"v": 1})
    runtime.add_post(
        lambda spec, args, result: ToolResult(ok=True, output={"v": 2}, meta={**result.meta, "fixed": True})
    )
    result = runtime.call("t")
    assert result.output == {"v": 2}
    assert result.meta["fixed"] is True


def test_timeout_returns_structured_error() -> None:
    def slow(**_: object) -> dict[str, object]:
        time.sleep(0.05)
        return {"ok": True}

    runtime = make_runtime(slow, timeout_s=0.01)
    result = runtime.call("t")
    assert result.ok is False
    assert result.error_code == E_SRC_TIMEOUT


def test_schema_violation_is_rejected() -> None:
    runtime = make_runtime(
        lambda **_: {"a": 1},
        output_schema={"type": "object", "required": ["b"]},
    )
    result = runtime.call("t")
    assert result.ok is False
    assert result.error_code == E_SCHEMA_STAGE_OUTPUT


def test_long_output_is_truncated_with_marker() -> None:
    runtime = make_runtime(lambda **_: "x" * 100, output_schema={"type": "string"}, max_output_chars=10)
    result = runtime.call("t")
    assert result.ok is True
    assert str(result.output).endswith("…[truncated]")
    assert result.meta["truncated"] is True


def test_budget_exhausted_blocks_call() -> None:
    runtime = make_runtime(lambda **_: {"ok": True})
    result = runtime.call("t", budget_usd=0)
    assert result.ok is False
    assert result.error_code == E_BUDGET_COST


def test_event_emitted_with_tool_name() -> None:
    class FakeLog:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict]] = []

        def emit(self, event_type, **kwargs) -> None:  # type: ignore[no-untyped-def]
            self.events.append((event_type, kwargs))

    log = FakeLog()
    runtime = make_runtime(lambda **_: {"ok": True})
    runtime.call("t", log=log)
    assert log.events and log.events[0][0] == EventType.TOOL_CALL
    assert log.events[0][1]["payload"]["tool"] == "t"


def test_concurrency_defaults_to_exclusive() -> None:
    runtime = make_runtime(lambda **_: {"ok": True})
    assert runtime.spec("t").concurrency == "exclusive"


def test_default_runtime_tools() -> None:
    runtime = default_runtime()
    assert runtime.names() == ["compress_context", "rewrite_query", "verify_claim"]

    rewritten = runtime.call("rewrite_query", args={"query": "The use of tools for agents"})
    assert rewritten.ok is True
    assert "the" not in str(rewritten.output["query"]).split()

    verified = runtime.call(
        "verify_claim",
        args={"text": "tool use improves agent reliability", "snippet": "tool use improves agent reliability"},
    )
    assert verified.ok is True
    assert verified.output["supported"] is True

    compressed = runtime.call("compress_context", args={"texts": ["a " * 200, "b " * 200]})
    assert compressed.ok is True
    assert compressed.output["tokens_after"] <= compressed.output["tokens_before"]
