"""S2/S3 验收：六类门禁 + 监督者优先级 + 两阶段提交（坏 claim 不落库）。"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from tests.wiring import fetch_events, prepare

from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.contracts.nodeio import GateResult
from lit_agent.graph import gates as gates_mod
from lit_agent.graph.supervisor import decide
from lit_agent.runtime.budget import RunBudget
from lit_agent.runtime.context import RunContext
from lit_agent.runtime.graph_runner import run_graph


def ctx(tmp_path: Path, *, budget: RunBudget | None = None) -> RunContext:
    settings = Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        logging=LoggingSettings(console=False),
    )
    return RunContext(
        settings=settings,
        run_id="g1",
        topic_id="ai-agents",
        budget=budget or RunBudget(),
    )


def claims_state(*, cited: list[bool], support: str = "supported") -> dict:
    claims = [
        {
            "text": f"claim {index}",
            "citations": [{"paper_id": "P1", "snippet": "x"}] if ok else [],
            "support": support,
        }
        for index, ok in enumerate(cited)
    ]
    import json

    return {"artifacts": {"claims_json": json.dumps(claims)}, "counters": {}}


# --------------------------------------------------------------------------- #
# 门禁单测：每条都测"触发 + 不触发"
# --------------------------------------------------------------------------- #
def test_schema_gate_flags_oversized_output(tmp_path: Path) -> None:
    big = {"artifacts": {"blob": "x" * 9000}, "counters": {}}
    assert gates_mod.gate_schema("analysis", big, {}, ctx(tmp_path)) is not None
    ok = {"artifacts": {"claims": 1}, "counters": {"claims": 1}}
    assert gates_mod.gate_schema("analysis", ok, {}, ctx(tmp_path)) is None


def test_evidence_gate_only_fires_when_retrieval_empty(tmp_path: Path) -> None:
    empty = {"counters": {"selected": 0}}
    assert gates_mod.gate_evidence_sufficiency("retrieval", empty, {}, ctx(tmp_path)) is not None
    full = {"counters": {"selected": 3}}
    assert gates_mod.gate_evidence_sufficiency("retrieval", full, {}, ctx(tmp_path)) is None
    # 没有 selected 键（阶段没跑）不得误报
    assert gates_mod.gate_evidence_sufficiency("retrieval", {"counters": {}}, {}, ctx(tmp_path)) is None


def test_citation_gate_finds_uncited_claims(tmp_path: Path) -> None:
    state = claims_state(cited=[True, False])
    result = gates_mod.gate_citation_integrity("report", {}, state, ctx(tmp_path))
    assert result is not None and result.details["bad_indexes"] == [1]

    good = claims_state(cited=[True, True])
    assert gates_mod.gate_citation_integrity("report", {}, good, ctx(tmp_path)) is None


def test_support_ratio_gate(tmp_path: Path) -> None:
    weak = claims_state(cited=[True, True], support="unsupported")
    result = gates_mod.gate_support_ratio("critique", {}, weak, ctx(tmp_path))
    assert result is not None and result.code == "E_GROUND_UNSUPPORTED_RATIO"
    strong = claims_state(cited=[True, True])
    assert gates_mod.gate_support_ratio("critique", {}, strong, ctx(tmp_path)) is None


def test_budget_gate(tmp_path: Path) -> None:
    budget = RunBudget(limit_usd=0.001)
    budget.add(cost_usd=0.01)
    assert gates_mod.gate_budget("analysis", {}, {}, ctx(tmp_path, budget=budget)) is not None
    assert gates_mod.gate_budget("analysis", {}, {}, ctx(tmp_path)) is None


def test_drift_gate(tmp_path: Path) -> None:
    blocked = gates_mod.gate_drift("analysis", {"counters": {"drift_block": 1}}, {}, ctx(tmp_path))
    assert blocked is not None and blocked.action == "abort"
    warned = gates_mod.gate_drift("analysis", {"counters": {"drift_warn": 1}}, {}, ctx(tmp_path))
    assert warned is not None and warned.action == "annotate"
    assert gates_mod.gate_drift("analysis", {"counters": {}}, {}, ctx(tmp_path)) is None


# --------------------------------------------------------------------------- #
# 监督者：取最重动作 + 传 drop 索引
# --------------------------------------------------------------------------- #
def test_supervisor_takes_heaviest_action(tmp_path: Path) -> None:
    gates = [
        GateResult(name="drift", ok=True, code="E_GUARD_DRIFT", action="annotate"),
        GateResult(name="support_ratio", ok=False, code="E_GROUND_UNSUPPORTED_RATIO", action="degrade"),
    ]
    decision = decide(stage="critique", gates=gates, guard=None, ctx=ctx(tmp_path), attempt=1)
    assert decision.action == "degrade"


def test_supervisor_budget_always_aborts(tmp_path: Path) -> None:
    budget = RunBudget(limit_usd=0.001)
    budget.add(cost_usd=0.01)
    decision = decide(
        stage="analysis", gates=[], guard=None, ctx=ctx(tmp_path, budget=budget), attempt=1
    )
    assert decision.action == "abort"
    assert decision.code == "E_BUDGET_EXCEEDED"


def test_supervisor_propagates_drop_indexes(tmp_path: Path) -> None:
    gate = GateResult(
        name="citation_integrity",
        ok=False,
        code="E_GROUND_UNRESOLVED_CITATION",
        action="repair",
        details={"bad_indexes": [1, 3]},
    )
    decision = decide(stage="report", gates=[gate], guard=None, ctx=ctx(tmp_path), attempt=1)
    assert decision.drop_claim_indexes == [1, 3]


# --------------------------------------------------------------------------- #
# 集成：坏 claim 不落库（两阶段提交 + drop）
# --------------------------------------------------------------------------- #
def test_bad_claim_is_not_persisted(tmp_path: Path) -> None:
    """坏 claim（无引用）必须被门禁挡住：要么报告不存在，要么落库的 claim 全部有引用。

    例外：完全无证据时报告会写入一条"降级占位 claim"（固定文案、support=unsupported），
    它不是证据结论，允许无引用。
    """
    import json

    from lit_agent.db.session import connect, make_engine
    from lit_agent.eval import faultinject

    settings = prepare(tmp_path)
    with faultinject.inject("bad_artifact"):
        result = run_graph(settings, "ai-agents", run_id="g-bad")

    assert result["state"] in {"succeeded", "aborted"}, result

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            row = conn.execute(
                text("SELECT claims_json FROM reports WHERE run_id='g-bad'")
            ).first()
    finally:
        engine.dispose()

    placeholder = "本轮未检索到可引用证据"
    if row is not None:
        claims = json.loads(row[0] or "[]")
        for claim in claims:
            if claim.get("text") == placeholder:
                continue
            assert claim.get("citations"), f"无引用的 claim 落库了：{claim}"

    events = fetch_events(settings, "g-bad")
    codes: set[str] = set()
    for event in events:
        if event["type"] != "guard_trigger":
            continue
        payload = event["payload"]
        codes.add(str(payload.get("code")))
        codes.update(str(item) for item in payload.get("codes") or [])
    # 坏 claim 同时会拉低 support_ratio；两种码都应出现在本次决策的 codes 里
    assert codes & {"E_GROUND_UNRESOLVED_CITATION", "E_GROUND_UNSUPPORTED_RATIO"}, codes


def test_healthy_run_has_no_gate_failures(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    result = run_graph(settings, "ai-agents", run_id="g-healthy")
    assert result["state"] == "succeeded"

    events = fetch_events(settings, "g-healthy")
    failures = [
        event
        for event in events
        if event["type"] == "phase_change"
        and event["payload"].get("phase") == "end"
        and event["payload"].get("gates")
    ]
    assert failures == [], f"健康 run 不应触发门禁：{failures}"
