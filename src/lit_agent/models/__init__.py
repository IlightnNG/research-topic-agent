"""契约模型包：所有跨模块传递的结构都在这里定义（guide §2.3）。

规则：
- 跨模块参数/返回只用本包类型，**禁止裸 dict**（`payload` / `selector` 等宽松字段除外）；
- 本包不依赖业务模块，可被任何层 import。
"""

from __future__ import annotations

from lit_agent.models._base import ContractModel, RunId, Severity, format_validation
from lit_agent.models.claim import Claim
from lit_agent.models.event import Event, EventType
from lit_agent.models.evidence import Citation, EvidenceCard, Support
from lit_agent.models.paper import Author, Chunk, Paper, ParsedDoc, ParseStatus, SourceRecord
from lit_agent.models.report import Report
from lit_agent.models.results import (
    AnalysisResult,
    EvalRecord,
    MappingResult,
    ReportDraft,
    RetrievalResult,
    RunContext,
    StageResult,
)
from lit_agent.models.run import Run, RunState, RunTrigger
from lit_agent.models.topic import Topic, TopicSource, TopicStatus
from lit_agent.models.verdict import GuardAction, GuardSeverity, GuardVerdict, Verdict

__all__ = [
    "AnalysisResult",
    "Author",
    "Chunk",
    "Citation",
    "Claim",
    "ContractModel",
    "EvalRecord",
    "Event",
    "EventType",
    "EvidenceCard",
    "GuardAction",
    "GuardSeverity",
    "GuardVerdict",
    "MappingResult",
    "Paper",
    "ParseStatus",
    "ParsedDoc",
    "Report",
    "ReportDraft",
    "RetrievalResult",
    "Run",
    "RunContext",
    "RunId",
    "RunState",
    "RunTrigger",
    "Severity",
    "SourceRecord",
    "StageResult",
    "Support",
    "Topic",
    "TopicSource",
    "TopicStatus",
    "Verdict",
    "format_validation",
]
