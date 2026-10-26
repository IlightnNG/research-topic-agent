"""配置管理（guide §1.3）：单一 YAML + 环境变量覆盖 + 安全默认。

要点
- 所有键都有安全默认，**空配置也能启动**（doctor 的 L1 验收）；
- `providers.cloud.api_key` **只从环境变量读**，绝不写进 YAML / 日志 / 事件；
- `storage.data_root` 为空间根：设置后 `data/...` 相对路径会被重挂到该根下
  （本项目仓库路径含非 ASCII 字符，Kuzu 必须落在纯 ASCII 目录，见 ADR-0003）；
- `config_version` 是"影响行为的关键配置"的短哈希，写进每条日志，便于复现与对比实验。
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic import ValidationError as PydanticValidationError

from lit_agent._version import __version__
from lit_agent.errors import (
    E_CONFIG_INVALID,
    E_STORE_PATH_NONASCII,
    LitError,
)
from lit_agent.models._base import format_validation

__all__ = [
    "ArxivSettings",
    "CloudProviderSettings",
    "EvalSettings",
    "GuardsSettings",
    "LocalProviderSettings",
    "LoggingSettings",
    "OpenAlexSettings",
    "ProvidersSettings",
    "RoutingSettings",
    "SchedulerSettings",
    "Settings",
    "SourcesSettings",
    "GateSettings",
    "LimitSettings",
    "PipelineSettings",
    "StorageSettings",
    "VectorSettings",
    "load_settings",
]

ENV_PREFIX = "LIT_AGENT_"
DEFAULT_CONFIG_PATHS = ("config/config.yaml", "config/config.example.yaml")
VECTOR_DIM_CONTRACT = 1024  # guide §2.6 冻结：papers collection size=1024


def _utcnow() -> datetime:
    return datetime.now(UTC)


class _Section(BaseModel):
    """配置分节基类：拒绝未知键（拼错的键不会被静默忽略）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


class StorageSettings(_Section):
    data_root: str = Field(
        default="",
        description="空间根（建议纯 ASCII 绝对路径）；为空时相对路径按仓库 cwd 解析",
    )
    sqlite_path: str = "data/app.db"
    kuzu_path: str = "data/kuzu"  # 注意：Kuzu 是**单文件**数据库
    qdrant_path: str = "data/qdrant"  # Qdrant local 是**目录**
    papers_dir: str = "data/papers"
    checkpoint_path: str = "data/checkpoints.db"

    def resolve(self, raw: str) -> Path:
        """把配置里的路径解析成绝对路径（`data_root` 优先重挂 `data/` 前缀）。"""
        path = Path(raw)
        if path.is_absolute():
            return path
        root = Path(self.data_root) if self.data_root else None
        parts = path.parts
        if root is not None and parts and parts[0] == "data":
            return (root / Path(*parts[1:])).absolute()
        if root is not None:
            return (root / path).absolute()
        return path.absolute()

    @property
    def root(self) -> Path:
        if self.data_root:
            return Path(self.data_root).absolute()
        return Path("data").absolute()

    @property
    def sqlite_file(self) -> Path:
        return self.resolve(self.sqlite_path)

    @property
    def kuzu_file(self) -> Path:
        return self.resolve(self.kuzu_path)

    @property
    def qdrant_dir(self) -> Path:
        return self.resolve(self.qdrant_path)

    @property
    def papers_path(self) -> Path:
        return self.resolve(self.papers_dir)

    @property
    def checkpoint_file(self) -> Path:
        return self.resolve(self.checkpoint_path)


class OpenAlexSettings(_Section):
    mailto: str = Field(default="", description="礼貌池邮箱（OpenAlex polite pool）")
    api_key: SecretStr | None = Field(
        default=None,
        description="OpenAlex API key（免费申请）；不配则共用日配额，容易 401",
    )
    per_page: int = Field(default=200, ge=1, le=200)
    timeout_s: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=3, ge=0)


class ArxivSettings(_Section):
    categories: list[str] = Field(default_factory=list)


