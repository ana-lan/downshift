from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from downshift.cli import app
from downshift.llm import FakeLLMClient, LLMError
from downshift.schema import ScanResult
from downshift.scorer import JUDGE_SYSTEM

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "supportdesk"
AUDIT = EXAMPLE / "downshift.audit.json"
SITES = ScanResult.load(AUDIT).call_sites
DRAFT = next(s.id for s in SITES if s.function == "draft_reply")
CLASSIFY = next(s.id for s in SITES if s.function == "classify_category")
HOSTED = ("--judge-base-url", "https://judge.example/v1", "--judge-api-key-env", "TEST_JUDGE_KEY")

cli = CliRunner()


def responder_with(score: int | None) -> Callable[[str, list[dict[str, str]]], str]:
    def responder(model: str, msgs: list[dict[str, str]]) -> str:
        if msgs[0]["content"] == JUDGE_SYSTEM:
            if score is None:
                raise LLMError("rate limited")
            return f'{{"score": {score}}}'
        return "Thanks for reaching out."

    return responder


def use_client(monkeypatch: pytest.MonkeyPatch, client: FakeLLMClient) -> FakeLLMClient:
    monkeypatch.setattr("downshift.cli._make_client", lambda base_url, api_key: client)
    return client


def use_hosted(monkeypatch: pytest.MonkeyPatch, client: FakeLLMClient) -> dict[str, str]:
    seen: dict[str, str] = {}

    def make(base_url: str, api_key: str) -> FakeLLMClient:
        seen.update(base_url=base_url, api_key=api_key)
        return client

    monkeypatch.setattr("downshift.cli._make_judge_client", make)
    monkeypatch.setenv("TEST_JUDGE_KEY", "secret")
    return seen


def seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_client(monkeypatch, FakeLLMClient(responder_with(5)))
    result = cli.invoke(
        app,
        [
            "run",
            "--callsites",
            str(AUDIT),
            "--site",
            DRAFT,
            "--model",
            "m",
            "--limit",
            "2",
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output


def rescore(*args: str):  # type: ignore[no-untyped-def]
    return cli.invoke(app, ["rescore", "--callsites", str(AUDIT), *args])


def test_rescore_with_main_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed(tmp_path, monkeypatch)
    use_client(monkeypatch, FakeLLMClient(responder_with(3)))
    result = rescore("--model", "m", "--results", str(tmp_path), "--judge-model", "new-j")
    assert result.exit_code == 0, result.output
    assert "judge: new-j" in result.output
    assert "2/2 -> 0/2 passed, 2 rescored" in result.output


def test_rescore_with_hosted_judge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed(tmp_path, monkeypatch)
    main = use_client(monkeypatch, FakeLLMClient(responder_with(5)))
    hosted = FakeLLMClient(responder_with(2))
    seen = use_hosted(monkeypatch, hosted)
    result = rescore("--model", "m", "--results", str(tmp_path), "--judge-model", "big", *HOSTED)
    assert result.exit_code == 0, result.output
    assert seen == {"base_url": "https://judge.example/v1", "api_key": "secret"}
    assert main.calls == []
    assert len(hosted.calls) == 2
    assert all(c.model == "big" and c.json_mode and c.max_tokens == 1024 for c in hosted.calls)
    assert "2/2 -> 0/2 passed" in result.output


def test_rescore_missing_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_client(monkeypatch, FakeLLMClient("x"))
    monkeypatch.delenv("TEST_JUDGE_KEY", raising=False)
    result = rescore("--results", str(tmp_path), *HOSTED)
    assert result.exit_code == 2
    assert "needs an API key in $TEST_JUDGE_KEY" in result.output


def test_rescore_errors_exit_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed(tmp_path, monkeypatch)
    use_client(monkeypatch, FakeLLMClient(responder_with(None)))
    result = rescore("--model", "m", "--results", str(tmp_path), "--judge-model", "new-j")
    assert result.exit_code == 1
    assert "EE" in result.output


def test_rescore_no_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_client(monkeypatch, FakeLLMClient("x"))
    result = rescore("--model", "m", "--results", str(tmp_path))
    assert result.exit_code == 0, result.output
    assert "run downshift run first" in result.output


def test_rescore_non_judge_site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_client(monkeypatch, FakeLLMClient("x"))
    result = rescore("--site", CLASSIFY, "--results", str(tmp_path))
    assert result.exit_code == 2
    assert "nothing to rescore" in result.output


def test_rescore_unknown_site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_client(monkeypatch, FakeLLMClient("x"))
    result = rescore("--site", "nope.py::x", "--results", str(tmp_path))
    assert result.exit_code == 2
    assert "unknown call site" in result.output


def test_rescore_missing_evals_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_client(monkeypatch, FakeLLMClient("x"))
    result = rescore("--evals", str(tmp_path / "nope"), "--results", str(tmp_path))
    assert result.exit_code == 2
    assert "folder not found" in result.output


def test_run_uses_hosted_judge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    main = use_client(monkeypatch, FakeLLMClient(responder_with(5)))
    hosted = FakeLLMClient(responder_with(4))
    use_hosted(monkeypatch, hosted)
    result = cli.invoke(
        app,
        [
            "run",
            "--callsites",
            str(AUDIT),
            "--site",
            DRAFT,
            "--model",
            "m",
            "--limit",
            "1",
            "--out",
            str(tmp_path),
            "--judge-model",
            "big",
            *HOSTED,
        ],
    )
    assert result.exit_code == 0, result.output
    assert sum(1 for c in hosted.calls if c.messages[0]["content"] == JUDGE_SYSTEM) == 1
    assert all(c.messages[0]["content"] != JUDGE_SYSTEM for c in main.calls)
