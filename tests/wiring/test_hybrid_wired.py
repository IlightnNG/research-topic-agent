"""S1 接线测试⑤：检索节点必须用 hybrid（S7 修复；xfail）。

把 `hybrid_search` 换成哨兵实现，断言节点返回的 paper_ids 来自它。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lit_agent.agents import hybrid as hybrid_mod
from lit_agent.agents import retrieval as retrieval_mod
from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.graph.nodes import Phase2Nodes
from lit_agent.models.evidence import EvidenceCard


@pytest.mark.xfail(strict=True, reason="S7：retrieval 仍用 select_cards，未接 hybrid")
def test_retrieval_uses_hybrid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sentinel = [EvidenceCard(paper_id="HYBRID", title="t", snippet="s", source="arxiv")]

    def fake_hybrid(cards, query, *, k=10, alpha=0.6):  # noqa: ANN001
        return type("R", (), {"cards": sentinel, "paper_ids": ["HYBRID"]})()

    monkeypatch.setattr(hybrid_mod, "hybrid_search", fake_hybrid)

    settings = Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        logging=LoggingSettings(console=False),
    )
    node = Phase2Nodes(settings)

    def fake_cards(self, paper_ids=None):  # noqa: ANN001
        return [EvidenceCard(paper_id="A", title="a", snippet="a", source="arxiv")]

    monkeypatch.setattr(Phase2Nodes, "_cards", fake_cards, raising=False)
    monkeypatch.setattr(
        retrieval_mod, "select_cards", lambda *a, **k: pytest.fail("不应再调用 select_cards")
    )

    patch: dict[str, Any] = node.retrieval({"run_id": "r", "topic_id": "t", "artifacts": {}})
    assert patch["artifacts"]["paper_ids"] == ["HYBRID"]
