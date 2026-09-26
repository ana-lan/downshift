"""End-to-end smoke test: the whole pipeline through the CLI. No network, no models."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from downshift.cli import app
from downshift.export import EXPORT_FILES
from downshift.llm import FakeLLMClient
from downshift.schema import ScanResult

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "supportdesk"
FIXTURE = ROOT / "tests" / "fixtures" / "supportdesk_v0"

cli = CliRunner()


def ok(*args: str) -> str:
    result = cli.invoke(app, list(args))
    assert result.exit_code == 0, f"downshift {' '.join(args)}\n{result.output}"
    return result.output


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Copy of examples/supportdesk without committed results, so the run starts fresh."""
    dest = tmp_path / "supportdesk"
    shutil.copytree(
        EXAMPLE,
        dest,
        ignore=shutil.ignore_patterns("results", ".downshift", "__pycache__"),
    )
    return dest


def test_full_pipeline(tmp_path: Path, project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeLLMClient("billing")
    monkeypatch.setattr("downshift.cli._make_client", lambda base_url, api_key: fake)

    audit = project / "downshift.audit.json"
    scan = project / "downshift.scan.json"
    config = project / "downshift.yaml"

    # 1. scan the app source (a copy, so nothing is written into the fixture)
    source = tmp_path / "source"
    shutil.copytree(FIXTURE, source)
    ok("scan", str(source))

    # 2. check Bob's audit and compare it with the ast scan
    ok("validate", str(audit))
    ok("compare", str(scan), str(audit))

    # 3. run evals on every call site with the fake client
    ok("run", "--callsites", str(audit), "--limit", "2")
    sites = ScanResult.load(audit).call_sites
    results = project / "results"
    assert len({p.parent.name for p in results.glob("*/*.jsonl")}) == len(sites)
    assert fake.calls

    # 4. report from the fresh results
    report = project / "report.md"
    ok("report", "--callsites", str(audit), "--out", str(report))
    assert "# Downshift report" in report.read_text(encoding="utf-8")

    # 5. static cost estimate, Bob vs ast
    out = ok("estimate", str(audit), "--base", str(scan), "-c", str(config))
    assert "## Downshift cost diff" in out

    # 6. export the web app data
    data = tmp_path / "data"
    out = ok("export", str(project), "--out", str(data))
    assert "Wrote 5 files" in out
    for name in EXPORT_FILES:
        assert (data / name).is_file()
