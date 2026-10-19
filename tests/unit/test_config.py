"""配置加载与路径解析（Step 1.1 验收）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from lit_agent.config import Settings, load_settings
from lit_agent.errors import E_CONFIG_INVALID, E_STORE_PATH_NONASCII, LitError


def write_yaml(path: Path, payload: dict) -> Path:
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return path


def test_defaults_are_safe_without_any_config(tmp_path: Path) -> None:
    cfg = write_yaml(tmp_path / "empty.yaml", {})
    settings = load_settings(cfg, environ={})

    assert settings.storage.sqlite_path == "data/app.db"
    assert settings.vector.dim == 1024
    assert settings.logging.level == "INFO"
    assert settings.routing.run_cost_budget_usd > 0
    assert settings.config_path == str(cfg)
    assert settings.config_version.startswith("cfg-")


def test_yaml_overrides_defaults(tmp_path: Path) -> None:
    cfg = write_yaml(
        tmp_path / "c.yaml",
        {"logging": {"level": "DEBUG"}, "guards": {"loop_k": 7}},
    )
    settings = load_settings(cfg, environ={})
    assert settings.logging.level == "DEBUG"
    assert settings.guards.loop_k == 7
    # 未指定的键仍取默认值
    assert settings.guards.no_progress_steps == 2


def test_env_overrides_yaml_nested(tmp_path: Path) -> None:
    cfg = write_yaml(tmp_path / "c.yaml", {"logging": {"level": "DEBUG"}})
    settings = load_settings(
        cfg,
        environ={"LIT_AGENT_LOGGING__LEVEL": "WARNING", "LIT_AGENT_GUARDS__LOOP_K": "9"},
    )
    assert settings.logging.level == "WARNING"
    assert settings.guards.loop_k == 9  # JSON 解析成 int


def test_env_value_parsed_as_json(tmp_path: Path) -> None:
    cfg = write_yaml(tmp_path / "c.yaml", {})
    settings = load_settings(
        cfg, environ={"LIT_AGENT_SCHEDULER__ENABLED": "true", "LIT_AGENT_EVAL__SAMPLE_RATE": "0.5"}
    )
    assert settings.scheduler.enabled is True
    assert settings.eval.sample_rate == 0.5


def test_api_key_only_from_environment(tmp_path: Path) -> None:
    """YAML 里写密钥必须被忽略：密钥只有一个来源（环境变量）。"""
    cfg = write_yaml(tmp_path / "c.yaml", {"providers": {"cloud": {"api_key": "sk-from-yaml"}}})
    without_env = load_settings(cfg, environ={})
    assert without_env.providers.cloud.api_key is None

    with_env = load_settings(cfg, environ={"DEEPSEEK_API_KEY": "sk-from-env"})
    assert with_env.providers.cloud.api_key is not None
    assert with_env.providers.cloud.api_key.get_secret_value() == "sk-from-env"


def test_config_version_is_stable_and_secret_free(tmp_path: Path) -> None:
    payload = {"logging": {"level": "DEBUG"}}
    a = load_settings(write_yaml(tmp_path / "a.yaml", payload), environ={})
    b = load_settings(write_yaml(tmp_path / "b.yaml", payload), environ={})
    assert a.config_version == b.config_version

    c = load_settings(write_yaml(tmp_path / "c.yaml", {"logging": {"level": "INFO"}}), environ={})
    assert c.config_version != a.config_version

    # 密钥不参与哈希（否则同一配置换密钥会改变版本号）
    with_key = load_settings(
        write_yaml(tmp_path / "d.yaml", payload), environ={"DEEPSEEK_API_KEY": "sk-x"}
    )
    assert with_key.config_version == a.config_version


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    cfg = write_yaml(tmp_path / "c.yaml", {"logging": {"levle": "DEBUG"}})  # 拼错
    with pytest.raises(LitError) as excinfo:
        load_settings(cfg, environ={})
    assert excinfo.value.code == E_CONFIG_INVALID


def test_missing_config_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(LitError) as excinfo:
        load_settings(tmp_path / "nope.yaml", environ={})
    assert excinfo.value.code == E_CONFIG_INVALID


def test_vector_dim_contract_is_enforced(tmp_path: Path) -> None:
    cfg = write_yaml(tmp_path / "c.yaml", {"vector": {"dim": 768}})
    with pytest.raises(LitError) as excinfo:
        load_settings(cfg, environ={})
    assert excinfo.value.code == E_CONFIG_INVALID
    assert "1024" in excinfo.value.message


def test_data_root_remaps_relative_data_paths(tmp_path: Path) -> None:
    root = tmp_path / "store"
    cfg = write_yaml(tmp_path / "c.yaml", {"storage": {"data_root": str(root)}})
    settings = load_settings(cfg, environ={})

    assert settings.storage.sqlite_file == root / "app.db"
    assert settings.storage.kuzu_file == root / "kuzu"
    assert settings.storage.qdrant_dir == root / "qdrant"
    # 非 data/ 前缀的相对路径也挂到 data_root 下
    assert settings.storage.resolve("checkpoints.db") == root / "checkpoints.db"


def test_absolute_paths_are_kept(tmp_path: Path) -> None:
    absolute = tmp_path / "elsewhere" / "x.db"
    cfg = write_yaml(
        tmp_path / "c.yaml",
        {"storage": {"data_root": str(tmp_path / "root"), "sqlite_path": str(absolute)}},
    )
    settings = load_settings(cfg, environ={})
    assert settings.storage.sqlite_file == absolute


def test_non_ascii_kuzu_path_is_blocking(tmp_path: Path) -> None:
    cfg = write_yaml(tmp_path / "c.yaml", {"storage": {"data_root": str(tmp_path / "学术")}})
    settings = load_settings(cfg, environ={})

    problems = settings.check()
    assert any(code == E_STORE_PATH_NONASCII for code, _ in problems)
    with pytest.raises(LitError) as excinfo:
        settings.ensure_dirs()
    assert excinfo.value.code == E_STORE_PATH_NONASCII


def test_ensure_dirs_creates_everything(tmp_path: Path) -> None:
    cfg = write_yaml(tmp_path / "c.yaml", {"storage": {"data_root": str(tmp_path / "store")}})
    settings = load_settings(cfg, environ={})
    created = settings.ensure_dirs()

    assert settings.storage.sqlite_file.parent.is_dir()
    assert settings.storage.qdrant_dir.is_dir()
    assert settings.storage.papers_path.is_dir()
    assert settings.log_dir().is_dir()
    assert all(path.exists() for path in created)


def test_settings_are_frozen() -> None:
    settings = Settings()
    with pytest.raises(ValidationError):  # frozen=True → 赋值即报错
        settings.logging = None  # type: ignore[misc]


def test_config_snapshot_is_json_serializable(tmp_path: Path) -> None:
    cfg = write_yaml(tmp_path / "c.yaml", {"storage": {"data_root": str(tmp_path / "store")}})
    settings = load_settings(cfg, environ={"DEEPSEEK_API_KEY": "sk-secret"})
    dumped = settings.model_dump(mode="json")
    text = json.dumps(dumped)
    assert "sk-secret" not in text  # SecretStr 不会明文序列化
