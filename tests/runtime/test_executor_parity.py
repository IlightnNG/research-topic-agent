"""3.6 / S25：GraphExecutor vs GoalRunner 等价（同一 ShellSpec）。"""

from __future__ import annotations

from pathlib import Path

from tests.wiring import fetch_events, prepare

from lit_agent.config import Settings
from lit_agent.contracts.shell import default_shell
from lit_agent.eval.faultinject import inject
from lit_agent.graph.nodes import PHASE2_STAGES
from lit_agent.runtime.graph_runner import run_graph


def run(settings: Settings, *, mode: str, run_id: str, shell=None, fault: str | None = None) -> tuple[dict, list[dict]]:
    with inject(fault) if fault else _null():
        out = run_graph(
            settings,
            "ai-agents",
            run_id=run_id,
            focus_hint="tool use",
            executor=mode,
            shell=shell,
        )
    return out, fetch_events(settings, run_id)


class _null:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> None:
        return None


def compare(tmp_path: Path, *, fault: str | None = None) -> None:
    graph = prepare(tmp_path / "graph", papers=3)
    goal = prepare(tmp_path / "goal", papers=3)

    out_graph, events_graph = run(graph, mode="graph", run_id="cmp", fault=fault)
    out_goal, events_goal = run(goal, mode="goal_runner", run_id="cmp", fault=fault)

    starts = lambda events: [  # noqa: E731
        event["stage"]
        for event in events
        if event["type"] == "phase_change"
        and event["stage"] in PHASE2_STAGES
        and event["payload"].get("phase") == "start"
    ]
    assert starts(events_graph) == starts(events_goal)
    assert list(dict.fromkeys(starts(events_graph))) == list(PHASE2_STAGES)
    assert out_graph["state"] == out_goal["state"]
    assert out_graph["stages"].get("claims") == out_goal["stages"].get("claims")
    assert out_graph["stages"].get("strategy") == out_goal["stages"].get("strategy")
    assert out_graph["stages"].get("grounding_rate") == out_goal["stages"].get("grounding_rate")


def test_parity_healthy(tmp_path: Path) -> None:
    compare(tmp_path)


def test_parity_bad_artifact(tmp_path: Path) -> None:
    compare(tmp_path, fault="bad_artifact")


def test_parity_empty_retrieval(tmp_path: Path) -> None:
    compare(tmp_path, fault="empty_retrieval")


def test_goal_runner_respects_shell_subset(tmp_path: Path) -> None:
    from lit_agent.contracts.goals import GOALS
    from lit_agent.contracts.shell import ShellSpec

    reduced = ShellSpec(
        name="reduced",
        goals=tuple(GOALS[name] for name in ("retrieval", "analysis", "critique", "report", "evaluate")),
    )
    settings = prepare(tmp_path, papers=3)
    out, events = run(settings, mode="goal_runner", run_id="red", shell=reduced)

    stages = [
        event["stage"]
        for event in events
        if event["type"] == "phase_change" and event["payload"].get("phase") == "start"
    ]
    assert "parse" not in stages
    assert out["state"] == "succeeded"
    assert out["stages"].get("claims", 0) >= 1


def test_default_shell_is_ten_goals() -> None:
    assert len(default_shell().goals) == 10
