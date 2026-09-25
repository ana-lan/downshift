from __future__ import annotations

import pytest

from downshift.llm import FakeLLMClient, LLMError
from downshift.scorer import (
    JUDGE_SYSTEM,
    Judge,
    Score,
    build_judge_messages,
    normalize_text,
    parse_json_object,
    parse_judge_score,
    score_case,
    score_exact,
    score_json_fields,
    score_judge,
    strip_fences,
)

PROMPT = [
    {"role": "system", "content": "You write support replies."},
    {"role": "user", "content": "Customer: where is my order?"},
]

# --- normalization -------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ("```\nbilling\n```", "billing"),
        ("```billing```", "billing"),
        ("  plain  ", "plain"),
    ],
)
def test_strip_fences(text: str, expected: str) -> None:
    assert strip_fences(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Billing", "billing"),
        ("  billing.\n", "billing"),
        ('"billing"', "billing"),
        ("**Billing**", "billing"),
        ("`en`", "en"),
        ("very   Negative", "very negative"),
        ("```\nshipping\n```", "shipping"),
        ("zh-CN", "zh-cn"),
    ],
)
def test_normalize_text(text: str, expected: str) -> None:
    assert normalize_text(text) == expected


# --- exact ----------------------------------------------------------------


@pytest.mark.parametrize("output", ["billing", "Billing.", " BILLING \n", "'billing'"])
def test_exact_match(output: str) -> None:
    score = score_exact(output, "billing")
    assert score == Score(1.0, True, "match")


@pytest.mark.parametrize("output", ["shipping", "Category: billing", "billing or refund", ""])
def test_exact_mismatch_is_strict(output: str) -> None:
    score = score_exact(output, "billing")
    assert score.value == 0.0
    assert not score.passed
    assert "expected 'billing'" in score.detail


def test_exact_clips_long_output_in_detail() -> None:
    score = score_exact("word " * 100, "billing")
    assert score.detail.endswith("...'")


# --- JSON parsing ---------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('Here you go: {"a": 1} hope it helps', {"a": 1}),
        ("[1, 2]", None),
        ("not json", None),
        ("", None),
        ("{broken", None),
        ("{ still broken }", None),
    ],
)
def test_parse_json_object(text: str, expected: dict[str, int] | None) -> None:
    assert parse_json_object(text) == expected


# --- json_fields ----------------------------------------------------------

REFUND_EXPECTED = {"is_refund_request": True, "eligible": False, "policy_section": "2.1"}
REFUND_FIELDS = ["is_refund_request", "eligible", "policy_section"]


def test_json_fields_all_match_ignores_ungraded_fields() -> None:
    output = (
        '{"is_refund_request": true, "eligible": false, '
        '"policy_section": "2.1", "reasoning": "anything"}'
    )
    score = score_json_fields(output, REFUND_EXPECTED, REFUND_FIELDS)
    assert score == Score(1.0, True, "all fields match")


def test_json_fields_tolerates_types_and_case() -> None:
    output = '{"is_refund_request": "True", "eligible": "false", "policy_section": 2.1}'
    assert score_json_fields(output, REFUND_EXPECTED, REFUND_FIELDS).passed


def test_json_fields_partial_credit() -> None:
    output = '{"is_refund_request": true, "eligible": true, "policy_section": "3.1"}'
    score = score_json_fields(output, REFUND_EXPECTED, REFUND_FIELDS)
    assert score.value == pytest.approx(1 / 3)
    assert not score.passed
    assert "eligible: expected False, got True" in score.detail
    assert "policy_section" in score.detail


def test_json_fields_missing_field() -> None:
    output = '{"is_refund_request": true, "eligible": false}'
    score = score_json_fields(output, REFUND_EXPECTED, REFUND_FIELDS)
    assert score.value == pytest.approx(2 / 3)
    assert "policy_section: missing" in score.detail


def test_json_fields_not_json() -> None:
    score = score_json_fields("I think it is eligible", REFUND_EXPECTED, REFUND_FIELDS)
    assert score == Score(0.0, False, "output is not a JSON object")


@pytest.mark.parametrize("got", ["null", '""', '"null"', '"None"'])
def test_json_fields_null_equivalents(got: str) -> None:
    output = f'{{"order_id": {got}, "order_date": "2026-09-01"}}'
    expected = {"order_id": None, "order_date": "2026-09-01"}
    assert score_json_fields(output, expected).passed


def test_json_fields_integer_float_and_nested() -> None:
    expected = {"n": 14, "tags": ["a", "b"]}
    assert score_json_fields('{"n": 14.0, "tags": ["a", "b"]}', expected).passed
    assert not score_json_fields('{"n": 14.5, "tags": ["a", "b"]}', expected).passed


def test_json_fields_defaults_to_expected_keys() -> None:
    score = score_json_fields('{"a": 1, "b": 2}', {"a": 1})
    assert score.passed