class SourcesSettings(_Section):
    openalex: OpenAlexSettings = OpenAlexSettings()
    arxiv: ArxivSettings = ArxivSettings()
    venues: list[str] = Field(
        default_factory=list, description="白名单候选（名称，Step 1.6 解析为 source.id）"
    )


class CloudProviderSettings(_Section):
    name: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"
    api_key_env: str = "DEEPSEEK_API_KEY"
    api_key: SecretStr | None = Field(default=None, description="只能来自环境变量")
    timeout_s: float = Field(default=60.0, gt=0)
    max_retries: int = Field(default=2, ge=0)
    max_tokens: int = Field(default=4096, ge=1)
    cache_enabled: bool = True


class LocalProviderSettings(_Section):
    engine: str = "ollama"
    base_url: str = "http://localhost:11434/v1"
    model: str = "qwen2.5:7b"
    ctx_len: int = Field(default=8192, ge=512)


class ProvidersSettings(_Section):
    cloud: CloudProviderSettings = CloudProviderSettings()
    local: LocalProviderSettings = LocalProviderSettings()


class RoutingSettings(_Section):
    sensitivity: Literal["strict", "balanced", "off"] = "strict"
    complexity_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    run_cost_budget_usd: float = Field(default=2.0, gt=0)


class GuardsSettings(_Section):
    scope_cosine_min: float = Field(default=0.60, ge=0.0, le=1.0)
    oos_share_max: float = Field(default=0.30, ge=0.0, le=1.0)
    loop_k: int = Field(default=5, ge=2)
    no_progress_steps: int = Field(default=2, ge=1)
    max_retries: int = Field(default=2, ge=0)


class SchedulerSettings(_Section):
    enabled: bool = Field(default=False, description="Phase 1 恒 False（仅装配，不注册 job）")
    timezone: str = "Asia/Singapore"
    default_cron: str = "0 3 * * 1"
    stagger_seconds: int = Field(default=300, ge=0)


class EvalSettings(_Section):
    enabled: bool = True
    judge_provider: Literal["cloud", "local"] = "cloud"
    sample_rate: float = Field(default=0.2, ge=0.0, le=1.0)


class LoggingSettings(_Section):
    level: str = "INFO"
    format: Literal["json", "console"] = "json"
    app_log: str = "logs/app.jsonl"
    error_log: str = "logs/errors.jsonl"
    console: bool = True
    max_field_chars: int = Field(default=500, ge=64)
    strict_contracts: bool = True
    max_bytes: int = Field(default=100 * 1024 * 1024, ge=1024)
    backup_count: int = Field(default=30, ge=1)
    debug_days: int = Field(default=7, ge=1)


class VectorSettings(_Section):
    model_id: str = "BAAI/bge-m3"
    model_rev: str = Field(default="", description="模型 commit 短哈希（锁定可复现）")
    dim: int = Field(default=VECTOR_DIM_CONTRACT, ge=1)
    batch_size: int = Field(default=32, ge=1)
    num_threads: int = Field(default=8, ge=1)
    hf_home: str = "data/models"
    active_collection: str = "papers_v1"


class GateSettings(_Section):
    """门禁阈值（Phase 2.2）：默认值与 2.1 行为等价。"""

    enabled: bool = True
    evidence_min_cards: int = Field(default=1, ge=1, description="证据最少篇数；生产建议 3")
    support_ratio_min: float = Field(default=0.6, ge=0.0, le=1.0)
    citation_required: bool = True
    drift_warn_below: float = Field(default=0.15, ge=0.0, le=1.0)
    drift_block_below: float = Field(default=0.05, ge=0.0, le=1.0)


class LimitSettings(_Section):
    """单 run 的硬上限（Phase 2.2）。"""

    max_attempts: dict[str, int] = Field(
        default_factory=lambda: {"analysis": 2, "retrieval": 2, "report": 1}
    )
    max_total_llm_calls: int = Field(default=12, ge=1)
    recursion_limit: int = Field(default=60, ge=10)
    max_run_usd: float = Field(default=2.0, gt=0.0)


