"""Eval sets: one JSONL file of test cases per call site.

File layout (``<slug>.jsonl``, slug from `slug_for`)::

    {"shared": {"policy": {"file": "../data/refund_policy.md"}}}   <- optional first line
    {"id": "c01", "inputs": {...}, "expected": ..., "grading": "exact", "notes": "..."}
    ...

`shared` inputs are merged under every case's own inputs, so long fixed
values (a policy document) are written once. A shared value is a JSON value
or ``{"file": "relative/path"}``, resolved against the eval file's folder.

`validate_eval_set` checks a file against its call site: the input keys must
match the prompt placeholders, and `expected` must fit the grading type.
The CLI command `check-evals` is a thin wrapper around `check_eval_dir`.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from downshift.schema import GRADINGS, CallSite

EVAL_SUFFIX = ".jsonl"
CASE_FIELDS = frozenset({"id", "inputs", "expected", "grading", "notes"})
MIN_CASES = 20

_BRACED = re.compile(r"\{([^{}\n]+)\}")
_GRADED_FIELDS = re.compile(r"Graded fields?:\s*([^\n]+)", re.IGNORECASE)
_VALUE_SET = re.compile(r"from the set \{([^{}]+)\}", re.IGNORECASE)


class EvalError(ValueError):
    """Raised when an eval file cannot be parsed at all."""


# --- call site helpers --------------------------------------------------------


def slug_for(site_id: str) -> str:
    """`supportdesk/triage.py::classify_category` -> `supportdesk.triage__classify_category`."""
    path, _, function = site_id.partition("::")
    module = path[:-3] if path.endswith(".py") else path
    module = module.replace("\\", "/").strip("/").replace("/", ".")
    return f"{module}__{function}" if function else module


def placeholders(template: str) -> list[str]:
    """Placeholders in a prompt as the scanner renders it, in order, without duplicates.

    `{name}` and `{ticket['body']}` both count. Braces around text that is not
    a Python expression (literal JSON such as `{"a": 1}`) are ignored.
    """
    found: list[str] = []
    for match in _BRACED.finditer(template):
        inner = match.group(1).strip()
        if not inner or not _is_expression(inner):
            continue
        if inner not in found:
            found.append(inner)
    return found


def site_placeholders(site: CallSite) -> list[str]:
    found: list[str] = []
    for message in site.messages or []:
        for name in placeholders(message.content):
            if name not in found:
                found.append(name)
    return found


def expression_placeholders(site: CallSite) -> list[str]:
    """Placeholders that are not plain names; eval inputs cannot fill them."""
    return [name for name in site_placeholders(site) if not name.isidentifier()]


def graded_fields(site: CallSite) -> list[str] | None:
    """Field names after 'Graded fields:' in the output contract, or None if absent."""
    if not site.output_contract:
        return None
    match = _GRADED_FIELDS.search(site.output_contract)
    if not match:
        return None
    names: list[str] = []
    for part in match.group(1).split(","):
        token = part.strip().rstrip(".;").strip("`'\"")
        if not token.isidentifier():
            break
        names.append(token)
    return names or None


def allowed_values(site: CallSite) -> list[str] | None:
    """Labels from 'from the set {a, b, c}' in the output contract, or None if absent."""
    if not site.output_contract:
        return None
    match = _VALUE_SET.search(site.output_contract)
    if not match:
        return None
    values = [v.strip().strip("`'\"") for v in match.group(1).split(",")]
    return [v for v in values if v] or None


def render_messages(site: CallSite, inputs: dict[str, Any]) -> list[dict[str, str]]:
    """Fill a call site's prompt with one case's inputs (for Phase 5 runs)."""
    rendered = []
    for message in site.messages or []:
        content = message.content
        for name in placeholders(content):
            if name in inputs:
                content = content.replace("{" + name + "}", _as_text(inputs[name]))
        rendered.append({"role": message.role, "content": content})
    return rendered


# --- loading ------------------------------------------------------------------


@dataclass
class EvalCase:
    id: str
    inputs: dict[str, Any]
    expected: Any
    grading: str
    notes: str | None = None
    line: int = 0


@dataclass
class EvalSet:
    path: Path
    cases: list[EvalCase]
    shared: dict[str, Any] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return self.path.name[: -len(EVAL_SUFFIX)]

    def inputs_for(self, case: EvalCase) -> dict[str, Any]:
        return {**self.shared, **case.inputs}


def load_eval_set(path: Path) -> EvalSet:
    """Parse a JSONL eval file. Bad lines become `problems`; unreadable files raise."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise EvalError(f"eval file not found: {path}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise EvalError(f"{path}: could not read ({exc})") from exc

    eval_set = EvalSet(path=path, cases=[])
    first_record = True
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        where = f"line {number}"
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            eval_set.problems.append(f"{where}: invalid JSON ({exc.msg})")
            first_record = False
            continue
        if not isinstance(record, dict):
            eval_set.problems.append(f"{where}: expected a JSON object")
            first_record = False
            continue

        if "shared" in record:
            if not first_record:
                eval_set.problems.append(f"{where}: 'shared' is only allowed on the first line")
            else:
                eval_set.shared = _load_shared(record, path, where, eval_set.problems)
            first_record = False
            continue
        first_record = False

        case = _case_from_record(record, number, eval_set.problems)
        if case is not None:
            eval_set.cases.append(case)
    return eval_set


