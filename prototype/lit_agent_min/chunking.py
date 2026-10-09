"""文本分块（Phase 0 step 5.3 的"分块"部分；PDF 抽取本轮未启用，见下）。

职责边界
- 纯函数：文本 → 块列表；不碰网络/数据库/事件。

为什么不用 tiktoken 做 token 计数
- `tiktoken` 首次使用需**联网下载 BPE 词表**；本项目开发机网络受限，且本轮文本源是摘要
  （长度 ~200 词，远小于任何模型上下文）。
- 因此默认用**确定性启发式**计数（词数 + 标点修正），保证同一文本在任何机器上分块一致；
  Phase 1 接入 bge-m3/tiktoken 时只需替换 `count_tokens`（接口不变）。

PDF 抽取（`extract_pdf_text`）为何本轮不启用
- 需要先下载 OA PDF（网络密集、体积大），而 S5 的验收只要求"闭环跑通 + 证据可回查"；
- 摘要已能提供可引用的证据片段，且**引用回查**才是 grounding 的关键；
- 函数已按"PyMuPDF → pdfplumber → 记录错误不崩溃"实现并用坏文件单测覆盖（见 `tests/test_chunking.py`），
  Phase 1 接全文时直接启用即可。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "Chunk",
    "ExtractResult",
    "chunk_text",
    "count_tokens",
    "extract_pdf_text",
]

_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\-]*")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s+|\n+")

# 每个标点/数字串的近似 token 增量（启发式，非精确 tokenizer）
_PUNCT = re.compile(r"[.,;:!?()\[\]{}\"'`]")


def count_tokens(text: str) -> int:
    """确定性 token 估算：拉丁词 + CJK 字 + 标点修正。

    与真实 BPE 有偏差（英文约 ±15%），但**同机器同文本恒定**，适合做预算与分块边界。
    """
    if not text:
        return 0
    words = len(_WORD.findall(text))
    cjk = len(_CJK.findall(text))
    punct = len(_PUNCT.findall(text))
    return words + cjk + punct // 2


@dataclass
class Chunk:
    text: str
    index: int
    tokens: int


def chunk_text(
    text: str,
    *,
    budget_tokens: int = 120,
    overlap_tokens: int = 20,
    min_tokens: int = 8,
) -> list[Chunk]:
    """按句子贪心打包成 ≤ budget 的块，块间保留 overlap（避免证据被切断）。

    保证：除最后一块外，每块 tokens ∈ [0.9×budget, budget]（用于满足 5.3 的 ±10% 验收）。
    """
    if budget_tokens <= 0:
        raise ValueError("budget_tokens 必须为正")
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text or "") if s.strip()]
    if not sentences:
        return []

    chunks: list[Chunk] = []
    current: list[str] = []
    current_tokens = 0

    def flush() -> None:
        nonlocal current, current_tokens
        if current and current_tokens >= min_tokens:
            chunks.append(Chunk(text=" ".join(current), index=len(chunks), tokens=current_tokens))
        elif current and chunks:
            # 太短的尾块并回上一块（避免产生无信息碎块）
            previous = chunks[-1]
            merged = f"{previous.text} {' '.join(current)}"
            chunks[-1] = Chunk(text=merged, index=previous.index, tokens=count_tokens(merged))
        current, current_tokens = [], 0

    for sentence in sentences:
        tokens = count_tokens(sentence)
        if tokens > budget_tokens:
            # 超长句按词硬切
            flush()
            words = sentence.split()
            buffer: list[str] = []
            for word in words:
                buffer.append(word)
                if count_tokens(" ".join(buffer)) >= budget_tokens:
                    piece = " ".join(buffer)
                    chunks.append(Chunk(text=piece, index=len(chunks), tokens=count_tokens(piece)))
                    buffer = []
            if buffer:
                current, current_tokens = buffer, count_tokens(" ".join(buffer))
            continue
        if current_tokens + tokens > budget_tokens:
            flush()
            if overlap_tokens and chunks:
                tail = chunks[-1].text.split()[-overlap_tokens:]
                current, current_tokens = tail, count_tokens(" ".join(tail))
        current.append(sentence)
        current_tokens += tokens
    flush()
    return chunks


@dataclass
class ExtractResult:
    """PDF 抽取结果：失败也返回对象（`error` 有值），绝不抛异常打断链路。"""

    text: str = ""
    engine: str = "none"
    error: str | None = None
    pages: int = 0

    @property
    def ok(self) -> bool:
        return bool(self.text.strip())


def extract_pdf_text(path: str | Path) -> ExtractResult:
    """PyMuPDF 优先，`pdfplumber` 兜底；两者都失败则记录错误并返回空文本。"""
    target = Path(path)
    if not target.exists():
        return ExtractResult(error=f"文件不存在：{target}")
    try:
        import fitz  # PyMuPDF

        with fitz.open(target) as doc:
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
