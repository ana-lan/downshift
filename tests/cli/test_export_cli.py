import json
from pathlib import Path

from typer.testing import CliRunner

from downshift.cli import app
from downshift.export import AUDIT_FILE, EVALS_FILE, EXPORT_FILES, SUMMARY_FILE

ROOT = Path(__file__).resolve().parents[2]
SD = ROOT / "examples" / "supportdesk"
runner = CliRunner()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_export_supportdesk(tmp_path: Path) -> None:
    out = tmp_path / "data"
    result = runner.invoke(app, ["export", str(SD), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert "Wrote 5 files" in result.output
    assert "downgraded 3 of 8" in result.output
    for name in EXPORT_FILES:
        assert (out / name).exists()
    summary = _load(out / SUMMARY_FILE)
    assert summary["project"] == "supportdesk"
    audit = _load(out / AUDIT_FILE)
    assert audit["ast"]["call_sites"] == 7
    assert audit["ast_after"]["models_resolved"] == 0


def test_export_explicit_options(tmp_path: Path) -> None:
    out = tmp_path / "data"
    result = runner.invoke(
        app,
        [
            "export",
            str(SD),
            "--out",
            str(out),
            "--callsites",
            str(SD / "downshift.audit.json"),
            "--ast",
            str(SD / "downshift.scan.json"),
            "--ast-after",
            str(SD / "downshift.scan.after.json"),
            "-c",
            str(SD / "downshift.yaml"),
            "--examples",
            "1",
            "--name",
            "demo",
        ],
    )
    assert result.exit_code == 0, result.output
    assert _load(out / SUMMARY_FILE)["project"] == "demo"
    evals = json.loads((out / EVALS_FILE).read_text(encoding="utf-8"))
    assert all(len(e["examples"]) == 1 for e in evals)


def test_export_without_ast_scans(tmp_path: Path) -> None:
    out = tmp_path / "data"
    result = runner.invoke(
        app,
        ["export", str(tmp_path), "--callsites", str(SD / "downshift.audit.json"), "-o", str(out)],
    )
    assert result.exit_code == 0, result.output
    audit = _load(out / AUDIT_FILE)
    assert audit["ast"] is None
    assert audit["ast_after"] is None


def test_export_missing_audit(tmp_path: Path) -> None:
    result = runner.invoke(app, ["export", str(tmp_path), "--out", str(tmp_path / "o")])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_export_missing_explicit_ast(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["export", str(SD), "--ast", str(tmp_path / "nope.json"), "-o", str(tmp_path / "o")],
    )
    assert result.exit_code != 0
    assert "nope.json" in result.output


def test_export_negative_examples(tmp_path: Path) -> None:
    result = runner.invoke(app, ["export", str(SD), "--examples", "-1", "-o", str(tmp_path)])
    assert result.exit_code != 0
