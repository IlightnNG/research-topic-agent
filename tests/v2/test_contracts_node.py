"""Node Platform contract tests: Node/Tool/Verifier/Plan."""

from __future__ import annotations

from lit_agent_v2.contracts.artifacts import ArtifactEnvelope, PlanSection, ReportPlan
from lit_agent_v2.contracts.features import FeatureProfile, ReportRequirements
from lit_agent_v2.contracts.node import NodeSpec, WorkflowDefinition
from lit_agent_v2.contracts.tool import ToolSpec
from lit_agent_v2.contracts.verdict import (
    AuditResult,
    CodeCheck,
    make_verdict,
)


def test_features_report_sections() -> None:
    features = FeatureProfile(classification=False, synthesis=True)
    assert features.enabled_sections() == ("overview", "paper_analysis", "synthesis", "paper_index")


def test_node_and_workflow_validation() -> None:
    source = NodeSpec(
        id="source.collect",
        goal="collect papers",
        tools=("source.search",),
    )
    evidence = NodeSpec(
        id="evidence.extract",
        goal="extract claims",
        tools=("claims.extract",),
        inputs=("source.collect",),
    )
    workflow = WorkflowDefinition("demo", "1", (source, evidence))
    assert workflow.validate() == []

    bad = NodeSpec(id="bad", goal="", tools=())
    assert bad.validate()


def test_workflow_missing_input() -> None:
    node = NodeSpec(id="report", goal="write", tools=("report.plan",), inputs=("evidence",))
    workflow = WorkflowDefinition("demo", "1", (node,))
    assert "report: missing input evidence" in workflow.validate()


def test_verifier_verdict_rules() -> None:
    code_ok = [CodeCheck("quote", True)]
    code_bad = [CodeCheck("quote", False, "quote not found")]
    audit_ok = AuditResult(accepted=True, verdict="accept")
    audit_bad = AuditResult(accepted=False, verdict="repair", problems=["weak"])

    assert make_verdict(code_ok, audit_ok).accept
    assert not make_verdict(code_bad, audit_ok).accept
    assert not make_verdict(code_ok, audit_bad).accept
    assert not make_verdict(code_bad, audit_bad).accept


def test_tool_spec_shape() -> None:
    tool = ToolSpec(
        name="source.search",
        description="search",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        side_effect=False,
        handler=lambda args: {"ok": True},
    )
    assert tool.idempotent
    assert tool.handler({"q": "x"}) == {"ok": True}


def test_report_plan_required_sections() -> None:
    requirements = ReportRequirements(required_sections=("overview", "paper_index"))
    valid = ReportPlan(
        "Report",
        [
            PlanSection("overview", "overview", "At a Glance"),
            PlanSection("index", "paper_index", "Paper Index"),
        ],
    )
    assert valid.validate(requirements) == []

    missing = ReportPlan("Report", [PlanSection("overview", "overview")])
    assert "missing required section: paper_index" in missing.validate(requirements)

    unknown = ReportPlan("Report", [PlanSection("x", "unknown")])
    assert any("unknown section kind" in problem for problem in unknown.validate(requirements))


def test_artifact_envelope_sha() -> None:
    first = ArtifactEnvelope("SourceArtifact", "r1", "source.collect", {"papers": 1})
    second = ArtifactEnvelope("SourceArtifact", "r1", "source.collect", {"papers": 1})
    assert first.sha256 == second.sha256
    assert first.to_dict()["schema_version"] == 1
