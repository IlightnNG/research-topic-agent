"""S1 接线测试⑥：生产只能有一条流水线（S9 修复；xfail）。"""

from __future__ import annotations

import inspect

import pytest

from lit_agent.runtime import scheduler


@pytest.mark.xfail(strict=True, reason="S9：scheduler 仍调用旧四阶段 run_topic")
def test_scheduler_uses_graph_runner() -> None:
    source = inspect.getsource(scheduler)
    assert "run_graph" in source, "定时任务必须调用十节点 run_graph"
    assert "run_topic" not in source, "生产不得再调用旧四阶段 run_topic"
