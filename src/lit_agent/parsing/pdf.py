"""OA PDF 下载与文本抽取（三级降级：PyMuPDF → pdfplumber → 记录失败）。

纪律：**坏文件绝不打断整轮 run**——返回带 `error` 的结果对象，由 pipeline 写
`parse_status='failed'` 与错误事件（Phase 0 已验证的兜底语义）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from lit_agent.config import Settings
from lit_agent.errors import E_SRC_SCHEMA, E_SRC_TIMEOUT, LitError
from lit_agent.stores.files import MAX_PDF_MB, save_pdf

__all__ = ["ExtractResult", "download_oa", "extract_pdf_text"]


@dataclass
class ExtractResult:
    """抽取结果：失败也返回对象（`error` 有值），绝不抛异常打断链路。"""

    text: str = ""
    engine: str = "none"
    error: str | None = None
    pages: int = 0

    @property
    def ok(self) -> bool:
        return bool(self.text.strip())


def download_oa(
    settings: Settings,
    paper_id: str,
    url: str,
    *,
    client: httpx.Client | None = None,
    max_mb: int = MAX_PDF_MB,
) -> Path:
    """下载 OA PDF 并落盘（大小/魔数校验在 `stores.files.save_pdf`）。"""
    if not url:
        raise LitError(
            E_SRC_SCHEMA, f"缺少 OA PDF 链接：{paper_id}", context={"paper_id": paper_id}
        )
    owned = client is None
    http = client or httpx.Client(timeout=60.0, follow_redirects=True)
    try:
        try:
            response = http.get(url)
        except httpx.TimeoutException as exc:
            raise LitError(
                E_SRC_TIMEOUT, f"PDF 下载超时：{url}（{exc}）", context={"paper_id": paper_id}
            ) from None
        if response.status_code >= 400:
            raise LitError(
                E_SRC_SCHEMA,
                f"PDF 下载失败 HTTP {response.status_code}：{url}",
                context={"paper_id": paper_id, "status": response.status_code},
            )
        return save_pdf(settings, paper_id, response.content, max_mb=max_mb)
    finally:
        if owned:
            http.close()


def extract_pdf_text(path: str | Path) -> ExtractResult:
    """PyMuPDF 优先，`pdfplumber` 兜底；两者都失败则记录错误并返回空文本。"""
    target = Path(path)
    if not target.exists():
        return ExtractResult(error=f"文件不存在：{target}")
    try:
        import pymupdf

        with pymupdf.open(target) as doc:
            pages = doc.page_count
            text = "\n".join(page.get_text() for page in doc)
        if text.strip():
            return ExtractResult(text=text, engine="pymupdf", pages=pages)
        pymupdf_note = "PyMuPDF 未提取到文本层"
    except Exception as exc:  # noqa: BLE001 - 坏文件/加密/无文本层都要兜底
        pymupdf_note = f"PyMuPDF 失败：{type(exc).__name__}: {str(exc)[:120]}"
        pages = 0

    try:
        import pdfplumber

        with pdfplumber.open(target) as pdf:
            pages = len(pdf.pages)
            text = "\n".join((page.extract_text() or "") for page in pdf.pages)
        if text.strip():
            return ExtractResult(text=text, engine="pdfplumber", pages=pages)
        return ExtractResult(
            engine="pdfplumber", pages=pages, error=f"{pymupdf_note}；pdfplumber 无文本层"
        )
    except Exception as exc:  # noqa: BLE001
        return ExtractResult(
            error=f"{pymupdf_note}；pdfplumber 失败：{type(exc).__name__}: {str(exc)[:120]}"
        )
