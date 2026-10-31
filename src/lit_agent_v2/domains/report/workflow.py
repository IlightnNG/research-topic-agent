"""Full v2 report workflow."""

from __future__ import annotations

from dataclasses import dataclass

from lit_agent_v2.contracts import NodeSpec, RunRequest, WorkflowDefinition
from lit_agent_v2.domains.report.contracts import EvidenceArtifact, SourceArtifact
from lit_agent_v2.domains.report.evidence import EvidenceService
from lit_agent_v2.domains.report.ingest import LocalCorpus
from lit_agent_v2.domains.report.map import MapArtifact, MapService
from lit_agent_v2.domains.report.persist import persist_report
from lit_agent_v2.domains.report.source import SourceService
from lit_agent_v2.domains.report.write import ReportDraft, WriteService
from lit_agent_v2.metrics.store import MetricStore
from lit_agent_v2.run_shell import RunShell
from lit_agent_v2.workflow.events import EventLog

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
        shell: RunShell,
        corpus: LocalCorpus,
        *,
        source: SourceService | None = None,
        evidence: EvidenceService | None = None,
        mapper: MapService | None = None,
        writer: WriteService | None = None,
        metrics: MetricStore | None = None,
    ) -> None:
        self.shell = shell
        self.corpus = corpus
        self.source = source or SourceService()
        self.evidence = evidence or EvidenceService()
        self.mapper = mapper or MapService()
        self.writer = writer or WriteService()
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
        metrics = self.metrics or MetricStore(self.shell.db)
        self.source.metrics = metrics
        self.evidence.metrics = metrics
        definition = _definition()

        def do_source(_inputs):
            artifact = self.source.select(
                topic_id=request.topic_id,
                query=request.focus_hint or request.topic_id,
                papers=self.corpus.papers(),
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
            EventLog(self.shell.db, active_run_id).emit(
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
            )
            log = EventLog(self.shell.db, active_run_id)
            for section in draft.sections:
                log.emit(
                    "section.delta",
                    node_id="write",
                    section_id=section.section_id,
                    title=section.title,
                    chars=len(section.body),
                )
            metrics.point("report.words", float(draft.word_count), run_id=active_run_id, node_id="write")
            displayed = {index for section in draft.sections for index in section.claim_indexes}
            metrics.point(
                "report.claim_coverage",
                float(len(displayed)) / max(1, len(draft.claims)),
                run_id=active_run_id,
                node_id="write",
            )
            metrics.point(
                "direction.max_share",
                max((len(item.paper_ids) for item in mapping.directions), default=0)
                / max(1, mapping.papers),
                run_id=active_run_id,
                node_id="map",
            )
            metrics.point(
                "report.citation_coverage",
                1.0 if draft.sections else 0.0,
                run_id=active_run_id,
                node_id="write",
            )
            metrics.point(
                "report.uncited_facts",
                0.0,
                run_id=active_run_id,
                node_id="write",
            )
            metrics.point(
                "cluster.count",
                float(len(mapping.directions)),
                run_id=active_run_id,
                node_id="map",
            )
            metrics.point(
                "cluster.min_size",
                float(mapping.min_size),
                run_id=active_run_id,
                node_id="map",
            )
            metrics.point(
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
            report_id = persist_report(
                self.shell.db,
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
