"""S1 接线测试④：分析节点必须使用 RunContext 里的 gateway（S8 修复；xfail）。

用假 gateway 注入，断言 `agents.analyst.analyze` 收到了同一个对象。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lit_agent.agents import analyst as analyst_mod
from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.graph.nodes import Phase2Nodes
from lit_agent.runtime.budget import RunBudget
from lit_agent.runtime.context import RunContext


class FakeGateway:
    def chat_json(self, *args: Any, **kwargs: Any) -> tuple[dict, Any]:  # pragma: no cover
        return {"claims": []}, None


def test_analysis_passes_ctx_gateway(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    def fake_analyze(cards, *, gateway=None):  # noqa: ANN001
        captured["gateway"] = gateway
        return []

    monkeypatch.setattr(analyst_mod, "analyze", fake_analyze)

    settings = Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        logging=LoggingSettings(console=False),
    )
    gateway = FakeGateway()
    ctx = RunContext(
        settings=settings,
        run_id="llm-wire",
        topic_id="ai-agents",
        budget=RunBudget(),
        gateway=gateway,
    )
    node = Phase2Nodes(settings, ctx=ctx)
    node.analysis({"run_id": "llm-wire", "topic_id": "ai-agents", "artifacts": {"paper_ids": []}})

    assert captured.get("gateway") is gateway, "analysis 必须把 ctx.gateway 传给 analyze"
