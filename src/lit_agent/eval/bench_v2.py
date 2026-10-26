"""3.5 / S21：bench v2（30 条查询 + 10 个脚本场景）。

说明：查询是**合成**的（覆盖 focus/无 focus/冷门词/长查询），用于回归与消融，
不是人工标注的 gold；gold 仍是 `eval.datasets.GOLD`（20 条）。
冻结哈希由 `scripts/verify_phase3.py --frozen-v2` 校验；改内容必须升版本并记录。
"""

from __future__ import annotations

import hashlib
import json

__all__ = ["BENCH_V2_SHA256", "SCENARIOS", "QUERIES", "bench_canonical", "bench_sha"]

_TOPICS = [
    ("tool use", "task success"),
    ("retrieval augmentation", "answer faithfulness"),
    ("multi agent debate", "reasoning accuracy"),
    ("memory modules", "long horizon coherence"),
    ("planner critic loops", "error recovery"),
    ("context compression", "cost efficiency"),
    ("citation grounding", "hallucination reduction"),
    ("graph mapping", "author disambiguation"),
    ("weekly reporting", "coverage of new work"),
    ("focus hints", "retrieval precision"),
]

QUERIES: tuple[dict[str, object], ...] = tuple(
    [
        {
            "id": f"q-{index:02d}",
            "topic": "ai-agents",
            "focus": None if index % 5 == 0 else f"{topic} {detail}",
            "cold": index % 7 == 0,
            "long": index % 11 == 0,
        }
        for index, (topic, detail) in enumerate(_TOPICS, start=1)
    ]
    + [
        {
            "id": f"q-{index:02d}",
            "topic": "ai-agents",
            "focus": f"{topic} evaluation",
            "cold": False,
            "long": False,
        }
        for index, (topic, _detail) in enumerate(_TOPICS, start=11)
    ]
    + [
        {
            "id": f"q-{index:02d}",
            "topic": "ai-agents",
            "focus": None if index % 2 else f"{topic} survey",
            "cold": True,
            "long": index % 3 == 0,
        }
        for index, (topic, _detail) in enumerate(_TOPICS, start=21)
    ]
)

SCENARIOS: tuple[dict[str, object], ...] = (
    {"id": "s-healthy", "fault": None, "expect": "succeeded"},
    {"id": "s-empty-retrieval", "fault": "empty_retrieval", "expect": "degraded"},
    {"id": "s-bad-artifact", "fault": "bad_artifact", "expect": "succeeded"},
    {"id": "s-timeout", "fault": "timeout", "expect": "failed"},
    {"id": "s-budget", "fault": "budget", "expect": "aborted"},
    {"id": "s-max-steps", "fault": "max_steps", "expect": "degraded"},
    {"id": "s-no-progress", "fault": "no_progress", "expect": "degraded"},
    {"id": "s-cancel", "fault": "cancel", "expect": "aborted"},
    {"id": "s-inject", "fault": "inject", "expect": "succeeded"},
    {"id": "s-resume", "fault": "crash_resume", "expect": "succeeded"},
)


def bench_canonical() -> str:
    payload = {"queries": list(QUERIES), "scenarios": list(SCENARIOS)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def bench_sha() -> str:
    return hashlib.sha256(bench_canonical().encode("utf-8")).hexdigest()


#: 冻结哈希（2026-10-26 首版）
BENCH_V2_SHA256 = "8ec94db92e3b15ae33893a49a241324886e81ceab69e15b30202f7df26547fb4"
