from types import SimpleNamespace
from typing import Any

import pytest

from downshift.llm import (
    Completion,
    FakeLLMClient,
    LLMClient,
    LLMError,
    OpenAICompatClient,
    estimate_tokens,
)

MESSAGES = [
    {"role": "system", "content": "You classify tickets."},
    {"role": "user", "content": "My order never arrived"},
]


class StubCompletions:
    """Mimics openai's client.chat.completions so no network is needed."""

    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.kwargs: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.response


def make_response(content: str | None, usage: tuple[int, int] | None = (12, 3)) -> Any:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=None
        if usage is None
        else SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1]),
    )


def make_client(stub: StubCompletions) -> OpenAICompatClient:
    sdk = SimpleNamespace(chat=SimpleNamespace(completions=stub))
    return OpenAICompatClient("http://unused", client=sdk)


# --- OpenAICompatClient -------------------------------------------------------


def test_openai_client_maps_response_and_usage() -> None:
    client = make_client(StubCompletions(make_response("shipping", usage=(20, 1))))
    result = client.complete("qwen2.5:7b", MESSAGES)
    assert result.text == "shipping"
    assert result.model == "qwen2.5:7b"
    assert result.prompt_tokens == 20
    assert result.completion_tokens == 1
    assert result.total_tokens == 21
    assert result.latency_s >= 0


def test_openai_client_sends_optional_params_when_set() -> None:
    stub = StubCompletions(make_response("{}"))
    make_client(stub).complete("m", MESSAGES, temperature=0.3, max_tokens=50, json_mode=True)
    assert stub.kwargs == {
        "model": "m",
        "messages": MESSAGES,
        "temperature": 0.3,
        "max_tokens": 50,
        "response_format": {"type": "json_object"},
    }


def test_openai_client_omits_optional_params_by_default() -> None:
    stub = StubCompletions(make_response("ok"))
    make_client(stub).complete("m", MESSAGES)
    assert stub.kwargs is not None
    assert "max_tokens" not in stub.kwargs
    assert "response_format" not in stub.kwargs
    assert stub.kwargs["temperature"] == 0.0


def test_openai_client_handles_missing_usage_and_empty_content() -> None:
    client = make_client(StubCompletions(make_response(None, usage=None)))
    result = client.complete("m", MESSAGES)
    assert result.text == ""
    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0


def test_openai_client_wraps_sdk_errors() -> None:
    client = make_client(StubCompletions(error=RuntimeError("connection refused")))
    with pytest.raises(LLMError, match="qwen2.5:7b.*connection refused"):
        client.complete("qwen2.5:7b", MESSAGES)


def test_openai_client_rejects_empty_choices() -> None:
    client = make_client(StubCompletions(SimpleNamespace(choices=[], usage=None)))
    with pytest.raises(LLMError, match="no choices"):
        client.complete("m", MESSAGES)


def test_openai_client_builds_real_sdk_client_without_network() -> None:
    client = OpenAICompatClient("http://localhost:11434/v1", "ollama")
    assert isinstance(client, LLMClient)


# --- FakeLLMClient ------------------------------------------------------------


def test_fake_returns_fixed_string_and_records_calls() -> None:
    fake = FakeLLMClient("refund")
    result = fake.complete("m", MESSAGES, max_tokens=5, json_mode=True)
    assert result.text == "refund"
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call.model == "m"
    assert call.messages == MESSAGES
    assert call.max_tokens == 5
    assert call.json_mode is True


def test_fake_mapping_by_model() -> None:
    fake = FakeLLMClient({"big": "billing", "small": "other"})
    assert fake.complete("big", MESSAGES).text == "billing"
    assert fake.complete("small", MESSAGES).text == "other"


def test_fake_mapping_unknown_model_raises() -> None:
    fake = FakeLLMClient({"big": "billing"})
    with pytest.raises(LLMError, match="tiny"):
        fake.complete("tiny", MESSAGES)


def test_fake_callable_receives_model_and_messages() -> None:
    fake = FakeLLMClient(lambda model, msgs: f"{model}:{msgs[-1]['content']}")
    assert fake.complete("m", MESSAGES).text == "m:My order never arrived"


def test_fake_token_counts_are_deterministic() -> None:
    result = FakeLLMClient("one two three").complete("m", MESSAGES)
    assert result.prompt_tokens == estimate_tokens("You classify tickets. My order never arrived")
    assert result.completion_tokens == 3


def test_fake_satisfies_protocol() -> None:
    assert isinstance(FakeLLMClient(), LLMClient)


def test_estimate_tokens_edge_cases() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("  spaced   out  ") == 2


def test_completion_total_tokens() -> None:
    assert Completion("x", "m", 7, 5, 0.1).total_tokens == 12
