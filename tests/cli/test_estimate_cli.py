"""CLI tests for `downshift estimate` (static cost projection from a scan or audit file)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from downshift.cli import app

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "supportdesk"
CONFIG = EXAMPLE / "downshift.yaml"
SCAN = EXAMPLE / "downshift.scan.json"
AUDIT = EXAMPLE / "downshift.audit.json"

cli = CliRunner()


def run(*args: str):  # type: ignore[no-untyped-def]
    return cli.invoke(app, ["estimate", *args])


def audit_without_max_tokens(tmp_path: Path) -> Path:
    data = json.loads(AUDIT.read_text())
    for site in data["call_sites"]:
        site["max_tokens"] = None
    path = tmp_path / "downshift.audit.json"
    path.write_text(json.dumps(data))
    return path


def test_single_file_prices_every_site_as_added() -> None:
    result = run(str(AUDIT), "-c", str(CONFIG))
    assert result.exit_code == 0, result.output
    assert "## Downshift cost diff" in result.output
    assert "`bob` vs `no call sites`" in result.output
    assert "| added |" in result.output


def test_base_file_compares_ast_scan_with_bob_audit() -> None:
    result = run(str(AUDIT), "--base", str(SCAN), "-c", str(CONFIG))
    assert result.exit_code == 0, result.output
    assert "`bob` vs `ast`" in result.output
    assert "| added |" in result.output
    assert "| removed |" in result.output


def test_same_generator_uses_before_after_labels() -> None:
    result = run(str(AUDIT), "--base", str(AUDIT), "-c", str(CONFIG))
    assert result.exit_code == 0, result.output
    assert "No LLM call site cost changes in `after` vs `before`" in result.output


def test_default_completion_tokens_when_max_tokens_unset(tmp_path: Path) -> None:
    result = run(str(audit_without_max_tokens(tmp_path)), "-c", str(CONFIG))
    assert result.exit_code == 0, result.output
    assert "assumed 256" in result.output


def test_completion_tokens_option(tmp_path: Path) -> None:
    path = audit_without_max_tokens(tmp_path)
    result = run(str(path), "-c", str(CONFIG), "--completion-tokens", "1000")
    assert result.exit_code == 0, result.output
    assert "assumed 1000" in result.output
    assert "output = max_tokens, or 1000 if unset" in result.output


def test_out_writes_markdown(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "estimate.md"
    result = run(str(AUDIT), "-c", str(CONFIG), "--out", str(out))
    assert result.exit_code == 0, result.output
    assert "Wrote" in result.output
    assert out.read_text().startswith("## Downshift cost diff")


def test_missing_file_fails(tmp_path: Path) -> None:
    result = run(str(tmp_path / "nope.json"), "-c", str(CONFIG))
    assert result.exit_code != 0


def test_completion_tokens_must_be_positive() -> None:
    result = run(str(AUDIT), "-c", str(CONFIG), "--completion-tokens", "0")
    assert result.exit_code != 0
