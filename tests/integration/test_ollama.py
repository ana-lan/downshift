import pytest

from downshift.llm import OpenAICompatClient

pytestmark = pytest.mark.integration


def test_real_ollama_roundtrip() -> None:
    client = OpenAICompatClient("http://localhost:11434/v1", "ollama")
    result = client.complete(
        "qwen2.5:0.5b",
        [{"role": "user", "content": "Reply with only the word: ok"}],
        max_tokens=5,
    )
    assert result.text.strip()
    assert result.prompt_tokens > 0
    assert result.completion_tokens > 0
