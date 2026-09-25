import pytest

from downshift.evalgen import generate_eval_set
from downshift.llm import OpenAICompatClient
from downshift.schema import CallSite, ModelRef, PromptMessage

pytestmark = pytest.mark.integration


def test_real_evalgen_with_ollama() -> None:
    site = CallSite(
        id="app/triage.py::classify",
        file="app/triage.py",
        line=1,
        function="classify",
        api="openai.chat.completions",
        model=ModelRef(value="m", source="literal", expression="'m'"),
        messages=[PromptMessage("user", "Classify this ticket:\n{ticket_text}")],
        purpose="Classify a support ticket.",
        output_contract="Exactly one word from the set {billing, shipping, other}.",
        grading="exact",
    )
    client = OpenAICompatClient("http://localhost:11434/v1", "ollama")
    result = generate_eval_set(client, "qwen2.5:7b", site, count=3)
    assert result.cases, result.dropped
    assert all(c.expected in {"billing", "shipping", "other"} for c in result.cases)
