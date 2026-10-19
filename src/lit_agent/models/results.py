"""阶段产物与运行上下文（Phase 1 阶段函数的统一签名：`(ctx: RunContext) -> StageResult`）。

**关键约束**：`RunContext` 进 checkpoint 前必须可 JSON 序列化，因此
- 只放标量/容器；
- 不可序列化资源（DB session、事件发射器、模型句柄）放 `resources`，该字段 `exclude=True`，永不落盘。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from lit_agent.models._base import ContractModel
from lit_agent.models.claim import Claim
from lit_agent.models.evidence import EvidenceCard
from lit_agent.models.paper import Paper

__all__ = [
    "AnalysisResult",
    "EvalRecord",
    "MappingResult",
    "ReportDraft",
    "RetrievalResult",
    "RunContext",
    "StageResult",
]


class StageResult(ContractModel):
    """单个阶段的结果信封：编排层只看这四个字段，不关心阶段内部实现。"""

    stage: str = Field(min_length=1)
    ok: bool = True
    artifacts: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    error_code: str | None = None


class RetrievalResult(ContractModel):
    papers: list[Paper] = Field(default_factory=list)
    new_count: int = Field(default=0, ge=0)
    updated_count: int = Field(default=0, ge=0)
    cursor: str | None = None
    since: str | None = None


class MappingResult(ContractModel):
    cards: list[EvidenceCard] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)


class AnalysisResult(ContractModel):
    findings: list[str] = Field(default_factory=list)
    by_paper: dict[str, list[str]] = Field(default_factory=dict)


class ReportDraft(ContractModel):
    title: str = ""
    content_md: str = Field(min_length=1)
    claims: list[Claim] = Field(default_factory=list)
    degraded: bool = False


class RunContext(ContractModel):
    """一次 run 内跨阶段传递的最小上下文（可序列化部分）。"""

    run_id: str = Field(min_length=1)
    topic_id: str = Field(min_length=1)
    stage: str | None = None
    attempt: int = Field(default=1, ge=1)
    input_hash: str = ""
    budget_remaining_usd: float | None = Field(default=None, ge=0.0)
    counters: dict[str, int] = Field(default_factory=dict)
    #: 运行时资源（session / emitter / 模型句柄）：**不参与序列化**，不得进 checkpoint。
    resources: dict[str, Any] = Field(default_factory=dict, exclude=True)


class EvalRecord(ContractModel):
    """一条评测记录（`eval_judgments` 的契约形态；P5 才大量产生）。"""

    target_type: str = Field(min_length=1, description="claim | report | run")
    target_id: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    score: float
    judge_model: str | None = None
    human: bool = False
    detail: dict[str, Any] = Field(default_factory=dict)
    ts: datetime | None = None
