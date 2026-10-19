"""论文契约（guide §2.3 + ADR-0005 §10 字段增量）。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from lit_agent.models._base import ContractModel
from lit_agent.models.author import Author

__all__ = ["Author", "Chunk", "Paper", "ParseStatus", "ParsedDoc", "SourceRecord"]


class ParseStatus(StrEnum):
    """论文全文解析状态（`na` = 无需解析，如非 OA；`failed` = 尝试过但失败）。"""

    PENDING = "pending"
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"
    NA = "na"


class Paper(ContractModel):
    paper_id: str = Field(
        min_length=1, description="canonical id：DOI → OpenAlex W → arxiv: → 标题指纹"
    )
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
    # --- ADR-0005 增量（与 SQLite 源字段一一对应） ---
    source_id: str = Field(default="", description="源侧 id（OpenAlex 'W…' / arXiv id）")
    venue_id: str | None = Field(default=None, description="OpenAlex source.id（白名单口径）")
    is_oa: bool = False
    language: str | None = None
    parse_status: ParseStatus = ParseStatus.PENDING
    cited_by_count: int | None = Field(default=None, ge=0)
    merged_ids: list[str] = Field(
        default_factory=list, description="被合并到本记录的其他 canonical id（ADR-0001，保留溯源）"
    )

    @field_validator("paper_id")
    @classmethod
    def _no_whitespace(cls, value: str) -> str:
        if any(ch.isspace() for ch in value):
            raise ValueError("paper_id 不得含空白字符")
        return value


class SourceRecord(ContractModel):
    """源侧原始记录（未归一化）：`papers_raw` 的原样留存对象。"""

    source: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    raw_json: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime
    content_sha: str = Field(default="", description="raw_json 的 sha256（幂等键的一部分）")


class ParsedDoc(ContractModel):
    """一篇论文的解析结果（正文落文件，库里只存路径与质量）。"""

    paper_id: str = Field(min_length=1)
    text_path: str | None = None
    page_count: int = Field(default=0, ge=0)
    quality: float = Field(default=0.0, ge=0.0, le=1.0)
    status: ParseStatus = ParseStatus.PENDING
    error_code: str | None = None


class Chunk(ContractModel):
    """分块结果（P3 才向量化，但 `chunk_id` 契约现在就冻结）。"""

    paper_id: str = Field(min_length=1)
    idx: int = Field(ge=0)
    text: str = Field(min_length=1)
    tokens: int = Field(ge=0)
    section: str | None = None

    @property
    def chunk_id(self) -> str:
        return f"{self.paper_id}#{self.section or 'body'}#{self.idx}"