def _load_shared(record: dict[str, Any], path: Path, where: str, problems: list[str]) -> dict:
    extra = sorted(set(record) - {"shared"})
    if extra:
        problems.append(f"{where}: unknown field(s) next to 'shared': {', '.join(extra)}")
    shared = record["shared"]
    if not isinstance(shared, dict):
        problems.append(f"{where}: 'shared' must be an object")
        return {}
    values: dict[str, Any] = {}
    for key, value in shared.items():
        if isinstance(value, dict) and set(value) == {"file"}:
            target = path.parent / str(value["file"])
            try:
                values[key] = target.read_text(encoding="utf-8")
            except OSError:
                problems.append(f"{where}: shared input {key!r}: file not found: {value['file']}")
        else:
            values[key] = value
    return values


def _case_from_record(record: dict[str, Any], number: int, problems: list[str]) -> EvalCase | None:
    where = f"line {number}"
    unknown = sorted(set(record) - CASE_FIELDS)
    if unknown:
        problems.append(f"{where}: unknown field(s) {', '.join(unknown)}")
    missing = [name for name in ("id", "inputs", "expected", "grading") if name not in record]
    if missing:
        problems.append(f"{where}: missing {', '.join(missing)}")
        return None

    case_id, inputs, grading = record["id"], record["inputs"], record["grading"]
    notes = record.get("notes")
    ok = True
    if not isinstance(case_id, str) or not case_id.strip():
        problems.append(f"{where}: id must be a non-empty string")
        ok = False
    if not isinstance(inputs, dict):
        problems.append(f"{where}: inputs must be an object")
        ok = False
    if grading not in GRADINGS:
        problems.append(f"{where}: grading must be one of {', '.join(sorted(GRADINGS))}")
        ok = False
    if notes is not None and not isinstance(notes, str):
        problems.append(f"{where}: notes must be a string")
        ok = False
    if not ok:
        return None
    return EvalCase(
        id=case_id,
        inputs=inputs,
        expected=record["expected"],
        grading=grading,
        notes=notes,
        line=number,
    )


# --- validation ---------------------------------------------------------------


