"""S11：十节点契约测试（自动生成，C1–C6）。

这六条只约束**边界**：形状、门禁、副作用、幂等键、上限、schema 必含。
节点内部怎么推理不在此约束（否则 ReAct 写不出来）。
"""

from __future__ import annotations

import pytest

from lit_agent.contracts.nodeio import GateResult, NodeOutput, PendingWrite
from lit_agent.contracts.specs import ALLOWED_SIDE_EFFECTS, SPECS
from lit_agent.graph.gates import GATE_NAMES
from lit_agent.graph.nodes import PHASE2_STAGES
from lit_agent.graph.transitions import MAX_ATTEMPTS

NAMES = list(PHASE2_STAGES)


def test_specs_cover_all_ten_nodes() -> None:
    assert set(SPECS) == set(PHASE2_STAGES)
    assert len(SPECS) == 10


@pytest.mark.parametrize("name", NAMES)
def test_c1_schema_roundtrip(name: str) -> None:
    spec = SPECS[name]
    sample = NodeOutput(
        stage=name,
        artifacts={"refs": 1},
        counters={"n": 1},
        pending_writes=[PendingWrite(kind="report")] if name == "report" else [],
    )
    assert NodeOutput.model_validate(sample.model_dump()) == sample
    assert spec.version


@pytest.mark.parametrize("name", NAMES)
def test_c2_gates_are_known(name: str) -> None:
    spec = SPECS[name]
    assert spec.gates, f"{name} 必须声明门禁"
    assert set(spec.gates) <= set(GATE_NAMES), spec.gates


@pytest.mark.parametrize("name", NAMES)
def test_c3_side_effects_declared(name: str) -> None:
    spec = SPECS[name]
    assert set(spec.side_effects) <= ALLOWED_SIDE_EFFECTS
    # 写报告的节点必须声明 reports；只读节点不得声明副作用
    if name == "report":
        assert "reports" in spec.side_effects
    if name in {"intake", "scope", "retrieval", "parse", "normalize", "mapping", "analysis", "critique"}:
        assert spec.side_effects == (), f"{name} 不应直接写库"


@pytest.mark.parametrize("name", NAMES)
def test_c4_idempotency_template(name: str) -> None:
    spec = SPECS[name]
    assert "{run_id}" in spec.idempotency
    assert "{stage}" in spec.idempotency
    assert "{attempt}" in spec.idempotency


@pytest.mark.parametrize("name", NAMES)
def test_c5_attempt_limits(name: str) -> None:
    spec = SPECS[name]
    assert 1 <= spec.max_attempts <= 2
    if name in MAX_ATTEMPTS:
        assert spec.max_attempts == MAX_ATTEMPTS[name]


@pytest.mark.parametrize("name", NAMES)
def test_c6_schema_gate_always_declared(name: str) -> None:
    assert "schema" in SPECS[name].gates


def test_gate_result_schema_is_frozen() -> None:
    gate = GateResult(name="schema", ok=False, code="E_SCHEMA_STAGE_OUTPUT", action="retry")
    assert gate.model_dump()["action"] == "retry"
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        GateResult(name="schema", ok=False, action="not-an-action")  # type: ignore[arg-type]
