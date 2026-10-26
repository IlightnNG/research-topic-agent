"""3.1 / M3：.env 加载与模型覆盖。"""

from __future__ import annotations

from pathlib import Path

from lit_agent.config import load_settings


def test_dotenv_supplies_key_and_model(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "DEEPSEEK_API_KEY=sk-test-123\n"
        "LIT_AGENT_PROVIDERS__CLOUD__MODEL=gpt-4o-mini\n"
        "LIT_AGENT_PROVIDERS__CLOUD__BASE_URL=https://example.test/v1\n",
        encoding="utf-8",
    )
    settings = load_settings(environ={}, dotenv_path=env)

    assert settings.providers.cloud.model == "gpt-4o-mini"
    assert settings.providers.cloud.base_url == "https://example.test/v1"
    assert settings.providers.cloud.api_key is not None


def test_real_env_overrides_dotenv(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("DEEPSEEK_API_KEY=from-dotenv\n", encoding="utf-8")
    settings = load_settings(environ={"DEEPSEEK_API_KEY": "from-process"}, dotenv_path=env)

    assert settings.providers.cloud.api_key is not None
    assert settings.providers.cloud.api_key.get_secret_value() == "from-process"


def test_direct_api_key_field(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "LIT_AGENT_PROVIDERS__CLOUD__NAME=openai\n"
        "LIT_AGENT_PROVIDERS__CLOUD__BASE_URL=https://api.openai.com/v1\n"
        "LIT_AGENT_PROVIDERS__CLOUD__MODEL=gpt-4o-mini\n"
        "LIT_AGENT_PROVIDERS__CLOUD__API_KEY=sk-direct\n",
        encoding="utf-8",
    )
    settings = load_settings(environ={}, dotenv_path=env)

    assert settings.providers.cloud.name == "openai"
    assert settings.providers.cloud.model == "gpt-4o-mini"
    assert settings.providers.cloud.api_key is not None
    assert settings.providers.cloud.api_key.get_secret_value() == "sk-direct"


def test_indirect_api_key_env_field(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "LIT_AGENT_PROVIDERS__CLOUD__API_KEY_ENV=OPENAI_API_KEY\n"
        "OPENAI_API_KEY=sk-indirect\n",
        encoding="utf-8",
    )
    settings = load_settings(environ={}, dotenv_path=env)

    assert settings.providers.cloud.api_key is not None
    assert settings.providers.cloud.api_key.get_secret_value() == "sk-indirect"


def test_direct_key_wins_over_indirect(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "LIT_AGENT_PROVIDERS__CLOUD__API_KEY=sk-direct\n"
        "OPENAI_API_KEY=sk-indirect\n"
        "LIT_AGENT_PROVIDERS__CLOUD__API_KEY_ENV=OPENAI_API_KEY\n",
        encoding="utf-8",
    )
    settings = load_settings(environ={}, dotenv_path=env)

    assert settings.providers.cloud.api_key is not None
    assert settings.providers.cloud.api_key.get_secret_value() == "sk-direct"
