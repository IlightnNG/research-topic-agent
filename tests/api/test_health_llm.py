"""3.1 / S3：health 暴露 LLM 配置（不泄露 key）。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr
from tests.wiring import prepare

from lit_agent.api.app import create_app


def _settings_with_key(tmp_path: Path):
    base = prepare(tmp_path, papers=1)
    cloud = base.providers.cloud.model_copy(
        update={
            "api_key": SecretStr("sk-test"),
            "model": "gpt-4o-mini",
            "base_url": "https://example.test/v1",
        }
    )
    providers = base.providers.model_copy(update={"cloud": cloud})
    return base.model_copy(update={"providers": providers})


def test_health_reports_llm_without_secret(tmp_path: Path) -> None:
    settings = _settings_with_key(tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()["llm"]
    assert payload["model"] == "gpt-4o-mini"
    assert payload["base_url"] == "https://example.test/v1"
    assert payload["key_present"] is True
    assert "sk-test" not in response.text


def test_health_reports_missing_key(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=1)
    with TestClient(create_app(settings)) as client:
        payload = client.get("/api/health").json()["llm"]

    assert payload["key_present"] is False
