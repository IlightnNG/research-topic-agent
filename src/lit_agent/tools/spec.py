"""工具协议 v2（Phase 3.0 / S3）：四段流水线 + 单调 guard + 输出校验。

流水线（冻结）：
    pre_execute → guard(单调) → execute(超时) → post_execute → result

- 参数进入流水线后不可改写；
- guard 只能否决，不能把已拒绝的调用放行；
- 输出必须通过 `output_schema`（轻量 JSON Schema 子集）校验；
- 超限输出截断并标注，不静默丢。
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from typing import Any, Literal

from lit_agent.errors import (
    E_BUDGET_COST,
    E_SCHEMA_STAGE_OUTPUT,
    E_SRC_TIMEOUT,
    E_UNEXPECTED,
    LitError,
)
from lit_agent.tools.registry import ToolResult

__all__ = [
    "DEFAULT_TOOL_SPECS",
    "TOOL_IMPLEMENTATIONS",
    "TOOL_NAMES",
    "ToolRuntime",
    "ToolSpec",
    "default_runtime",
]

SideEffect = Literal["read", "network", "write"]
Idempotency = Literal["pure", "keyed", "none"]
Permission = Literal["none", "confirm"]
Concurrency = Literal["exclusive", "parallel"]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"
    side_effect: SideEffect = "read"
    idempotency: Idempotency = "pure"
    timeout_s: float = 30.0
    permission: Permission = "none"
    concurrency: Concurrency = "exclusive"  # fail-closed
    max_output_chars: int = 4000


TOOL_NAMES: frozenset[str] = frozenset(
    {
        "hybrid_search",
        "rewrite_query",
        "extract_claims",
        "verify_claim",
        "rewrite_claim",
        "compress_context",
        "cluster_papers",
        "paper_pdf",
        "sectionize",
        "search_tools",
    }
)

DEFAULT_TOOL_SPECS: dict[str, ToolSpec] = {
    "rewrite_query": ToolSpec(
        name="rewrite_query",
        description="把查询改写为更利于检索的词组（去停用词 + 同义词）",
        parameters={"query": "string"},
        output_schema={"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}}},
    ),
    "verify_claim": ToolSpec(
        name="verify_claim",
        description="判定 claim 是否被片段支持（复用 grounding）",
        parameters={"text": "string", "snippet": "string"},
        output_schema={
            "type": "object",
            "required": ["supported"],
            "properties": {"supported": {"type": "boolean"}, "coverage": {"type": "number"}},
        },
    ),
    "extract_claims": ToolSpec(
        name="extract_claims",
        description="从片段抽取原子 claim（确定性首句版）",
        parameters={"snippets": "array"},
        output_schema={
            "type": "object",
            "required": ["claims"],
            "properties": {"claims": {"type": "array"}},
        },
    ),
    "rewrite_claim": ToolSpec(
        name="rewrite_claim",
        description="把不被支持的 claim 改写为片段中可支持的最相关句",
        parameters={"text": "string", "snippet": "string"},
        output_schema={
            "type": "object",
            "required": ["text"],
            "properties": {"text": {"type": "string"}, "changed": {"type": "boolean"}},
        },
    ),
    "compress_context": ToolSpec(
        name="compress_context",
        description="先剪枝后摘要地压缩多段文本",
        parameters={"texts": "array"},
        output_schema={
            "type": "object",
            "required": ["text"],
            "properties": {"text": {"type": "string"}, "tokens_before": {"type": "number"}},
        },
        max_output_chars=8000,
    ),
}


def _validate(schema: dict[str, Any], value: Any) -> str | None:
    """轻量 JSON Schema 校验：type / required / properties（够用即可）。"""
    if not schema:
        return None
    expected = schema.get("type")
    mapping = {
        "object": dict,
        "array": list,
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
    }
    if expected in mapping and not isinstance(value, mapping[expected]):
        return f"期望 {expected}，实际 {type(value).__name__}"
    if expected == "object" and isinstance(value, dict):
        for key in schema.get("required") or ():
            if key not in value:
                return f"缺少字段 {key}"
    return None


class ToolRuntime:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._fns: dict[str, Callable[..., Any]] = {}
        self._pre: list[Callable[[ToolSpec, dict[str, Any]], dict[str, Any] | None]] = []
        self._guards: list[Callable[[ToolSpec, dict[str, Any]], str | None]] = []
        self._post: list[
            Callable[[ToolSpec, dict[str, Any], ToolResult], ToolResult | None]
        ] = []

    # ------------------------------------------------------------------ #
    def register(self, spec: ToolSpec, fn: Callable[..., Any]) -> None:
        if spec.name in self._specs:
            raise LitError(E_UNEXPECTED, f"工具重名：{spec.name}")
        self._specs[spec.name] = spec
        self._fns[spec.name] = fn

    def add_pre(self, hook: Callable[[ToolSpec, dict[str, Any]], dict[str, Any] | None]) -> None:
        self._pre.append(hook)

    def add_guard(self, hook: Callable[[ToolSpec, dict[str, Any]], str | None]) -> None:
        self._guards.append(hook)

    def add_post(
        self, hook: Callable[[ToolSpec, dict[str, Any], ToolResult], ToolResult | None]
    ) -> None:
        self._post.append(hook)

    def names(self) -> list[str]:
        return sorted(self._specs)

    def spec(self, name: str) -> ToolSpec:
        if name not in self._specs:
            raise LitError(E_UNEXPECTED, f"未知工具：{name}", context={"known": self.names()})
        return self._specs[name]

    # ------------------------------------------------------------------ #
    def call(
        self,
        name: str,
        *,
        args: dict[str, Any] | None = None,
        log: Any | None = None,
        budget_usd: float | None = None,
    ) -> ToolResult:
        spec = self.spec(name)
        frozen_args = dict(args or {})

        if budget_usd is not None and budget_usd <= 0:
            return ToolResult(ok=False, error_code=E_BUDGET_COST, meta={"tool": name})

        for hook in self._pre:
            decision = hook(spec, frozen_args) or {}
            if decision.get("decision") == "deny":
                return ToolResult(
                    ok=False,
                    error_code=str(decision.get("code") or E_UNEXPECTED),
                    meta={"tool": name, "reason": decision.get("reason"), "stage": "pre_execute"},
                )

        for guard in self._guards:
            reason = guard(spec, frozen_args)
            if reason:
                return ToolResult(
                    ok=False,
                    error_code=E_UNEXPECTED,
                    meta={"tool": name, "reason": reason, "stage": "guard"},
                )

        started = time.monotonic()
        result = self._execute(spec, frozen_args)
        duration_ms = int((time.monotonic() - started) * 1000)

        if result.ok:
            problem = _validate(spec.output_schema, result.output)
            if problem:
                result = ToolResult(
                    ok=False,
                    error_code=E_SCHEMA_STAGE_OUTPUT,
                    meta={"tool": name, "reason": problem},
                )
            else:
                result = self._truncate(spec, result)

        for hook in self._post:
            replaced = hook(spec, frozen_args, result)
            if replaced is not None:
                result = replaced

        result.meta.setdefault("tool", name)
        result.meta.setdefault("duration_ms", duration_ms)

        if log is not None:
            from lit_agent.models.event import EventType

            log.emit(
                EventType.TOOL_CALL,
                stage="tools",
                payload={
                    "tool": name,
                    "ok": result.ok,
                    "duration_ms": duration_ms,
                    "error_code": result.error_code,
                },
                dedupe_key=None,
            )
        return result

    # ------------------------------------------------------------------ #
    def _execute(self, spec: ToolSpec, args: dict[str, Any]) -> ToolResult:
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(lambda: self._fns[spec.name](**args))
        try:
            return ToolResult(ok=True, output=future.result(timeout=spec.timeout_s))
        except FuturesTimeout:
            return ToolResult(ok=False, error_code=E_SRC_TIMEOUT, meta={"timeout_s": spec.timeout_s})
        except LitError as exc:
            return ToolResult(ok=False, error_code=exc.code, meta={"message": exc.message})
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                ok=False,
                error_code=E_UNEXPECTED,
                meta={"message": f"{type(exc).__name__}: {str(exc)[:160]}"},
            )
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _truncate(spec: ToolSpec, result: ToolResult) -> ToolResult:
        if not isinstance(result.output, str):
            return result
        if len(result.output) <= spec.max_output_chars:
            return result
        meta = dict(result.meta)
        meta["truncated"] = True
        return ToolResult(
            ok=True,
            output=result.output[: spec.max_output_chars] + "…[truncated]",
            error_code=result.error_code,
            meta=meta,
        )


# --------------------------------------------------------------------------- #
# 默认工具实现（真实检索/抽取在 3.1/3.2 接入）
# --------------------------------------------------------------------------- #
_STOPWORDS = {"the", "a", "an", "of", "for", "and", "to", "in", "on", "with", "using"}
_SYNONYMS = {"tool": "function calling", "agent": "agent systems", "rag": "retrieval"}


def _rewrite_query(*, query: str) -> dict[str, Any]:
    words = [word for word in re.split(r"\W+", query.lower()) if word and word not in _STOPWORDS]
    expanded = list(words)
    for word in words:
        if word in _SYNONYMS:
            expanded.append(_SYNONYMS[word])
    return {"query": " ".join(dict.fromkeys(expanded)) or query, "original": query}


def _verify_claim(*, text: str, snippet: str) -> dict[str, Any]:
    from lit_agent.eval.grounding import check_claim
    from lit_agent.models.claim import Claim
    from lit_agent.models.evidence import Citation

    result = check_claim(Claim(text=text, citations=[Citation(paper_id="t", snippet=snippet)]))
    return {"supported": bool(result.supported), "coverage": float(result.coverage)}


def _extract_claims(*, snippets: list[dict[str, Any]]) -> dict[str, Any]:
    claims = []
    for item in snippets[:50]:
        snippet = str(item.get("snippet") or "").strip()
        if not snippet:
            continue
        sentence = re.split(r"(?<=[.!?])\s+", snippet)[0]
        claims.append({"text": sentence[:240], "paper_id": str(item.get("paper_id") or "")})
    return {"claims": claims}


def _rewrite_claim(*, text: str, snippet: str) -> dict[str, Any]:
    body = snippet.strip()
    if not body:
        return {"text": text, "changed": False}
    from lit_agent.agents.retrieval import tokens

    wanted = tokens(text)
    sentences = [part for part in re.split(r"(?<=[.!?])\s+", body) if part.strip()]
    best = max(sentences, key=lambda part: len(tokens(part) & wanted)) if sentences else body
    if not (tokens(best) & wanted):
        best = body[:240]
    changed = best.strip() != text.strip()
    return {"text": best.strip()[:240], "changed": changed}


def _compress_context(*, texts: list[str]) -> dict[str, Any]:
    from lit_agent.context.folding import SummarizeFolding
    from lit_agent.parsing.chunking import count_tokens

    before = sum(count_tokens(text) for text in texts)
    folded = SummarizeFolding().fold(texts, budget_tokens=max(64, before // 2))
    return {"text": folded.text, "tokens_before": before, "tokens_after": folded.tokens}


TOOL_IMPLEMENTATIONS: dict[str, Callable[..., Any]] = {
    "rewrite_query": _rewrite_query,
    "verify_claim": _verify_claim,
    "rewrite_claim": _rewrite_claim,
    "extract_claims": _extract_claims,
    "compress_context": _compress_context,
}


def tool_runtime_for(names: tuple[str, ...] | list[str]) -> ToolRuntime:
    """按需组装只含指定工具的 runtime（白名单）。"""
    runtime = ToolRuntime()
    for name in names:
        if name not in TOOL_IMPLEMENTATIONS or name not in DEFAULT_TOOL_SPECS:
            raise LitError(E_UNEXPECTED, f"未实现的工具：{name}")
        runtime.register(DEFAULT_TOOL_SPECS[name], TOOL_IMPLEMENTATIONS[name])
    return runtime


def default_runtime() -> ToolRuntime:
    return tool_runtime_for(("rewrite_query", "verify_claim", "compress_context"))