def test_json_fields_needs_a_field() -> None:
    with pytest.raises(ValueError, match="at least one field"):
        score_json_fields("{}", {})


# --- judge parsing --------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"score": 4, "reason": "ok"}', 4),
        ('{"score": "5"}', 5),
        ('```json\n{"score": 2}\n```', 2),
        ('{"score": 3.0}', 3),
        ("Score: 3", 3),
        ("**Score:** 2", 2),
        ("The score is 5.", 5),
        ("I'd give it 4/5.", 4),
        ("4 out of 5, minor tone issue", 4),
        ("3", 3),
        (" 1. ", 1),
        ('{"score": 7}', None),
        ('{"score": 0}', None),
        ('{"score": 4.5}', None),
        ('{"score": true}', None),
        ('{"score": "high"}', None),
        ("Score: 45", None),
        ("no idea", None),
        ("", None),
    ],
)
def test_parse_judge_score(text: str, expected: int | None) -> None:
    assert parse_judge_score(text) == expected


def test_build_judge_messages_includes_task_output_rubric() -> None:
    msgs = build_judge_messages(PROMPT, "It ships tomorrow.", "No timing promises.")
    assert msgs[0] == {"role": "system", "content": JUDGE_SYSTEM}
    user = msgs[1]["content"]
    assert "[system]\nYou write support replies." in user
    assert "Customer: where is my order?" in user
    assert "## Assistant output\nIt ships tomorrow." in user
    assert "## Rubric\nNo timing promises." in user


# --- judge scoring --------------------------------------------------------


def test_score_judge_pass() -> None:
    client = FakeLLMClient('{"score": 5, "reason": "Polite and accurate."}')
    judge = Judge(client, "judge-m")
    score = score_judge(judge, PROMPT, "Sorry about that, checking now.", "Be polite.")
    assert score == Score(1.0, True, "judge 5/5: Polite and accurate.", judge_score=5)
    call = client.calls[0]
    assert call.model == "judge-m"
    assert call.json_mode is True
    assert call.temperature == 0.0
    assert call.max_tokens == 200
    assert "Be polite." in call.messages[1]["content"]


def test_score_judge_below_threshold() -> None:
    judge = Judge(FakeLLMClient('{"score": 3}'), "judge-m")
    score = score_judge(judge, PROMPT, "ok", "rubric")
    assert score.value == 0.5
    assert not score.passed
    assert score.detail == "judge 3/5"
    assert score.judge_score == 3


def test_score_judge_custom_pass_at() -> None:
    judge = Judge(FakeLLMClient("Score: 3"), "judge-m", pass_at=3)
    assert score_judge(judge, PROMPT, "ok", "rubric").passed


def test_score_judge_unparseable() -> None:
    judge = Judge(FakeLLMClient("looks fine to me"), "judge-m")
    score = score_judge(judge, PROMPT, "ok", "rubric")
    assert score.value == 0.0
    assert not score.passed
    assert score.judge_score is None
    assert "unparseable" in score.detail


def test_score_judge_empty_output_skips_judge() -> None:
    client = FakeLLMClient('{"score": 5}')
    score = score_judge(Judge(client, "judge-m"), PROMPT, "   ", "rubric")
    assert score == Score(0.0, False, "empty output")
    assert client.calls == []


def test_score_judge_llm_error_propagates() -> None:
    judge = Judge(FakeLLMClient({"other": "x"}), "judge-m")
    with pytest.raises(LLMError):
        score_judge(judge, PROMPT, "ok", "rubric")


# --- dispatch -------------------------------------------------------------


def test_score_case_exact() -> None:
    assert score_case("exact", "en", "EN").passed


def test_score_case_json_fields_uses_fields() -> None:
    score = score_case("json_fields", {"a": 1}, '{"a": 1, "b": 9}', fields=["a"])
    assert score.passed


def test_score_case_judge() -> None:
    judge = Judge(FakeLLMClient('{"score": 4}'), "judge-m")
    score = score_case("judge", "Be polite.", "Hello!", prompt_messages=PROMPT, judge=judge)
    assert score.passed
    assert score.judge_score == 4


def test_score_case_judge_needs_judge() -> None:
    with pytest.raises(ValueError, match="needs a Judge"):
        score_case("judge", "rubric", "output")


def test_score_case_json_fields_needs_object() -> None:
    with pytest.raises(ValueError, match="must be an object"):
        score_case("json_fields", "not a dict", "{}")


def test_score_case_unknown_grading() -> None:
    with pytest.raises(ValueError, match="unknown grading"):
        score_case("fuzzy", "x", "x")


def test_score_to_dict() -> None:
    assert Score(0.5, False, "d", 3).to_dict() == {
        "value": 0.5,
        "passed": False,
        "detail": "d",
        "judge_score": 3,
    }
