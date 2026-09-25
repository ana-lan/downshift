"""LLM client interface used by every Downshift command.

All model calls go through LLMClient, so tests can swap in FakeLLMClient
and run with no network and no models.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

ChatMessage = Mapping[str, str]
Responder = Callable[[str, list[dict[str, str]]], str]


class LLMError(Exception):
    """Raised when a model call fails."""


@dataclass(frozen=True)
class Completion:
    """One model response plus the numbers Downshift needs for cost math."""

    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@runtime_checkable
class LLMClient(Protocol):
    """Anything that can run a chat completion."""

    def complete(
        self,
        model: str,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> Completion: ...


class OpenAICompatClient:
    """Client for any OpenAI-compatible endpoint (Ollama, vLLM, OpenAI, Groq, ...)."""

    def __init__(
        self,
        base_url: str,
        api_key: str = "not-needed",
        *,
        timeout: float = 120.0,
        client: Any = None,
    ) -> None:
        if client is None:
            from openai import OpenAI

            client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self._client = client

    def complete(
        self,
        model: str,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> Completion:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [dict(m) for m in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        start = time.perf_counter()
        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise LLMError(f"call to {model!r} failed: {exc}") from exc
        latency = time.perf_counter() - start

        if not response.choices:
            raise LLMError(f"call to {model!r} returned no choices")
        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        return Completion(
            text=text,
            model=model,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            latency_s=latency,
        )


@dataclass(frozen=True)
class FakeCall:
    """A call recorded by FakeLLMClient, for assertions in tests."""

    model: str
    messages: list[dict[str, str]]
    temperature: float
    max_tokens: int | None
    json_mode: bool


def estimate_tokens(text: str) -> int:
    """Deterministic stand-in for a tokenizer: one token per whitespace-separated word."""
    return len(text.split())


class FakeLLMClient:
    """In-memory client for tests. No network, no models.

    responses can be:
      - a string: every call returns it
      - a mapping of model name to string: unknown models raise LLMError
      - a function (model, messages) -> string
    """

    def __init__(
        self,
        responses: str | Mapping[str, str] | Responder = "",
        *,
        latency_s: float = 0.0,
    ) -> None:
        self._responses = responses
        self._latency_s = latency_s
        self.calls: list[FakeCall] = []

    def complete(
        self,
        model: str,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> Completion:
        msgs = [dict(m) for m in messages]
        self.calls.append(FakeCall(model, msgs, temperature, max_tokens, json_mode))
        text = self._respond(model, msgs)
        prompt_text = " ".join(m.get("content", "") for m in msgs)
        return Completion(
            text=text,
            model=model,
            prompt_tokens=estimate_tokens(prompt_text),
            completion_tokens=estimate_tokens(text),
            latency_s=self._latency_s,
        )

    def _respond(self, model: str, msgs: list[dict[str, str]]) -> str:
        if isinstance(self._responses, str):
            return self._responses
        if isinstance(self._responses, Mapping):
            if model not in self._responses:
                raise LLMError(f"FakeLLMClient has no response for model {model!r}")
            return self._responses[model]
        return self._responses(model, msgs)
