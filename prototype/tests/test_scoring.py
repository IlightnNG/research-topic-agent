"""打分与阈值标定单测（Phase 0 step 6 的标定基础）。

S6 的核心教训：**阈值必须按打分器的实际分布标定**，不能套用别处的数字；
本文件把"标定算法"本身锁进回归测试。
"""

from __future__ import annotations

from lit_agent_min.scoring import (
    build_centroid,
    build_idf,
    calibrate_drift_thresholds,
    calibrate_threshold,
    cosine,
    cosine_to_vector,
    rank,
    tokenize,
)

ON_TOPIC = [
    "multi-agent LLM orchestration reliability verifier agent message bus failure detection",
    "agentic workflow scheduling verification stages latency token cost multi-agent systems",
    "benchmarking adversarial risks multi-agent llm systems robustness evaluation",
]
OFF_TOPIC = [
    "crispr cas9 off-target effects gene editing human cells repair pathways",
    "genome editing unintended outcomes detection prevalence clinical translation",
]


def test_tokenize_drops_stopwords_and_keeps_technical_terms() -> None:
    tokens = tokenize("The Multi-Agent LLM orchestration is a method for reliability")
    assert "multi-agent" in tokens
    assert "orchestration" in tokens
    assert "the" not in tokens and "method" not in tokens


def test_cosine_identical_text_is_one() -> None:
    assert cosine(ON_TOPIC[0], ON_TOPIC[0]) == 1.0


def test_cosine_unrelated_text_is_low() -> None:
    related = cosine(ON_TOPIC[0], ON_TOPIC[1])
    unrelated = cosine(ON_TOPIC[0], OFF_TOPIC[0])
    assert related > unrelated


def test_rank_is_deterministic_and_sorted() -> None:
    docs = {"a": ON_TOPIC[0], "b": OFF_TOPIC[0], "c": ON_TOPIC[1]}
    first = rank("multi-agent orchestration reliability", docs)
    second = rank("multi-agent orchestration reliability", docs)
    assert first == second
    assert first[0][0] in {"a", "c"}
    assert [score for _, score in first] == sorted((s for _, s in first), reverse=True)


def test_centroid_separates_on_topic_from_off_topic() -> None:
    """质心表示是 G1 可分的前提（关键词串表示下正负分布重叠，S6 实测）。"""
    idf = build_idf([*ON_TOPIC, *OFF_TOPIC])
    centroid = build_centroid(ON_TOPIC, idf)
    assert centroid
    on_scores = [cosine_to_vector(text, centroid, idf=idf) for text in ON_TOPIC]
    off_scores = [cosine_to_vector(text, centroid, idf=idf) for text in OFF_TOPIC]
    assert min(on_scores) > max(off_scores)


def test_centroid_of_empty_corpus_is_empty() -> None:
    assert build_centroid([], build_idf([])) == {}


def test_calibrate_drift_thresholds_returns_gap_midpoint_and_warn_below_pos_min() -> None:
    """block 取间隙中点；warn 必须落在正样本下界之下 → 两级都零误报。"""
    positives = [0.20, 0.15, 0.12, 0.10]
    negatives = [0.04, 0.06, 0.08]
    result = calibrate_drift_thresholds(positives, negatives, warn_margin=0.02)
    assert result["separable"] is True
    assert result["block"] == round((0.10 + 0.08) / 2, 4)
    assert result["warn"] < min(positives)
    # 用标定结果判定：正样本全过、负样本全中
    assert all(score >= result["warn"] for score in positives)
    assert all(score < result["block"] for score in negatives)


def test_calibrate_drift_thresholds_flags_overlap() -> None:
    """两分布重叠时必须如实标注 separable=False，而不是假装能分开。"""
    result = calibrate_drift_thresholds([0.20, 0.05], [0.04, 0.10])
    assert result["separable"] is False


def test_calibrate_threshold_picks_zero_fpr_best_recall() -> None:
    positives = [0.20, 0.15, 0.10]
    negatives = [0.02, 0.04]
    best = calibrate_threshold(positives, negatives, step=0.01)
    assert best["fpr"] == 0.0
    assert best["tpr"] == 1.0
    assert 0.04 < float(best["threshold"]) <= 0.10


def test_calibrate_drift_thresholds_handles_missing_samples() -> None:
    result = calibrate_drift_thresholds([], [])
    assert result["block"] is None and result["separable"] is False
