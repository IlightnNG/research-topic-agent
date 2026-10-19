"""FastAPI 依赖：配置与 engine 由 app 持有，测试可注入临时 Settings。"""

from __future__ import annotations

from typing import Any

from fastapi import Request

from lit_agent.config import Settings
from lit_agent.db.session import make_engine

__all__ = ["get_engine", "get_settings"]


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_engine(request: Request) -> Any:
    engine = request.app.state.engine
    if engine is None:
        engine = make_engine(request.app.state.settings)
        request.app.state.engine = engine
    return engine
