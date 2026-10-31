"""PDF text extraction for v2."""

from __future__ import annotations

import io

import httpx

__all__ = ["download_html_text", "download_pdf_text", "extract_pdf_text"]


def extract_pdf_text(data: bytes) -> str:
    import pymupdf

    document = pymupdf.open(stream=io.BytesIO(data), filetype="pdf")
    try:
        return "\n\n".join(page.get_text("text") for page in document).strip()
    finally:
        document.close()


def download_pdf_text(url: str, *, client: httpx.Client | None = None) -> str:
    if not url:
        return ""
    active = client or httpx.Client(timeout=60.0, follow_redirects=True)
    response = active.get(url)
    response.raise_for_status()
    return extract_pdf_text(response.content)


def download_html_text(url: str, *, client: httpx.Client | None = None) -> str:
    """Best-effort landing-page fallback; strips tags and scripts."""
    if not url:
        return ""
    import html
    import re

    active = client or httpx.Client(timeout=30.0, follow_redirects=True)
    response = active.get(url)
    response.raise_for_status()
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", response.text, flags=re.S | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", html.unescape(body)).strip()
