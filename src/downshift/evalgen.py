"""Generate eval sets with any configured model (the no-Bob path).

`generate_eval_set` asks a model for test cases for one call site, then keeps
only the cases that pass the same checks as `downshift check-evals`. Cases are
renumbered, so the model never has to get ids right. The CLI command
`evalgen` is a thin wrapper that writes one `<slug>.jsonl` per call site.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from downshift.evals import (
    EvalCase,
    EvalSet,
    allowed_values,
    expression_placeholders,
    graded_fields,
    site_placeholders,
    validate_eval_set,
)
from downshift.llm import LLMClient
from downshift.schema import CallSite

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")

SYSTEM_PROMPT = (
    "You write test cases for one LLM feature in a software product. "
    "Every expected answer must be certainly correct. Reply with JSON only."
)


class EvalGenSkip(Exception):
    """Raised when a call site cannot get generated evals; the message says why."""


@dataclass
class GenerationResult:
    site_id: str
    grading: str
    cases: list[EvalCase] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    attempts: int = 0


def grading_for(site: CallSite) -> str:
    """The audit's grading, or a safe default for an unaudited call site."""
    if site.grading:
        return site.grading
    return "json_fields" if site.output_format == "json" else "judge"


def generate_eval_set(
    client: LLMClient,
    model: str,
    site: CallSite,
    *,
    count: int = 20,
    shared: dict[str, str] | None = None,
    max_attempts: int = 3,
    temperature: float = 0.7,
) -> GenerationResult:
    """Ask `model` for cases until `count` valid ones are kept or attempts run out."""
    _check_site(site)
    shared = {k: v for k, v in (shared or {}).items() if k in site_placeholders(site)}
    grading = grading_for(site)
    result = GenerationResult(site_id=site.id, grading=grading)
    seen_inputs: set[str] = set()

    while len(result.cases) < count and result.attempts < max_attempts:
        result.attempts += 1
        wanted = count - len(result.cases)
        messages = build_messages(site, grading, wanted, shared)
        completion = client.complete(model, messages, temperature=temperature, json_mode=True)
        try:
            raw_cases = parse_cases(completion.text)
        except ValueError as exc:
            result.dropped.append(f"attempt {result.attempts}: {exc}")
            continue
        for raw in raw_cases:
            if len(result.cases) >= count:
                break
            case, problem = _to_case(raw, site, grading, shared, len(result.cases) + 1)
            if case is None:
                result.dropped.append(problem)
                continue
            key = json.dumps(case.inputs, sort_keys=True, ensure_ascii=False)
            if key in seen_inputs:
                result.dropped.append(f"duplicate inputs: {case.notes}")
                continue
            seen_inputs.add(key)
            result.cases.append(case)
    return result


def build_messages(
    site: CallSite, grading: str, count: int, shared: dict[str, str]
) -> list[dict[str, str]]:
    inputs = [name for name in site_placeholders(site) if name not in shared]
    prompt_lines = [f"[{m.role}]\n{m.content}" for m in site.messages or []]
    parts = [
        f"Feature: {site.purpose or site.function}",
        f"Output contract: {site.output_contract or 'not documented'}",
        "Prompt template sent to the model ({name} is filled per case):",
        "\n\n".join(prompt_lines),
    ]
    if shared:
        parts.append("Fixed inputs, the same for every case (do not repeat them in cases):")
        parts.extend(f"--- {k} ---\n{v}" for k, v in shared.items())
    parts.append(f"Write {count} diverse, realistic test cases.")
    parts.append(
        f"Each case has keys: inputs (an object with exactly these keys: "
        f"{', '.join(inputs)}), expected, notes (what the case tests)."
    )
    parts.append(_expected_rule(site, grading))
    parts.append(
        "Include edge cases: very short text, other languages, typos, "
        "missing details. Skip any case whose answer could be argued."
    )
    parts.append('Reply with: {"cases": [ ... ]}')
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def parse_cases(text: str) -> list[Any]:
    """Pull the case list out of a model reply. Raises ValueError if there is none."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"reply is not valid JSON ({exc.msg})") from exc
    if isinstance(data, dict):
        data = data.get("cases")
    if not isinstance(data, list):
        raise ValueError('reply has no "cases" list')
    return data


def write_eval_set(
    path: Path, cases: list[EvalCase], shared_files: dict[str, Path] | None = None
) -> None:
    """Write cases as JSONL, with a `shared` first line pointing at files if given."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if shared_files:
        header = {
            key: {"file": Path(os.path.relpath(target, path.parent)).as_posix()}
            for key, target in shared_files.items()
        }
        lines.append(json.dumps({"shared": header}, ensure_ascii=False))
    for case in cases:
        record = {
            "id": case.id,
            "inputs": case.inputs,
            "expected": case.expected,
            "grading": case.grading,
            "notes": case.notes,
        }
        lines.append(json.dumps(record, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --- helpers ------------------------------------------------------------------


def _check_site(site: CallSite) -> None:
    if not site.prompt_resolved:
        raise EvalGenSkip("prompt is not resolved; run the Bob auditor first")
    expressions = expression_placeholders(site)
    if expressions:
        names = ", ".join("{" + e + "}" for e in expressions)
        raise EvalGenSkip(f"prompt has expression placeholders {names}; run the Bob auditor first")


def _expected_rule(site: CallSite, grading: str) -> str:
    if grading == "exact":
        labels = allowed_values(site)
        if labels:
            return f"expected: exactly one of {', '.join(labels)} (a string)."
        return "expected: the exact short answer as a string."
    if grading == "json_fields":
        fields = graded_fields(site)
        if fields:
            return f"expected: an object with exactly these keys: {', '.join(fields)}."
        return "expected: the JSON object the feature should return."
    return (
        "expected: a rubric string listing what a correct reply must and must not do, "
        "point by point."
    )


def _to_case(
    raw: Any, site: CallSite, grading: str, shared: dict[str, str], number: int
) -> tuple[EvalCase | None, str]:
    if not isinstance(raw, dict):
        return None, f"not an object: {str(raw)[:60]}"
    notes = raw.get("notes")
    notes = notes if isinstance(notes, str) and notes.strip() else "generated"
    inputs = raw.get("inputs")
    if not isinstance(inputs, dict):
        return None, f"inputs is not an object: {notes}"
    case = EvalCase(
        id=f"{site.function}-{number:02d}",
        inputs=inputs,
        expected=raw.get("expected"),
        grading=grading,
        notes=notes,
    )
    check = validate_eval_set(EvalSet(path=Path("-"), cases=[case], shared=shared), site)
    if check.errors:
        reason = check.errors[0].split(": ", 1)[-1]
        return None, f"{reason}: {notes}"
    return case, ""
