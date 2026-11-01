"""Report workflow as a Node chain."""

from __future__ import annotations

from lit_agent_v2.contracts.features import FeatureProfile, ReportRequirements
from lit_agent_v2.contracts.node import NodeSpec, WorkflowDefinition
from lit_agent_v2.contracts.verdict import VerifierProfile

__all__ = ["build_report_workflow"]

SOURCE_GOAL = (
    "Collect at least 100 unique, relevant papers. Prefer full text, but "
    "abstract-only is acceptable. Deduplicate and report coverage honestly."
)
EVIDENCE_GOAL = (
    "Extract one to two research claims per paper. Every claim must have an "
    "exact verbatim quote. Reject author lists, references, and truncated text."
)
MAP_GOAL = (
    "Cluster the evidence into 5-8 research directions when classification is "
    "enabled. Names must not contain authors or venues."
)
REPORT_GOAL = (
    "Generate the report from the supplied evidence. First plan sections, then "
    "write each planned section, check it, and assemble. The plan must satisfy "
    "the supplied requirements."
)
FINALIZE_GOAL = "Persist the verified report and publish the final artifact."


def build_report_workflow(
    features: FeatureProfile | None = None,
    requirements: ReportRequirements | None = None,
) -> WorkflowDefinition:
    features = features or FeatureProfile()
    requirements = requirements or ReportRequirements()

    nodes: list[NodeSpec] = [
        NodeSpec(
            id="source.collect",
            goal=SOURCE_GOAL,
            tools=("source.search", "source.fetch_pdf", "source.fetch_html", "corpus.store", "corpus.stats", "corpus.dedupe"),
            inputs=("request",),
            output_schema="SourceArtifact",
            verifier=VerifierProfile(
                code=("schema", "papers", "dedupe"),
                audit="source_relevance",
            ),
        ),
        NodeSpec(
            id="evidence.extract",
            goal=EVIDENCE_GOAL,
            tools=("claims.extract", "quote.check", "claims.filter", "evidence.stats"),
            inputs=("source.collect",),
            output_schema="EvidenceArtifact",
            verifier=VerifierProfile(
                code=("schema", "quote", "claim"),
                audit="evidence_quality",
            ),
        ),
    ]
    if features.classification:
        nodes.append(
            NodeSpec(
                id="map.classify",
                goal=MAP_GOAL,
                tools=("map.cluster", "map.name", "map.validate"),
                inputs=("evidence.extract",),
                output_schema="MapArtifact",
                verifier=VerifierProfile(
                    code=("schema", "directions", "coverage"),
                    audit="direction_quality",
                ),
                optional=True,
            )
        )
    nodes.append(
        NodeSpec(
            id="report.generate",
            goal=REPORT_GOAL,
            tools=("report.plan", "report.write_section", "report.check_section", "report.assemble"),
            inputs=("evidence.extract", "requirements", "features"),
            output_schema="ReportDraft",
            verifier=VerifierProfile(
                code=("schema", "quote", "citation", "count", "word_limit"),
                audit="report_quality",
            ),
            max_steps=12,
            max_usd=0.50,
        )
    )
    if features.scorecard:
        nodes.append(
            NodeSpec(
                id="scorecard.build",
                goal="Score the verified report and record a ScoreCard.",
                tools=("eval.scorecard", "eval.judge"),
                inputs=("report.generate",),
                output_schema="ScoreCard",
                verifier=VerifierProfile(code=("schema",), audit="scorecard_quality"),
                optional=True,
            )
        )
    nodes.append(
        NodeSpec(
            id="finalize",
            goal=FINALIZE_GOAL,
            tools=("report.persist",),
            inputs=("report.generate",),
            output_schema="ReportDraft",
            verifier=VerifierProfile(code=("schema", "file_exists"), audit="final_report"),
        )
    )
    definition = WorkflowDefinition(
        name="report",
        version="2",
        nodes=tuple(nodes),
        features=features,
    )
    problems = definition.validate()
    if problems:
        raise ValueError("; ".join(problems))
    return definition
