"""LLM adapters — Groq (prod path) + Fake (tests).

Why an adapter: services depend on a narrow interface, not Groq SDK details.
Swap providers later without rewriting drafting logic.
"""

from __future__ import annotations

from typing import Protocol, Sequence

import httpx

from app.config import get_settings
from app.schemas.drafting import LLMCompletion, LLMMessage


class LLMAdapter(Protocol):
    def complete(self, messages: Sequence[LLMMessage], *, temperature: float = 0.2) -> LLMCompletion: ...


class LLMError(Exception):
    pass


class GroqAdapter:
    """OpenAI-compatible Chat Completions against Groq."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://api.groq.com/openai/v1",
        timeout: float = 60.0,
    ):
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.groq_api_key
        self.model = model or settings.groq_model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(self, messages: Sequence[LLMMessage], *, temperature: float = 0.2) -> LLMCompletion:
        if not self.api_key:
            raise LLMError(
                "GROQ_API_KEY is not set. Add it to .env before generating drafts."
            )

        payload = {
            "model": self.model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise LLMError(f"Groq request failed: {exc}") from exc

        if response.status_code >= 400:
            raise LLMError(f"Groq error {response.status_code}: {response.text}")

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
            model_name = data.get("model") or self.model
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected Groq response shape: {data}") from exc

        return LLMCompletion(content=content, model_name=model_name, raw=data)


class FakeLLMAdapter:
    """Deterministic stub for unit tests — no network."""

    def __init__(self, content: str, model_name: str = "fake-llm"):
        self.content = content
        self.model_name = model_name
        self.calls: list[list[LLMMessage]] = []

    def complete(self, messages: Sequence[LLMMessage], *, temperature: float = 0.2) -> LLMCompletion:
        self.calls.append(list(messages))
        return LLMCompletion(content=self.content, model_name=self.model_name)


def get_llm_adapter() -> GroqAdapter:
    return GroqAdapter()
