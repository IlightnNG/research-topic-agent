"""S10：PDF 工具（下载 / 读取 → 抽文本 → 分块 → 幂等）。

幂等口径：块以 `sha1(paper_id|chunk_index|text)` 标识；同一 PDF 解析两次
**不会**产生重复块（内存去重 / 传入 `settings` 时对比 `paper_chunks`）。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lit_agent.parsing.chunking import chunk_text
from lit_agent.parsing.pdf import download_oa, extract_pdf_text
from lit_agent.tools.registry import Tool

__all__ = ["PdfResult", "build_tool", "chunk_hashes", "run"]


@dataclass
class PdfResult:
    ok: bool
    paper_id: str = ""
    chars: int = 0
    chunks: list[str] = field(default_factory=list)
    hashes: list[str] = field(default_factory=list)
    new_chunks: int = 0
    error: str | None = None
    sha: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "paper_id": self.paper_id,
            "chars": self.chars,
            "chunks": len(self.chunks),
            "new_chunks": self.new_chunks,
            "hashes": self.hashes,
            "sha": self.sha,
            "error": self.error,
        }


def chunk_hashes(paper_id: str, chunks: list[str]) -> list[str]:
    return [
        hashlib.sha1(f"{paper_id}|{index}|{text}".encode()).hexdigest()[:16]
        for index, text in enumerate(chunks)
    ]


def run(
    *,
    paper_id: str = "",
    path: str | Path | None = None,
    url: str | None = None,
    text: str | None = None,
    budget_tokens: int = 512,
    known_hashes: set[str] | None = None,
) -> dict[str, Any]:
    """解析一个 PDF（或直接给文本）；返回结构化结果，**失败不抛异常**。"""
    if text is None:
        if path is None and url is None:
            return PdfResult(ok=False, paper_id=paper_id, error="需要 path/url/text 之一").as_dict()
        if url is not None:
            fetched = download_oa(url, Path("D:/lit-agent-store/temp/pdf"))
            if not getattr(fetched, "ok", False):
                return PdfResult(
                    ok=False, paper_id=paper_id, error=str(getattr(fetched, "error", "download failed"))
                ).as_dict()
            path = getattr(fetched, "path", None)
        extracted = extract_pdf_text(Path(path) if path else Path(""))
        if not getattr(extracted, "ok", False):
            return PdfResult(
                ok=False, paper_id=paper_id, error=str(getattr(extracted, "error", "extract failed"))
            ).as_dict()
        text = str(getattr(extracted, "text", ""))

    if not text.strip():
        return PdfResult(ok=False, paper_id=paper_id, error="empty text").as_dict()

    chunks = chunk_text(text, budget_tokens=budget_tokens)
    hashes = chunk_hashes(paper_id, chunks)
    known = known_hashes or set()
    new_chunks = sum(1 for item in hashes if item not in known)
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return PdfResult(
        ok=True,
        paper_id=paper_id,
        chars=len(text),
        chunks=chunks,
        hashes=hashes,
        new_chunks=new_chunks,
        sha=sha,
    ).as_dict()


def build_tool() -> Tool:
    return Tool(
        name="paper_pdf",
        run=run,
        description="Fetch or read a paper PDF, extract text and chunk it idempotently",
        parameters={
            "paper_id": "string",
            "path": "string?",
            "url": "string?",
            "text": "string?",
            "budget_tokens": "integer",
        },
        timeout_s=120.0,
    )
