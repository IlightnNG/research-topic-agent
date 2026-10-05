"""Step 0.1 验收单测：配置加载、路径解析、密钥校验与错误可预期性。

约定：所有测试使用 tmp_path 构造独立配置，不触碰真实目录与真实环境变量。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from lit_agent_min import selfcheck
from lit_agent_min.config import ConfigError, ensure_dirs, load_settings, missing_env

MINIMAL_CONFIG = """
providers:
  cloud:
    name: deepseek
    model: deepseek-chat
    api_key_env: DEEPSEEK_API_KEY
"""


def write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.local.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_minimal_config(tmp_path: Path) -> None:
    cfg = write_config(tmp_path, MINIMAL_CONFIG)
    settings = load_settings(cfg)

    assert settings.providers.cloud.name == "deepseek"
    assert settings.config_path == cfg.resolve()
    # 未在配置中出现的节使用安全默认值
    assert settings.guards.loop_k == 5
    assert settings.logging.level == "INFO"


def test_relative_paths_resolved_against_config_dir(tmp_path: Path) -> None:
    cfg = write_config(tmp_path, MINIMAL_CONFIG)
    settings = load_settings(cfg)

    for value in (
        settings.paths.data_dir,
        settings.paths.kuzu_path,
        settings.paths.qdrant_path,
        settings.paths.logs_dir,
        settings.logging.app_log,
    ):
        assert value.is_absolute()
        assert value.is_relative_to(tmp_path.resolve())


def test_missing_config_error_is_actionable(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    with pytest.raises(ConfigError) as excinfo:
        load_settings(missing)

    message = str(excinfo.value)
    assert str(missing) in message
    assert "修复" in message  # 错误信息必须包含修复指引


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    cfg = write_config(tmp_path, MINIMAL_CONFIG + "\ngaurds:\n  loop_k: 5\n")  # 故意拼错
    with pytest.raises(ConfigError) as excinfo:
        load_settings(cfg)
    assert "gaurds" in str(excinfo.value)


def test_missing_env_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = write_config(tmp_path, MINIMAL_CONFIG)
    settings = load_settings(cfg)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert missing_env(settings) == ["DEEPSEEK_API_KEY"]

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    assert missing_env(settings) == []


def test_ensure_dirs_creates_layout(tmp_path: Path) -> None:
    cfg = write_config(tmp_path, MINIMAL_CONFIG)
    settings = load_settings(cfg)

    created = ensure_dirs(settings)
    assert created, "首次调用应创建目录"
    assert ensure_dirs(settings) == [], "重复调用不应重复创建"
    assert settings.paths.data_dir.is_dir()
    assert settings.paths.logs_dir.is_dir()


def test_selfcheck_exit_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = write_config(tmp_path, MINIMAL_CONFIG)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert selfcheck(strict=True, config_path=cfg) == 2  # 缺密钥：可预期失败
    assert selfcheck(strict=False, config_path=cfg) == 0  # lax：仅告警
    out = capsys.readouterr()
    assert "lit_agent_min" in out.out
    assert "DEEPSEEK_API_KEY" in (out.out + out.err)
