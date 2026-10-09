"""词法打分（TF-IDF 余弦）：无本地 embedding 时的统一定量口径。

为什么要有这个模块
- S5（检索排序）与 S6（G1 漂移守卫）都要"给文本相似度打分"。两处各写一份必然口径漂移，
  而 **G1 的阈值只能在同一个打分器上标定**——口径一变，阈值立刻失效。
- 因此把打分集中到这里：`tokenize` / `build_idf` / `cosine` / `rank`，纯函数、确定性、零依赖、可离线。

与 embedding 的关系（务必记住）
- 本模块是 **代理打分器**（proxy）：量纲与 embedding 余弦不可比。
  S5 实测同主题论文的词法余弦仅 0.038–0.134，而配置里按 embedding 给的阈值是 0.60/0.45 ——
  **直接套用会把全部正常样本判为漂移**（S6 实测确认）。
- Phase 1 接入 bge-m3 后，`cosine` 换成向量余弦即可，但**所有阈值必须重新标定**（本模块提供了
  `calibrate_threshold` 做这件事，标定结果记入文档）。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

__all__ = [
    "build_idf",
    "calibrate_drift_thresholds",
    "calibrate_threshold",
    "cosine",
    "cosine_to_vector",
    "build_centroid",
    "rank",
    "tokenize",
]

_WORD = re.compile(r"[a-z0-9][a-z0-9\-]+")

STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "then",
        "than",
        "that",
        "this",
        "these",
        "those",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "from",
        "with",
        "without",
        "by",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "do",
        "does",
        "did",
        "not",
        "no",
        "we",
        "our",
        "us",
        "it",
        "its",
        "their",
        "there",
        "here",
        "can",
        "could",
        "may",
        "might",
        "will",
        "would",
        "should",
        "which",
        "who",
        "whom",
        "whose",
        "what",
        "when",
        "where",
        "how",
        "all",
        "any",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "only",
        "own",
        "same",
        "so",
        "too",
        "very",
        "s",
        "t",
        "just",
        "don",
        "now",
        "also",
        "using",
        "use",
        "used",
        "based",
        "approach",
        "method",
        "results",
        "show",
        "shows",
        "paper",
        "propose",
        "proposed",
        "new",
    ]
)


def tokenize(text: str) -> list[str]:
    """小写、去停用词、保留带连字符的技术词（`multi-agent` 等）。"""
    return [t for t in _WORD.findall((text or "").lower()) if t not in STOPWORDS]


def build_idf(docs: Iterable[str]) -> dict[str, float]:
    """在给定语料上构建 IDF（`log((N+1)/(df+1)) + 1`，平滑避免零权重）。"""
    tokenized = [set(tokenize(doc)) for doc in docs]
    total = len(tokenized)
    df = Counter()
    for tokens in tokenized:
        df.update(tokens)
    return {term: math.log((total + 1) / (count + 1)) + 1.0 for term, count in df.items()}


def _weights(tokens: Sequence[str], idf: Mapping[str, float] | None) -> dict[str, float]:
    counts = Counter(tokens)
    if idf is None:
        return {term: float(count) for term, count in counts.items()}
    return {term: count * idf.get(term, 1.0) for term, count in counts.items()}


def cosine(left: str, right: str, *, idf: Mapping[str, float] | None = None) -> float:
    """TF-IDF 余弦相似度（0..1）。不传 `idf` 时退化为归一化词频余弦。"""
    a = _weights(tokenize(left), idf)
    b = _weights(tokenize(right), idf)
    if not a or not b:
        return 0.0
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if not na or not nb:
        return 0.0
    dot = sum(weight * b.get(term, 0.0) for term, weight in a.items())
    return round(min(1.0, dot / (na * nb)), 6)


def rank(
    query: str, docs: Mapping[str, str], *, idf: Mapping[str, float] | None = None
) -> list[tuple[str, float]]:
    """按与 query 的相似度降序返回 `(key, score)`（同分按 key 字典序，保证可复现）。"""
    scored = [(key, cosine(query, text, idf=idf)) for key, text in docs.items()]
    return sorted(scored, key=lambda kv: (-kv[1], kv[0]))


def build_centroid(docs: Iterable[str], idf: Mapping[str, float] | None = None) -> dict[str, float]:
    """种子语料质心（各文档 TF-IDF 向量的均值，再做 L2 归一化）。

    **为什么需要它**（S6 实测教训）：用"关键词字符串"当 scope 表示时，同主题但换了词汇的论文
    余弦会掉到 0，导致正负样本分布重叠、任何绝对阈值都无法兼顾召回与误报。
    改用**种子语料质心**表示 scope 后，正/负样本才真正可分（见 `RESULTS.md` §2.13）。
    """
    vectors = [_weights(tokenize(doc), idf) for doc in docs]
    vectors = [v for v in vectors if v]
    if not vectors:
        return {}
    centroid: Counter[str] = Counter()
    for vec in vectors:
        centroid.update(vec)
    for term in centroid:
        centroid[term] /= len(vectors)
    norm = math.sqrt(sum(v * v for v in centroid.values()))
    if not norm:
        return {}
    return {term: value / norm for term, value in centroid.items() if value}


def cosine_to_vector(
    text: str, vector: Mapping[str, float], *, idf: Mapping[str, float] | None = None
) -> float:
    """文本与（已归一化的）质心向量之间的余弦（0..1）。"""
    a = _weights(tokenize(text), idf)
    if not a or not vector:
        return 0.0
    na = math.sqrt(sum(v * v for v in a.values()))
    if not na:
        return 0.0
    dot = sum(weight * vector.get(term, 0.0) for term, weight in a.items())
    return round(min(1.0, dot / na), 6)


def calibrate_threshold(
    positives: Sequence[float],
    negatives: Sequence[float],
    *,
    step: float = 0.02,
    max_threshold: float = 1.0,
) -> dict[str, float | None]:
    """在真实正/负样本上扫描阈值，返回**零误报下召回最高**的阈值与 TPR/FPR。

    语义：分数 **低于** 阈值判为"越界/漂移"，所以 positives 应得高分、negatives 应得低分。
    """
    thresholds = [round(i * step, 4) for i in range(int(max_threshold / step) + 1)]
    best: dict[str, float | None] = {"threshold": None, "tpr": 0.0, "fpr": 0.0}
    for thr in thresholds:
        tp = sum(1 for s in negatives if s < thr)
        fp = sum(1 for s in positives if s < thr)
        tpr = tp / len(negatives) if negatives else 0.0
        fpr = fp / len(positives) if positives else 0.0
        if fpr == 0.0 and tpr > float(best["tpr"] or 0.0):
            best = {"threshold": thr, "tpr": round(tpr, 3), "fpr": round(fpr, 3)}
    return best


def calibrate_drift_thresholds(
    positives: Sequence[float],
    negatives: Sequence[float],
    *,
    warn_margin: float = 0.02,
) -> dict[str, float | bool | None]:
    """为"低分=漂移"的守卫标定 **block / warn** 两级阈值。

    为什么不能把 warn 拍成 `block × 常数`（S6 实测踩到）
    - 若 warn 落进正样本分布内部，正常产物会被 warn 级判为漂移 → **必然误报**。
      实测：block=0.08 时按 ×1.5 得 warn=0.12，而正样本最低分是 0.0885 → 3/3 正常 run 误报。
    - 正确做法是按**分布间隙**标定：
      · `block` = 间隙中点 `(max(负), min(正)) / 2` → 最大间隔，两侧都不碰；
      · `warn`  = `min(正) × (1 - warn_margin)` → 只落在间隙内、正样本之下，因此**零误报**。
    - 代价是 warn 带很窄（本轮 0.078→0.087），但这恰恰说明**正负分布分离良好**；
      若两分布重叠（`separable=False`），则退化为扫描阈值并如实标注"检测能力受限"。
    """
    if not positives or not negatives:
        return {"block": None, "warn": None, "separable": False, "note": "缺少正/负样本"}
    pos_min = min(positives)
    neg_max = max(negatives)
    separable = pos_min > neg_max
    if separable:
        block = round((pos_min + neg_max) / 2, 4)
    else:
        scanned = calibrate_threshold(positives, negatives)
        block = scanned["threshold"]
    warn = round(pos_min * (1 - warn_margin), 4) if block is not None else None
    return {
        "block": block,
        "warn": warn,
        "separable": separable,
        "pos_min": round(pos_min, 6),
        "neg_max": round(neg_max, 6),
        "gap": round(pos_min - neg_max, 6),
        "note": "block=间隙中点（最大间隔）；warn=min(正)×(1-margin)，故两级均零误报",
    }
