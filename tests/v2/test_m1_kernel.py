"""M1-P01: LLM client, ReAct kernel, tool schema, step checkpoint."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lit_agent_v2.kernel.checkpoint import KernelCheckpoint
from lit_agent_v2.kernel.llm import LLMConfig, LLMUsage
from lit_agent_v2.kernel.loop import Goal, Kernel
from lit_agent_v2.kernel.tools import ToolBox, ToolSpec

ACTIONS = [
    {"action": "tool", "tool": "search", "args": {"q": "agents"}},
    {"action": "final", "outputs": {"answer": "ok"}},
]


class FakeLLM:
    def __init__(self, actions=None) -> None:
        self.actions = list(actions or ACTIONS)
        self.calls = 0
        self.config = type("Config", (), {"model": "fake"})()

    def chat_json(self, messages, *, prompt_version="m1-p01", **kwargs):  # noqa: ANN001
        action = self.actions[min(self.calls, len(self.actions) - 1)]
        self.calls += 1
        return action, LLMUsage(prompt_tokens=10, completion_tokens=5, model="fake", prompt_version=prompt_version)


def _toolbox() -> ToolBox:
    toolbox = ToolBox()
    toolbox.register(
        ToolSpec(
            name="search",
            description="search",
            parameters={"q": "string"},
            required=("q",),
            handler=lambda args: {"hits": [args["q"]]},
        )
    )
    return toolbox


def test_kernel_tool_then_final_and_checkpoint() -> None:
    checkpoints: list[KernelCheckpoint] = []
    events: list[str] = []
    result = Kernel().run(
        Goal(node_id="n1", objective="find", max_steps=4),
        _toolbox(),
        llm=FakeLLM(),
        on_checkpoint=checkpoints.append,
        on_event=lambda name, _payload: events.append(name),
    )
    assert result.stop_reason == "final"
    assert result.output == {"answer": "ok"}
    assert result.usage.prompt_tokens == 20
    assert checkpoints[-1].step == 1
    assert "kernel.started" in events
    assert "step.started" in events
    assert "tool.called" in events
    assert "tool.result" in events
    assert "kernel.finished" in events


def test_kernel_resume_from_step_checkpoint() -> None:
    first = Kernel().run(
        Goal(node_id="n1", objective="find", max_steps=1),
        _toolbox(),
        llm=FakeLLM(),
    )
    assert first.stop_reason == "max_steps"
    state = KernelCheckpoint(node_id="n1", step=1, history=[{"tool": "search"}], trace=[{"ok": True}])
    resumed = Kernel().run(
        Goal(node_id="n1", objective="find", max_steps=3),
        _toolbox(),
        llm=FakeLLM([{"action": "final", "outputs": {"answer": "resumed"}}]),
        checkpoint=state,
    )
    assert resumed.stop_reason == "final"
    assert resumed.output["answer"] == "resumed"


def test_tool_schema_and_no_progress() -> None:
    result = Kernel().run(
        Goal(node_id="n1", objective="x", max_steps=3),
        _toolbox(),
        llm=FakeLLM(
            [
                {"action": "tool", "tool": "search", "args": {}},
                {"action": "tool", "tool": "search", "args": {}},
            ]
        ),
    )
    assert result.stop_reason == "failed"

    result = Kernel().run(
        Goal(node_id="n2", objective="x", max_steps=4),
        _toolbox(),
        llm=FakeLLM(
            [
                {"action": "tool", "tool": "search", "args": {"q": "a"}},
                {"action": "tool", "tool": "search", "args": {"q": "a"}},
            ]
        ),
    )
    assert result.stop_reason == "no_progress"


def test_llm_config_reads_dotenv(tmp_path: Path, monkeypatch) -> None:
    for key in (
        "LIT_AGENT_PROVIDERS__CLOUD__API_KEY",
        "LIT_AGENT_PROVIDERS__CLOUD__BASE_URL",
        "LIT_AGENT_PROVIDERS__CLOUD__MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_text(
        "LIT_AGENT_PROVIDERS__CLOUD__API_KEY=sk-test\n"
        "LIT_AGENT_PROVIDERS__CLOUD__BASE_URL=https://api.deepseek.com\n"
        "LIT_AGENT_PROVIDERS__CLOUD__MODEL=deepseek-flash\n",
        encoding="utf-8",
    )
    config = LLMConfig.from_env(path)
    assert config.api_key == "sk-test"
    assert config.model == "deepseek-flash"


@pytest.mark.skipif(os.environ.get("LIT_V2_LIVE") != "1", reason="set LIT_V2_LIVE=1 for live LLM")
def test_live_llm_returns_json() -> None:
    from lit_agent_v2.kernel.llm import DeepSeekChatClient, load_llm_config

    client = DeepSeekChatClient(load_llm_config())
    payload, usage = client.chat_json(
        [{"role": "user", "content": 'Return JSON {"ok": true} only.'}],
        max_tokens=200,
    )
    assert payload.get("ok") is True
    assert usage.prompt_tokens > 0


def test_checkpoint_store_persists(tmp_path: Path) -> None:
    from lit_agent_v2.kernel.checkpoint import KernelCheckpointStore
    from lit_agent_v2.storage.db import Database

    db = Database(tmp_path / "v2.sqlite")
    db.migrate()
    store = KernelCheckpointStore(db, "r1")
    checkpoint = KernelCheckpoint(node_id="n1", step=2, history=[{"tool": "x"}])
    store.save(checkpoint)
    loaded = store.load("n1")
    assert loaded is not None
    assert loaded.step == 2
    assert loaded.history == [{"tool": "x"}]


def test_tool_timeout() -> None:
    import time

    toolbox = ToolBox()
    toolbox.register(
        ToolSpec(
            name="slow",
            description="slow",
            timeout_s=0.01,
            handler=lambda _args: (time.sleep(0.2), {}),
        )
    )
    started = time.monotonic()
    result = toolbox.call("slow", {})
    assert result.ok is False
    assert result.error == "E_TOOL_TIMEOUT"
    assert time.monotonic() - started < 0.15
