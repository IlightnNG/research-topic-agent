"""S5/S6/S7 验收：agents、grounding/judge/gold、折叠与注入物化。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import text

from lit_agent.agents import analyst, critic, mapper, retrieval
from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.context import budget as ctx_budget
from lit_agent.context import folding, slots
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.eval import datasets, faultinject, grounding, judge
from lit_agent.models.claim import Claim
from lit_agent.models.evidence import Citation, EvidenceCard, Support
from lit_agent.models.paper import Paper
from lit_agent.models.topic import Topic
from lit_agent.runtime.events import SqliteEventLog
from lit_agent.runtime.graph_runner import run_graph


def cards() -> list[EvidenceCard]:
    return [
        EvidenceCard(paper_id="P1", title="Tool use agents", snippet="tool use improves task success", source="arxiv", year=2025),
        EvidenceCard(paper_id="P2", title="Diffusion proteins", snippet="diffusion sampling for proteins", source="arxiv", year=2025),
    ]


# --------------------------------------------------------------------------- #
# S5：retrieval / mapper
# --------------------------------------------------------------------------- #
def test_retrieval_filters_by_focus_hint() -> None:
    result = retrieval.select_cards(cards(), focus_hint="tool use")
    assert [card.paper_id for card in result.cards] == ["P1"]
    assert result.dropped == 1


def test_retrieval_without_hint_keeps_all() -> None:
    result = retrieval.select_cards(cards())
    assert len(result.cards) == 2


def test_retrieval_no_match_is_empty_not_fallback() -> None:
    result = retrieval.select_cards(cards(), focus_hint="quantum chromodynamics")
    assert result.cards == [], "不命中必须返回空（显式降级），不得回落到全量"


def test_mapper_builds_clusters_and_flags_orphans() -> None:
    result = mapper.map_clusters(["P1", "P2"], [("P1", "P1v2"), ("PX", "PY")])
    assert result.cluster_count == 1
    assert result.merged_count == 1
    assert result.orphan_merges == ["PX->PY"]


# --------------------------------------------------------------------------- #
# S6：analyst / critic / grounding / judge / gold
# --------------------------------------------------------------------------- #
def test_analyst_claims_all_cited() -> None:
    claims = analyst.analyze(cards())
    assert len(claims) == 2
    assert all(claim.citations for claim in claims)
    assert all(claim.support is Support.SUPPORTED for claim in claims)


def test_critic_blocks_missing_citation() -> None:
    verdict = critic.critique([Claim(text="no evidence", citations=[], support=Support.UNSUPPORTED)])
    assert verdict.ok is False
    assert verdict.code == "E_GROUND_UNRESOLVED_CITATION"


def test_critic_passes_grounded_claims() -> None:
    verdict = critic.critique(analyst.analyze(cards()))
    assert verdict.ok is True


def test_grounding_detects_unsupported_claim() -> None:
    supported = Claim(text="tool use improves task success", citations=[Citation(paper_id="P1", snippet="tool use improves task success")], support=Support.SUPPORTED)
    unsupported = Claim(text="protein folding guarantees planning", citations=[Citation(paper_id="P2", snippet="diffusion sampling for proteins")], support=Support.SUPPORTED)
    assert grounding.check_claim(supported).supported is True
    assert grounding.check_claim(unsupported).supported is False


def test_gold_has_twenty_items_and_threshold() -> None:
    gold = datasets.load_gold()
    assert len(gold) == 20
    hits = 0
    for item in gold:
        claim = Claim(text=item.claim, citations=[Citation(paper_id="gold", snippet=item.snippet)], support=Support.SUPPORTED)
        predicted = "supported" if grounding.check_claim(claim).supported else "unsupported"
        hits += int(predicted == item.label)
    accuracy = hits / len(gold)
    assert accuracy >= 0.9, f"gold accuracy={accuracy}"


def test_judge_falls_back_and_kappa_matches() -> None:
    gold = datasets.load_gold()
    result = judge.judge_gold(gold)
    assert result["kappa"] >= 0.8, result


def test_fault_injection_three_kinds() -> None:
    with faultinject.inject("empty_retrieval"):
        assert faultinject.is_active("empty_retrieval")
    assert not faultinject.is_active("empty_retrieval")

    from lit_agent.errors import E_SRC_TIMEOUT, LitError

    with pytest.raises(LitError) as excinfo, faultinject.inject("timeout"):
        pass
    assert excinfo.value.code == E_SRC_TIMEOUT

    with pytest.raises(ValueError), faultinject.inject("nope"):
        pass


# --------------------------------------------------------------------------- #
# S7：折叠与注入物化
# --------------------------------------------------------------------------- #
def test_summarize_reduces_tokens_and_keeps_numbers() -> None:
    filler = "This section restates the motivation at length without new information whatsoever. "
    texts = [
        f"We study agent systems. {filler}Results show 12 benchmarks improve. {filler}"
        for _index in range(6)
    ]
    baseline = sum(ctx_budget.count_tokens(text) for text in texts)
    folded = folding.folding_for("summarize").fold(texts, budget_tokens=200)
    assert folded.tokens < baseline * 0.6, (folded.tokens, baseline)
    assert "12" in folded.text, "含数字的句子必须保留"


def test_hierarchical_is_explicitly_unimplemented() -> None:
    from lit_agent.errors import LitError

    with pytest.raises(LitError):
        folding.folding_for("hierarchical")


def test_materialize_slots_writes_events(tmp_path: Path) -> None:
    settings = Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        logging=LoggingSettings(console=False),
    )
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            topic_repo.upsert(conn, Topic(id="ai-agents", name="AI", scope_statement="agents"))
        from lit_agent.runtime import jobs

        jobs.start(settings, "ai-agents", run_id="slot-run", engine=engine)
        log = SqliteEventLog(engine, "slot-run")
        registry = slots.SlotRegistry()
        registry.register(slots.CtxSlot(name="scope", content="llm agents", source="topic"))
        registry.register(slots.CtxSlot(name="evidence", content="", source="retrieval"))
        written = slots.materialize_slots(registry, log)
        twice = slots.materialize_slots(registry, log)
        jobs.finish(settings, "slot-run", state=__import__("lit_agent.models.run", fromlist=["RunState"]).RunState.ABORTED, engine=engine)
    finally:
        engine.dispose()

    assert written == 1, "空槽不写事件"
    assert twice == 0, "同 slot 同内容幂等"


# --------------------------------------------------------------------------- #
# 端到端：图用上 agents（不是"写完不接线"）
# --------------------------------------------------------------------------- #
def test_graph_uses_agents_and_persists_claims(tmp_path: Path) -> None:
    settings = Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        logging=LoggingSettings(console=False),
    )
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            topic_repo.upsert(conn, Topic(id="ai-agents", name="AI", scope_statement="agents"))
            paper_repo.upsert_many(
                conn,
                [Paper(paper_id="P1", title="Tool use", abstract="agents use tools", source="arxiv", year=2025)],
            )
    finally:
        engine.dispose()

    result = run_graph(settings, "ai-agents", run_id="e2e-agents")
    assert result["state"] == "succeeded", result

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            claims = json.loads(
                conn.execute(text("SELECT claims_json FROM reports WHERE run_id='e2e-agents'")).scalar_one()
            )
    finally:
        engine.dispose()
    assert claims and all(claim["citations"] for claim in claims), claims
