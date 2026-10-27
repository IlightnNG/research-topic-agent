"""S8 验收：LLM 进入分析节点 + 无 key 显式降级。

- 有 gateway：claims 来自 gateway 返回（而不是确定性模板），报告事件标 `extraction=llm`；
- 无 key/gateway：报告仍生成，事件标 `extraction=deterministic` 且 `llm_used=false`。
"""

from __future__ import annotations

from pathlib import Path

from tests.wiring import fetch_events, prepare

from lit_agent.runtime.graph_runner import run_graph


class FakeGateway:
    def __init__(self) -> None:
        self.calls = 0

    def chat_json(self, messages, **kwargs):  # noqa: ANN001
        self.calls += 1
        return (
            {
                "claims": [
                    {
                        "text": "fake finding from llm",
                        "paper_id": "P0",
                        "quote": "tool use improves task success",
                    }
                ]
            },
            None,
        )


def end_payload(events: list[dict], stage: str) -> dict:
    for event in events:
        if (
            event["type"] == "phase_change"
            and event["stage"] == stage
            and event["payload"].get("phase") == "end"
        ):
            return event["payload"]
    raise AssertionError(f"没有找到 {stage} 的 end 事件")


def test_llm_gateway_is_used_by_analysis(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    gateway = FakeGateway()

    result = run_graph(settings, "ai-agents", run_id="llm-1", gateway=gateway)
    assert result["state"] == "succeeded", result
    assert gateway.calls >= 1, "分析/报告应至少调用一次 gateway"

    events = fetch_events(settings, "llm-1")
    payload = end_payload(events, "report")
    assert payload["extraction"] == "llm"
    assert payload["llm_used"] is True

    # 报告里的 claim 来自假 gateway，而不是确定性模板
    from sqlalchemy import text

    from lit_agent.db.session import connect, make_engine

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            claims_json = conn.execute(
                text("SELECT claims_json FROM reports WHERE run_id='llm-1'")
            ).scalar_one()
    finally:
        engine.dispose()
    assert "fake finding from llm" in (claims_json or "")


def test_without_gateway_degrades_explicitly(tmp_path: Path) -> None:
    settings = prepare(tmp_path)  # 无 api_key
    result = run_graph(settings, "ai-agents", run_id="llm-2")
    assert result["state"] == "succeeded", result

    events = fetch_events(settings, "llm-2")
    payload = end_payload(events, "report")
    assert payload["extraction"] == "deterministic"
    assert payload["llm_used"] is False

    stages = result.get("stages") or {}
    assert stages.get("extraction") == "deterministic"
