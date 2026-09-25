"""CLI tests for `downshift check-evals`."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from downshift.cli import app
from downshift.schema import CallSite, ModelRef, PromptMessage, ScanResult

runner = CliRunner()


def _audit(tmp_path: Path) -> Path:
    site = CallSite(
        id="app/triage.py::classify",
        file="app/triage.py",
        line=1,
        function="classify",
        api="openai.chat.completions",
        model=ModelRef(value="m", source="literal", expression="'m'"),
        messages=[PromptMessage("user", "{ticket_text}")],
        purpose="p",
        output_contract="One word from the set {billing, other}.",
        difficulty="easy",
        grading="exact",
    )
    path = tmp_path / "audit.json"
    ScanResult(root=".", files_scanned=1, call_sites=[site]).write(path)
    return path


def _evals(tmp_path: Path, n: int, expected: str = "billing") -> Path:
    folder = tmp_path / "evals"
    folder.mkdir()
    lines = [
        json.dumps(
            {
                "id": f"c{i:02d}",
                "inputs": {"ticket_text": "I was charged twice"},
                "expected": expected,
                "grading": "exact",
            }
        )
        for i in range(n)
    ]
    (folder / "app.triage__classify.jsonl").write_text("\n".join(lines) + "\n")
    return folder


def test_check_evals_passes(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["check-evals", str(_evals(tmp_path, 20)), "--callsites", str(_audit(tmp_path))]
    )
    assert result.exit_code == 0, result.output
    assert "1 eval files, 20 cases, 0 errors, 0 warnings" in result.output


def test_check_evals_warnings_pass_unless_strict(tmp_path: Path) -> None:
    folder, audit = _evals(tmp_path, 2), _audit(tmp_path)
    loose = runner.invoke(app, ["check-evals", str(folder), "--callsites", str(audit)])
    assert loose.exit_code == 0
    assert "only 2 cases" in loose.output
    strict = runner.invoke(app, ["check-evals", str(folder), "--callsites", str(audit), "--strict"])
    assert strict.exit_code == 1


def test_check_evals_errors_fail(tmp_path: Path) -> None:
    folder = _evals(tmp_path, 20, expected="refund")
    result = runner.invoke(app, ["check-evals", str(folder), "--callsites", str(_audit(tmp_path))])
    assert result.exit_code == 1
    assert "'refund' is not one of billing, other" in result.output
    assert "20 errors" in result.output


def test_check_evals_missing_folder(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["check-evals", str(tmp_path / "nope"), "--callsites", str(_audit(tmp_path))]
    )
    assert result.exit_code == 2
    assert "folder not found" in result.output


def test_check_evals_bad_callsites(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    result = runner.invoke(app, ["check-evals", str(tmp_path), "--callsites", str(bad)])
    assert result.exit_code == 2
    assert "schema_version" in result.output
