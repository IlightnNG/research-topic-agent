"""主题（topic）定义：scope statement 的唯一来源。

为什么单独成模块
- S5（闭环）与 S6（守卫）都要用同一个 scope statement：**G1 漂移守卫的判据就是"阶段产物 vs 这个 scope"**，
  两边各写一份必然漂移。
- Phase 1 会把它搬进 `config.yaml` 的 `topics:` 段（每个 topic 订阅集 + scope 文本）；
  本轮先用代码常量，接口（`get_topic`/`topic_scope`）保持不变即可平滑迁移。
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["TOPICS", "TopicSpec", "get_topic"]


@dataclass(frozen=True)
class TopicSpec:
    key: str
    name: str
    """面向人的主题名（报告标题、UI 展示）。"""
    scope: str
    """scope statement：G1 漂移守卫的比对基准（越具体越可判）。"""
    query: str
    """检索用的关键词串（供词法/向量检索构造查询）。"""


TOPICS: dict[str, TopicSpec] = {
    "T1": TopicSpec(
        key="T1",
        name="多智能体 LLM 编排与可靠性",
        scope=(
            "multi-agent LLM orchestration reliability coordination failure detection "
            "verification robustness agent communication benchmarks"
        ),
        query=(
            "multi-agent LLM orchestration reliability coordination failure detection "
            "verification robustness agent communication benchmarks"
        ),
    ),
    "T2": TopicSpec(
        key="T2",
        name="边缘设备 VLM 量化与部署",
        scope=(
            "edge device vision language model quantization deployment inference "
            "efficiency latency memory pruning distillation"
        ),
        query=(
            "edge device vision language model quantization deployment inference "
            "efficiency latency memory pruning distillation"
        ),
    ),
}


def get_topic(key: str) -> TopicSpec:
    try:
        return TOPICS[key]
    except KeyError:  # pragma: no cover - 由 CLI choices 兜底
        raise KeyError(f"未知 topic：{key}（可用：{', '.join(sorted(TOPICS))}）") from None
