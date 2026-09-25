"""CLI tests for `downshift evalgen`, with the model client faked."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from downshift import cli
from downshift.cli import app
from downshift.evals import load_eval_set
from downshift.llm import FakeLLMClient
from downshift.schema import CallSite, ModelRef, PromptMessage, ScanResult

runner = CliRunner()
GOOD = json.dumps(
    {"cases": [{"inputs": {"ticket_text": f"t{i}"}, "expected": "billing"} for i in range(3)]}
)


def _site(site_id: str, content: str) -> CallSite:
    file, function = site_id.split("::")
    return CallSite(
        id=site_id,
        file=file,
        line=1,
        function=function,
        api="openai.chat.completions",
        model=ModelRef(value="m", source="literal", expression="'m'"),
        messages=[PromptMessage("user", content)],
        output_contract="One word from the set {billing, other}.",
        grading="exact",
    )


def _audit(tmp_path: Path, *sites: CallSite) -> Path:
    if not sites:
        sites = (
            _site("app/a.py::classify", "{ticket_text}"),
            _site("app/b.py::raw", "{ticket['body']}"),
        )
    path = tmp_path / "audit.json"
    ScanResult(root=".", files_scanned=1, call_sites=list(sites)).write(path)
    return path


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeLLMClient:
    client = FakeLLMClient(GOOD)
    monkeypatch.setattr(cli, "_make_client", lambda url, key: client)
    return client


def _run(tmp_path: Path, *extra: str, audit: Path | None = None):
    audit = audit or _audit(tmp_path)
    args = ["evalgen", "--callsites", str(audit), "--out", str(tmp_path / "evals"), "--count", "3"]
    return runner.invoke(app, [*args, *extra])


def test_writes_files_and_skips_expression_sites(tmp_path: Path, fake: FakeLLMClient) -> None:
    result = _run(tmp_path)
    assert result.exit_code == 0, result.output
    assert "wrote" in result.output and "3 cases, 0 dropped, 1 calls" in result.output
    assert "skip app/b.py::raw: prompt has expression placeholders" in result.output
    written = load_eval_set(tmp_path / "evals" / "app.a__classify.jsonl")
    assert len(written.cases) == 3
    assert fake.calls[0].model == "qwen2.5:7b"


def test_model_option(tmp_path: Path, fake: FakeLLMClient) -> None:
    _run(tmp_path, "--model", "other", "--site", "app/a.py::classify")
    assert fake.calls[0].model == "other"


def test_existing_file_needs_force(tmp_path: Path, fake: FakeLLMClient) -> None:
    _run(tmp_path)
    again = _run(tmp_path)
    assert "exists (use --force)" in again.output
    forced = _run(tmp_path, "--force")
    assert "wrote" in forced.output


def test_unknown_site(tmp_path: Path, fake: FakeLLMClient) -> None:
    result = _run(tmp_path, "--site", "nope.py::x")
    assert result.exit_code == 2
    assert "unknown call site id(s): nope.py::x" in result.output


@pytest.mark.parametrize("value", ["policy", "policy=missing.md", "=x.md"])
def test_bad_shared(tmp_path: Path, fake: FakeLLMClient, value: str) -> None:
    result = _run(tmp_path, "--shared", value)
    assert result.exit_code == 2
    assert "--shared expects KEY=FILE" in result.output


def test_shared_file_header(tmp_path: Path, fake: FakeLLMClient) -> None:
    policy = tmp_path / "policy.md"
    policy.write_text("Refund rules.")
    audit = _audit(tmp_path, _site("app/p.py::decide", "{policy}\n{ticket_text}"))
    result = _run(tmp_path, "--shared", f"policy={policy}", audit=audit)
    assert result.exit_code == 0, result.output
    written = load_eval_set(tmp_path / "evals" / "app.p__decide.jsonl")
    assert written.shared == {"policy": "Refund rules."}
    assert "Refund rules." in fake.calls[0].messages[1]["content"]


def test_no_valid_cases_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_make_client", lambda url, key: FakeLLMClient("{}"))
    result = _run(tmp_path)
    assert result.exit_code == 1
    assert "no valid cases after 3 attempts" in result.output


def test_llm_error_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_make_client", lambda url, key: FakeLLMClient({}))
    result = _run(tmp_path)
    assert result.exit_code == 1
    assert "has no response for model" in result.output


def test_bad_callsites(tmp_path: Path, fake: FakeLLMClient) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    result = _run(tmp_path, audit=bad)
    assert result.exit_code == 2
