"""Full v2 report workflow, expressed against ports only."""

from __future__ import annotations

from dataclasses import dataclass

from lit_agent_v2.contracts import NodeSpec, RunRequest, WorkflowDefinition
from lit_agent_v2.contracts.ports import (
    EventPort,
    EvidencePort,
    MapPort,
    MetricPort,
    ReportRunPort,
    ReportStorePort,
    SourcePort,
    WriterPort,
)
from lit_agent_v2.contracts.report import EvidenceArtifact, SourceArtifact
from lit_agent_v2.domains.report.audit import audit_report
from lit_agent_v2.domains.report.map import MapArtifact
from lit_agent_v2.domains.report.write import ReportDraft

__all__ = ["ReportOutcome", "ReportWorkflow"]


@dataclass
class ReportOutcome:
    run_id: str
    report_id: str
    draft: ReportDraft
    evidence: EvidenceArtifact
    mapping: MapArtifact


def _definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        name="report",
        version="1",
        nodes=(
            NodeSpec(id="source", kind="deterministic", output_key="source", postconditions=("papers",)),
            NodeSpec(
                id="evidence",
                kind="deterministic",
                input_keys=("source",),
                output_key="evidence",
                postconditions=("claims", "fulltext"),
            ),
            NodeSpec(
                id="map",
                kind="deterministic",
                input_keys=("evidence",),
                output_key="map",
                postconditions=("directions",),
            ),
            NodeSpec(
                id="write",
                kind="deterministic",
                input_keys=("map", "evidence"),
                output_key="draft",
                postconditions=("report_id",),
            ),
            NodeSpec(
                id="finalize",
                kind="deterministic",
                input_keys=("draft",),
                output_key="finished",
                postconditions=("report_id",),
            ),
        ),
    )


class ReportWorkflow:
    def __init__(
        self,
        shell: ReportRunPort,
        *,
        source: SourcePort,
        evidence: EvidencePort,
        mapper: MapPort,
        writer: WriterPort,
        store: ReportStorePort,
        events: EventPort,
        metrics: MetricPort,
    ) -> None:
        self.shell = shell
        self.source = source
        self.evidence = evidence
        self.mapper = mapper
        self.writer = writer
        self.store = store
        self.events = events
        self.metrics = metrics

    def run(
        self,
        request: RunRequest,
        *,
        title: str | None = None,
        run_id: str | None = None,
        resume: bool = False,
    ) -> ReportOutcome:
        active_run_id = run_id or self.shell.prepare(request)
        definition = _definition()

        def do_source(_inputs):
            artifact = self.source.select(
                topic_id=request.topic_id,
                query=request.focus_hint or request.topic_id,
                limit=request.limit,
                run_id=active_run_id,
            )
            return {"papers": len(artifact.papers), **artifact.to_dict()}

        def do_evidence(inputs):
            source = SourceArtifact.from_dict(inputs["source"])
            artifact = self.evidence.build(source, run_id=active_run_id)
            return {"claims": artifact.claims, "fulltext": artifact.fulltext, **artifact.to_dict()}

        def do_map(inputs):
            evidence = EvidenceArtifact.from_dict(inputs["evidence"])
            artifact = self.mapper.build(evidence)
            return {"directions": len(artifact.directions), **artifact.to_dict()}

        def emit_section(section) -> None:
            self.events.emit(
                active_run_id,
                "section.delta",
                node_id="write",
                section_id=section.section_id,
                title=section.title,
                chars=len(section.body),
            )

        def do_write(inputs):
            mapping = MapArtifact.from_dict(inputs["map"])
            evidence = EvidenceArtifact.from_dict(inputs["evidence"])
            draft = self.writer.build(
                run_id=active_run_id,
                topic_id=request.topic_id,
                title=title or f"Weekly report: {request.topic_id}",
                evidence=evidence,
                mapping=mapping,
                on_section=emit_section,
            )
            self.metrics.point(
                "report.words", float(draft.word_count), run_id=active_run_id, node_id="write"
            )
            displayed = sorted(
                {index for section in draft.sections if section.kind == "deep_dive" for index in section.claim_indexes}
            )
            self.metrics.point(
                "report.claim_coverage",
                float(len(displayed)) / max(1, len(draft.claims)),
                run_id=active_run_id,
                node_id="write",
            )
            self.metrics.point(
                "report.count_reconciliation",
                1.0 if len(displayed) == len(draft.claims) else 0.0,
                run_id=active_run_id,
                node_id="write",
            )
            self.metrics.point(
                "direction.max_share",
                max((len(item.paper_ids) for item in mapping.directions), default=0)
                / max(1, mapping.papers),
                run_id=active_run_id,
                node_id="map",
            )
            audit = audit_report(draft)
            self.metrics.point(
                "report.citation_coverage",
                audit.citation_coverage,
                run_id=active_run_id,
                node_id="write",
            )
            self.metrics.point(
                "report.uncited_facts",
                float(audit.uncited_facts),
                run_id=active_run_id,
                node_id="write",
            )
            self.metrics.point(
                "report.duplicate_claim_rate",
                audit.duplicate_claim_rate,
                run_id=active_run_id,
                node_id="write",
            )
            self.metrics.point(
                "cluster.count",
                float(len(mapping.directions)),
                run_id=active_run_id,
                node_id="map",
            )
            self.metrics.point(
                "cluster.min_size",
                float(mapping.min_size),
                run_id=active_run_id,
                node_id="map",
            )
            self.metrics.point(
                "cluster.outlier_rate",
                float(mapping.outlier_rate),
                run_id=active_run_id,
                node_id="map",
                sample_size=mapping.papers,
            )
            return {
                "report_id": f"{active_run_id}:{draft.content_sha}",
                "words": draft.word_count,
                "sections": len(draft.sections),
                **draft.to_dict(),
            }

        def do_finalize(inputs):
            draft = ReportDraft.from_dict(inputs["draft"])
            report_id = self.store.save(
                run_id=active_run_id,
                topic_id=request.topic_id,
                draft=draft,
            )
            return {"report_id": report_id, "state": draft.state}

        outputs = self.shell.run(
            active_run_id,
            definition,
            handlers={
                "source": do_source,
                "evidence": do_evidence,
                "map": do_map,
                "write": do_write,
                "finalize": do_finalize,
            },
            resume=resume,
        )
        finished = outputs.get("finished") or {}
        report_id = str(finished.get("report_id") or "")
        if not report_id:
            raise RuntimeError("report workflow did not finish")
        return ReportOutcome(
            run_id=active_run_id,
            report_id=report_id,
            draft=ReportDraft.from_dict(outputs["draft"]),
            evidence=EvidenceArtifact.from_dict(outputs["evidence"]),
            mapping=MapArtifact.from_dict(outputs["map"]),
        )
