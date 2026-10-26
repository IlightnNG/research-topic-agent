"""3.4 / S18：工具检索 top-k 命中率 ≥80%（20 例以内）。"""

from __future__ import annotations

from lit_agent.tools.spec import ToolRuntime, ToolSpec

CASES: list[tuple[str, str]] = [
    ("rewrite query for retrieval", "rewrite_query"),
    ("search the web for papers", "web_search"),
    ("fetch a URL", "fetch_url"),
    ("extract claims from text", "extract_claims"),
    ("verify citation support", "verify_claim"),
    ("rewrite an unsupported claim", "rewrite_claim"),
    ("compress long context", "compress_context"),
    ("read a local PDF file", "read_pdf"),
    ("send email notification", "send_email"),
    ("summarize a document", "summarize"),
]

TOOLS = [
    ("rewrite_query", "rewrite a user query with synonyms", "read"),
    ("web_search", "search the web for relevant pages", "network"),
    ("fetch_url", "fetch a URL and return text", "network"),
    ("extract_claims", "extract atomic claims from text", "read"),
    ("verify_claim", "verify whether a claim is supported", "read"),
    ("rewrite_claim", "rewrite an unsupported claim", "read"),
    ("compress_context", "compress long context to a budget", "read"),
    ("read_pdf", "read a local PDF file", "read"),
    ("send_email", "send an email notification", "write"),
    ("summarize", "summarize a document", "read"),
]


def build() -> ToolRuntime:
    runtime = ToolRuntime()
    for name, description, side_effect in TOOLS:
        runtime.register(
            ToolSpec(name=name, description=description, side_effect=side_effect),  # type: ignore[arg-type]
            lambda **_: {"ok": True},
        )
    return runtime


def test_search_hit_rate_at_least_80_percent() -> None:
    runtime = build()
    hits = 0
    for query, expected in CASES:
        top = [spec.name for spec in runtime.search(query, k=3)]
        if expected in top:
            hits += 1
    assert hits / len(CASES) >= 0.8, hits


def test_search_returns_empty_for_unknown_query() -> None:
    assert build().search("zzz qqq", k=3) == []


def test_search_respects_k() -> None:
    assert len(build().search("claim", k=2)) == 2
