"""PaperCard（3.2 / S2）：每篇论文的结构化卡片 + quote 校验 + 缓存。

设计：确定性兜底优先；LLM 只做增强。任何 LLM/解析失败都回落，不阻断报告。
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import text

from lit_agent.config import Settings
from lit_agent.db.session import connect, make_engine
from lit_agent.errors import E_NOT_FOUND, E_REPORT_LLM, LitError

__all__ = ["CARD_VERSION", "PaperCard", "build_card", "get_or_build_card", "quote_ok", "source_sha"]

logger = logging.getLogger(__name__)

CARD_VERSION = 2
_MIN_QUOTE = 8


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def source_sha(title: str, text: str) -> str:
    return hashlib.sha256(f"{_norm(title)}\n{_norm(text)}".encode()).hexdigest()


def quote_ok(quote: str, source: str) -> bool:
    q = _norm(quote)
    return len(q) >= _MIN_QUOTE and q in _norm(source)


@dataclass
class PaperCard:
    paper_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    venue: str = ""
    year: int | None = None
    url: str = ""
    abstract: str = ""
    evidence_level: str = "abstract_only"  # abstract_only | full_text | missing
    problem: dict[str, Any] | None = None
    method: dict[str, Any] | None = None
    data: dict[str, Any] | None = None
    findings: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaperCard:
        return cls(**data)


def _sentence(text: str, limit: int = 240) -> str:
    return re.split(r"(?<=[.!?])\s+", _norm(text))[0][:limit]


def _deterministic(paper: dict[str, Any], text: str, limit: int) -> PaperCard:
    snippet = _sentence(text)
    findings = [{"text": snippet, "quote": snippet, "page": None}] if quote_ok(snippet, text) else []
    claims = []
    for sentence in re.split(r"(?<=[.!?])\s+", _norm(text))[:limit]:
        if quote_ok(sentence, text):
            claims.append({"text": sentence[:240], "quote": sentence, "page": None})
    return PaperCard(
        paper_id=str(paper["paper_id"]),
        title=str(paper["title"]),
        authors=list(paper.get("authors") or []),
        venue=str(paper.get("source") or ""),
        year=paper.get("year"),
        url=str(paper.get("url") or ""),
        abstract=text,
        evidence_level="abstract_only" if text else "missing",
        findings=findings,
        claims=claims,
        keywords=[],
    )


def _prompt(limit: int) -> str:
    return (
        "Extract a structured research card. Return JSON only:\n"
        '{"problem":{"text":str,"quote":str},"method":{...},"data":{...},'
        '"findings":[{"text":str,"quote":str}],"limitations":[{...}],'
        '"claims":[{"text":str,"quote":str}],"keywords":[str]}\n'
        "Rules: quote MUST be a verbatim substring of the text; use null/[] when unknown; "
        f"at most {limit} claims; never invent results."
    )


def _llm_enrich(card: PaperCard, text: str, gateway: Any, limit: int) -> PaperCard:
    payload, _call = gateway.chat_json(
        [
            {"role": "system", "content": _prompt(limit)},
            {"role": "user", "content": f"TITLE: {card.title}\nTEXT: {_norm(text)[:12000]}"},
        ],
        max_tokens=900,
        agent="report_cards",
    )
    if not isinstance(payload, dict):
        raise LitError(E_REPORT_LLM, "paper card 返回非 JSON")
    dropped = 0
    for key in ("problem", "method", "data"):
        item = payload.get(key)
        if isinstance(item, dict) and quote_ok(str(item.get("quote") or ""), text):
            card.__dict__[key] = {
                "text": str(item.get("text") or "")[:400],
                "quote": str(item.get("quote") or ""),
                "page": item.get("page"),
            }
        elif item:
            dropped += 1
    for key in ("findings", "limitations", "claims"):
        values = payload.get(key)
        if not isinstance(values, list):
            continue
        kept = []
        for item in values[:limit]:
            if isinstance(item, dict) and quote_ok(str(item.get("quote") or ""), text):
                kept.append(
                    {
                        "text": str(item.get("text") or "")[:400],
                        "quote": str(item.get("quote") or ""),
                        "page": item.get("page"),
                    }
                )
            else:
                dropped += 1
        # LLM 没有产出合法项时，保留确定性兜底（不要清空）
        if kept:
            if key == "claims":
                card.claims = kept[:limit]
            else:
                card.__dict__[key] = kept
    keywords = payload.get("keywords")
    if isinstance(keywords, list):
        card.keywords = [str(item)[:60] for item in keywords[:8]]
    card.meta.update({"llm_used": True, "dropped_quotes": dropped})
    return card


def build_card(
    settings: Settings,
    paper: dict[str, Any],
    *,
    text: str | None = None,
    gateway: Any | None = None,
) -> PaperCard:
    """构建单篇卡片；LLM 失败/quote 非法自动回落，不抛出（除 DB/编程错误）。"""
    source = (text if text is not None else paper.get("abstract") or "").strip()
    limit = settings.report.max_claims_per_paper
    card = _deterministic(paper, source, limit)
    if gateway is None or not source:
        return card

    started = time.monotonic()
    try:
        card = _llm_enrich(card, source, gateway, limit)
        logger.info(
            "paper_card.llm_ok",
            extra={"paper_id": card.paper_id, "ms": int((time.monotonic() - started) * 1000)},
        )
    except Exception as exc:  # noqa: BLE001 - LLM 不能阻断报告
        logger.warning(
            "paper_card.llm_fallback",
            extra={"paper_id": card.paper_id, "error": type(exc).__name__, "code": E_REPORT_LLM},
        )
        card.meta.update({"llm_used": False, "llm_error": type(exc).__name__})
    return card


def _load_paper(conn: Any, paper_id: str) -> dict[str, Any]:
    row = conn.execute(
        text(
            "SELECT paper_id, title, COALESCE(abstract,''), COALESCE(source,''), year"
            " FROM papers WHERE paper_id = :pid"
        ),
        {"pid": paper_id},
    ).first()
    if row is None:
        raise LitError(E_NOT_FOUND, f"paper 不存在：{paper_id}")
    authors = [
        str(item[0])
        for item in conn.execute(
            text(
                "SELECT a.name FROM authors a"
                " JOIN paper_authors pa ON pa.author_id = a.author_id"
                " WHERE pa.paper_id = :pid ORDER BY pa.position"
            ),
            {"pid": paper_id},
        ).all()
    ]
    return {
        "paper_id": row[0],
        "title": row[1],
        "abstract": row[2],
        "source": row[3],
        "year": row[4],
        "authors": authors,
    }


def get_or_build_card(
    settings: Settings,
    paper_id: str,
    *,
    gateway: Any | None = None,
    force: bool = False,
) -> PaperCard:
    """读论文 → 查缓存 → 构建 → 写缓存；缓存失败不影响返回。"""
    from lit_agent.db.repo import paper_cards as card_repo

    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            paper = _load_paper(conn, paper_id)
            sha = source_sha(paper["title"], paper["abstract"])
            if settings.report.cache and not force:
                cached = card_repo.get_card(conn, paper_id, sha, CARD_VERSION)
                if cached is not None:
                    logger.info("paper_card.cache_hit", extra={"paper_id": paper_id})
                    return PaperCard.from_dict(cached)

            started = time.monotonic()
            card = build_card(settings, paper, gateway=gateway)
            if settings.report.cache:
                try:
                    card_repo.upsert_card(
                        conn,
                        paper_id=paper_id,
                        content_sha=sha,
                        version=CARD_VERSION,
                        card=card.to_dict(),
                    )
                except Exception as exc:  # noqa: BLE001 - 缓存不是业务事实
                    logger.warning(
                        "paper_card.cache_write_failed",
                        extra={"paper_id": paper_id, "error": type(exc).__name__},
                    )
            logger.info(
                "paper_card.built",
                extra={
                    "paper_id": paper_id,
                    "ms": int((time.monotonic() - started) * 1000),
                    "claims": len(card.claims),
                    "llm": bool(card.meta.get("llm_used")),
                },
            )
            return card
    finally:
        engine.dispose()
