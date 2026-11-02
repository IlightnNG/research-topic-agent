"""LLM client for the M1 kernel.

M1 owns this interface; it does not import any domain module.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import httpx

from lit_agent_v2.contracts.errors import ModuleError

__all__ = ["DeepSeekChatClient", "LLMClient", "LLMConfig", "LLMUsage", "load_llm_config"]


@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    prompt_version: str = ""
    reasoning: str = ""


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    model: str
    api_key: str
    timeout_s: float = 120.0
    input_cost_per_m: float = 0.30
    output_cost_per_m: float = 1.20
    off_peak_multiplier: float = 0.5

    @classmethod
    def from_env(cls, dotenv_path: str | Path = ".env") -> LLMConfig:
        values = _read_dotenv(Path(dotenv_path))
        values.update({key: value for key, value in os.environ.items() if key.startswith("LIT_AGENT_")})

        def get(name: str, default: str = "") -> str:
            return str(values.get(f"LIT_AGENT_PROVIDERS__CLOUD__{name}") or default)

        api_key = get("API_KEY") or str(values.get("DEEPSEEK_API_KEY") or "")
        base_url = get("BASE_URL", "https://api.deepseek.com")
        model = get("MODEL", "deepseek-flash")
        pricing = {
            "deepseek-flash": (0.30, 1.20),
            "deepseek-v4-pro": (1.32, 3.96),
            "deepseek-chat": (0.30, 1.20),
            "deepseek-reasoner": (0.55, 2.19),
        }.get(model, (0.0, 0.0))
        input_cost = float(
            get("INPUT_COST_PER_M", str(pricing[0])) or pricing[0]
        )
        output_cost = float(
            get("OUTPUT_COST_PER_M", str(pricing[1])) or pricing[1]
        )
        if not api_key:
            raise ModuleError(
                "E_LLM_CONFIG",
                "missing LIT_AGENT_PROVIDERS__CLOUD__API_KEY",
                "M1",
                retryable=False,
            )
        return cls(
            base_url=base_url.rstrip("/"),
            model=model,
            api_key=api_key,
            input_cost_per_m=input_cost,
            output_cost_per_m=output_cost,
        )


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


class LLMClient(Protocol):
    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        prompt_version: str = "m1-p01",
        max_tokens: int = 1200,
        temperature: float = 0.1,
    ) -> tuple[dict, LLMUsage]: ...


class DeepSeekChatClient:
    def __init__(self, config: LLMConfig, *, client: httpx.Client | None = None) -> None:
        self.config = config
        self.client = client or httpx.Client(timeout=config.timeout_s)

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        prompt_version: str = "m1-p01",
        max_tokens: int = 1200,
        temperature: float = 0.1,
    ) -> tuple[dict, LLMUsage]:
        body = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            response = self.client.post(
                f"{self.config.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                json=body,
            )
        except Exception as exc:  # noqa: BLE001
            raise ModuleError(
                "E_LLM_HTTP", f"LLM request failed: {type(exc).__name__}", "M1", retryable=True
            ) from exc
        if response.status_code != 200:
            raise ModuleError(
                "E_LLM_HTTP",
                f"LLM HTTP {response.status_code}",
                "M1",
                retryable=response.status_code >= 500 or response.status_code == 429,
            )
        payload = response.json()
        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or message.get("reasoning_content") or ""
        if not content:
            raise ModuleError(
                "E_LLM_EMPTY",
                "LLM returned empty content",
                "M1",
                retryable=True,
            )
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        if not text.startswith("{"):
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                text = text[start : end + 1]
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ModuleError(
                "E_LLM_JSON",
                "LLM returned non-JSON content",
                "M1",
                retryable=True,
                details={"preview": text[:300]},
            ) from exc
        if not isinstance(parsed, dict):
            raise ModuleError("E_LLM_JSON", "LLM returned non-object", "M1", retryable=True)
        usage_raw = payload.get("usage") or {}
        usage = self._usage(usage_raw, prompt_version)
        usage = LLMUsage(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=usage.cost_usd,
            model=usage.model,
            prompt_version=usage.prompt_version,
            reasoning=str(message.get("reasoning_content") or ""),
        )
        return parsed, usage


    def stream_json(
        self,
        messages: list[dict[str, str]],
        *,
        on_delta: Callable[[str], None] | None = None,
        prompt_version: str = "m1-p01",
        max_tokens: int = 1200,
        temperature: float = 0.1,
    ) -> tuple[dict, LLMUsage]:
        body = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "stream": True,
        }
        content: list[str] = []
        usage_raw: dict = {}
        try:
            with self.client.stream(
                "POST",
                f"{self.config.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                json=body,
            ) as response:
                if response.status_code != 200:
                    raise ModuleError(
                        "E_LLM_HTTP",
                        f"LLM HTTP {response.status_code}",
                        "M1",
                        retryable=response.status_code >= 500 or response.status_code == 429,
                    )
                for line in response.iter_lines():
                    if not line:
                        continue
                    data = line[5:].strip() if line.startswith("data:") else line.strip()
                    if data == "[DONE]":
                        break
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    usage_raw = payload.get("usage") or usage_raw
                    choice = (payload.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}
                    piece = delta.get("content") or ""
                    if piece:
                        content.append(piece)
                        if on_delta is not None:
                            on_delta(piece)
        except ModuleError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ModuleError(
                "E_LLM_HTTP",
                f"LLM stream failed: {type(exc).__name__}",
                "M1",
                retryable=True,
            ) from exc
        text = "".join(content).strip()
        if not text:
            raise ModuleError("E_LLM_EMPTY", "LLM returned empty stream", "M1", retryable=True)
        parsed = self._parse_text(text)
        usage = self._usage(usage_raw, prompt_version)
        return parsed, usage

    def _parse_text(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        if not text.startswith("{"):
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                text = text[start : end + 1]
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ModuleError(
                "E_LLM_JSON",
                "LLM returned non-JSON content",
                "M1",
                retryable=True,
                details={"preview": text[:300]},
            ) from exc
        if not isinstance(parsed, dict):
            raise ModuleError("E_LLM_JSON", "LLM returned non-object", "M1", retryable=True)
        return parsed

    def _usage(self, usage_raw: dict, prompt_version: str) -> LLMUsage:
        prompt = int(usage_raw.get("prompt_tokens") or 0)
        completion = int(usage_raw.get("completion_tokens") or 0)
        now = datetime.now(UTC)
        peak = now.weekday() < 5 and (
            1 <= now.hour < 4 or 6 <= now.hour < 10
        )
        multiplier = 1.0 if peak else self.config.off_peak_multiplier
        cost = (
            prompt / 1_000_000 * self.config.input_cost_per_m * multiplier
            + completion / 1_000_000 * self.config.output_cost_per_m * multiplier
        )
        return LLMUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            cost_usd=cost,
            model=self.config.model,
            prompt_version=prompt_version,
        )


def load_llm_config(dotenv_path: str | Path = ".env") -> LLMConfig:
    return LLMConfig.from_env(dotenv_path)
