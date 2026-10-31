"""Module ports. Implementations live outside this module.

Modules import ports; composition wires concrete implementations.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from lit_agent_v2.contracts import RunRequest, WorkflowDefinition
    from lit_agent_v2.contracts.report import (
        EvidenceArtifact,
        SourceArtifact,
    )
    from lit_agent_v2.domains.report.map import MapArtifact
    from lit_agent_v2.domains.report.write import ReportDraft, Section

__all__ = [
    "EventPort",
    "EventReaderPort",
    "EvidencePort",
    "MapPort",
    "MetricPort",
    "ReportRunPort",
    "ReportReaderPort",
    "ReportStorePort",
    "SourcePort",
    "WriterPort",
]


class ReportRunPort(Protocol):
    def prepare(self, request: RunRequest) -> str: ...
    def run(self, run_id: str, definition: WorkflowDefinition, **kwargs: Any) -> dict[str, Any]: ...


class SourcePort(Protocol):
    def select(
        self, *, topic_id: str, query: str, limit: int, run_id: str
    ) -> SourceArtifact: ...


class EvidencePort(Protocol):
    def build(
        self, source: SourceArtifact, *, run_id: str, max_claims_per_paper: int = 2
    ) -> EvidenceArtifact: ...


class MapPort(Protocol):
    def build(self, evidence: EvidenceArtifact) -> MapArtifact: ...


class WriterPort(Protocol):
    def build(
        self,
        *,
        run_id: str,
        topic_id: str,
        title: str,
        evidence: EvidenceArtifact,
        mapping: MapArtifact,
        on_section: Callable[[Section], None] | None = None,
    ) -> ReportDraft: ...


class ReportStorePort(Protocol):
    def save(self, *, run_id: str, topic_id: str, draft: ReportDraft) -> str: ...


class ReportReaderPort(Protocol):
    def get(self, report_id: str) -> dict[str, Any] | None: ...
    def by_run(self, run_id: str) -> str | None: ...


class EventPort(Protocol):
    def emit(self, run_id: str, event_type: str, *, node_id: str | None = None, **payload: Any) -> None: ...


class EventReaderPort(Protocol):
    def after(self, run_id: str, seq: int) -> list[dict[str, Any]]: ...


class MetricPort(Protocol):
    def point(
        self,
        metric_id: str,
        value: float | None,
        *,
        run_id: str,
        node_id: str | None = None,
        sample_size: int | None = None,
        **kwargs: Any,
    ) -> None: ...
