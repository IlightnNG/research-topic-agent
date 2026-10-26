"""3.4 / S17：permission=confirm 工具默认不执行，确认后才执行。"""

from __future__ import annotations

from typing import Any

from lit_agent.errors import E_PERMISSION_REQUIRED
from lit_agent.tools.spec import ToolRuntime, ToolSpec

CALLS: list[str] = []


def runtime() -> ToolRuntime:
    rt = ToolRuntime()
    rt.register(
        ToolSpec(name="write_file", description="写文件", permission="confirm", side_effect="write"),
        lambda **_: CALLS.append("write") or {"ok": True},
    )
    rt.register(ToolSpec(name="read_file", description="读文件"), lambda **_: {"ok": True})
    return rt


def test_confirm_tool_denied_without_approval() -> None:
    result = runtime().call("write_file", args={})
    assert result.ok is False
    assert result.error_code == E_PERMISSION_REQUIRED
    assert result.meta["stage"] == "permission"
    assert CALLS == []


def test_confirm_tool_runs_when_approved() -> None:
    result = runtime().call("write_file", args={}, approved=True)
    assert result.ok is True
    assert CALLS == ["write"]


def test_read_tool_is_not_gated() -> None:
    result = runtime().call("read_file", args={})
    assert result.ok is True


def test_permission_denial_emits_event() -> None:
    class FakeLog:
        def __init__(self) -> None:
            self.events: list[Any] = []

        def emit(self, event_type: Any, **kwargs: Any) -> None:
            self.events.append((event_type, kwargs))

    log = FakeLog()
    runtime().call("write_file", args={}, log=log)
    assert log.events
    _event_type, kwargs = log.events[0]
    assert kwargs["payload"]["code"] == E_PERMISSION_REQUIRED
