"""Alembic 环境：URL 与 metadata 都从本项目配置解析，不依赖 alembic.ini 里的硬编码。

URL 解析优先级：
1. `config.attributes["settings"]`（CLI 以编程方式调用时注入）；
2. `alembic.ini` 的 `sqlalchemy.url`；
3. 环境变量 `LIT_AGENT_DB_URL`；
4. `load_settings()` 的 `storage.data_root` + `sqlite_path`。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import context

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import lit_agent.db.tables  # noqa: E402,F401  (注册全部表)
from lit_agent.db.base import metadata  # noqa: E402

config = context.config
target_metadata = metadata


def _resolve_url() -> str:
    settings = config.attributes.get("settings")
    if settings is not None:
        return f"sqlite:///{settings.storage.sqlite_file.as_posix()}"
    configured = config.get_main_option("sqlalchemy.url", None)
    if configured:
        return configured
    env_url = os.environ.get("LIT_AGENT_DB_URL")
    if env_url:
        return env_url
    from lit_agent.config import load_settings

    settings = load_settings()
    return f"sqlite:///{settings.storage.sqlite_file.as_posix()}"


def run_migrations_offline() -> None:
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine

    engine = create_engine(_resolve_url(), future=True)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=True,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
