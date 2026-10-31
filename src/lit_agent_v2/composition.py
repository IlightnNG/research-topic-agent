"""Composition root. The only place that wires concrete implementations."""

from __future__ import annotations

from typing import Any

from lit_agent_v2.contracts import RunRequest
from lit_agent_v2.contracts.ports import EventPort, MetricPort, SourcePort
from lit_agent_v2.domains.chat.answer import ChatService
from lit_agent_v2.domains.report.evidence import EvidenceService
from lit_agent_v2.domains.report.ingest import LocalCorpus
from lit_agent_v2.domains.report.llm_writer import LLMReportWriter
from lit_agent_v2.domains.report.map import MapService
from lit_agent_v2.domains.report.persist import ReportStore
from lit_agent_v2.domains.report.source import LocalCorpusSource, SourceService
from lit_agent_v2.domains.report.workflow import ReportWorkflow
from lit_agent_v2.domains.report.write import WriteService
from lit_agent_v2.evaluation.dataset import EvalDataset
from lit_agent_v2.evaluation.evaluators import evaluate
from lit_agent_v2.evaluation.runner import EvalRunner, TuneConfig, Tuner
from lit_agent_v2.metrics.store import MetricStore
from lit_agent_v2.run_shell import RunShell
from lit_agent_v2.storage.db import Database
from lit_agent_v2.workflow.events import EventLog, EventReader

__all__ = [
    "EventBridge",
    "build_chat_service",
    "build_eval_runner",
    "build_event_reader",
    "build_report_workflow",
    "build_report_reader",
    "build_report_workflow_from_path",
    "build_tuner",
]


class EventBridge:
    def __init__(self, db: Database) -> None:
        self.db = db

    def emit(
        self, run_id: str, event_type: str, *, node_id: str | None = None, **payload: Any
    ) -> None:
        EventLog(self.db, run_id).emit(event_type, node_id=node_id, **payload)


def build_report_workflow(
    shell: RunShell,
    corpus: LocalCorpus,
    *,
    source: SourcePort | None = None,
    metrics: MetricPort | None = None,
    events: EventPort | None = None,
    writer=None,
    mapper=None,
    llm=None,
) -> ReportWorkflow:
    active_metrics = metrics or MetricStore(shell.db)
    return ReportWorkflow(
        shell,
        source=source or LocalCorpusSource(corpus, SourceService(active_metrics)),
        evidence=EvidenceService(active_metrics),
        mapper=mapper or MapService(),
        writer=writer or (LLMReportWriter(llm) if llm is not None else WriteService()),
        store=ReportStore(shell.db),
        events=events or EventBridge(shell.db),
        metrics=active_metrics,
    )



def build_report_workflow_from_path(shell: RunShell, corpus_root, **kwargs) -> ReportWorkflow:
    return build_report_workflow(shell, LocalCorpus(corpus_root), **kwargs)


def build_chat_service(corpus_root, *, composer=None) -> ChatService:
    return ChatService(LocalCorpus(corpus_root), composer=composer)


def build_eval_runner(db: Database, artifacts) -> EvalRunner:
    def run_case(case, config: TuneConfig):
        shell = RunShell(db, artifacts)
        workflow = build_report_workflow(
            shell,
            LocalCorpus(case.corpus_root),
            mapper=MapService(
                threshold=config.threshold,
                min_size=config.min_size,
                max_directions=config.max_directions,
            ),
        )
        outcome = workflow.run(
            RunRequest(
                topic_id=case.topic_id,
                limit=case.limit,
                focus_hint=case.focus_hint,
            )
        )
        return evaluate(
            case=case,
            mapping=outcome.mapping,
            words=outcome.draft.word_count,
            citations=1.0,
        )

    return EvalRunner(run_case)


def build_tuner(db: Database, artifacts, dataset: EvalDataset) -> Tuner:
    return Tuner(db, dataset, build_eval_runner(db, artifacts))


def build_report_reader(db: Database):
    from lit_agent_v2.domains.report.persist import ReportStore

    return ReportStore(db)


def build_event_reader(db: Database) -> EventReader:
    return EventReader(db)
