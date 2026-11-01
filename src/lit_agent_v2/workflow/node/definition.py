"""Report workflow as a Node chain."""

from __future__ import annotations

from lit_agent_v2.contracts.features import FeatureProfile, ReportRequirements
from lit_agent_v2.contracts.node import NodeSpec, WorkflowDefinition
from lit_agent_v2.contracts.verdict import VerifierProfile

__all__ = [
    "build_demo100_workflow",
    "build_report_demo_workflow",
    "build_report_workflow",
]

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
REPORT_DEMO_GOAL = """You are report.generate for a local corpus.
1. Call corpus.papers with the request root.
2. Call claims.extract once per paper using its abstract.
3. Call report.plan with the papers.
4. For each planned section, call report.write_section with that section and the claims.
5. Call report.assemble with the written sections.
6. Call report.persist with the assembled title/content and claims.
7. Return final with the persisted path and the assembled report.
Use only extracted claims. Every factual sentence needs [C#]. Do not invent papers or claims.
If a claim is missing, say so instead of filling the gap."""
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
            max_tokens=12000,
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


def build_report_demo_workflow(
    features: FeatureProfile | None = None,
    requirements: ReportRequirements | None = None,
) -> WorkflowDefinition:
    """One-node local-corpus report workflow used for S6 acceptance."""
    features = features or FeatureProfile()
    requirements = requirements or ReportRequirements()
    node = NodeSpec(
        id="report.generate",
        goal=REPORT_DEMO_GOAL,
        tools=(
            "corpus.papers",
            "claims.extract",
            "report.plan",
            "report.write_section",
            "report.check_section",
            "report.assemble",
            "report.persist",
        ),
        inputs=("request",),
        output_schema={
            "type": "object",
            "required": ["title", "content_md", "claims", "path"],
        },
        verifier=VerifierProfile(
            code=("schema", "claim", "citation", "word_limit", "file_exists"),
            audit=None,
        ),
        max_steps=24,
        max_usd=0.80,
        max_tokens=12000,
    )
    definition = WorkflowDefinition(
        name="report-demo",
        version="2",
        nodes=(node,),
        features=features,
    )
    problems = definition.validate()
    if problems:
        raise ValueError("; ".join(problems))
    return definition


def build_demo100_workflow(
    features: FeatureProfile | None = None,
) -> WorkflowDefinition:
    """Full 4-Node chain for the 100-paper local-corpus demo."""
    features = features or FeatureProfile()
    nodes = (
        NodeSpec(
            id="source.collect",
            goal=(
                "Call demo.source exactly once with root from request and out_dir from request. "
                "Then return final JSON with source_path, papers, fulltext, fulltext_ratio, state. "
                "Do not call any other tool."
            ),
            tools=("demo.source",),
            inputs=("request",),
            output_schema={
                "type": "object",
                "required": ["source_path", "papers", "fulltext_ratio", "state"],
            },
            verifier=VerifierProfile(code=("schema",), audit=None),
            max_steps=4,
        ),
        NodeSpec(
            id="evidence.extract",
            goal=(
                "Use source_path from the source.collect input. Call demo.evidence exactly once "
                "with source_path and out_dir from request. Return final JSON with evidence_path, "
                "papers, claims. Do not call any other tool."
            ),
            tools=("demo.evidence",),
            inputs=("source.collect", "request"),
            output_schema={"type": "object", "required": ["evidence_path", "papers", "claims"]},
            verifier=VerifierProfile(code=("schema",), audit=None),
            max_steps=4,
        ),
        NodeSpec(
            id="report.generate",
            goal=(
                "Use source_path and evidence_path from input. Call demo.report exactly once with "
                "source_path, evidence_path, out_dir from request, and language from request. "
                "Return final JSON with report_path, papers, claims, sections, word_count, state."
            ),
            tools=("demo.report",),
            inputs=("source.collect", "evidence.extract", "request"),
            output_schema={
                "type": "object",
                "required": ["report_path", "papers", "claims", "sections"],
            },
            verifier=VerifierProfile(code=("schema",), audit=None),
            max_steps=4,
        ),
        NodeSpec(
            id="finalize",
            goal=(
                "Use report_path from report.generate. Call demo.finalize exactly once with "
                "report_path and out_dir from request. Return final JSON with report_path, "
                "content_sha, papers, claims, state."
            ),
            tools=("demo.finalize",),
            inputs=("report.generate", "request"),
            output_schema={
                "type": "object",
                "required": ["report_path", "content_sha", "papers", "claims"],
            },
            verifier=VerifierProfile(code=("schema",), audit=None),
            max_steps=4,
        ),
    )
    definition = WorkflowDefinition("demo100", "2", nodes, features)
    problems = definition.validate()
    if problems:
        raise ValueError("; ".join(problems))
    return definition