@dataclass
class EvalReport:
    path: Path
    site_id: str | None = None
    cases: int = 0
    grading: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_eval_set(eval_set: EvalSet, site: CallSite) -> EvalReport:
    report = EvalReport(
        path=eval_set.path, site_id=site.id, cases=len(eval_set.cases), grading=site.grading
    )
    report.errors.extend(eval_set.problems)

    names = site_placeholders(site)
    expressions = [name for name in names if not name.isidentifier()]
    if site.messages is None or not site.prompt_resolved:
        report.errors.append("call site prompt is not resolved; re-run the Bob auditor")
    if expressions:
        report.errors.append(
            "prompt has expression placeholders "
            + ", ".join("{" + e + "}" for e in expressions)
            + "; rename them to plain names in the audit"
        )
    wanted = set(names) - set(expressions)

    fields = graded_fields(site)
    labels = allowed_values(site)
    if site.grading == "json_fields" and fields is None:
        report.warnings.append("output_contract has no 'Graded fields:' list")

    seen: set[str] = set()
    for case in eval_set.cases:
        where = f"line {case.line} ({case.id})"
        if case.id in seen:
            report.errors.append(f"{where}: duplicate id")
        seen.add(case.id)

        if site.grading is not None and case.grading != site.grading:
            report.errors.append(
                f"{where}: grading {case.grading} does not match call site grading {site.grading}"
            )

        given = set(eval_set.inputs_for(case))
        if not expressions:
            missing = sorted(wanted - given)
            extra = sorted(given - wanted)
            if missing:
                report.errors.append(f"{where}: inputs missing {', '.join(missing)}")
            if extra:
                report.errors.append(f"{where}: inputs not in the prompt: {', '.join(extra)}")

        report.errors.extend(f"{where}: {p}" for p in _check_expected(case, fields, labels))

    if len(eval_set.cases) < MIN_CASES:
        report.warnings.append(f"only {len(eval_set.cases)} cases (aim for {MIN_CASES} or more)")
    return report


def _check_expected(case: EvalCase, fields: list[str] | None, labels: list[str] | None) -> list:
    expected = case.expected
    if case.grading == "exact":
        if not isinstance(expected, str) or not expected.strip():
            return ["exact grading needs expected to be a non-empty string"]
        if labels is not None and expected not in labels:
            return [f"expected {expected!r} is not one of {', '.join(labels)}"]
        return []
    if case.grading == "json_fields":
        if not isinstance(expected, dict) or not expected:
            return ["json_fields grading needs expected to be a non-empty object"]
        if fields is None:
            return []
        problems = []
        missing = [name for name in fields if name not in expected]
        extra = sorted(set(expected) - set(fields))
        if missing:
            problems.append(f"expected missing graded field(s) {', '.join(missing)}")
        if extra:
            problems.append(f"expected has fields that are not graded: {', '.join(extra)}")
        return problems
    if not isinstance(expected, str) or not expected.strip():
        return ["judge grading needs expected to be a reference answer or rubric string"]
    return []


def check_eval_dir(directory: Path, sites: list[CallSite]) -> list[EvalReport]:
    """Validate every `*.jsonl` in a folder against the call sites it is named after.

    Returns one report per eval file, plus one per call site that has no file.
    """
    by_slug = {slug_for(site.id): site for site in sites}
    reports: list[EvalReport] = []
    covered: set[str] = set()

    for path in sorted(directory.glob(f"*{EVAL_SUFFIX}")):
        slug = path.name[: -len(EVAL_SUFFIX)]
        site = by_slug.get(slug)
        if site is None:
            reports.append(
                EvalReport(path=path, errors=[f"no call site with slug {slug!r} in the audit"])
            )
            continue
        covered.add(slug)
        try:
            eval_set = load_eval_set(path)
        except EvalError as exc:
            reports.append(EvalReport(path=path, site_id=site.id, errors=[str(exc)]))
            continue
        reports.append(validate_eval_set(eval_set, site))

    for slug, site in by_slug.items():
        if slug not in covered:
            reports.append(
                EvalReport(
                    path=directory / f"{slug}{EVAL_SUFFIX}",
                    site_id=site.id,
                    grading=site.grading,
                    warnings=["no eval file"],
                )
            )
    return reports


# --- helpers ------------------------------------------------------------------


def _is_expression(text: str) -> bool:
    if text[0] in "\"'":
        return False
    try:
        node = ast.parse(text, mode="eval").body
    except SyntaxError:
        return False
    return not isinstance(node, ast.Constant)


def _as_text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
