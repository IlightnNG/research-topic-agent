"""Report workflow v2: five specialized Nodes over the generic AgentKernel."""

from __future__ import annotations

from lit_agent_v2.contracts.features import FeatureProfile, ReportRequirements
from lit_agent_v2.contracts.node import NodeSpec, WorkflowDefinition
from lit_agent_v2.contracts.verdict import VerifierProfile

__all__ = [
    "REPORT_V2_NODES",
    "build_report_v2_workflow",
    "report_v2_toolsets",
]

REPORT_V2_NODES = (
    "source.collect",
    "evidence.extract",
    "report.plan",
    "report.write",
    "report.audit_finalize",
)


def report_v2_toolsets() -> dict[str, tuple[str, ...]]:
    return {
        "source.collect": (
            "source.collect",
            "corpus.stats",
            "context.inspect",
            "plan.update",
        ),
        "evidence.extract": (
            "evidence.extract",
            "corpus.papers",
            "claims.extract",
            "quote.check",
            "context.compact",
        ),
        "report.plan": (
            "report.plan_v2",
            "context.inspect",
            "plan.update",
            "artifact.put",
        ),
        "report.write": (
            "report.write_v2",
            "report.write_section_v2",
            "report.check_section_v2",
            "report.assemble_v2",
            "context.compact",
            "artifact.put",
        ),
        "report.audit_finalize": (
            "report.finalize_v2",
            "report.assemble",
            "report.persist",
            "verify.code",
            "context.inspect",
        ),
    }


def build_report_v2_workflow(
    features: FeatureProfile | None = None,
    requirements: ReportRequirements | None = None,
) -> WorkflowDefinition:
    features = features or FeatureProfile()
    requirements = requirements or ReportRequirements()
    nodes = (
        NodeSpec(
            id="source.collect",
            goal=(
                "Call source.collect with root and out_dir from request. "
                "Then call context.inspect. Return final JSON with source_path, papers, "
                "fulltext, fulltext_ratio, state."
            ),
            tools=report_v2_toolsets()["source.collect"],
            toolset="source.collect",
            inputs=("request",),
            output_schema={
                "type": "object",
                "required": ["source_path", "papers", "fulltext_ratio", "state"],
            },
            verifier=VerifierProfile(code=("schema",), audit=None),
            max_steps=6,
            max_usd=0.20,
            max_tokens=4000,
        ),
        NodeSpec(
            id="evidence.extract",
            goal=(
                "Use source_path from source.collect and out_dir from request. "
                "Call evidence.extract. Then quote.check a sample and context.compact if needed. "
                "Return final JSON with evidence_path, papers, claims."
            ),
            tools=report_v2_toolsets()["evidence.extract"],
            toolset="evidence.extract",
            inputs=("source.collect", "request"),
            output_schema={
                "type": "object",
                "required": ["evidence_path", "papers", "claims"],
            },
            verifier=VerifierProfile(code=("schema",), audit=None),
            max_steps=8,
            max_usd=0.30,
            max_tokens=6000,
        ),
        NodeSpec(
            id="report.plan",
            goal=(
                "Use evidence_path from evidence.extract and out_dir from request. "
                "Call report.plan_v2. Then context.inspect. Return final JSON with plan_path, "
                "sections, coverage."
            ),
            tools=report_v2_toolsets()["report.plan"],
            toolset="report.plan",
            inputs=("evidence.extract", "request"),
            output_schema={
                "type": "object",
                "required": ["plan_path", "sections"],
            },
            verifier=VerifierProfile(code=("schema",), audit=None),
            max_steps=6,
            max_usd=0.20,
            max_tokens=4000,
        ),
        NodeSpec(
            id="report.write",
            goal=(
                "Use plan_path from report.plan, evidence_path from evidence.extract and "
                "language/out_dir from request. Call report.write_v2. Then report.check_section "
                "on one section and context.compact if needed. Return final JSON with draft_path, "
                "sections, word_count, citation_coverage."
            ),
            tools=report_v2_toolsets()["report.write"],
            toolset="report.write",
            inputs=("report.plan", "evidence.extract", "request"),
            output_schema={
                "type": "object",
                "required": ["draft_path", "sections", "word_count", "citation_coverage"],
            },
            verifier=VerifierProfile(code=("schema",), audit=None),
            max_steps=12,
            max_usd=1.20,
            max_tokens=16000,
        ),
        NodeSpec(
            id="report.audit_finalize",
            goal=(
                "Use draft_path from report.write, evidence_path from evidence.extract and "
                "out_dir from request. Call report.finalize_v2. Then verify.code on report_path. "
                "Return final JSON with report_path, path, content_sha, papers, claims, sections, "
                "word_count, state, citation_coverage."
            ),
            tools=report_v2_toolsets()["report.audit_finalize"],
            toolset="report.audit_finalize",
            inputs=("report.write", "evidence.extract", "request"),
            output_schema={
                "type": "object",
                "required": [
                    "report_path",
                    "content_sha",
                    "papers",
                    "claims",
                    "sections",
                    "citation_coverage",
                ],
            },
            verifier=VerifierProfile(code=("schema",), audit=None),
            max_steps=8,
            max_usd=0.30,
            max_tokens=6000,
        ),
    )
    definition = WorkflowDefinition(
        name="report-v2",
        version="2",
        nodes=nodes,
        features=features,
    )
    problems = definition.validate()
    if problems:
        raise ValueError("; ".join(problems))
    return definition
