"""配置加载与校验（Step 0.1 最小可用；Step 0.2 起在其上扩展）。

设计要点
- 只从 YAML + 环境变量读取；密钥绝不进 YAML，配置里只保存"环境变量名"。
- 相对路径一律以**配置文件所在目录**为基准解析，与启动时的工作目录无关。
- `.env` 作为兜底加载（已存在的环境变量优先），因此 `cp .env.example .env` 即可生效。
- 所有可预期错误统一抛 `ConfigError`，消息包含"哪里错 + 怎么修"，由 CLI 边界转成友好输出。
- 扩展方式：在对应 BaseModel 上新增字段即可；`extra="forbid"` 会立刻拦住拼写错误。
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError

__all__ = [
    "ConfigError",
    "Settings",
    "default_config_path",
    "ensure_dirs",
    "ensure_env",
    "load_settings",
    "missing_env",
    "project_root",
    "required_env",
    "runtime_dirs",
]


class ConfigError(RuntimeError):
    """配置相关的可预期错误；CLI 层捕获后打印友好提示（不显示堆栈）。"""


class _Model(BaseModel):
    """所有配置节的基类：禁止未知字段 + 不可变，保证配置在运行期稳定。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Paths(_Model):
    out_dir: Path = Path("out")
    data_dir: Path = Path("out/data")
    sqlite_path: Path = Path("out/data/sqlite.db")
    kuzu_path: Path = Path("out/data/kuzu")
    qdrant_path: Path = Path("out/data/qdrant")
    papers_dir: Path = Path("out/data/papers")
    logs_dir: Path = Path("logs")


class Provider(_Model):
    name: str
    base_url: str | None = None
    model: str | None = None
    api_key_env: str | None = None  # 只存环境变量名，不存密钥
    engine: str | None = None  # 本地引擎：ollama | vllm | llama.cpp
    ctx_len: int | None = None


class Providers(_Model):
    cloud: Provider
    local: Provider | None = None


class Sources(_Model):
    openalex_mailto: str = ""
    arxiv_categories: list[str] = Field(default_factory=list)
    venues: list[str] = Field(default_factory=list)


class Guards(_Model):
    scope_cosine_min: float = 0.60
    oos_share_max: float = 0.30
    loop_k: int = 5
    no_progress_steps: int = 2
    max_retries: int = 2


class Logging(_Model):
    level: str = "INFO"
    format: str = "json"
    app_log: Path = Path("logs/app.jsonl")
    error_log: Path = Path("logs/errors.jsonl")
    retain_days: int = 30
    retain_error_days: int = 90
    debug_runs: list[str] = Field(default_factory=list)
    console: bool = True  # 是否同时输出到控制台
    max_field_chars: int = Field(default=500, ge=64)  # info 及以上单字段长度上限（超出转摘要）
    strict_contracts: bool = True  # ERROR 级缺 error_code 等契约违规是否直接报错


class Settings(_Model):
    paths: Paths = Field(default_factory=Paths)
    providers: Providers
    sources: Sources = Field(default_factory=Sources)
    guards: Guards = Field(default_factory=Guards)
    logging: Logging = Field(default_factory=Logging)
    config_path: Path | None = None  # 实际使用的配置文件（由 load_settings 填充）


# --------------------------------------------------------------------------- #
# 路径
# --------------------------------------------------------------------------- #
def project_root() -> Path:
    """prototype 根目录（本文件位于 <root>/lit_agent_min/config.py）。"""
    return Path(__file__).resolve().parents[1]


