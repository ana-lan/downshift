import pytest
from typer.testing import CliRunner

from downshift import __version__
from downshift.cli import app

runner = CliRunner()
COMMANDS = ["scan", "evalgen", "report", "diff", "dashboard"]
NOT_IMPLEMENTED = ["dashboard"]


def test_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in COMMANDS:
        assert command in result.output


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


@pytest.mark.parametrize("command", NOT_IMPLEMENTED)
def test_unimplemented_commands_fail_cleanly(command: str) -> None:
    result = runner.invoke(app, [command])
    assert result.exit_code == 1
