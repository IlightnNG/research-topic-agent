"""LLM judge（S11 落地，S6 先给可测的最小实现）。

- 有 completer 时调模型返回 `supported` / `unsupported`；
- 无 completer 或调用失败 → 回落 `eval.grounding.check_claim`（可解释、零成本）；
- `kappa()` 计算 judge 与人工标签的一致度（Cohen's κ）。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lit_agent.eval.grounding import check_claim
from lit_agent.models.claim import Claim
from lit_agent.models.evidence import Citation

__all__ = ["agreement", "judge", "judge_gold", "kappa"]

Completer = Callable[..., dict[str, Any]]


def judge(claim: Claim, snippet: str = "", *, completer: Completer | None = None) -> dict[str, Any]:
    if completer is not None:
        try:
            response = completer(
                messages=[
                    {
                        "role": "system",
                        "content": 'Decide if the snippet supports the claim. Return JSON {"verdict":"supported"|"unsupported"}.',
                    },
                    {"role": "user", "content": f"CLAIM: {claim.text}\nSNIPPET: {snippet}"},
                ]
            )
            content = str(
                (response.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            )
            lowered = content.lower()
            if "unsupported" in lowered:
                return {"verdict": "unsupported", "used": "llm"}
            if "supported" in lowered:
                return {"verdict": "supported", "used": "llm"}
        except Exception:  # noqa: BLE001 - judge 失败回落，不阻断流程
            pass
    result = check_claim(claim, [snippet] if snippet else None)
    return {"verdict": "supported" if result.supported else "unsupported", "used": "grounding"}


def agreement(labels_a: list[str], labels_b: list[str]) -> float:
    if not labels_a or len(labels_a) != len(labels_b):
        return 0.0
    same = sum(1 for left, right in zip(labels_a, labels_b, strict=True) if left == right)
    return same / len(labels_a)


def kappa(labels_a: list[str], labels_b: list[str]) -> float:
    """Cohen's κ（两标注者、二分类）。"""
    if not labels_a or len(labels_a) != len(labels_b):
        return 0.0
    total = len(labels_a)
    observed = agreement(labels_a, labels_b)
    p_a = sum(1 for label in labels_a if label == "supported") / total
    p_b = sum(1 for label in labels_b if label == "supported") / total
    expected = p_a * p_b + (1 - p_a) * (1 - p_b)
    if expected >= 1.0:
        return 1.0 if observed >= 1.0 else 0.0
    return round((observed - expected) / (1 - expected), 4)


def judge_gold(items: list[Any], *, completer: Completer | None = None) -> dict[str, Any]:
    """对 gold 集跑 judge，返回一致率与 κ（以标注为"人类"标签）。"""
    human: list[str] = []
    predicted: list[str] = []
    for item in items:
        claim = Claim(
            text=item.claim,
            citations=[Citation(paper_id="gold", snippet=item.snippet)],
        )
        human.append(item.label)
        predicted.append(str(judge(claim, item.snippet, completer=completer)["verdict"]))
    return {"agreement": agreement(human, predicted), "kappa": kappa(human, predicted)}
