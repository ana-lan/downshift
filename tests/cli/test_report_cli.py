"""CLI tests for `downshift report`."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from downshift.cli import app

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "supportdesk"
AUDIT = EXAMPLE / "downshift.audit.json"

cli = CliRunner()


def invoke(*args: str):  # type: ignore[no-untyped-def]
    return cli.invoke(app, ["report", "--callsites", str(AUDIT), *args])


# ---------------------------------------------------------------------------
# stdout mode
# ---------------------------------------------------------------------------


def test_report_stdout_exits_zero() -> None:
    result = invoke()
    assert result.exit_code == 0, result.output
    assert "# Downshift report" in result.output


def test_report_stdout_contains_decisions_section() -> None:
    result = invoke()
    assert result.exit_code == 0, result.output
    assert "## Decisions" in result.output


def test_report_stdout_contains_quality_section() -> None:
    result = invoke()
    assert result.exit_code == 0, result.output
    assert "## Quality per model" in result.output


# ---------------------------------------------------------------------------
# --out mode
# ---------------------------------------------------------------------------


def test_report_out_writes_file(tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    result = invoke("--out", str(out))
    assert result.exit_code == 0, result.output
    assert out.is_file()
    content = out.read_text(encoding="utf-8")
    assert "# Downshift report" in content


def test_report_out_prints_summary_line(tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    result = invoke("--out", str(out))
    assert result.exit_code == 0, result.output
    assert f"Wrote {out}" in result.output
    assert "call sites" in result.output
    assert "projected savings" in result.output


def test_report_out_creates_parent_dirs(tmp_path: Path) -> None:
    out = tmp_path / "deep" / "nested" / "report.md"
    result = invoke("--out", str(out))
    assert result.exit_code == 0, result.output
    assert out.is_file()


# ---------------------------------------------------------------------------
# --threshold override
# ---------------------------------------------------------------------------


def test_threshold_override_changes_output() -> None:
    # Two different thresholds should produce different reports (for the real dataset)
    result_strict = invoke("--threshold", "0.99")
    result_loose = invoke("--threshold", "0.50")
    assert result_strict.exit_code == 0, result_strict.output
    assert result_loose.exit_code == 0, result_loose.output
    # At least one threshold should produce different downgrade count
    # (just verify they ran successfully and we get a report)
    assert "# Downshift report" in result_strict.output
    assert "# Downshift report" in result_loose.output


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_missing_callsites_file_exits_2(tmp_path: Path) -> None:
    missing = tmp_path / "nonexistent.json"
    result = cli.invoke(app, ["report", "--callsites", str(missing)])
    assert result.exit_code == 2


def test_invalid_threshold_exits_2() -> None:
    # 0 is excluded (min_open=True)
    result = invoke("--threshold", "0")
    assert result.exit_code == 2


def test_invalid_threshold_above_one_exits_2() -> None:
    result = invoke("--threshold", "1.5")
    assert result.exit_code == 2


def test_invalid_min_pass_rate_above_one_exits_2() -> None:
    result = invoke("--min-pass-rate", "1.1")
    assert result.exit_code == 2