class PipelineSettings(_Section):
    """Phase 2.2 冻结的 pipeline 配置（ADR-0007）。"""

    gates: GateSettings = GateSettings()
    limits: LimitSettings = LimitSettings()
    transitions: bool = True
    hybrid_alpha: float = Field(default=0.6, ge=0.0, le=1.0)
    hybrid_min_score: float = Field(default=0.15, ge=0.0, le=1.0)
    llm: Literal["auto", "on", "off"] = "auto"
    pdf_enabled: bool = False
    micro_enabled: bool = False  # Phase 3：节点内 MicroAgent（默认关，3.0 只接线）
    retrieval_l2: bool = False  # 3.1：retrieval 走 L2（rewrite → hybrid），默认 L1
    analysis_l2: bool = False  # 3.2：analysis 逐条校验-修复，默认 L1


class Settings(_Section):
    app_name: str = "lit-agent"
    app_version: str = __version__
    config_version: str = Field(
        default="cfg-unknown", description="关键配置短哈希（由 load_settings 计算）"
    )
    config_path: str = Field(default="", description="实际加载的配置文件路径（空 = 全用默认）")
    storage: StorageSettings = StorageSettings()
    sources: SourcesSettings = SourcesSettings()
    providers: ProvidersSettings = ProvidersSettings()
    routing: RoutingSettings = RoutingSettings()
    guards: GuardsSettings = GuardsSettings()
    scheduler: SchedulerSettings = SchedulerSettings()
    eval: EvalSettings = EvalSettings()
    logging: LoggingSettings = LoggingSettings()
    vector: VectorSettings = VectorSettings()
    pipeline: PipelineSettings = PipelineSettings()

    @model_validator(mode="after")
    def _check_vector_dim(self) -> Settings:
        if self.vector.dim != VECTOR_DIM_CONTRACT:
            raise ValueError(
                f"vector.dim 必须是 {VECTOR_DIM_CONTRACT}（guide §2.6 冻结契约，改动需新 ADR）"
            )
        return self

    # ------------------------------------------------------------------ #
    # 路径与目录
    # ------------------------------------------------------------------ #
    def log_dir(self) -> Path:
        return Path(self.logging.app_log).absolute().parent

    def paths(self) -> dict[str, Path]:
        st = self.storage
        return {
            "data_root": st.root,
            "sqlite": st.sqlite_file,
            "kuzu": st.kuzu_file,
            "qdrant": st.qdrant_dir,
            "papers": st.papers_path,
            "checkpoints": st.checkpoint_file,
            "hf_home": st.resolve(self.vector.hf_home),
            "logs": self.log_dir(),
        }

    def check(self) -> list[tuple[str, str]]:
        """静态自检：返回 [(code, message)]，空列表 = 通过。"""
        problems: list[tuple[str, str]] = []
        st = self.storage

        if self.vector.dim != VECTOR_DIM_CONTRACT:  # 防御：模型校验之外的二次确认
            problems.append(
                (E_CONFIG_INVALID, f"vector.dim={self.vector.dim} != {VECTOR_DIM_CONTRACT}")
            )

        for label, path in (("storage.kuzu_path", st.kuzu_file), ("storage.data_root", st.root)):
            if not str(path).isascii():
                problems.append(
                    (
                        E_STORE_PATH_NONASCII,
                        f"{label} 含非 ASCII 字符（{path}）：Kuzu 在 Windows 上无法打开此类路径，"
                        "请把 storage.data_root 指到纯 ASCII 目录（如 E:\\lit-agent-data）",
                    )
                )
        return problems

    def ensure_dirs(self, *, strict_ascii: bool = True) -> list[Path]:
        """创建所有必需目录；非 ASCII 的 Kuzu 路径直接报错（ADR-0003）。"""
        if strict_ascii:
            problems = self.check()
            blocking = [msg for code, msg in problems if code == E_STORE_PATH_NONASCII]
            if blocking:
                raise LitError(E_STORE_PATH_NONASCII, blocking[0], context={"problems": blocking})
        created: list[Path] = []
        p = self.paths()
        for key in ("data_root", "qdrant", "papers", "hf_home", "logs"):
            path = p[key]
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
        for key in ("sqlite", "checkpoints"):
            path = p[key]
            path.parent.mkdir(parents=True, exist_ok=True)
            created.append(path.parent)
        return created


