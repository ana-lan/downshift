"""Score model outputs against eval expectations.

Three gradings, matching the call site's `grading` field:
  exact        strict string match after normalizing case, whitespace, fences
               and outer punctuation
  json_fields  output parsed as a JSON object, graded fields compared one by one
  judge        a judge model scores the output 1 to 5 against the case rubric

Every scorer returns a Score with a value in [0, 1] and a pass flag, so the
decide step can treat all gradings the same way.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from downshift.llm import ChatMessage, LLMClient

JUDGE_PASS_AT = 4

_OUTER_PUNCT = " \t\r\n.,;:!?\"'`*()[]"
_FENCE = re.compile(r"^```(?:[\w-]+\n)?\s*(.*?)\s*```$", re.DOTALL)
_SCORE_LABEL = re.compile(r"\bscore\b\s*(?:is|of|=|:)?\s*\**\s*([1-5])(?!\d|\.\d)", re.IGNORECASE)
_OUT_OF = re.compile(r"(?<![\d.])([1-5])\s*(?:/|out of)\s*5(?!\d)", re.IGNORECASE)
_LONE = re.compile(r"\s*([1-5])\s*\.?\s*")

JUDGE_SYSTEM = (
    "You grade the output of an AI assistant inside a customer support app. "
    "Read the task the assistant was given, its output, and the rubric. "
    "Score the output from 1 (fails the rubric) to 5 (fully meets it). "
    'Reply with JSON only: {"score": <1-5>, "reason": "<one sentence>"}.'
)


@dataclass(frozen=True)
class Score:
    """Result of scoring one output. value is in [0, 1]."""

    value: float
    passed: bool
    detail: str = ""
    judge_score: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Judge:
    """The model that grades judge-graded call sites."""

    client: LLMClient
    model: str
    pass_at: int = JUDGE_PASS_AT
    max_tokens: int = 200


def _clip(text: str, limit: int = 80) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def strip_fences(text: str) -> str:
    """Remove a surrounding ``` or ```lang fence, if any."""
    stripped = text.strip()
    match = _FENCE.match(stripped)
    return match.group(1).strip() if match else stripped


def normalize_text(text: str) -> str:
    """Lowercase, collapse whitespace, drop fences and outer punctuation."""
    collapsed = " ".join(strip_fences(text).split()).lower()
    return collapsed.strip(_OUTER_PUNCT)


def score_exact(output: str, expected: Any) -> Score:
    got = normalize_text(output)
    want = normalize_text(str(expected))
    if got == want:
        return Score(1.0, True, "match")
    return Score(0.0, False, f"expected {want!r}, got {_clip(got)!r}")


def parse_json_object(text: str) -> dict[str, Any] | None:
    """Parse a JSON object from model output (fences and surrounding prose allowed)."""
    body = strip_fences(text)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        start, end = body.find("{"), body.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            data = json.loads(body[start : end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _norm_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, dict | list):
        return json.dumps(value, sort_keys=True).lower()
    text = " ".join(str(value).split()).lower()
    return "" if text in {"null", "none"} else text


def score_json_fields(
    output: str, expected: Mapping[str, Any], fields: Sequence[str] | None = None
) -> Score:
    """Compare graded fields. value = fraction matching; passed only if all match."""
    names = list(fields) if fields else list(expected)
    if not names:
        raise ValueError("json_fields grading needs at least one field")
    data = parse_json_object(output)
    if data is None:
        return Score(0.0, False, "output is not a JSON object")
    wrong: list[str] = []
    for name in names:
        if name not in data:
            wrong.append(f"{name}: missing")
        elif _norm_value(data[name]) != _norm_value(expected.get(name)):
            wrong.append(f"{name}: expected {expected.get(name)!r}, got {data[name]!r}")
    value = (len(names) - len(wrong)) / len(names)
    detail = "all fields match" if not wrong else "; ".join(wrong)
    return Score(value, not wrong, detail)


def _as_score(raw: Any) -> int | None:
    if isinstance(raw, bool):
        return None
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    if not number.is_integer() or not 1 <= number <= 5:
        return None
    return int(number)


def parse_judge_score(text: str) -> int | None:
    """Pull a 1 to 5 score out of a judge reply. None if there is no clear score."""
    data = parse_json_object(text)
    if data is not None and "score" in data:
        return _as_score(data["score"])
    for pattern in (_SCORE_LABEL, _OUT_OF):
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    lone = _LONE.fullmatch(text)
    return int(lone.group(1)) if lone else None


def build_judge_messages(
    prompt_messages: Sequence[ChatMessage], output: str, rubric: str
) -> list[dict[str, str]]:
    task = "\n\n".join(
        f"[{m.get('role', 'user')}]\n{m.get('content', '')}" for m in prompt_messages
    )
    user = (
        f"## Task given to the assistant\n{task}\n\n"
        f"## Assistant output\n{output}\n\n"
        f"## Rubric\n{rubric}\n\n"
        "Return the JSON now."
    )
    return [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}]


def score_judge(
    judge: Judge, prompt_messages: Sequence[ChatMessage], output: str, rubric: str
) -> Score:
    """Ask the judge model for a 1 to 5 score. LLMError propagates to the caller."""
    if not output.strip():
        return Score(0.0, False, "empty output")
    completion = judge.client.complete(
        judge.model,
        build_judge_messages(prompt_messages, output, rubric),
        temperature=0.0,
        max_tokens=judge.max_tokens,
        json_mode=True,
    )
    score = parse_judge_score(completion.text)
    if score is None:
        return Score(0.0, False, f"judge reply unparseable: {_clip(completion.text)!r}")
    data = parse_json_object(completion.text)
    reason = str(data.get("reason", "")).strip() if data else ""
    detail = f"judge {score}/5" + (f": {_clip(reason, 160)}" if reason else "")
    return Score((score - 1) / 4, score >= judge.pass_at, detail, judge_score=score)


def score_case(
    grading: str,
    expected: Any,
    output: str,
    *,
    fields: Sequence[str] | None = None,
    prompt_messages: Sequence[ChatMessage] = (),
    judge: Judge | None = None,
) -> Score:
    """Score one output with the case's grading."""
    if grading == "exact":
        return score_exact(output, expected)
    if grading == "json_fields":
        if not isinstance(expected, Mapping):
            raise ValueError("json_fields expected value must be an object")
        return score_json_fields(output, expected, fields)
    if grading == "judge":
        if judge is None:
            raise ValueError("judge grading needs a Judge")
        return score_judge(judge, prompt_messages, output, str(expected))
    raise ValueError(f"unknown grading {grading!r}")
