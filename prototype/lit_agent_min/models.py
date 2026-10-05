"""数据契约（Pydantic v2）——跨模块传递的唯一结构定义。

Step 0.2 只落 Phase 0 需要的最小集合：`Author / Paper / EvidenceCard / Citation / Claim / Verdict / Event`。
其余模型（SourceRecord / ParsedDoc / Chunk / 阶段产物 / EvalRecord）按 Step 0.5+ 演进，
字段清单见 `docs/implementation/implementation-guide.md` §2.3。

设计要点
- 所有契约模型 **extra="forbid" + frozen=True**：拼写错误在入口暴露，模型构造后不可变。
- 关键约束写进模型（而不是靠调用方自觉）：claim 必须可回查、失败判决必须给原因、
  事件的 ts 必须带时区、payload 必须可 JSON 序列化。
- 不依赖业务代码，纯数据层：`models.py` 只 import 标准库与 pydantic。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

__all__ = [
    "Author",
    "Citation",
    "Claim",
    "ContractModel",
    "Event",
    "EventType",
    "EvidenceCard",
    "GuardAction",
    "Paper",
    "RunId",
    "Severity",
    "Support",
    "Verdict",
]

#: Phase 0 的 run 标识是字符串（如 `p0-s5-001`），Phase 1 的 SQLite 主键是整数；两者都允许。
RunId = str | int


class ContractModel(BaseModel):
    """所有契约模型的基类：拒绝未知字段 + 不可变。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------- #
# 枚举
# --------------------------------------------------------------------------- #
class Severity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventType(StrEnum):
    """事件类型（契约固定分类，见 implementation-guide §2.2）。"""

    PHASE_CHANGE = "phase_change"
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"
    GUARD_TRIGGER = "guard_trigger"
    RECOVERY = "recovery"
    MESSAGE = "message"
    ERROR = "error"
    METRIC = "metric"
    REPORT_WRITTEN = "report_written"


class GuardAction(StrEnum):
    """守卫判决动作（升级阶梯，见 state-machine-and-guards §8）。"""

    CONTINUE = "continue"
    RETRY = "retry"
    DEGRADE = "degrade"
    REPLAN = "replan"
    ABORT = "abort"
    ANNOTATE = "annotate"


class Support(StrEnum):
    """证据对断言的支持状态（grounding 三类判定 + 未核实）。"""

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"
    UNVERIFIED = "unverified"


# --------------------------------------------------------------------------- #
# 论文与证据
# --------------------------------------------------------------------------- #
class Author(ContractModel):
    author_id: str = Field(min_length=1, description="稳定键：源内 author id 或 name_norm 派生")
    name: str = Field(min_length=1)
    name_norm: str = Field(min_length=1, description="归一化名（消歧预留，本轮不做消歧）")


class Paper(ContractModel):
    paper_id: str = Field(min_length=1, description="canonical id：DOI → OpenAlex W → arxiv:")
    title: str = Field(min_length=1)
    abstract: str = ""
    authors: list[Author] = Field(default_factory=list)
    venue: str | None = None
    year: int | None = Field(default=None, ge=1800, le=2200)
    published_at: datetime | None = None
    updated_at: datetime | None = None
    source: str = Field(min_length=1, description="来源：openalex / arxiv / …")
    references: list[str] = Field(default_factory=list, description="被引论文的 canonical id 列表")
    oa_pdf_url: str | None = None

    @field_validator("paper_id")
    @classmethod
    def _no_whitespace(cls, value: str) -> str:
        if any(ch.isspace() for ch in value):
            raise ValueError("paper_id 不得含空白字符")
        return value


class EvidenceCard(ContractModel):
    """检索结果卡片：进上下文的最小单元，必须带可回查的片段。"""

    paper_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    year: int | None = Field(default=None, ge=1800, le=2200)
    snippet: str = Field(min_length=1)
    source: str = Field(min_length=1)
    score: float = Field(default=0.0, ge=0.0, le=1.0)

    def to_citation(self) -> Citation:
        return Citation(paper_id=self.paper_id, snippet=self.snippet)


class Citation(ContractModel):
    """断言到证据的引用；`snippet`/`locator` 用于 grounding 回查。"""

    paper_id: str = Field(min_length=1)
    locator: str | None = Field(default=None, description="页码/章节/片段锚点")
    snippet: str | None = None


class Claim(ContractModel):
    text: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)
    support: Support = Support.UNVERIFIED

    @model_validator(mode="after")
    def _require_evidence(self) -> Claim:
        if self.support is not Support.UNVERIFIED and not self.citations:
            raise ValueError("非 unverified 的 claim 必须至少带 1 条 citation")
        return self


# --------------------------------------------------------------------------- #
# 守卫判决
# --------------------------------------------------------------------------- #
class Verdict(ContractModel):
    ok: bool
    severity: Severity = Severity.INFO
    action: GuardAction = GuardAction.CONTINUE
    code: str = Field(min_length=1, description="错误/判决码，如 E_GUARD_DRIFT")
    reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_reasons_on_failure(self) -> Verdict:
        if not self.ok and not self.reasons:
            raise ValueError("ok=False 的判决必须给出至少 1 条 reasons")
        return self


# --------------------------------------------------------------------------- #
# 事件
# --------------------------------------------------------------------------- #
class Event(ContractModel):
    """事件真相源的一行（Phase 0 落 JSONL；Phase 1 迁 SQLite `run_events`）。"""

    id: int | None = Field(default=None, description="全局主键，Phase 1 由数据库分配")
    run_id: RunId
    seq: int = Field(ge=1, description="同一 run 内单调递增（由 JsonlEventLog 维护）")
    ts: datetime = Field(description="UTC，必须带时区")
    type: EventType
    stage: str | None = None
    agent: str | None = None
    severity: Severity = Severity.INFO
    payload: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = Field(default="1.0", min_length=1)

    @field_validator("run_id")
    @classmethod
    def _run_id_not_empty(cls, value: RunId) -> RunId:
        if isinstance(value, str) and not value.strip():
            raise ValueError("run_id 不得为空字符串")
        return value

    @field_validator("ts")
    @classmethod
    def _tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ts 必须带时区（UTC），例如 2026-01-01T03:00:00Z")
        return value.astimezone(UTC)

    @field_validator("payload")
    @classmethod
    def _json_serializable(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"payload 必须可 JSON 序列化：{exc}") from None
        return value

    def to_json_line(self) -> str:
        """单行 JSON（不含换行符），供 append-only 写入。"""
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json_line(cls, line: str) -> Event:
        try:
            return cls.model_validate_json(line)
        except ValidationError as exc:
            raise ValueError(f"事件行不符合契约：{_format_validation(exc)}") from None


def _format_validation(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(item) for item in err.get("loc", ())) or "<root>"
        parts.append(f"{loc}: {err.get('msg')}")
    return "; ".join(parts)
