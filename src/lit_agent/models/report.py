"""报告契约：`content_sha` 是幂等键；内容变化必须新增行而非覆盖（ADR-0005 §7.1）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from lit_agent.models._base import ContractModel
from lit_agent.models.claim import Claim

__all__ = ["Report"]


class ReportSection(ContractModel):
    """报告分节（S12：真实分节，由 claims 分组落库）。"""

    id: str
    title: str
    body: str
    claim_indexes: list[int] = Field(default_factory=list)
    kind: str = "findings"


class Report(ContractModel):
    report_id: str = Field(min_length=1)
    topic_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    period: str | None = Field(default=None, description="'2026-W42' / None")
    title: str = ""
    content_md: str = Field(min_length=1)
    content_sha: str = Field(min_length=1, description="sha256(content_md)，幂等键")
    claims: list[Claim] = Field(default_factory=list)
    sections: list[ReportSection] = Field(default_factory=list)
    metrics_snapshot: dict[str, Any] = Field(default_factory=dict)
    n_claims: int = Field(default=0, ge=0)
    degraded: bool = False
    language: str = "en"
    generated_by: str = "template"
    fallback_count: int = 0
    coverage: float = 0.0
    word_count: int = 0
    fallback_reason: str | None = None
    created_at: datetime | None = None
