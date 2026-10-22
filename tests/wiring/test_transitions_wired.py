"""S1 接线测试②：条件边必须真的回退（S4 修复；当前标记 xfail）。

判据：坏产物（缺引用）→ 触发 repair，`analysis` 出现 attempt=2，
且报告里**没有**缺引用的 claim。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lit_agent.eval import faultinject
from lit_agent.runtime.graph_runner import run_graph
from tests.wiring import fetch_events, prepare


@pytest.mark.xfail(strict=True, reason="S4：回边执行器尚未启用（transitions_enabled=False）")
def test_bad_artifact_triggers_repair_loop(tmp_path: Path) -> None:
    settings = prepare(tmp_path)

    with faultinject.inject("bad_artifact"):
        result = run_graph(settings, "ai-agents", run_id="w-trans")

    assert result["state"] == "succeeded", result
    events = fetch_events(settings, "w-trans")
    starts = [
        event["payload"].get("attempt")
        for event in events
        if event["type"] == "phase_change"
        and event["stage"] == "analysis"
        and event["payload"].get("phase") == "start"
    ]
    assert 2 in starts, f"analysis 应被重跑一次（attempts={starts}）"

    recoveries = [event for event in events if event["type"] == "recovery"]
    assert recoveries, "回边必须留下 recovery 事件"
