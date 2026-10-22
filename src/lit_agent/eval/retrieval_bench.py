"""S10：检索评测基准（20 条查询 + 40 篇语料）。

设计意图：查询词与语料用**形态相近但不同词**表达（invoke / invocation / invoking），
因此"纯词面"会漏，而 char-ngram 向量能捞回来 —— 这样 hybrid vs keyword 的差异是
**可测的**，而不是靠调参调出来的。
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CORPUS", "QUERIES", "Query", "evaluate", "recall_at_k"]


@dataclass(frozen=True)
class Query:
    text: str
    expected: str  # 期望命中的 paper_id


#: 40 篇语料（8 组形态变体 × 5 篇噪声）
CORPUS: dict[str, str] = {
    "P01": "function calling for language agents improves task success",
    "P02": "tool invocation policies in agent frameworks",
    "P03": "invoking external APIs with LLM planners",
    "P04": "planner based orchestration of tool calls",
    "P05": "planning and re planning in agent loops",
    "P06": "retrieval augmented generation keeps answers faithful",
    "P07": "compressive context cuts inference cost",
    "P08": "citation grounded output fights hallucinated text",
    "P09": "multi agent debating improves reasoning accuracy",
    "P10": "memories for long horizon coherence",
    "N01": "protein folding kinetics studied with cryo electron microscopy",
    "N02": "galaxy rotation curves and dark matter halos",
    "N03": "crop yield prediction from satellite imagery",
    "N04": "earthquake early warning with seismometer arrays",
    "N05": "market microstructure and limit order books",
    "N06": "catalyst design with density functional theory",
    "N07": "battery degradation modelling for electric vehicles",
    "N08": "urban heat islands and building energy use",
    "N09": "speech enhancement with beamforming microphone arrays",
    "N10": "genome wide association of rare variants",
    "N11": "reinforcement learning for robotics locomotion",
    "N12": "graph neural networks for molecule property prediction",
    "N13": "compiler optimisation for vectorised kernels",
    "N14": "distributed consensus under network partitions",
    "N15": "recommender systems with implicit feedback",
    "N16": "time series forecasting with state space models",
    "N17": "fairness auditing of ranking algorithms",
    "N18": "differential privacy in federated learning",
    "N19": "causal inference with instrumental variables",
    "N20": "text to speech prosody modelling",
    "N21": "code search with learned embeddings",
    "N22": "database query optimisation with sketches",
    "N23": "wireless scheduling under interference",
    "N24": "optical network fault localisation",
    "N25": "hardware verification with symbolic execution",
    "N26": "energy aware scheduling in data centres",
    "N27": "graph partitioning for parallel computing",
    "N28": "numerical stability of iterative solvers",
    "N29": "sensor calibration for autonomous driving",
    "N30": "anomaly detection in industrial telemetry",
}

#: 20 条查询：每条期望命中 1 篇（形态变体，纯词面易漏）
QUERIES: tuple[Query, ...] = (
    Query("tool invocation policy", "P02"),
    Query("invoking external tools", "P03"),
    Query("planner orchestration of calls", "P04"),
    Query("re planning loops", "P05"),
    Query("faithfulness", "P06"),
    Query("compression", "P07"),
    Query("hallucination", "P08"),
    Query("debate", "P09"),
    Query("memory", "P10"),
    Query("function calling success", "P01"),
    Query("protein folding microscopy", "N01"),
    Query("galaxy rotation dark matter", "N02"),
    Query("crop yield satellite", "N03"),
    Query("earthquake early warning", "N04"),
    Query("limit order books", "N05"),
    Query("density functional catalyst", "N06"),
    Query("battery degradation electric", "N07"),
    Query("urban heat building energy", "N08"),
    Query("beamforming speech enhancement", "N09"),
    Query("rare variant association", "N10"),
)


def recall_at_k(ranker, k: int = 10) -> float:  # noqa: ANN001 - 接受任意 ranker
    hits = 0
    for query in QUERIES:
        ranked = ranker(query.text, k)
        if query.expected in [paper_id for paper_id, _ in ranked]:
            hits += 1
    return hits / len(QUERIES)


def evaluate() -> dict[str, float]:
    """返回 keyword / hybrid 的 recall@10（给测试与探针共用）。"""
    from lit_agent.agents.hybrid import char_ngrams, cosine, keyword_score

    ids = list(CORPUS)

    def keyword_rank(text: str, k: int) -> list[tuple[str, float]]:
        scores = [(pid, keyword_score_text(pid, text)) for pid in ids]
        return sorted(scores, key=lambda item: (-item[1], item[0]))[:k]

    def keyword_score_text(pid: str, text: str) -> float:
        from lit_agent.models.evidence import EvidenceCard

        return keyword_score(
            EvidenceCard(paper_id=pid, title=CORPUS[pid], snippet=CORPUS[pid], source="bench"), text
        )

    def hybrid_rank(text: str, k: int) -> list[tuple[str, float]]:
        grams = char_ngrams(text)
        scores = [
            (
                pid,
                0.6 * keyword_score_text(pid, text) + 0.4 * cosine(grams, char_ngrams(CORPUS[pid])),
            )
            for pid in ids
        ]
        return sorted(scores, key=lambda item: (-item[1], item[0]))[:k]

    return {
        "keyword_recall": round(recall_at_k(keyword_rank), 4),
        "hybrid_recall": round(recall_at_k(hybrid_rank), 4),
        "queries": float(len(QUERIES)),
    }
