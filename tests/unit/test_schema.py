import json
import re
from pathlib import Path
from typing import Any

import pytest

from downshift.schema import (
    SCHEMA_VERSION,
    CallSite,
    ModelRef,
    PromptMessage,
    ScanResult,
    SchemaError,
)

DELETE = object()


def make_site(site_id: str = "app/triage.py::classify", **overrides: Any) -> CallSite:
    site = CallSite(
        id=site_id,
        file="app/triage.py",
        line=10,
        end_line=18,
        function="classify",
        api="openai.chat.completions",
        model=ModelRef(value="qwen2.5:7b", source="literal", expression="'qwen2.5:7b'"),
        messages=[
            PromptMessage(role="system", content="You classify tickets."),
            PromptMessage(role="user", content="Ticket:\n{ticket_text}"),
        ],
        temperature=0.0,
        max_tokens=5,
    )
    for key, value in overrides.items():
        setattr(site, key, value)
    return site


def site_dict(**changes: Any) -> dict[str, Any]:
    data = make_site().to_dict()
    for key, value in changes.items():
        if value is DELETE:
            data.pop(key)
        else:
            data[key] = value
    return data


def make_result(*sites: CallSite) -> ScanResult:
    return ScanResult(root="app", files_scanned=4, call_sites=list(sites), warnings=["w1"])


# --- round trips --------------------------------------------------------------


def test_call_site_round_trip() -> None:
    site = make_site()
    assert CallSite.from_dict(site.to_dict()) == site


def test_scan_result_round_trip_through_file(tmp_path: Path) -> None:
    result = make_result(make_site(), make_site("app/other.py::summarize"))
    path = tmp_path / "nested" / "callsites.json"
    result.write(path)
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert ScanResult.load(path) == result


def test_to_dict_has_header_and_summary() -> None:
    data = make_result(make_site()).to_dict()
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["tool"] == "downshift"
    assert data["summary"]["call_sites"] == 1
    assert data["summary"]["files_scanned"] == 4


def test_minimal_call_site_gets_defaults() -> None:
    data = {
        "id": "a.py::f",
        "file": "a.py",
        "line": 1,
        "function": "f",
        "api": "openai.chat.completions",
        "model": {"value": None, "source": "kwargs", "expression": "**params"},
    }
    site = CallSite.from_dict(data)
    assert site.messages is None
    assert site.output_format == "text"
    assert site.callers == []
    assert site.found_by == "ast"
    assert site.model.resolved is False


def test_bob_enriched_call_site_loads() -> None:
    data = site_dict(
        id="app/triage.py::detect_sentiment",
        via="app/llm.py::ask",
        purpose="Detect customer sentiment",
        output_contract="one of: positive, neutral, negative",
        difficulty="easy",
        grading="exact",
        found_by="bob",
    )
    site = CallSite.from_dict(data)
    assert site.via == "app/llm.py::ask"
    assert site.difficulty == "easy"
    assert site.found_by == "bob"


# --- derived properties -------------------------------------------------------


def test_prompt_resolved() -> None:
    assert make_site().prompt_resolved is True
    assert make_site(messages=None).prompt_resolved is False
    partly = [PromptMessage("user", "{prompt}", resolved=False)]
    assert make_site(messages=partly).prompt_resolved is False


def test_summary_counts() -> None:
    unresolved_model = make_site(
        "b.py::f", model=ModelRef(value=None, source="kwargs", expression="**params")
    )
    dynamic_prompt = make_site("c.py::g", messages=None)
    summary = make_result(make_site(), unresolved_model, dynamic_prompt).summary()
    assert summary == {
        "files_scanned": 4,
        "call_sites": 3,
        "models_resolved": 2,
        "prompts_resolved": 2,
    }


# --- validation errors --------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (site_dict(id=DELETE), "call_site.id: missing required field"),
        (site_dict(id=""), "call_site.id"),
        (site_dict(line=0), "call_site.line"),
        (site_dict(line=True), "call_site.line"),
        (site_dict(model="qwen2.5:7b"), "call_site.model: expected an object"),
        (
            site_dict(model={"value": "m", "source": "guess", "expression": "m"}),
            "call_site.model.source",
        ),
        (site_dict(model={"value": "m", "source": "literal"}), "model.expression: missing"),
        (site_dict(output_format="xml"), "call_site.output_format"),
        (site_dict(difficulty="trivial"), "call_site.difficulty"),
        (site_dict(grading="vibes"), "call_site.grading"),
        (site_dict(found_by="gpt"), "call_site.found_by"),
        (site_dict(messages="hello"), "call_site.messages: expected a list"),
        (site_dict(messages=[{"content": "x"}]), "call_site.messages[0].role"),
        (
            site_dict(messages=[{"role": "user", "content": "x", "resolved": "yes"}]),
            "call_site.messages[0].resolved",
        ),
        (site_dict(callers="a.py::f"), "call_site.callers"),
        (site_dict(max_tokens=0), "call_site.max_tokens"),
        (site_dict(temperature="hot"), "call_site.temperature"),
        (site_dict(colour="blue"), "unknown field(s) colour"),
    ],
)
def test_invalid_call_site(data: dict[str, Any], expected: str) -> None:
    with pytest.raises(SchemaError, match=re.escape(expected)):
        CallSite.from_dict(data)


def test_call_site_must_be_object() -> None:
    with pytest.raises(SchemaError, match="expected an object"):
        CallSite.from_dict(["not", "a", "dict"])


def test_error_path_includes_index() -> None:
    data = make_result(make_site(), make_site("x.py::g")).to_dict()
    data["call_sites"][1]["line"] = -3
    with pytest.raises(SchemaError, match=r"call_sites\[1\]\.line"):
        ScanResult.from_dict(data)


def test_duplicate_ids_rejected() -> None:
    data = make_result(make_site(), make_site()).to_dict()
    with pytest.raises(SchemaError, match="duplicate id"):
        ScanResult.from_dict(data)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ([], "top level"),
        ({"schema_version": 2, "call_sites": []}, "schema_version"),
        ({"call_sites": []}, "schema_version"),
        ({"schema_version": SCHEMA_VERSION, "call_sites": {}}, "call_sites: expected a list"),
        ({"schema_version": SCHEMA_VERSION, "call_sites": [], "generated_by": "x"}, "generated_by"),
    ],
)
def test_invalid_scan_result(data: Any, expected: str) -> None:
    with pytest.raises(SchemaError, match=re.escape(expected)):
        ScanResult.from_dict(data)


def test_load_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "callsites.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SchemaError, match="invalid JSON"):
        ScanResult.load(path)


def test_load_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SchemaError, match="not found"):
        ScanResult.load(tmp_path / "missing.json")


def test_json_output_is_stable() -> None:
    result = make_result(make_site())
    assert result.to_json() == result.to_json()
    assert json.loads(result.to_json())["call_sites"][0]["id"] == "app/triage.py::classify"
