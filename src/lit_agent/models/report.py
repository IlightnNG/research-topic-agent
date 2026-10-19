"""报告契约：`content_sha` 是幂等键；内容变化必须新增行而非覆盖（ADR-0005 §7.1）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from lit_agent.models._base import ContractModel
from lit_agent.models.claim import Claim

__all__ = ["Report"]


class Report(ContractModel):
    report_id: str = Field(min_length=1)
    topic_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    period: str | None = Field(default=None, description="'2026-W42' / None")
    title: str = ""
    content_md: str = Field(min_length=1)
    content_sha: str = Field(min_length=1, description="sha256(content_md)，幂等键")
    claims: list[Claim] = Field(default_factory=list)
    metrics_snapshot: dict[str, Any] = Field(default_factory=dict)
    n_claims: int = Field(default=0, ge=0)
    degraded: bool = False
    created_at: datetime | None = None
