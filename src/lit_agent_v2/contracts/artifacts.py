"""Artifact contracts for Node Platform migration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from lit_agent_v2.contracts.features import ReportRequirements

__all__ = [
    "ArtifactEnvelope",
    "PlanSection",
    "ReportPlan",
    "SectionArtifact",
]


@dataclass
class ArtifactEnvelope:
    artifact_type: str
    run_id: str
    node_id: str
    payload: dict[str, Any]
    sha256: str = ""
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not self.sha256:
            body = json.dumps(self.payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
            self.sha256 = hashlib.sha256(body).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_type": self.artifact_type,
            "run_id": self.run_id,
            "node_id": self.node_id,
            "sha256": self.sha256,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class PlanSection:
    section_id: str
    kind: str
    title: str = ""
    target_words: int = 0
    paper_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "kind": self.kind,
            "title": self.title,
            "target_words": self.target_words,
            "paper_ids": list(self.paper_ids),
        }


@dataclass
class ReportPlan:
    title: str
    sections: list[PlanSection] = field(default_factory=list)
    schema_version: int = 1

    def validate(self, requirements: ReportRequirements) -> list[str]:
        return requirements.validate_plan(tuple(section.kind for section in self.sections))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "title": self.title,
            "sections": [section.to_dict() for section in self.sections],
        }


@dataclass
class SectionArtifact:
    section_id: str
    kind: str
    title: str
    body: str
    claim_ids: list[str] = field(default_factory=list)
    state: str = "accepted"
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "section_id": self.section_id,
            "kind": self.kind,
            "title": self.title,
            "body": self.body,
            "claim_ids": self.claim_ids,
            "state": self.state,
        }
