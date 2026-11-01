"""DeepSeek streaming transport test."""

from __future__ import annotations

import json

import httpx

from lit_agent_v2.kernel.llm import DeepSeekChatClient, LLMConfig


def test_stream_json_reads_sse_and_reports_usage() -> None:
    chunks = [
        {"choices": [{"delta": {"content": '{"action":"final",'}}]},
        {"choices": [{"delta": {"content": '"outputs":{"ok":true}}'}}], "usage": {"prompt_tokens": 7, "completion_tokens": 3}},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        body = b"".join(
            b"data: " + json.dumps(chunk).encode() + b"\n\n" for chunk in chunks
        )
        body += b"data: [DONE]\n\n"
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    client = DeepSeekChatClient(
        LLMConfig("https://example.test", "deepseek-flash", "key"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    deltas: list[str] = []
    action, usage = client.stream_json(
        [{"role": "user", "content": "go"}], on_delta=deltas.append
    )
    assert action == {"action": "final", "outputs": {"ok": True}}
    assert "".join(deltas) == '{"action":"final","outputs":{"ok":true}}'
    assert usage.prompt_tokens == 7
    assert usage.completion_tokens == 3
