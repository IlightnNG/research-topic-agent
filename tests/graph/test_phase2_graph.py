"""Phase 2 图：十节点（S2）+ 条件边（S3）+ 续跑幂等（S4）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import text

from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.graph.edges import EDGES, MAINLINE, RULES, backoff_edge, evaluate_edges, route_after
from lit_agent.graph.nodes import PHASE2_STAGES
from lit_agent.graph.pipeline import build_phase2_graph
from lit_agent.models.paper import Paper
from lit_agent.models.topic import Topic
from lit_agent.runtime.graph_runner import SimulatedCrash, run_graph


def prepare(tmp_path: Path, *, papers: int = 2) -> Settings:
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
                [
                    Paper(
                        paper_id=f"arxiv:{index}",
                        title=f"Paper {index}",
                        abstract="agents use tools",
                        source="arxiv",
                        year=2025,
                    )
                    for index in range(papers)
                ],
            )
    finally:
        engine.dispose()
    return settings


def event_rows(settings: Settings, run_id: str) -> list[dict]:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            rows = conn.execute(
                text("SELECT seq, type, stage, payload_json FROM run_events WHERE run_id = :r ORDER BY seq"),
                {"r": run_id},
            ).all()
    finally:
        engine.dispose()
    return [
        {"seq": row[0], "type": row[1], "stage": row[2], "payload": json.loads(row[3] or "{}")}
        for row in rows
    ]


# --------------------------------------------------------------------------- #
# S2：十节点
# --------------------------------------------------------------------------- #
def test_phase2_declares_ten_stages() -> None:
    assert len(PHASE2_STAGES) == 10
    assert PHASE2_STAGES == MAINLINE


def test_graph_compiles_with_ten_nodes(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    graph = build_phase2_graph(settings)
    nodes = set(graph.get_graph().nodes)
    assert set(PHASE2_STAGES).issubset(nodes), nodes


def test_full_run_covers_ten_stage_starts(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=3)
    result = run_graph(settings, "ai-agents", run_id="s2-run")

    assert result["state"] == "succeeded", result
    events = event_rows(settings, "s2-run")
    starts = [e["stage"] for e in events if e["type"] == "phase_change" and e["payload"].get("phase") == "start"]
    assert starts[0] == "run"
    assert starts[1:] == list(PHASE2_STAGES), starts

    ends = [e["stage"] for e in events if e["type"] == "phase_change" and e["payload"].get("phase") == "end"]
    assert ends == list(PHASE2_STAGES)


def test_report_node_persists_report(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    run_graph(settings, "ai-agents", run_id="s2-report")
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM reports WHERE run_id='s2-report'")).scalar_one()
    finally:
        engine.dispose()
    assert int(count) == 1


# --------------------------------------------------------------------------- #
# S3：E1–E13 条件边
# --------------------------------------------------------------------------- #
def test_every_edge_has_a_rule() -> None:
    assert {rule.edge for rule in RULES} == set(EDGES)


@pytest.mark.parametrize("rule", RULES, ids=[rule.edge for rule in RULES])
def test_edge_fires_on_its_counter(rule) -> None:
    state = {"counters": {}}
    _bump(state, rule)
    fired = evaluate_edges(state, "retrieval" if rule.stage == "*" else rule.stage)
    assert rule in fired, f"{rule.edge} 未触发"
    action = route_after("retrieval" if rule.stage == "*" else rule.stage, state)
    assert action in {
        "abort",
        "replan",
        "retry",
        "degrade",
        "skip",
        "annotate",
        "expand",
        "rewrite",
        "warn",
    }


@pytest.mark.parametrize("rule", RULES, ids=[rule.edge for rule in RULES])
def test_edge_does_not_fire_by_default(rule) -> None:
    fired = evaluate_edges({"counters": {}}, "retrieval" if rule.stage == "*" else rule.stage)
    assert rule not in fired, f"{rule.edge} 不应在空状态触发"


def _counter_name(rule) -> str:
    # 从谓词闭包外无法直接读名字，这里按边号映射（与 RULES 定义一一对应）
    return {
        "E1": "drift_warn",
        "E2": "drift_block",
        "E3": "retrieval_errors",
        "E4": "new_papers",
        "E5": "parse_failed",
        "E6": "schema_errors",
        "E7": "cards",
        "E8": "no_progress",
        "E9": "unresolved_citations",
        "E10": "eval_below",
        "E11": "loop",
        "E12": "budget_stop",
        "E13": "retries_exhausted",
    }[rule.edge]


def _bump(state: dict, rule) -> None:
    name = _counter_name(rule)
    if name == "no_progress":
        state["counters"][name] = 2
    elif name in {"new_papers", "cards"}:
        state["counters"][name] = 0  # 零值型边：键必须存在且为 0
    else:
        state["counters"][name] = 1


def test_backoff_edge_returns_action() -> None:
    assert backoff_edge("E11") == "replan"
    with pytest.raises(ValueError):
        backoff_edge("E99")


def test_route_after_falls_through_mainline() -> None:
    assert route_after("intake", {"counters": {}}) == "scope"
    assert route_after("evaluate", {"counters": {}}) == "end"


def test_budget_edge_wins_priority() -> None:
    state = {"counters": {"drift_warn": 1, "budget_stop": 1}}
    assert route_after("scope", state) == "abort"


# --------------------------------------------------------------------------- #
# S4：续跑幂等
# --------------------------------------------------------------------------- #
def test_resume_does_not_duplicate_stage_events(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    checkpoint = str(tmp_path / "ckpt.sqlite")

    with pytest.raises(SimulatedCrash):
        run_graph(
            settings,
            "ai-agents",
            run_id="s4-run",
            checkpoint_path=checkpoint,
            crash_after_stage="analysis",
        )

    before = event_rows(settings, "s4-run")
    starts_before = [e["stage"] for e in before if e["type"] == "phase_change" and e["payload"].get("phase") == "start"]
    assert starts_before[:4] == ["run", *PHASE2_STAGES[:3]], starts_before

    result = run_graph(
        settings,
        "ai-agents",
        run_id="s4-run",
        checkpoint_path=checkpoint,
        resume=True,
    )
    assert result["state"] == "succeeded", result

    after = event_rows(settings, "s4-run")
    starts = [e["stage"] for e in after if e["type"] == "phase_change" and e["payload"].get("phase") == "start"]
    stage_starts = [stage for stage in starts if stage != "run"]
    # 十个阶段各自**只**出现一次 start（run 级别的 start 允许一次 fresh + 一次 resume）
    assert len(stage_starts) == len(set(stage_starts)), stage_starts
    assert set(PHASE2_STAGES) == set(stage_starts), stage_starts
    assert any(event["payload"].get("resume") for event in after), "应记录 resume 标记"
