"""Downshift command line interface."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from downshift import __version__
from downshift.config import ConfigError, resolve_config
from downshift.scanner import scan_path
from downshift.schema import ScanResult

DEFAULT_OUT = Path(".downshift") / "callsites.json"

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


def _fail(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=2)


# --- scan ---------------------------------------------------------------------


@app.command()
def scan(
    path: Path = typer.Argument(Path("."), help="Repository directory or Python file to scan."),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file. Default: downshift.yaml in PATH, if present.",
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        "-o",
        help="Where to write callsites.json. Default: PATH/.downshift/callsites.json.",
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Print the JSON to stdout instead of a table."
    ),
) -> None:
    """Find every LLM call site in a repository."""
    try:
        cfg = resolve_config(config, path)
        result = scan_path(path, cfg.scan)
    except (ConfigError, FileNotFoundError) as exc:
        _fail(str(exc))
        return

    if as_json:
        typer.echo(result.to_json(), nl=False)
        if out is not None:
            result.write(out)
        return

    target = out if out is not None else _default_out(path)
    result.write(target)
    _print_table(result)

    summary = result.summary()
    total = summary["call_sites"]
    typer.echo(
        f"{total} call sites in {summary['files_scanned']} files, "
        f"models resolved {summary['models_resolved']}/{total}, "
        f"prompts resolved {summary['prompts_resolved']}/{total}"
    )
    for warning in result.warnings:
        typer.echo(f"warning: {warning}", err=True)
    typer.echo(f"Wrote {target}")


def _default_out(path: Path) -> Path:
    base = path if path.is_dir() else path.parent
    return base / DEFAULT_OUT


def _print_table(result: ScanResult) -> None:
    table = Table(title=f"LLM call sites in {result.root}")
    table.add_column("File", no_wrap=True)
    table.add_column("Function", no_wrap=True)
    table.add_column("Line", justify="right")
    table.add_column("Model", no_wrap=True)
    table.add_column("Source")
    table.add_column("Prompt")
    table.add_column("Output")
    for site in result.call_sites:
        table.add_row(
            site.file,
            site.function,
            str(site.line),
            site.model.value or "[red]?[/red]",
            site.model.source,
            "known" if site.prompt_resolved else "[yellow]runtime[/yellow]",
            site.output_format,
        )
    Console().print(table)


# --- not implemented yet ------------------------------------------------------


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
