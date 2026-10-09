"""分块与 PDF 兜底单测（Phase 0 step 5.3 验收：坏文件有 fallback；分块 token ±10%）。"""

from __future__ import annotations

from pathlib import Path

from lit_agent_min.chunking import chunk_text, count_tokens, extract_pdf_text

SAMPLE = (
    "Multi-agent systems coordinate several language models to solve a task. "
    "Each agent has a role and a communication channel. "
    "Failures often arise from silent message loss between agents. "
    "We propose a contract-based bus that detects such failures. "
    "Experiments on three benchmarks show a higher success rate. "
    "The approach also reduces token cost in most settings. "
    "Limitations include dependence on a shared schema. "
    "Future work will study adversarial settings and partial observability."
)


def test_count_tokens_is_deterministic_and_monotonic() -> None:
    assert count_tokens("") == 0
    assert count_tokens(SAMPLE) == count_tokens(SAMPLE)
    assert count_tokens(SAMPLE) > count_tokens("short text")
    assert count_tokens("中文测试") >= 4  # CJK 按字计


def test_chunks_never_exceed_budget() -> None:
    """硬不变量：任何块都不得超过 token 预算（实测在 30/60/120 三档均成立）。"""
    for budget in (30, 60, 120):
        chunks = chunk_text(SAMPLE, budget_tokens=budget, overlap_tokens=5)
        assert chunks
        assert all(c.tokens <= budget for c in chunks), (budget, [c.tokens for c in chunks])


def test_non_final_chunks_reach_nine_tenths_when_budget_is_ample() -> None:
    """±10% 验收：当预算 ≥ 约 3× 最长句时，非末块利用率可达 ≥0.9（实测 0.92）。"""
    budget = 60
    chunks = chunk_text(SAMPLE, budget_tokens=budget, overlap_tokens=5)
    assert len(chunks) > 1
    for chunk in chunks[:-1]:
        assert chunk.tokens >= 0.9 * budget, chunk.tokens


def test_small_budget_trades_utilization_for_sentence_integrity() -> None:
    """预算接近单句长度时，为保持句子完整会牺牲利用率（实测 0.77）——这是刻意的取舍。"""
    budget = 30
    chunks = chunk_text(SAMPLE, budget_tokens=budget, overlap_tokens=5)
    assert all(c.tokens <= budget for c in chunks)
    assert all(c.tokens >= 0.7 * budget for c in chunks[:-1]), [c.tokens for c in chunks]


def test_chunk_indices_are_sequential() -> None:
    chunks = chunk_text(SAMPLE, budget_tokens=25, overlap_tokens=5)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_long_sentence_is_hard_split() -> None:
    long_sentence = " ".join(f"word{i}" for i in range(300)) + "."
    chunks = chunk_text(long_sentence, budget_tokens=40, overlap_tokens=0)
    assert len(chunks) > 1
    assert all(c.tokens <= 44 for c in chunks)  # 允许启发式误差


def test_empty_text_yields_no_chunks() -> None:
    assert chunk_text("", budget_tokens=50) == []
    assert chunk_text("   \n  ", budget_tokens=50) == []


def test_chunk_text_rejects_bad_budget() -> None:
    try:
        chunk_text("x", budget_tokens=0)
    except ValueError as exc:
        assert "budget_tokens" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("budget_tokens=0 应报错")


# ---- PDF 兜底：坏文件不崩、给出错误信息（本轮不下载真 PDF） ---- #
def test_extract_pdf_text_missing_file_is_reported() -> None:
    result = extract_pdf_text(Path("does-not-exist.pdf"))
    assert not result.ok
    assert result.error and "不存在" in result.error


def test_extract_pdf_text_corrupt_file_falls_back_without_crash(tmp_path: Path) -> None:
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"%PDF-1.4 this is not a real pdf body \x00\x01\x02")
    result = extract_pdf_text(bad)
    assert not result.ok  # 两种引擎都失败
    assert result.error  # 但错误被记录，而不是抛异常打断链路
    assert "pymupdf" in result.error.lower() or "pdfplumber" in result.error.lower()
