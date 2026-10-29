"""AI venue/query suggestions（3.3 / S2）。

LLM only proposes *names*; OpenAlex resolve_venues returns real source ids.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from lit_agent.config import Settings
from lit_agent.sources.whitelist import resolve_venues

__all__ = ["suggest_sources"]


def _default_resolver(settings: Settings) -> Callable[[list[str]], dict[str, str | None]]:
    def resolve(names: list[str]) -> dict[str, str | None]:
        with httpx.Client(timeout=15.0) as client:
            return resolve_venues(
                client, names, mailto=settings.sources.openalex.mailto
            )

    return resolve


def _fallback(scope: str) -> dict[str, Any]:
    words = [word for word in scope.replace(",", " ").split() if len(word) > 3]
    return {
        "venues": [],
        "queries": [" ".join(words[:8])] if words else [scope],
        "from_year": None,
        "source": "fallback",
    }


def suggest_sources(
    settings: Settings,
    scope: str,
    *,
    gateway: Any | None = None,
    resolver: Callable[[list[str]], dict[str, str | None]] | None = None,
) -> dict[str, Any]:
    if gateway is None:
        return _fallback(scope)

    prompt = (
        "Suggest research sources for this topic. Return JSON only:\n"
        '{"venues":[str],"queries":[str],"from_year":int|null}\n'
        "Use real venue names (ACL, NeurIPS, ICML, ICLR, EMNLP...); "
        "do not invent ids; 2-4 venues and 1-3 short queries."
    )
    try:
        payload, _ = gateway.chat_json(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": scope[:1000]},
            ],
            max_tokens=300,
            agent="source_suggest",
        )
        if not isinstance(payload, dict):
            return _fallback(scope)
        names = [str(item).strip() for item in payload.get("venues") or [] if str(item).strip()][:4]
        queries = [str(item).strip() for item in payload.get("queries") or [] if str(item).strip()][:3]
        if not names:
            return _fallback(scope)
        resolve = resolver or _default_resolver(settings)
        resolved = resolve(names)
    except Exception:  # noqa: BLE001 - suggestions must not block topic creation
        return _fallback(scope)

    venues = []
    for name in names:
        source_id = resolved.get(name)
        venues.append(
            {
                "name": name,
                "source_id": source_id,
                "confidence": 0.9 if source_id else 0.0,
            }
        )
    return {
        "venues": venues,
        "queries": queries or [scope],
        "from_year": payload.get("from_year"),
        "source": "ai",
    }
