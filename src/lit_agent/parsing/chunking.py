"""文本分块：token 预算 + 句界 + overlap（guide §3 / phase1 Step 1.7）。

token 计数优先用 **tiktoken**（`cl100k_base`，确定性）；词表不可用（离线首次）时退回
**确定性启发式**（拉丁词 + CJK 字 + 标点修正），保证任何机器上都能分块。
`tokenizer_name()` 暴露实际使用的计数方式，便于在 RESULTS 里记录口径。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["Chunk", "chunk_text", "count_tokens", "tokenizer_name"]

_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\-]*")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s+|\n+")
_PUNCT = re.compile(r"[.,;:!?()\[\]{}\"'`]")

_ENCODER: object | None = None
_ENCODING_NAME = "cl100k_base"


def _encoder() -> object | None:
    global _ENCODER
    if _ENCODER is None:
        try:
            import tiktoken

            _ENCODER = tiktoken.get_encoding(_ENCODING_NAME)
        except Exception:  # noqa: BLE001 - 离线/无词表时退回启发式
            _ENCODER = False
    return _ENCODER or None


def tokenizer_name() -> str:
    return "tiktoken:" + _ENCODING_NAME if _encoder() is not None else "heuristic"


def count_tokens(text: str) -> int:
    """token 数（tiktoken 优先，失败退回确定性启发式）。"""
    if not text:
        return 0
    encoder = _encoder()
    if encoder is not None:
        try:
            return len(encoder.encode(text))  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - 极端文本（超长/异常字符）退回启发式
            pass
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
    budget_tokens: int = 400,
    overlap_tokens: int = 40,
    min_tokens: int = 8,
) -> list[Chunk]:
    """按句子贪心打包成 ≤ budget 的块，块间保留 overlap（避免证据被切断）。"""
    if budget_tokens <= 0:
        raise ValueError("budget_tokens 必须为正")
    sentences = [piece.strip() for piece in _SENTENCE_SPLIT.split(text or "") if piece.strip()]
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
            previous = chunks[-1]
            merged = f"{previous.text} {' '.join(current)}"
            chunks[-1] = Chunk(text=merged, index=previous.index, tokens=count_tokens(merged))
        current, current_tokens = [], 0

    for sentence in sentences:
        tokens = count_tokens(sentence)
        if tokens > budget_tokens:
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
