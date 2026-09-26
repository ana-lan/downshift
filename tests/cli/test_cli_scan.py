import json
import textwrap
from pathlib import Path

from typer.testing import CliRunner

from downshift.cli import app
from downshift.schema import ScanResult

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[2]
SUPPORTDESK = ROOT / "tests" / "fixtures" / "supportdesk_v0"

LLM_CALL = """
def classify(text):
    return client.chat.completions.create(model="m", messages=[])
"""


def write_tree(root: Path, files: dict[str, str]) -> Path:
    for rel, src in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(src), encoding="utf-8")
    return root


def test_scan_supportdesk_writes_callsites(tmp_path: Path) -> None:
    out = tmp_path / "callsites.json"
    result = runner.invoke(app, ["scan", str(SUPPORTDESK), "--out", str(out)])

    assert result.exit_code == 0, result.output
    assert "7 call sites in 9 files" in result.output
    assert "models resolved 6/7" in result.output
    assert "prompts resolved 5/7" in result.output
    assert f"Wrote {out}" in result.output
    assert len(ScanResult.load(out).call_sites) == 7


def test_default_output_location(tmp_path: Path) -> None:
    write_tree(tmp_path, {"app.py": LLM_CALL})
    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 0, result.output
    written = tmp_path / ".downshift" / "callsites.json"
    assert written.is_file()
    assert [s.id for s in ScanResult.load(written).call_sites] == ["app.py::classify"]


def test_json_flag_prints_json_and_writes_nothing_by_default(tmp_path: Path) -> None:
    write_tree(tmp_path, {"app.py": LLM_CALL})
    result = runner.invoke(app, ["scan", str(tmp_path), "--json"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["summary"]["call_sites"] == 1
    assert not (tmp_path / ".downshift").exists()


def test_json_flag_with_out_also_writes(tmp_path: Path) -> None:
    write_tree(tmp_path, {"app.py": LLM_CALL})
    out = tmp_path / "out.json"
    result = runner.invoke(app, ["scan", str(tmp_path), "--json", "--out", str(out)])

    assert result.exit_code == 0, result.output
    assert out.is_file()


def test_scan_single_file(tmp_path: Path) -> None:
    write_tree(tmp_path, {"app.py": LLM_CALL})
    result = runner.invoke(app, ["scan", str(tmp_path / "app.py")])

    assert result.exit_code == 0, result.output
    assert "1 call sites in 1 files" in result.output
    assert (tmp_path / ".downshift" / "callsites.json").is_file()


def test_discovered_config_applies_scan_excludes(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "app.py": LLM_CALL,
            "legacy/old.py": LLM_CALL,
            "downshift.yaml": 'scan:\n  exclude: ["legacy/*"]\n',
        },
    )
    result = runner.invoke(app, ["scan", str(tmp_path), "--json"])

    assert result.exit_code == 0, result.output
    ids = [site["id"] for site in json.loads(result.stdout)["call_sites"]]
    assert ids == ["app.py::classify"]


def test_explicit_invalid_config_exits_2(tmp_path: Path) -> None:
    write_tree(tmp_path, {"app.py": LLM_CALL, "bad.yaml": "quality_threshold: 7\n"})
    result = runner.invoke(app, ["scan", str(tmp_path), "--config", str(tmp_path / "bad.yaml")])

    assert result.exit_code == 2
    assert "Error:" in result.output
    assert "quality_threshold" in result.output


def test_missing_path_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(app, ["scan", str(tmp_path / "nope")])

    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_warnings_are_shown_but_scan_succeeds(tmp_path: Path) -> None:
    write_tree(tmp_path, {"app.py": LLM_CALL, "broken.py": "def oops(:\n"})
    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "warning: broken.py" in result.output
