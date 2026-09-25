"""Tests for audit.py: validating audit files and comparing them with the scan."""

from __future__ import annotations

import json
from pathlib import Path

from downshift.audit import compare_scans, is_enriched, lint, validate_file
from downshift.schema import CallSite, ModelRef, PromptMessage, ScanResult

BOB_NOTE = ["Bob: resolved from the caller."]


def _site(
    site_id: str,
    *,
    model: str | None = "m-large",
    source: str = "literal",
    prompt: bool = True,
    via: str | None = None,
    callers: list[str] | None = None,
    enriched: bool = False,
    found_by: str = "ast",
    output_format: str = "text",
    grading: str | None = None,
    notes: list[str] | None = None,
) -> CallSite:
    file, function = site_id.split("::")
    return CallSite(
        id=site_id,
        file=file,
        line=1,
        function=function,
        api="openai.chat.completions",
        model=ModelRef(value=model, source=source, expression="MODEL"),
        messages=[PromptMessage(role="user", content="{text}", resolved=prompt)],
        output_format=output_format,
        via=via,
        callers=callers or [],
        notes=notes or [],
        purpose="Does a thing." if enriched else None,
        output_contract="One word." if enriched else None,
        difficulty="easy" if enriched else None,
        grading=grading if grading is not None else ("judge" if enriched else None),
        found_by=found_by,
    )


def _result(sites: list[CallSite], generated_by: str = "ast") -> ScanResult:
    return ScanResult(root=".", files_scanned=3, call_sites=sites, generated_by=generated_by)


def _ast_scan() -> ScanResult:
    return _result(
        [
            _site("a.py::classify"),
            _site("h.py::ask", prompt=False, callers=["s.py::sentiment", "u.py::urgency"]),
            _site("k.py::lang_of", model=None, source="kwargs", prompt=False),
        ]
    )


def _bob_audit() -> ScanResult:
    return _result(
        [
            _site("a.py::classify", enriched=True),
            _site(
                "k.py::lang_of",
                model="m-small",
                source="manual",
                enriched=True,
                found_by="bob",
                notes=BOB_NOTE,
            ),
            _site(
                "s.py::sentiment", via="h.py::ask", enriched=True, found_by="bob", notes=BOB_NOTE
            ),
            _site("u.py::urgency", via="h.py::ask", enriched=True, found_by="bob", notes=BOB_NOTE),
        ],
        generated_by="bob",
    )


def _write(tmp_path: Path, result: ScanResult, name: str = "callsites.json") -> Path:
    path = tmp_path / name
    result.write(path)
    return path


# --- validate_file ------------------------------------------------------------


def test_validate_clean_scan_has_no_warnings(tmp_path: Path) -> None:
    report = validate_file(_write(tmp_path, _result([_site("a.py::f")])))
    assert report.ok
    assert report.result is not None
    assert report.warnings == []


def test_validate_clean_bob_audit_has_no_warnings(tmp_path: Path) -> None:
    report = validate_file(_write(tmp_path, _bob_audit(), "downshift.audit.json"))
    assert report.ok
    assert report.warnings == []


def test_validate_reports_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    report = validate_file(path)
    assert not report.ok
    assert "invalid JSON" in (report.error or "")


def test_validate_reports_schema_error_with_path(tmp_path: Path) -> None:
    data = _bob_audit().to_dict()
    data["call_sites"][1]["difficulty"] = "trivial"
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    report = validate_file(path)
    assert not report.ok
    assert "call_sites[1].difficulty" in (report.error or "")


def test_validate_rejects_unknown_fields(tmp_path: Path) -> None:
    data = _bob_audit().to_dict()
    data["call_sites"][0]["confidence"] = 0.9
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    report = validate_file(path)
    assert not report.ok
    assert "unknown field" in (report.error or "")


def test_validate_missing_file(tmp_path: Path) -> None:
    report = validate_file(tmp_path / "nope.json")
    assert not report.ok
    assert "not found" in (report.error or "")


# --- lint ---------------------------------------------------------------------


def test_lint_ignores_gaps_in_ast_scan() -> None:
    assert lint(_ast_scan()) == []


