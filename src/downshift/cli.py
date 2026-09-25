"""Downshift command line interface."""

import typer

from downshift import __version__

app = typer.Typer(
    name="downshift",
    help=(
        "Find every LLM call in your repo, prove which ones can use cheaper "
        "models, and show the cost impact of every PR."
    ),
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"downshift {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Downshift: cut LLM costs per PR."""


def _not_implemented(name: str) -> None:
    typer.echo(f"`downshift {name}` is not implemented yet.", err=True)
    raise typer.Exit(code=1)


@app.command()
def scan() -> None:
    """Find every LLM call site in a repository."""
    _not_implemented("scan")


@app.command()
def evalgen() -> None:
    """Generate an eval set for each call site."""
    _not_implemented("evalgen")


@app.command()
def run() -> None:
    """Run evals across candidate models."""
    _not_implemented("run")


@app.command()
def report() -> None:
    """Render the cost and quality report."""
    _not_implemented("report")


@app.command()
def diff() -> None:
    """Show the projected LLM cost change between two git refs."""
    _not_implemented("diff")


@app.command()
def dashboard() -> None:
    """Build the static HTML dashboard."""
    _not_implemented("dashboard")


def main() -> None:
    app()
