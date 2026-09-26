"""CLI tests for `downshift diff`, using temp git repos."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from downshift.cli import app

CONFIG = Path(__file__).resolve().parents[2] / "examples" / "supportdesk" / "downshift.yaml"

cli = CliRunner()


def call_source(name: str, model: str = "qwen2.5:7b", max_tokens: int = 64) -> str:
    return (
        "from openai import OpenAI\n\nclient = OpenAI()\n\n\n"
        f"def {name}(text):\n"
        "    return client.chat.completions.create(\n"
        f'        model="{model}",\n'
        '        messages=[{"role": "user", "content": "Help with this ticket"}],\n'
        f"        max_tokens={max_tokens},\n"
        "    )\n"
    )


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        check=True,
        capture_output=True,
    )


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "app.py").write_text(call_source("classify"))
    commit_all(root, "base")
    return root


def invoke(*args: str):  # type: ignore[no-untyped-def]
    return cli.invoke(app, ["diff", *args, "-c", str(CONFIG)])


def test_no_changes(repo: Path) -> None:
    result = invoke(str(repo))
    assert result.exit_code == 0, result.output
    assert "No LLM call site cost changes" in result.output


def test_added_in_working_tree(repo: Path) -> None:
    (repo / "big.py").write_text(call_source("escalate", max_tokens=2048))
    result = invoke(str(repo))
    assert result.exit_code == 0, result.output
    assert "| added |" in result.output
    assert "`big.py::escalate`" in result.output
    assert "(+$" in result.output


def test_removed(repo: Path) -> None:
    (repo / "app.py").unlink()
    result = invoke(str(repo))
    assert result.exit_code == 0, result.output
    assert "| removed |" in result.output
    assert "-$" in result.output


def test_changed_model(repo: Path) -> None:
    (repo / "app.py").write_text(call_source("classify", model="qwen2.5:0.5b"))
    result = invoke(str(repo))
    assert result.exit_code == 0, result.output
    assert "| changed |" in result.output
    assert "qwen2.5:7b -> qwen2.5:0.5b" in result.output


def test_head_ref(repo: Path) -> None:
    git(repo, "checkout", "-q", "-b", "feature")
    (repo / "big.py").write_text(call_source("escalate"))
    commit_all(repo, "add escalate")
    git(repo, "checkout", "-q", "main")
    result = invoke(str(repo), "--head", "feature")
    assert result.exit_code == 0, result.output
    assert "`big.py::escalate`" in result.output
    assert "`feature` vs `main`" in result.output


def test_subdirectory_new_at_head(repo: Path) -> None:
    sub = repo / "sub"
    sub.mkdir()
    (sub / "tool.py").write_text(call_source("helper"))
    result = invoke(str(sub))
    assert result.exit_code == 0, result.output
    assert "`tool.py::helper`" in result.output
    assert "| added |" in result.output
    assert "app.py" not in result.output


def test_fail_above(repo: Path) -> None:
    (repo / "big.py").write_text(call_source("escalate", max_tokens=2048))
    over = invoke(str(repo), "--fail-above", "0")
    assert over.exit_code == 1, over.output
    assert "above --fail-above" in over.output
    under = invoke(str(repo), "--fail-above", "1000000")
    assert under.exit_code == 0, under.output


def test_out_file(repo: Path, tmp_path: Path) -> None:
    (repo / "big.py").write_text(call_source("escalate"))
    out = tmp_path / "out" / "diff.md"
    result = invoke(str(repo), "--out", str(out))
    assert result.exit_code == 0, result.output
    assert "Wrote" in result.output
    assert "1 call site change(s)" in result.output
    assert out.read_text().startswith("## Downshift cost diff")


def test_unknown_ref(repo: Path) -> None:
    result = invoke(str(repo), "--base", "nope")
    assert result.exit_code == 2
    assert "unknown git ref: nope" in result.output


def test_not_a_git_repo(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "app.py").write_text(call_source("classify"))
    result = invoke(str(plain))
    assert result.exit_code == 2
    assert "not inside a git repository" in result.output
