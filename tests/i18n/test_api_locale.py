"""3.1 / S4：API 错误文案默认英文，Accept-Language: zh 时中文。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from lit_agent.api.app import create_app
from tests.wiring import prepare


def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(prepare(tmp_path)))


def test_default_is_english(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        response = api.get("/api/runs/does-not-exist")
    assert response.status_code == 404
    assert response.json()["message"] == "Resource not found."


def test_accept_language_chinese(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        response = api.get("/api/runs/does-not-exist", headers={"Accept-Language": "zh-CN"})
    assert response.status_code == 404
    assert response.json()["message"] == "资源不存在。"
