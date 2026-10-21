"""分析 agent（S6）：证据卡 → claims（每条必带引用）。

两条路径
- **确定性**（默认）：一卡一 claim，`support=supported`，citation 指向该卡；
- **LLM 抽取**（传入 gateway）：要求返回 JSON 数组，逐条校验 `paper_id`
  必须来自输入卡片；不合格条目直接丢弃（宁少不假）。
"""

from __future__ import annotations

import json
from typing import Any

from lit_agent.models.claim import Claim
from lit_agent.models.evidence import Citation, EvidenceCard, Support

__all__ = ["analyze", "analyze_with_llm", "claims_from_json", "claims_to_json", "run"]

MAX_CLAIMS = 50


def _deterministic(cards: list[EvidenceCard]) -> list[Claim]:
    claims: list[Claim] = []
    seen: set[str] = set()
    for card in cards:
        text = f"{card.title} — {card.snippet}".strip()
        if text in seen:
            continue
        seen.add(text)
        claims.append(
            Claim(
                text=text[:500],
                citations=[Citation(paper_id=card.paper_id, snippet=card.snippet)],
                support=Support.SUPPORTED,
            )
        )
        if len(claims) >= MAX_CLAIMS:
            break
    return claims


def analyze_with_llm(cards: list[EvidenceCard], gateway: Any) -> list[Claim]:
    """严格校验引用：非法条目丢弃；解析失败回落到确定性路径。"""
    if not cards:
        return []
    allowed = {card.paper_id for card in cards}
    material = "\n".join(
        f"[{card.paper_id}] {card.title}: {card.snippet[:300]}" for card in cards[:20]
    )
    payload, _call = gateway.chat_json(
        [
            {
                "role": "system",
                "content": (
                    "Extract 3-8 atomic claims. Return JSON: "
                    '{"claims":[{"text":str,"paper_id":str,"quote":str}]}. '
                    "Every claim MUST reference one of the given paper ids."
                ),
            },
            {"role": "user", "content": material},
        ],
        max_tokens=800,
        agent="analyst",
    )
    raw = payload.get("claims") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        return _deterministic(cards)
    claims: list[Claim] = []
    for item in raw[:MAX_CLAIMS]:
        if not isinstance(item, dict):
            continue
        paper_id = str(item.get("paper_id") or "")
        text = str(item.get("text") or "").strip()
        if paper_id not in allowed or not text:
            continue
        quote = str(item.get("quote") or "")
        claims.append(
            Claim(
                text=f"{text}（{paper_id}）",
                citations=[Citation(paper_id=paper_id, snippet=quote[:400] or None)],
                support=Support.SUPPORTED,
            )
        )
    return claims or _deterministic(cards)


def analyze(cards: list[EvidenceCard], *, gateway: Any | None = None) -> list[Claim]:
    if gateway is not None:
        try:
            return analyze_with_llm(cards, gateway)
        except Exception:  # noqa: BLE001 - LLM 失败必须回落，不能整轮失败
            return _deterministic(cards)
    return _deterministic(cards)


def claims_to_json(claims: list[Claim]) -> str:
    return json.dumps([claim.model_dump(mode="json") for claim in claims], ensure_ascii=False)


def claims_from_json(blob: str) -> list[Claim]:
    return [Claim.model_validate(item) for item in json.loads(blob or "[]")]


def run(state: dict[str, Any], *, cards: list[EvidenceCard] | None = None, **_: Any) -> dict[str, Any]:
    claims = analyze(cards or [])
    return {
        "artifacts": {
            "claims": len(claims),
            "claims_json": claims_to_json(claims),
            "citations": sum(len(claim.citations) for claim in claims),
        },
        "counters": {"claims": len(claims)},
    }