def default_config_path() -> Path:
    """配置文件位置：环境变量 LIT_AGENT_CONFIG 优先，否则 <root>/config.local.yaml。"""
    override = os.environ.get("LIT_AGENT_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    return project_root() / "config.local.yaml"


# --------------------------------------------------------------------------- #
# 加载与校验
# --------------------------------------------------------------------------- #
def load_settings(path: str | Path | None = None) -> Settings:
    """读取并校验配置；失败时抛 `ConfigError`（含修复提示）。"""
    cfg_path = Path(path).expanduser().resolve() if path else default_config_path()
    if not cfg_path.is_file():
        raise ConfigError(
            f"找不到配置文件：{cfg_path}\n"
            "修复：\n"
            f"  1) 复制模板：copy config.example.yaml config.local.yaml（Windows）"
            f" / cp config.example.yaml config.local.yaml（bash）\n"
            "  2) 或设置 LIT_AGENT_CONFIG 指向你的配置文件\n"
            f"  3) 当前目录：{project_root()}"
        )

    load_dotenv(cfg_path.parent / ".env", override=False)  # 已存在的环境变量优先

    try:
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML 解析失败：{cfg_path}\n{exc}") from None
    if not isinstance(raw, dict):
        raise ConfigError(f"配置文件顶层必须是键值映射（key: value）：{cfg_path}")

    try:
        settings = Settings(**raw, config_path=cfg_path)
    except ValidationError as exc:
        raise ConfigError(f"配置校验失败：{cfg_path}\n{_format_validation(exc)}") from None

    return _resolve_paths(settings, cfg_path.parent)


def _resolve_paths(settings: Settings, base: Path) -> Settings:
    """把 Paths 与日志路径统一解析为绝对路径（相对配置文件目录）。"""
    resolved = {name: base / getattr(settings.paths, name) for name in Paths.model_fields}
    logging_resolved = {
        "app_log": base / settings.logging.app_log,
        "error_log": base / settings.logging.error_log,
    }
    return settings.model_copy(
        update={
            "paths": Paths(**resolved),
            "logging": settings.logging.model_copy(update=logging_resolved),
        }
    )


def _format_validation(exc: ValidationError) -> str:
    lines = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ())) or "<root>"
        lines.append(f"  - {loc}: {err.get('msg')} [{err.get('type')}]")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 环境变量（密钥）
# --------------------------------------------------------------------------- #
def required_env(settings: Settings) -> list[str]:
    """配置中声明的必需环境变量名（去重保序）。"""
    names: list[str] = []
    for provider in (settings.providers.cloud, settings.providers.local):
        if provider is not None and provider.api_key_env:
            names.append(provider.api_key_env)
    return list(dict.fromkeys(names))


def missing_env(settings: Settings) -> list[str]:
    """尚未设置（或为空）的必需环境变量。"""
    return [name for name in required_env(settings) if not os.environ.get(name, "").strip()]


def ensure_env(settings: Settings) -> None:
    """校验密钥类环境变量；缺失时抛 `ConfigError` 并给出三种修复方式。"""
    missing = missing_env(settings)
    if not missing:
        return
    names = "、".join(missing)
    raise ConfigError(
        f"缺少必需的环境变量：{names}\n"
        "修复（任选其一）：\n"
        "  1) copy .env.example .env（Windows）/ cp .env.example .env（bash），再填入真实密钥\n"
        "  2) 当前 shell 直接设置：set DEEPSEEK_API_KEY=...（Windows cmd）"
        ' / $env:DEEPSEEK_API_KEY="..."（PowerShell） / export DEEPSEEK_API_KEY=...（bash）\n'
        "  3) 只做结构自检、暂时不需要云端密钥：python -m lit_agent_min selfcheck --lax"
    )


# --------------------------------------------------------------------------- #
# 目录
# --------------------------------------------------------------------------- #
def runtime_dirs(settings: Settings) -> list[Path]:
    """运行期需要存在的目录（去重保序由 ensure_dirs 负责）。"""
    p = settings.paths
    return [
        p.out_dir,
        p.data_dir,
        p.kuzu_path,
        p.qdrant_path,
        p.papers_dir,
        p.logs_dir,
        p.sqlite_path.parent,
        settings.logging.app_log.parent,
        settings.logging.error_log.parent,
    ]


def ensure_dirs(settings: Settings) -> list[Path]:
    """创建运行所需目录，返回**本次新建**的目录列表。"""
    created: list[Path] = []
    for directory in dict.fromkeys(runtime_dirs(settings)):
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created.append(directory)
    return created
