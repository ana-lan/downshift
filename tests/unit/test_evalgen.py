"""Tests for eval generation with a fake model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from downshift.evalgen import (
    EvalGenSkip,
    generate_eval_set,
    grading_for,
    parse_cases,
    write_eval_set,
)
from downshift.evals import EvalCase, load_eval_set
from downshift.llm import FakeLLMClient
from downshift.schema import CallSite, ModelRef, PromptMessage


def _site(
    *,
    contents: tuple[str, ...] = ("Ticket:\n{ticket_text}",),
    grading: str | None = "exact",
    contract: str | None = "One word from the set {billing, shipping, other}.",
    output_format: str = "text",
    resolved: bool = True,
) -> CallSite:
    return CallSite(
        id="app/triage.py::classify",
        file="app/triage.py",
        line=1,
        function="classify",
        api="openai.chat.completions",
        model=ModelRef(value="m", source="literal", expression="'m'"),
        messages=[PromptMessage("user", c, resolved) for c in contents],
        output_format=output_format,
        purpose="Classify a ticket.",
        output_contract=contract,
        grading=grading,
    )


def _c(text: str, expected: Any = "billing", notes: str = "n") -> dict:
    return {"inputs": {"ticket_text": text}, "expected": expected, "notes": notes}


def _reply(*cases: Any) -> str:
    return json.dumps({"cases": list(cases)})


def _prompt(fake: FakeLLMClient, call: int = 0) -> str:
    return fake.calls[call].messages[1]["content"]


# --- generate ---------------------------------------------------------------------


def test_generates_and_renumbers() -> None:
    fake = FakeLLMClient(_reply(_c("a"), _c("b", "shipping"), _c("c", "other")))
    result = generate_eval_set(fake, "big", _site(), count=3)
    assert [c.id for c in result.cases] == ["classify-01", "classify-02", "classify-03"]
    assert all(c.grading == "exact" for c in result.cases)
    assert result.attempts == 1 and result.dropped == []
    call = fake.calls[0]
    assert call.model == "big" and call.json_mode and call.temperature == 0.7


def test_drops_bad_cases_with_reasons() -> None:
    reply = _reply(
        _c("good"),
        _c("label", "Billing"),
        {"inputs": {"text": "x"}, "expected": "billing"},
        "just a string",
        {"inputs": "flat", "expected": "billing", "notes": "flat inputs"},
        _c("good", notes="again"),
    )
    result = generate_eval_set(FakeLLMClient(reply), "m", _site(), count=10, max_attempts=1)
    assert len(result.cases) == 1
    joined = "\n".join(result.dropped)
    assert "'Billing' is not one of billing, shipping, other" in joined
    assert "inputs missing ticket_text" in joined
    assert "not an object: just a string" in joined
    assert "inputs is not an object: flat inputs" in joined
    assert "duplicate inputs: again" in joined


def test_retries_after_malformed_json() -> None:
    replies = iter(["not json at all", _reply(_c("a"), _c("b"))])
    fake = FakeLLMClient(lambda model, msgs: next(replies))
    result = generate_eval_set(fake, "m", _site(), count=2)
    assert len(result.cases) == 2
    assert result.attempts == 2
    assert result.dropped[0].startswith("attempt 1: reply is not valid JSON")


def test_second_attempt_asks_only_for_the_rest() -> None:
    replies = iter([_reply(_c("a"), _c("b")), _reply(_c("c"), _c("d"))])
    fake = FakeLLMClient(lambda model, msgs: next(replies))
    result = generate_eval_set(fake, "m", _site(), count=3)
    assert [c.inputs["ticket_text"] for c in result.cases] == ["a", "b", "c"]
    assert "Write 3 diverse" in _prompt(fake, 0)
    assert "Write 1 diverse" in _prompt(fake, 1)


def test_stops_after_max_attempts() -> None:
    fake = FakeLLMClient("{}")
    result = generate_eval_set(fake, "m", _site(), count=5, max_attempts=3)
    assert result.cases == []
    assert result.attempts == 3
    assert all('no "cases" list' in d for d in result.dropped)


@pytest.mark.parametrize(
    ("site", "message"),
    [
        (_site(contents=("{ticket['body']}",)), "expression placeholders {ticket['body']}"),
        (_site(resolved=False), "prompt is not resolved"),
    ],
)
def test_skips_sites_that_need_the_auditor(site: CallSite, message: str) -> None:
    fake = FakeLLMClient(_reply(_c("a")))
    with pytest.raises(EvalGenSkip, match=message.replace("[", r"\[").replace("{", r"\{")):
        generate_eval_set(fake, "m", site)
    assert fake.calls == []


def test_shared_inputs_go_in_prompt_not_cases() -> None:
    site = _site(contents=("{policy}\n{ticket_text}",))
    fake = FakeLLMClient(_reply(_c("a")))
    shared = {"policy": "POLICY TEXT", "unused": "IGNORED"}
    result = generate_eval_set(fake, "m", site, count=1, shared=shared)
    assert len(result.cases) == 1
    prompt = _prompt(fake)
    assert "--- policy ---\nPOLICY TEXT" in prompt
    assert "IGNORED" not in prompt
    assert "exactly these keys: ticket_text" in prompt


# --- prompt rules -----------------------------------------------------------------


def test_prompt_rules_per_grading() -> None:
    cases = [
        (_site(), "exactly one of billing, shipping, other"),
        (_site(contract="Two-letter code."), "the exact short answer"),
        (
            _site(grading="json_fields", contract="Graded fields: order_id, order_date."),
            "exactly these keys: order_id, order_date",
        ),
        (_site(grading="json_fields", contract="Some JSON."), "the JSON object the feature"),
        (_site(grading="judge", contract="Two sentences."), "a rubric string"),
    ]
    for site, expected_text in cases:
        fake = FakeLLMClient("{}")
        generate_eval_set(fake, "m", site, count=1, max_attempts=1)
        assert expected_text in _prompt(fake)


def test_grading_for_defaults() -> None:
    assert grading_for(_site(grading="exact")) == "exact"
    assert grading_for(_site(grading=None, output_format="json")) == "json_fields"
    assert grading_for(_site(grading=None)) == "judge"


# --- parse ------------------------------------------------------------------------


def test_parse_cases_accepts_fences_and_bare_lists() -> None:
    assert parse_cases('```json\n{"cases": [1]}\n```') == [1]
    assert parse_cases("[1, 2]") == [1, 2]


@pytest.mark.parametrize(("text", "message"), [("nope", "not valid JSON"), ('{"x": 1}', "no")])
def test_parse_cases_errors(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_cases(text)


# --- write ------------------------------------------------------------------------


def _cases() -> list[EvalCase]:
    return [EvalCase("classify-01", {"ticket_text": "a"}, "billing", "exact", "n")]


def test_write_eval_set_plain(tmp_path: Path) -> None:
    path = tmp_path / "out" / "x.jsonl"
    write_eval_set(path, _cases())
    first = json.loads(path.read_text().splitlines()[0])
    assert first["id"] == "classify-01"
    assert load_eval_set(path).cases[0].expected == "billing"


def test_write_eval_set_with_shared_file(tmp_path: Path) -> None:
    policy = tmp_path / "data" / "policy.md"
    policy.parent.mkdir()
    policy.write_text("30 days.")
    path = tmp_path / "evals" / "x.jsonl"
    write_eval_set(path, _cases(), {"policy": policy})
    header = json.loads(path.read_text().splitlines()[0])
    assert header == {"shared": {"policy": {"file": "../data/policy.md"}}}
    loaded = load_eval_set(path)
    assert loaded.shared == {"policy": "30 days."}
    assert loaded.problems == []
