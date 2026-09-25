from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from downshift.cli import app
from downshift.evals import slug_for
from downshift.llm import FakeLLMClient, LLMError
from downshift.runner import WARMUP_MESSAGES, load_results
from downshift.schema import ScanResult

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "supportdesk"
AUDIT = EXAMPLE / "downshift.audit.json"
SITES = ScanResult.load(AUDIT).call_sites
CLASSIFY = next(s.id for s in SITES if s.function == "classify_category")

cli = CliRunner()


def use_client(monkeypatch: pytest.MonkeyPatch, client: FakeLLMClient) -> FakeLLMClient:
    monkeypatch.setattr("downshift.cli._make_client", lambda base_url, api_key: client)
    return client


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeLLMClient:
    return use_client(monkeypatch, FakeLLMClient("billing"))


def invoke(*args: str):  # type: ignore[no-untyped-def]
    return cli.invoke(app, ["run", "--callsites", str(AUDIT), *args])


def test_run_default_models_one_site(tmp_path: Path, fake: FakeLLMClient) -> None:
    result = invoke("--site", CLASSIFY, "--limit", "2", "--out", str(tmp_path))
    assert result.exit_code == 0, result.output
    folder = tmp_path / slug_for(CLASSIFY)
    assert sorted(p.name for p in folder.iterdir()) == [
        "qwen2.5-0.5b.jsonl",
        "qwen2.5-1.5b.jsonl",
        "qwen2.5-7b.jsonl",
    ]
    rows = load_results(folder / "qwen2.5-7b.jsonl")
    assert len(rows) == 2
    assert all(r.ok for r in rows.values())
    assert "Run results" in result.output
    assert "3 site/model runs, 0 errors" in result.output


def test_run_resumes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_client(monkeypatch, FakeLLMClient("billing"))
    args = ("--site", CLASSIFY, "--model", "m", "--limit", "2", "--out", str(tmp_path))
    assert invoke(*args).exit_code == 0

    second = use_client(monkeypatch, FakeLLMClient("billing"))
    result = invoke(*args)
    assert result.exit_code == 0, result.output
    assert "0 new" in result.output
    assert second.calls == []


def test_run_all_sites_one_model(tmp_path: Path, fake: FakeLLMClient) -> None:
    result = invoke("--model", "m", "--limit", "1", "--out", str(tmp_path))
    assert result.exit_code == 0, result.output
    assert len(list(tmp_path.glob("*/m.jsonl"))) == len(SITES)


def test_run_no_warmup(tmp_path: Path, fake: FakeLLMClient) -> None:
    result = invoke(
        "--site", CLASSIFY, "--model", "m", "--limit", "1", "--no-warmup", "--out", str(tmp_path)
    )
    assert result.exit_code == 0, result.output
    assert all(c.messages != WARMUP_MESSAGES for c in fake.calls)


def test_run_unavailable_model_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_client(monkeypatch, FakeLLMClient({"qwen2.5:7b": "billing"}))
    result = invoke(
        "--site",
        CLASSIFY,
        "--model",
        "missing",
        "--model",
        "qwen2.5:7b",
        "--limit",
        "1",
        "--out",
        str(tmp_path),
    )
    assert result.exit_code == 1
    assert "skipping this model" in result.output
    folder = tmp_path / slug_for(CLASSIFY)
    assert (folder / "qwen2.5-7b.jsonl").exists()
    assert not (folder / "missing.jsonl").exists()


def test_run_case_errors_exit_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def responder(model: str, msgs: list[dict[str, str]]) -> str:
        if msgs == WARMUP_MESSAGES:
            return "OK"
        raise LLMError("timeout")

    use_client(monkeypatch, FakeLLMClient(responder))
    result = invoke("--site", CLASSIFY, "--model", "m", "--limit", "2", "--out", str(tmp_path))
    assert result.exit_code == 1
    assert "EE" in result.output
    assert "2 errors" in result.output


def test_run_unknown_site(tmp_path: Path, fake: FakeLLMClient) -> None:
    result = invoke("--site", "nope.py::x", "--out", str(tmp_path))
    assert result.exit_code == 2
    assert "unknown call site" in result.output


def test_run_missing_evals_folder(tmp_path: Path, fake: FakeLLMClient) -> None:
    result = invoke("--evals", str(tmp_path / "nope"), "--out", str(tmp_path))
    assert result.exit_code == 2
    assert "folder not found" in result.output


def test_run_no_eval_files(tmp_path: Path, fake: FakeLLMClient) -> None:
    evals = tmp_path / "evals"
    evals.mkdir()
    result = invoke("--evals", str(evals), "--out", str(tmp_path / "out"))
    assert result.exit_code == 2
    assert "no eval file" in result.output
    assert "nothing to run" in result.output


def test_run_skips_invalid_eval_file(tmp_path: Path, fake: FakeLLMClient) -> None:
    evals = tmp_path / "evals"
    evals.mkdir()
    (evals / f"{slug_for(CLASSIFY)}.jsonl").write_text(
        '{"id": "x", "inputs": {}, "expected": "billing", "grading": "exact"}\n'
    )
    result = invoke("--site", CLASSIFY, "--evals", str(evals), "--out", str(tmp_path / "out"))
    assert result.exit_code == 2
    assert "eval errors" in result.output
