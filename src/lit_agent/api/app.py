"""FastAPI 装配：异常映射、CORS、路由挂载。

异常 → HTTP：`E_LOCK_HELD` 409 / `E_FEATURE_DISABLED` 501 / `E_NOT_FOUND` 404 /
`E_CONFIG_INVALID` 400 / 其余 500（带 `code`）。**未实现功能必须是 501 而不是 404**
（前端要能区分"没有"与"还没做"）。
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from lit_agent._version import __version__
from lit_agent.api.routes import (
    authors,
    chat,
    graph,
    health,
    metrics,
    papers,
    reports,
    runs,
    sources,
    topics,
    workflow,
)
from lit_agent.config import Settings, load_settings
from lit_agent.errors import (
    E_CONFIG_INVALID,
    E_FEATURE_DISABLED,
    E_LOCK_HELD,
    E_NOT_FOUND,
    LitError,
)

__all__ = ["app", "create_app"]

_STATUS = {
    E_LOCK_HELD: 409,
    E_FEATURE_DISABLED: 501,
    E_NOT_FOUND: 404,
    E_CONFIG_INVALID: 400,
}


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or load_settings()
    app = FastAPI(title="lit-agent API", version=__version__)
    app.state.settings = resolved
    app.state.engine = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:8000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(LitError)
    async def _lit_error(request: Request, exc: LitError) -> JSONResponse:
        from lit_agent.i18n import resolve_locale, translate_error

        payload = exc.to_dict()
        payload["message"] = translate_error(
            exc.code,
            resolve_locale(request.headers.get("accept-language")),
            fallback=str(payload.get("message") or ""),
        )
        return JSONResponse(status_code=_STATUS.get(exc.code, 500), content=payload)

    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(topics.router, prefix="/api/topics", tags=["topics"])
    app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
    app.include_router(reports.router, prefix="/api/topics", tags=["reports"])
    app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
    app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
    app.include_router(chat.router, prefix="/api/topics", tags=["chat"])
    app.include_router(workflow.router, tags=["workflow"])
    app.include_router(graph.router, prefix="/api/graph", tags=["graph"])
    app.include_router(papers.router, prefix="/api/papers", tags=["papers"])
    app.include_router(authors.router, prefix="/api/authors", tags=["authors"])
    return app


def export_openapi(path: str) -> dict[str, Any]:
    """导出 OpenAPI（前端类型生成的来源）。"""
    import json
    from pathlib import Path

    schema = create_app().openapi()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    return schema


app = create_app()
