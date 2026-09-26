from typer.testing import CliRunner

from downshift import __version__
from downshift.cli import app

runner = CliRunner()
COMMANDS = ["scan", "evalgen", "report", "diff", "export"]


def test_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in COMMANDS:
        assert command in result.output


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
