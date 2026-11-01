"""Phase 4.1.5: code + audit verification."""

from __future__ import annotations

import json

import pytest

from lit_agent_v2.contracts.features import FeatureProfile
from lit_agent_v2.contracts.node import NodeContext, NodeResult, NodeSpec, WorkflowDefinition
from lit_agent_v2.contracts.verdict import AuditResult, VerifierProfile
from lit_agent_v2.verify.audit import AuditVerifier
from lit_agent_v2.verify.code import CodeVerifier
from lit_agent_v2.verify.verdict import Verifier
from lit_agent_v2.workflow.node.runner import NodeFailed, WorkflowRunner


def _context(schema: dict | str = "") -> NodeContext:
    return NodeContext("r1", "n1", "goal", FeatureProfile(), {}, schema)


def _result(output: dict) -> NodeResult:
    return NodeResult(output)


def _node(code: tuple[str, ...], audit: str | None = "default", required: bool = True) -> NodeSpec:
    return NodeSpec(
        "n1",
        "goal",
        ("tool",),
        verifier=VerifierProfile(code=code, audit=audit, audit_required=required),
    )


def test_code_schema_and_papers() -> None:
    verifier = CodeVerifier()
    schema = {"type": "object", "required": ["papers"]}
    assert verifier.verify(_node(("schema",)), _context(schema), _result({"papers": []}))[0].passed

    papers = [{"paper_id": "P1"}, {"paper_id": "P1"}]
    checks = verifier.verify(_node(("papers",)), _context(), _result({"papers": papers}))
    assert checks[0].passed is False
    assert "duplicate" in checks[0].reason


def test_quote_and_citation_checks() -> None:
    verifier = CodeVerifier()
    output = {
        "text": "We find that tool use improves success.",
        "claims": [{"claim_id": "C1", "quote": "tool use improves success"}],
        "content_md": "Finding [C1].",
    }
    assert verifier.verify(_node(("quote",)), _context(), _result(output))[0].passed
    assert verifier.verify(_node(("citation",)), _context(), _result(output))[0].passed

    bad = {**output, "content_md": "Finding without a citation."}
    check = verifier.verify(_node(("citation",)), _context(), _result(bad))[0]
    assert check.passed is False


def test_counts_directions_and_unknown_check() -> None:
    verifier = CodeVerifier()
    output = {"claims": [1, 2], "claim_count": 3}
    assert verifier.verify(_node(("count",)), _context(), _result(output))[0].passed is False
    assert verifier.verify(_node(("directions",)), _context(), _result({"directions": [1, 2]}))[0].passed
    unknown = verifier.verify(_node(("nope",)), _context(), _result({}))[0]
    assert unknown.passed is False
    assert "unknown" in unknown.reason


class AuditLLM:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.messages: list[list[dict]] = []

    def chat_json(self, messages, **kwargs):  # noqa: ANN001
        self.messages.append(messages)
        return self.payload, None


def test_combined_rules() -> None:
    audit = AuditVerifier(AuditLLM({"verdict": "accept", "scores": {"grounding": 5}, "problems": []}))
    verifier = Verifier(audit=audit)
    output = {"text": "x", "claims": [{"claim_id": "C1", "quote": "x"}], "content_md": "[C1]"}
    assert verifier.verify(_node(("quote", "citation")), _context(), _result(output)).accept

    failing_code = Verifier(
        audit=AuditVerifier(AuditLLM({"verdict": "accept", "scores": {"grounding": 5}}))
    )
    bad_code = failing_code.verify(_node(("citation",)), _context(), _result({"content_md": "no cite"}))
    assert bad_code.accept is False
    assert bad_code.code[0].passed is False

    failing_audit = Verifier(
        audit=AuditVerifier(AuditLLM({"verdict": "repair", "scores": {"grounding": 2}}))
    )
    bad_audit = failing_audit.verify(_node(("quote",)), _context(), _result(output))
    assert bad_audit.accept is False
    assert bad_audit.code[0].passed is True


def test_audit_optional_and_missing() -> None:
    no_audit = Verifier()
    result = no_audit.verify(
        _node(("schema",), audit=None), _context(), _result({"ok": True})
    )
    assert result.accept is True

    missing = no_audit.verify(_node(("schema",)), _context(), _result({"ok": True}))
    assert missing.accept is False
    assert "audit_unavailable" in missing.reasons


def test_audit_does_not_receive_trace() -> None:
    llm = AuditLLM({"verdict": "accept", "scores": {"grounding": 5}})
    result = NodeResult({"ok": True}, trace=[{"secret": "producer reasoning"}])
    AuditVerifier(llm).audit(_node(("schema",), audit="default"), _context(), result)
    text = json.dumps(llm.messages)
    assert "producer reasoning" not in text


def test_audit_failure_is_repair() -> None:
    audit = AuditVerifier(AuditLLM({"verdict": "accept", "scores": {"grounding": 2}}))
    result = audit.audit(_node(("schema",)), _context(), _result({"ok": True}))
    assert result.accepted is False
    assert result.verdict == "accept"
    assert isinstance(result, AuditResult)


class Kernel:
    def __init__(self, output: dict) -> None:
        self.output = output

    def run(self, node, context):  # noqa: ANN001
        return NodeResult(self.output)


class Store:
    def __init__(self) -> None:
        self.committed: dict[str, dict] = {}

    def state(self, run_id: str, node_id: str) -> str | None:
        return None

    def load_output(self, run_id: str, node_id: str) -> dict | None:
        return None

    def commit(self, run_id: str, node_id: str, output: dict, verdict) -> None:  # noqa: ANN001
        self.committed[node_id] = output

    def degrade(self, run_id: str, node_id: str, reason: str) -> None:
        pass


def test_verifier_integrates_with_runner() -> None:
    node = _node(("schema",), audit="default")
    workflow = WorkflowDefinition("t", "1", (node,))
    audit = AuditVerifier(AuditLLM({"verdict": "accept", "scores": {"grounding": 5}}))
    store = Store()
    runner = WorkflowRunner(
        kernel=Kernel({"ok": True}),
        verifier=Verifier(audit=audit),
        store=store,
    )
    runner.run(workflow, run_id="r1")
    assert store.committed["n1"] == {"ok": True}

    bad = WorkflowRunner(
        kernel=Kernel({"ok": True}),
        verifier=Verifier(audit=AuditVerifier(AuditLLM({"verdict": "repair", "scores": {"grounding": 1}}))),
        store=Store(),
    )
    with pytest.raises(NodeFailed):
        bad.run(workflow, run_id="r1")
