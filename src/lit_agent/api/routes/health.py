"""健康检查：进程 + 三库身份 + 版本。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from lit_agent.api.dependencies import get_settings
from lit_agent.config import Settings
from lit_agent.db.session import database_status

router = APIRouter()


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    status = database_status(settings)
    ok = bool(status["exists"]) and status["schema_version"] == status["expected_schema_version"]
    return {
        "ok": ok,
        "app_version": settings.app_version,
        "config_version": settings.config_version,
        "sqlite": {
            "path": status["path"],
            "schema_version": status["schema_version"],
            "tables": status["tables"],
            "runs": status["runs"],
            "events": status["events"],
        },
        "kuzu_exists": settings.storage.kuzu_file.exists(),
        "qdrant_exists": settings.storage.qdrant_dir.exists(),
    }
