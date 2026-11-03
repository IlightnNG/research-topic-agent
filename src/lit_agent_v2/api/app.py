"""V2 FastAPI app: platform topics, runs, trace, report and chat."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from lit_agent_v2.interface.router import build_platform_router
from lit_agent_v2.storage.db import Database

__all__ = ["create_app"]


def _default_corpus() -> Path:
    configured = os.environ.get("LIT_V2_CORPUS")
    candidates = [
        Path(configured) if configured else None,
        Path("D:/lit-agent-store/v2-eval/gold/corpora/agents-fulltext"),
        Path("D:/lit-agent-store/v2-live/corpus"),
        Path("D:/lit-agent-store/v2/corpus"),
    ]
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate
    return Path(configured or "D:/lit-agent-store/v2/corpus")


def create_app(
    *,
    db_path: str | Path | None = None,
    corpus_root: str | Path | None = None,
    platform_llm=None,
) -> FastAPI:
    db = Database(db_path or os.environ.get("LIT_V2_DB", "D:/lit-agent-store/v2/v2.sqlite"))
    db.migrate()
    corpus = Path(corpus_root) if corpus_root is not None else _default_corpus()
    app = FastAPI(title="lit-agent-v2")
    app.include_router(
        build_platform_router(db, corpus_root=corpus, llm=platform_llm)
    )

    def error_response(status: int, code: str, message: str, **details: Any) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            content={"error": {"code": code, "message": message, "details": details}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = str(exc.detail) if str(exc.detail).startswith("E_") else "E_HTTP"
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(422, "E_INVALID_REQUEST", "request validation failed", errors=exc.errors())

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception) -> JSONResponse:
        return error_response(500, "E_INTERNAL", "internal error")

    @app.get("/api/v2/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "tables": len(db.table_names())}

    return app
