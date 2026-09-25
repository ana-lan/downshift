"""Tests for eval set loading and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from downshift.audit import lint
from downshift.evals import (
    EvalError,
    allowed_values,
    check_eval_dir,
    expression_placeholders,
    graded_fields,
    load_eval_set,
    placeholders,
    render_messages,
    site_placeholders,
    slug_for,
    validate_eval_set,
)
from downshift.schema import CallSite, ModelRef, PromptMessage, ScanResult


def _site(
    site_id: str = "app/triage.py::classify",
    *,
    contents: tuple[str, ...] = ("Ticket:\n{ticket_text}",),
    grading: str | None = "exact",
    contract: str | None = "One word from the set {billing, shipping, other}.",
    resolved: bool = True,
    output_format: str = "text",
) -> CallSite:
    file, function = site_id.split("::")
    return CallSite(
        id=site_id,
        file=file,
        line=1,
        function=function,
        api="openai.chat.completions",
        model=ModelRef(value="m", source="literal", expression="'m'"),
        messages=[PromptMessage("user", c, resolved) for c in contents],
        output_format=output_format,
        purpose="p",
        output_contract=contract,
        difficulty="easy",
        grading=grading,
    )


def _json_site() -> CallSite:
    return _site(
        "app/extract.py::extract",
        grading="json_fields",
        output_format="json",
        contract="JSON with order_id and order_date. Graded fields: order_id, order_date.",
    )


def _case(case_id: str = "c01", **overrides: object) -> dict:
    case = {
        "id": case_id,
        "inputs": {"ticket_text": "Where is my order?"},
        "expected": "shipping",
        "grading": "exact",
        "notes": "basic",
    }
    case.update(overrides)
    return case


def _write(path: Path, records: list, raw_lines: tuple[str, ...] = ()) -> Path:
    lines = [json.dumps(r) for r in records] + list(raw_lines)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _cases(n: int) -> list[dict]:
    return [_case(f"c{i:02d}") for i in range(n)]


# --- helpers ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("site_id", "slug"),
    [
        ("supportdesk/triage.py::classify_category", "supportdesk.triage__classify_category"),
        ("app.py::f", "app__f"),
        ("a/b/c.py::run", "a.b.c__run"),
        ("a\\b.py::run", "a.b__run"),
    ],
)
def test_slug_for(site_id: str, slug: str) -> None:
    assert slug_for(site_id) == slug


def test_placeholders_names_and_expressions_in_order() -> None:
    text = "Hi {name}, re {ticket['body']} and {name} again, {json.dumps(x)}"
    assert placeholders(text) == ["name", "ticket['body']", "json.dumps(x)"]


@pytest.mark.parametrize(
    "text",
    [
        'Return {"a": 1, "b": 2}',
        "Pick from {a, b: c}",
        "Positional {0} and {'quoted'}",
        "Empty {} and { }",
        "Multi {line\nbrace}",
    ],
)
def test_placeholders_ignores_literal_braces(text: str) -> None:
    assert placeholders(text) == []


def test_site_placeholders_across_messages_dedupes() -> None:
    site = _site(contents=("System {lang}", "{ticket_text} in {lang}"))
    assert site_placeholders(site) == ["lang", "ticket_text"]


def test_site_placeholders_no_messages() -> None:
    site = _site()
    site.messages = None
    assert site_placeholders(site) == []


def test_expression_placeholders() -> None:
    site = _site(contents=("{subject} {ticket['body']}",))
    assert expression_placeholders(site) == ["ticket['body']"]


def test_graded_fields_parses_until_prose() -> None:
    site = _site(
        contract="JSON. Graded fields: is_refund_request, eligible, policy_section, "
        "which must match the policy. reasoning is not graded."
    )
    assert graded_fields(site) == ["is_refund_request", "eligible", "policy_section"]


def test_graded_fields_with_backticks_and_period() -> None:
    assert graded_fields(_site(contract="Graded fields: `a`, `b`.")) == ["a", "b"]


@pytest.mark.parametrize("contract", [None, "No list here.", "Graded fields: not a list"])
def test_graded_fields_absent(contract: str | None) -> None:
    assert graded_fields(_site(contract=contract)) is None


def test_allowed_values() -> None:
    site = _site(contract="Exactly one word from the set {low, medium, high}; no punctuation.")
    assert allowed_values(site) == ["low", "medium", "high"]
    assert allowed_values(_site(contract="A two-letter code.")) is None
    assert allowed_values(_site(contract=None)) is None


def test_render_messages_fills_names_and_dumps_non_strings() -> None:
    site = _site(contents=("Info: {info}\n{ticket_text}", 'Literal {"k": 1}'))
    rendered = render_messages(site, {"ticket_text": "hello", "info": {"order_id": None}})
    assert rendered[0] == {"role": "user", "content": 'Info: {"order_id": null}\nhello'}
    assert rendered[1]["content"] == 'Literal {"k": 1}'


def test_render_messages_leaves_unknown_placeholders() -> None:
    assert render_messages(_site(), {})[0]["content"] == "Ticket:\n{ticket_text}"


# --- loading ------------------------------------------------------------------


def test_load_valid_file(tmp_path: Path) -> None:
    eval_set = load_eval_set(_write(tmp_path / "x.jsonl", _cases(3)))
    assert [c.id for c in eval_set.cases] == ["c00", "c01", "c02"]
    assert eval_set.cases[0].line == 1
    assert eval_set.cases[0].notes == "basic"
    assert eval_set.problems == []
    assert eval_set.slug == "x"


def test_load_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    path.write_text(json.dumps(_case()) + "\n\n   \n" + json.dumps(_case("c02")) + "\n")
    eval_set = load_eval_set(path)
    assert [c.line for c in eval_set.cases] == [1, 4]


def test_load_missing_file(tmp_path: Path) -> None:
    with pytest.raises(EvalError, match="not found"):
        load_eval_set(tmp_path / "nope.jsonl")


def test_load_bad_lines_become_problems(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "x.jsonl",
        [_case(), [1, 2], {"id": "c09"}],
        raw_lines=("{not json", '{"id": "c10"'),
    )
    eval_set = load_eval_set(path)
    assert len(eval_set.cases) == 1
    joined = "\n".join(eval_set.problems)
    assert "line 2: expected a JSON object" in joined
    assert "line 3: missing inputs, expected, grading" in joined
    assert "line 4: invalid JSON" in joined
    assert "line 5: invalid JSON" in joined


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"id": ""}, "id must be a non-empty string"),
        ({"id": 7}, "id must be a non-empty string"),
        ({"inputs": "text"}, "inputs must be an object"),
        ({"grading": "fuzzy"}, "grading must be one of exact, json_fields, judge"),
        ({"notes": 3}, "notes must be a string"),
    ],
)
def test_load_rejects_bad_fields(tmp_path: Path, overrides: dict, message: str) -> None:
    eval_set = load_eval_set(_write(tmp_path / "x.jsonl", [_case(**overrides)]))
    assert eval_set.cases == []
    assert message in eval_set.problems[0]


def test_load_unknown_fields_is_a_problem_but_keeps_case(tmp_path: Path) -> None:
    eval_set = load_eval_set(_write(tmp_path / "x.jsonl", [_case(extra=1)]))
    assert len(eval_set.cases) == 1
    assert "unknown field(s) extra" in eval_set.problems[0]


def test_load_shared_values_and_files(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "policy.md").write_text("Refunds within 30 days.")
    evals = tmp_path / "evals"
    evals.mkdir()
    shared = {"shared": {"policy": {"file": "../data/policy.md"}, "lang": "en"}}
    eval_set = load_eval_set(_write(evals / "x.jsonl", [shared, _case()]))
    assert eval_set.shared == {"policy": "Refunds within 30 days.", "lang": "en"}
    assert eval_set.inputs_for(eval_set.cases[0]) == {
        "policy": "Refunds within 30 days.",
        "lang": "en",
        "ticket_text": "Where is my order?",
    }


def test_case_inputs_override_shared(tmp_path: Path) -> None:
    records = [{"shared": {"ticket_text": "default"}}, _case()]
    eval_set = load_eval_set(_write(tmp_path / "x.jsonl", records))
    assert eval_set.inputs_for(eval_set.cases[0])["ticket_text"] == "Where is my order?"


@pytest.mark.parametrize(
    ("records", "message"),
    [
        ([_case(), {"shared": {}}], "'shared' is only allowed on the first line"),
        ([{"shared": [1]}], "'shared' must be an object"),
        ([{"shared": {}, "x": 1}], "unknown field(s) next to 'shared': x"),
        ([{"shared": {"p": {"file": "missing.md"}}}], "file not found: missing.md"),
    ],
)
def test_load_shared_problems(tmp_path: Path, records: list, message: str) -> None:
    eval_set = load_eval_set(_write(tmp_path / "x.jsonl", records))
    assert message in "\n".join(eval_set.problems)


# --- validation ---------------------------------------------------------------


def _validate(tmp_path: Path, records: list, site: CallSite | None = None):
    eval_set = load_eval_set(_write(tmp_path / "x.jsonl", records))
    return validate_eval_set(eval_set, site or _site())


def test_validate_clean(tmp_path: Path) -> None:
    report = _validate(tmp_path, _cases(20))
    assert report.ok
    assert report.warnings == []
    assert report.cases == 20
    assert report.grading == "exact"


def test_validate_warns_on_few_cases(tmp_path: Path) -> None:
    report = _validate(tmp_path, _cases(3))
    assert report.ok
    assert report.warnings == ["only 3 cases (aim for 20 or more)"]


def test_validate_duplicate_ids(tmp_path: Path) -> None:
    report = _validate(tmp_path, [_case("a"), _case("a")])
    assert report.errors == ["line 2 (a): duplicate id"]


def test_validate_grading_must_match_site(tmp_path: Path) -> None:
    report = _validate(tmp_path, [_case(grading="judge", expected="rubric")])
    assert "grading judge does not match call site grading exact" in report.errors[0]


def test_validate_site_without_grading_accepts_any(tmp_path: Path) -> None:
    report = _validate(tmp_path, [_case(grading="judge", expected="r")], _site(grading=None))
    assert report.ok


def test_validate_inputs_missing_and_extra(tmp_path: Path) -> None:
    report = _validate(tmp_path, [_case(inputs={"text": "x"})])
    assert "inputs missing ticket_text" in report.errors[0]
    assert "inputs not in the prompt: text" in report.errors[1]


def test_validate_shared_inputs_count(tmp_path: Path) -> None:
    site = _site(contents=("{policy}\n{ticket_text}",))
    report = _validate(tmp_path, [{"shared": {"policy": "p"}}, _case()], site)
    assert report.ok


def test_validate_expression_placeholders_is_one_error(tmp_path: Path) -> None:
    site = _site(contents=("{ticket['body']} {subject}",))
    report = _validate(tmp_path, [_case(), _case("c2")], site)
    assert len(report.errors) == 1
    assert "{ticket['body']}" in report.errors[0]
    assert "rename them to plain names" in report.errors[0]


def test_validate_unresolved_prompt(tmp_path: Path) -> None:
    report = _validate(tmp_path, [_case()], _site(resolved=False))
    assert "prompt is not resolved" in report.errors[0]


def test_validate_missing_messages(tmp_path: Path) -> None:
    site = _site()
    site.messages = None
    report = _validate(tmp_path, [_case(inputs={})], site)
    assert report.errors == ["call site prompt is not resolved; re-run the Bob auditor"]


def test_validate_load_problems_are_errors(tmp_path: Path) -> None:
    eval_set = load_eval_set(_write(tmp_path / "x.jsonl", [_case()], raw_lines=("oops",)))
    report = validate_eval_set(eval_set, _site())
    assert any("invalid JSON" in e for e in report.errors)


@pytest.mark.parametrize(
    ("expected", "message"),
    [
        ("", "non-empty string"),
        (["shipping"], "non-empty string"),
        ("Shipping", "'Shipping' is not one of billing, shipping, other"),
    ],
)
def test_validate_exact_expected(tmp_path: Path, expected: object, message: str) -> None:
    report = _validate(tmp_path, [_case(expected=expected)])
    assert message in report.errors[0]


def test_validate_exact_without_label_set(tmp_path: Path) -> None:
    site = _site(contract="Two-letter ISO code.")
    assert _validate(tmp_path, [_case(expected="fr")], site).ok


def _json_case(case_id: str = "j1", expected: object = None) -> dict:
    if expected is None:
        expected = {"order_id": "ORD-1", "order_date": None}
    return _case(case_id, grading="json_fields", expected=expected)


def test_validate_json_fields_ok(tmp_path: Path) -> None:
    assert _validate(tmp_path, [_json_case()], _json_site()).ok


@pytest.mark.parametrize(
    ("expected", "message"),
    [
        ("ORD-1", "needs expected to be a non-empty object"),
        ({}, "needs expected to be a non-empty object"),
        ({"order_id": "ORD-1"}, "expected missing graded field(s) order_date"),
        (
            {"order_id": None, "order_date": None, "reasoning": "x"},
            "fields that are not graded: reasoning",
        ),
    ],
)
def test_validate_json_fields_expected(tmp_path: Path, expected: object, message: str) -> None:
    report = _validate(tmp_path, [_json_case(expected=expected)], _json_site())
    assert message in "\n".join(report.errors)


def test_validate_json_fields_without_list_warns(tmp_path: Path) -> None:
    site = _json_site()
    site.output_contract = "Some JSON."
    report = _validate(tmp_path, [_json_case(expected={"anything": 1})], site)
    assert report.ok
    assert "no 'Graded fields:' list" in report.warnings[0]


def test_validate_judge(tmp_path: Path) -> None:
    site = _site(grading="judge", contract="Two sentences.")
    good = _case("a", grading="judge", expected="Mentions ORD-1 and the refund ask.")
    bad = _case("b", grading="judge", expected={"x": 1})
    report = _validate(tmp_path, [good, bad], site)
    assert len(report.errors) == 1
    assert "reference answer or rubric" in report.errors[0]


# --- folder check ---------------------------------------------------------------


def test_check_eval_dir(tmp_path: Path) -> None:
    sites = [_site(), _json_site(), _site("app/other.py::g")]
    _write(tmp_path / "app.triage__classify.jsonl", _cases(20))
    _write(tmp_path / "app.extract__extract.jsonl", [_json_case()])
    _write(tmp_path / "stray__file.jsonl", [_case()])
    (tmp_path / "notes.txt").write_text("ignored")

    reports = {r.path.name: r for r in check_eval_dir(tmp_path, sites)}
    assert set(reports) == {
        "app.triage__classify.jsonl",
        "app.extract__extract.jsonl",
        "stray__file.jsonl",
        "app.other__g.jsonl",
    }
    assert reports["app.triage__classify.jsonl"].ok
    assert reports["app.extract__extract.jsonl"].warnings == ["only 1 cases (aim for 20 or more)"]
    assert "no call site with slug 'stray__file'" in reports["stray__file.jsonl"].errors[0]
    missing = reports["app.other__g.jsonl"]
    assert missing.ok and missing.warnings == ["no eval file"] and missing.cases == 0


def test_check_eval_dir_unreadable_file(tmp_path: Path) -> None:
    (tmp_path / "app.triage__classify.jsonl").write_bytes(b"\xff\xfe\x00bad")
    reports = check_eval_dir(tmp_path, [_site()])
    assert "could not read" in reports[0].errors[0]


# --- audit lint -------------------------------------------------------------------


def test_lint_flags_expression_placeholders_in_bob_audit() -> None:
    site = _site(contents=("{ticket['body']}",))
    site.notes = ["Bob: checked."]
    site.found_by = "bob"
    result = ScanResult(root=".", files_scanned=1, call_sites=[site], generated_by="bob")
    warnings = lint(result)
    assert any("placeholder {ticket['body']} is an expression" in w for w in warnings)


def test_lint_ignores_expressions_in_ast_scan() -> None:
    site = _site(contents=("{ticket['body']}",))
    result = ScanResult(root=".", files_scanned=1, call_sites=[site])
    assert not any("is an expression" in w for w in lint(result))
