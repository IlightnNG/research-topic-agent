"""方向综合（3.2 / S5）：LLM 只写“共性/差异/问题”，claim_id 必须受控。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from lit_agent.models.claim import Claim
from lit_agent.report.clusters import Direction

__all__ = ["DirectionInsight", "synthesize_all", "synthesize_direction"]

logger = logging.getLogger(__name__)


@dataclass
class InsightItem:
    text: str
    claim_ids: list[str] = field(default_factory=list)


@dataclass
class DirectionInsight:
    direction_id: str
    name: str
    definition: str = ""
    common_ground: list[InsightItem] = field(default_factory=list)
    differences: list[InsightItem] = field(default_factory=list)
    open_questions: list[InsightItem] = field(default_factory=list)
    generated_by: str = "template"


def _claim_texts(claims: list[Claim]) -> dict[str, str]:
    return {claim.claim_id: claim.text for claim in claims if claim.claim_id}


def _fallback(direction: Direction, claims: list[Claim], language: str) -> DirectionInsight:
    by_id = _claim_texts(claims)
    common = [
        InsightItem(text=by_id[cid], claim_ids=[cid])
        for cid in direction.claim_ids
        if cid in by_id
    ][:3]
    return DirectionInsight(
        direction_id=direction.id,
        name=direction.name,
        definition=direction.definition,
        common_ground=common,
    )


def _valid_items(values: Any, allowed: set[str], *, min_refs: int = 1) -> list[InsightItem]:
    if not isinstance(values, list):
        return []
    kept: list[InsightItem] = []
    for item in values[:8]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        ids = [str(cid) for cid in (item.get("claim_ids") or []) if str(cid) in allowed]
        if not text or len(ids) < min_refs:
            continue
        kept.append(InsightItem(text=text[:500], claim_ids=ids))
    return kept


def synthesize_direction(
    direction: Direction,
    claims: list[Claim],
    *,
    gateway: Any | None = None,
    language: str = "en",
    max_tokens: int = 1000,
) -> DirectionInsight:
    if gateway is None:
        return _fallback(direction, claims, language)

    by_id = _claim_texts(claims)
    allowed = set(direction.claim_ids) & set(by_id)
    material = "\n".join(f"[{cid}] {by_id[cid][:300]}" for cid in sorted(allowed))
    prompt = (
        "Synthesize one research direction. Return JSON only:\n"
        '{"definition":str,"common_ground":[{"text":str,"claim_ids":[str]}],'
        '"differences":[{"text":str,"claim_ids":[str]}],"open_questions":[{"text":str,"claim_ids":[str]}]}\n'
        "Rules: use only the given [claim_id] items; every item needs >=1 claim id; "
        "differences need >=2 different claim ids; no new facts; "
        f"write in {'Chinese' if language == 'zh' else 'English'}."
    )
    try:
        payload, _ = gateway.chat_json(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Direction: {direction.name}\n{material}"},
            ],
            max_tokens=max_tokens,
            agent="report_synthesis",
        )
        if not isinstance(payload, dict):
            raise ValueError("non-dict")
        common = _valid_items(payload.get("common_ground"), allowed)
        differences = _valid_items(payload.get("differences"), allowed, min_refs=2)
        questions = _valid_items(payload.get("open_questions"), allowed)
        if not common and not differences:
            raise ValueError("empty synthesis")
        return DirectionInsight(
            direction_id=direction.id,
            name=direction.name,
            definition=str(payload.get("definition") or direction.definition)[:400],
            common_ground=common,
            differences=differences,
            open_questions=questions,
            generated_by="llm",
        )
    except Exception as exc:  # noqa: BLE001 - 单方向失败回落
        logger.warning(
            "report.synthesis.fallback",
            extra={"direction": direction.id, "error": type(exc).__name__},
        )
        return _fallback(direction, claims, language)


def synthesize_all(
    directions: list[Direction],
    claims: list[Claim],
    *,
    gateway: Any | None = None,
    language: str = "en",
    max_tokens: int = 1000,
) -> list[DirectionInsight]:
    insights = [
        synthesize_direction(
            direction, claims, gateway=gateway, language=language, max_tokens=max_tokens
        )
        for direction in directions
    ]
    logger.info(
        "report.synthesis.done",
        extra={
            "directions": len(insights),
            "llm": sum(1 for item in insights if item.generated_by == "llm"),
        },
    )
    return insights
