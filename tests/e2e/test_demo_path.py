"""S11：浏览器 e2e（Playwright）。

默认**跳过**（`LIT_E2E=1` 才跑），避免把网络/浏览器依赖塞进常规单元测试。
运行：`$env:LIT_E2E=1; uv run pytest -q tests/e2e`

流程：起 uvicorn（子进程）→ 等 /api/health → 调 `npm run test:e2e` → 关进程。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
API = "http://127.0.0.1:8000"


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONPATH", str(ROOT / "src"))
    env.setdefault("PLAYWRIGHT_BROWSERS_PATH", r"D:\lit-agent-store\playwright")
    env["LIT_E2E_NO_SERVER"] = ""
    return env


@pytest.mark.skipif(os.environ.get("LIT_E2E") != "1", reason="set LIT_E2E=1 to run browser e2e")
def test_demo_path_in_browser() -> None:
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "lit_agent.api.app:app", "--port", "8000"],
        cwd=str(ROOT),
        env=_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(120):
            try:
                if httpx.get(f"{API}/api/health", timeout=1.0).status_code == 200:
                    break
            except Exception:  # noqa: BLE001 - 启动期连接失败是正常的
                time.sleep(0.5)
        else:
            pytest.fail("后端未在 60s 内就绪")

        result = subprocess.run(
            ["npm", "run", "test:e2e"],
            cwd=str(WEB),
            env=_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=True,
        )
        print((result.stdout or "")[-4000:])
        print((result.stderr or "")[-2000:])
        assert result.returncode == 0, "Playwright 用例失败（见上方输出）"
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            server.kill()