# --------------------------------------------------------------------------- #
# 加载
# --------------------------------------------------------------------------- #
def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise LitError(E_CONFIG_INVALID, f"配置文件不是 UTF-8：{path}（{exc}）") from None
    except yaml.YAMLError as exc:
        raise LitError(E_CONFIG_INVALID, f"配置文件 YAML 解析失败：{path}（{exc}）") from None
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise LitError(E_CONFIG_INVALID, f"配置文件顶层必须是映射：{path}")
    return raw


def _set_nested(target: dict[str, Any], dotted: list[str], value: Any) -> None:
    node = target
    for key in dotted[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            child = {}
            node[key] = child
        node = child
    node[dotted[-1]] = value


def _parse_env_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return raw


def _apply_env_overrides(raw: dict[str, Any], environ: Mapping[str, str]) -> None:
    """支持 `LIT_AGENT_<SECTION>__<KEY>__<SUBKEY>=value`（大小写不敏感）。"""
    for key, value in environ.items():
        if not key.upper().startswith(ENV_PREFIX) or "__" not in key:
            continue
        suffix = key[len(ENV_PREFIX) :]
        parts = [part.lower() for part in suffix.split("__") if part]
        if len(parts) < 2:
            continue
        _set_nested(raw, parts, _parse_env_value(value))


def _config_hash(raw: Mapping[str, Any]) -> str:
    """对**去密钥**后的配置做短哈希（可复现，且不泄露敏感值）。"""
    sanitized = json.loads(json.dumps(raw, default=str, ensure_ascii=False))
    providers = sanitized.get("providers")
    if isinstance(providers, dict):
        for section in providers.values():
            if isinstance(section, dict):
                section.pop("api_key", None)
    sanitized.pop("config_version", None)
    payload = json.dumps(sanitized, sort_keys=True, ensure_ascii=False, default=str)
    return "cfg-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _resolve_config_path(config_path: str | Path | None, environ: Mapping[str, str]) -> Path | None:
    if config_path is not None:
        path = Path(config_path)
        if not path.exists():
            raise LitError(E_CONFIG_INVALID, f"指定的配置文件不存在：{path}")
        return path
    env_path = environ.get(f"{ENV_PREFIX}CONFIG")
    if env_path:
        path = Path(env_path)
        if not path.exists():
            raise LitError(E_CONFIG_INVALID, f"{ENV_PREFIX}CONFIG 指向的文件不存在：{path}")
        return path
    for candidate in DEFAULT_CONFIG_PATHS:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def load_settings(
    config_path: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """加载配置：默认值 ← YAML ← 环境变量（后者覆盖前者）。"""
    env = os.environ if environ is None else environ
    path = _resolve_config_path(config_path, env)
    raw: dict[str, Any] = _read_yaml(path) if path is not None else {}

    _apply_env_overrides(raw, env)

    # 密钥只从环境变量读（覆盖 YAML 中可能的残留）
    cloud = raw.setdefault("providers", {}).setdefault("cloud", {})
    if isinstance(cloud, dict):
        key_env = str(cloud.get("api_key_env") or "DEEPSEEK_API_KEY")
        secret = env.get(key_env, "")
        cloud["api_key"] = secret or None

    raw["config_version"] = _config_hash(raw)
    raw["config_path"] = str(path) if path is not None else ""

    try:
        return Settings(**raw)
    except PydanticValidationError as exc:
        raise LitError(
            E_CONFIG_INVALID,
            f"配置校验失败（{path or '<defaults>'}）：{format_validation(exc)}",
            context={"problems": format_validation(exc)},
        ) from None