def test_lint_flags_missing_enrichment_in_bob_file() -> None:
    result = _result([_site("a.py::f", found_by="bob", notes=BOB_NOTE)], generated_by="bob")
    assert lint(result) == ["a.py::f: missing purpose, output_contract, difficulty, grading"]


def test_lint_flags_unresolved_model_and_prompt_in_bob_file() -> None:
    site = _site(
        "a.py::f",
        model=None,
        source="kwargs",
        prompt=False,
        enriched=True,
        found_by="bob",
        notes=BOB_NOTE,
    )
    assert lint(_result([site], generated_by="bob")) == [
        "a.py::f: model still unresolved",
        "a.py::f: prompt still unresolved",
    ]


def test_lint_flags_json_fields_on_text_output() -> None:
    result = _result([_site("a.py::f", grading="json_fields")])
    assert lint(result) == ["a.py::f: grading is json_fields but output_format is text"]


def test_lint_accepts_json_fields_on_json_output() -> None:
    result = _result([_site("a.py::f", grading="json_fields", output_format="json")])
    assert lint(result) == []


def test_lint_flags_helper_still_listed() -> None:
    result = _result([_site("h.py::ask"), _site("s.py::sentiment", via="h.py::ask")])
    assert lint(result) == ["s.py::sentiment: via h.py::ask is still listed as its own call site"]


def test_lint_flags_bob_site_without_note() -> None:
    result = _result([_site("a.py::f", enriched=True, found_by="bob")], generated_by="bob")
    assert lint(result) == ["a.py::f: found_by is bob but there is no 'Bob:' note"]


def test_lint_flags_bob_file_without_bob_sites() -> None:
    result = _result([_site("a.py::f", enriched=True)], generated_by="bob")
    assert lint(result) == ["generated_by is bob but no call site has found_by bob"]


def test_is_enriched() -> None:
    assert is_enriched(_site("a.py::f", enriched=True))
    assert not is_enriched(_site("a.py::f"))


# --- compare_scans ------------------------------------------------------------


def test_compare_metrics() -> None:
    comparison = compare_scans(_ast_scan(), _bob_audit())
    rows = {m.name: (m.ast, m.audit) for m in comparison.metrics}
    assert rows == {
        "Call sites": (3, 4),
        "Models resolved": (2, 4),
        "Prompts resolved": (1, 4),
        "Enriched": (0, 4),
        "Found by Bob": (0, 3),
        "Split from helpers": (0, 2),
    }


def test_compare_changes() -> None:
    comparison = compare_scans(_ast_scan(), _bob_audit())
    changes = {c.id: (c.kind, c.detail) for c in comparison.changes}
    assert changes == {
        "a.py::classify": ("enriched", "purpose, output_contract, difficulty, grading"),
        "h.py::ask": ("split", "into s.py::sentiment, u.py::urgency"),
        "k.py::lang_of": ("resolved", "model resolved: m-small; prompt resolved"),
        "s.py::sentiment": ("added", "via h.py::ask"),
        "u.py::urgency": ("added", "via h.py::ask"),
    }


def test_compare_changes_are_sorted_by_id() -> None:
    ids = [c.id for c in compare_scans(_ast_scan(), _bob_audit()).changes]
    assert ids == sorted(ids)


def test_compare_removed_added_and_changed() -> None:
    before = _result([_site("a.py::f"), _site("b.py::g")])
    after = _result([_site("a.py::f", model="m-small"), _site("c.py::h")])
    changes = {c.id: (c.kind, c.detail) for c in compare_scans(before, after).changes}
    assert changes == {
        "a.py::f": ("changed", "model m-large -> m-small"),
        "b.py::g": ("removed", "not in the audit"),
        "c.py::h": ("added", "not found by the scanner"),
    }


def test_compare_unchanged() -> None:
    same = _result([_site("a.py::f")])
    changes = compare_scans(same, same).changes
    assert [(c.kind, c.detail) for c in changes] == [("unchanged", "")]


def test_comparison_to_dict_is_json_ready() -> None:
    data = compare_scans(_ast_scan(), _bob_audit()).to_dict()
    assert data["metrics"][0] == {"name": "Call sites", "ast": 3, "audit": 4}
    assert data["changes"][0]["id"] == "a.py::classify"
    json.dumps(data)
