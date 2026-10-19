"""证据与引用契约（进上下文的最小单元，必须可回查）。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from lit_agent.models._base import ContractModel

__all__ = ["Citation", "EvidenceCard", "Support"]


class Support(StrEnum):
    """证据对断言的支持状态（grounding 三类判定 + 未核实）。"""

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"
    UNVERIFIED = "unverified"


class Citation(ContractModel):
    """断言到证据的引用；`snippet`/`locator` 用于 grounding 回查。"""

    paper_id: str = Field(min_length=1)
    locator: str | None = Field(default=None, description="页码/章节/片段锚点")
    snippet: str | None = None


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
