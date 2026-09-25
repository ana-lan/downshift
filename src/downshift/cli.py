"""Downshift command line interface."""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from downshift import __version__
from downshift.audit import Comparison, compare_scans, validate_file
from downshift.config import ConfigError, resolve_config
from downshift.evalgen import EvalGenSkip, generate_eval_set, write_eval_set
from downshift.evals import (
    EVAL_SUFFIX,
    EvalError,
    EvalReport,
    EvalSet,
    check_eval_dir,
    load_eval_set,
    site_placeholders,
    slug_for,
    validate_eval_set,
)
from downshift.llm import LLMClient, LLMError, OpenAICompatClient
from downshift.runner import ResultRow, Runner, RunSummary
from downshift.scanner import scan_path
from downshift.schema import CallSite, ScanResult, SchemaError
from downshift.scorer import Judge

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


# --- validate -----------------------------------------------------------------


@app.command()
def validate(
    path: Path = typer.Argument(..., help="callsites or audit JSON file to check."),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as errors."),
) -> None:
    """Check a callsites or audit file against the schema."""
    if not path.is_file():
        _fail(f"file not found: {path}")
        return

    report = validate_file(path)
    result = report.result
    if report.error is not None or result is None:
        typer.echo(f"Invalid: {report.error}", err=True)
        raise typer.Exit(code=1)

    summary = result.summary()
    total = summary["call_sites"]
    typer.echo(
        f"Valid: {path} ({total} call sites, generated by {result.generated_by}, "
        f"models resolved {summary['models_resolved']}/{total}, "
        f"prompts resolved {summary['prompts_resolved']}/{total})"
    )
    for warning in report.warnings:
        typer.echo(f"warning: {warning}", err=True)
    if strict and report.warnings:
        raise typer.Exit(code=1)


# --- compare ------------------------------------------------------------------


@app.command()
def compare(
    ast_file: Path = typer.Argument(..., help="Scan output from `downshift scan`."),
    audit_file: Path = typer.Argument(..., help="Audit output from the Bob auditor."),
    as_json: bool = typer.Option(False, "--json", help="Print the comparison as JSON."),
) -> None:
    """Compare the ast scan with a Bob audit, side by side."""
    try:
        before = ScanResult.load(ast_file)
        after = ScanResult.load(audit_file)
    except SchemaError as exc:
        _fail(str(exc))
        return

    comparison = compare_scans(before, after)
    if as_json:
        typer.echo(json.dumps(comparison.to_dict(), indent=2))
        return

    left, right = before.generated_by, after.generated_by
    if left == right:
        left, right = "before", "after"
    _print_comparison(comparison, left, right)

    b, a = before.summary(), after.summary()
    typer.echo(
        f"{left}: {b['call_sites']} call sites, {b['models_resolved']} models resolved | "
        f"{right}: {a['call_sites']} call sites, {a['models_resolved']} models resolved"
    )


def _print_comparison(comparison: Comparison, left: str, right: str) -> None:
    console = Console()
    metrics = Table(title="Scan vs audit")
    metrics.add_column("Metric")
    metrics.add_column(left, justify="right")
    metrics.add_column(right, justify="right")
    for metric in comparison.metrics:
        metrics.add_row(metric.name, str(metric.ast), str(metric.audit))
    console.print(metrics)

    changes = Table(title="Call site changes")
    changes.add_column("Call site", no_wrap=True)
    changes.add_column("Change")
    changes.add_column("Detail")
    for change in comparison.changes:
        changes.add_row(change.id, change.kind, change.detail)
    console.print(changes)


# --- check-evals --------------------------------------------------------------


@app.command("check-evals")
def check_evals(
    directory: Path = typer.Argument(..., help="Folder of <slug>.jsonl eval files."),
    callsites: Path = typer.Option(
        ..., "--callsites", help="Audit (or callsites) JSON the eval files belong to."
    ),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as errors."),
) -> None:
    """Check eval files against the call sites they test."""
    if not directory.is_dir():
        _fail(f"folder not found: {directory}")
        return
    try:
        result = ScanResult.load(callsites)
    except SchemaError as exc:
        _fail(str(exc))
        return

    reports = check_eval_dir(directory, result.call_sites)
    _print_eval_reports(reports)

    errors = sum(len(r.errors) for r in reports)
    warnings = sum(len(r.warnings) for r in reports)
    cases = sum(r.cases for r in reports)
    files = sum(1 for r in reports if r.path.exists())
    for r in reports:
        for message in r.errors:
            typer.echo(f"error: {r.path.name}: {message}", err=True)
        for message in r.warnings:
            typer.echo(f"warning: {r.path.name}: {message}", err=True)
    typer.echo(f"{files} eval files, {cases} cases, {errors} errors, {warnings} warnings")
    if errors or (strict and warnings):
        raise typer.Exit(code=1)


def _print_eval_reports(reports: list[EvalReport]) -> None:
    table = Table(title="Eval sets")
    table.add_column("Call site", overflow="fold")
    table.add_column("Grading")
    table.add_column("Cases", justify="right")
    table.add_column("Status")
    for r in reports:
        if r.errors:
            status = f"[red]{len(r.errors)} errors[/red]"
        elif r.warnings:
            status = f"[yellow]{len(r.warnings)} warnings[/yellow]"
        else:
            status = "[green]ok[/green]"
        table.add_row(r.site_id or "?", r.grading or "-", str(r.cases), status)
    Console().print(table)


# --- evalgen ------------------------------------------------------------------


def _make_client(provider_base_url: str, api_key: str) -> LLMClient:
    return OpenAICompatClient(provider_base_url, api_key)


@app.command()
def evalgen(
    callsites: Path = typer.Option(..., "--callsites", help="Audit (or callsites) JSON."),
    out: Path = typer.Option(..., "--out", "-o", help="Folder to write <slug>.jsonl files to."),
    site: list[str] = typer.Option([], "--site", help="Only this call site id. Repeatable."),
    model: str | None = typer.Option(None, "--model", help="Default: models.judge or baseline."),
    count: int = typer.Option(20, "--count", min=1, help="Cases per call site."),
    shared: list[str] = typer.Option(
        [], "--shared", help="KEY=FILE, a fixed input read from a file. Repeatable."
    ),
    config: Path | None = typer.Option(None, "--config", "-c", help="Config file."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing eval files."),
) -> None:
    """Generate an eval set for each call site with a configured model."""
    try:
        result = ScanResult.load(callsites)
        cfg = resolve_config(config, callsites.parent)
        client = _make_client(cfg.provider.base_url, cfg.provider.api_key())
    except (SchemaError, ConfigError) as exc:
        _fail(str(exc))
        return

    shared_files: dict[str, Path] = {}
    for item in shared:
        key, sep, file = item.partition("=")
        if not sep or not key or not Path(file).is_file():
            _fail(f"--shared expects KEY=FILE with an existing file, got {item!r}")
            return
        shared_files[key] = Path(file)
    shared_text = {k: p.read_text(encoding="utf-8") for k, p in shared_files.items()}

    sites = result.call_sites
    if site:
        known = {s.id for s in sites}
        unknown = [s for s in site if s not in known]
        if unknown:
            _fail(f"unknown call site id(s): {', '.join(unknown)}")
            return
        sites = [s for s in sites if s.id in site]

    use_model = model or cfg.models.judge_model
    failed = False
    for call_site in sites:
        path = out / f"{slug_for(call_site.id)}{EVAL_SUFFIX}"
        if path.exists() and not force:
            typer.echo(f"skip {call_site.id}: {path} exists (use --force)")
            continue
        try:
            gen = generate_eval_set(client, use_model, call_site, count=count, shared=shared_text)
        except EvalGenSkip as exc:
            typer.echo(f"skip {call_site.id}: {exc}")
            continue
        except LLMError as exc:
            typer.echo(f"error {call_site.id}: {exc}", err=True)
            failed = True
            continue
        if not gen.cases:
            typer.echo(
                f"error {call_site.id}: no valid cases after {gen.attempts} attempts", err=True
            )
            failed = True
            continue
        names = set(site_placeholders(call_site))
        used = {k: p for k, p in shared_files.items() if k in names}
        write_eval_set(path, gen.cases, used)
        typer.echo(
            f"wrote {path} ({len(gen.cases)} cases, {len(gen.dropped)} dropped, "
            f"{gen.attempts} calls, model {use_model})"
        )
    if failed:
        raise typer.Exit(code=1)


# --- run ----------------------------------------------------------------------


@app.command()
def run(
    callsites: Path = typer.Option(..., "--callsites", help="Audit (or callsites) JSON."),
    evals: Path | None = typer.Option(
        None, "--evals", help="Eval folder. Default: evals/ next to --callsites."
    ),
    out: Path | None = typer.Option(
        None, "--out", "-o", help="Results folder. Default: results/ next to --callsites."
    ),
    model: list[str] = typer.Option(
        [], "--model", help="Model to run. Repeatable. Default: baseline + candidates."
    ),
    site: list[str] = typer.Option([], "--site", help="Only this call site id. Repeatable."),
    limit: int | None = typer.Option(
        None, "--limit", min=1, help="Only the first N cases per call site."
    ),
    config: Path | None = typer.Option(None, "--config", "-c", help="Config file."),
    warmup: bool = typer.Option(
        True, "--warmup/--no-warmup", help="One untimed call per model before timing."
    ),
) -> None:
    """Run each call site's evals on the baseline and candidate models, and score them."""
    try:
        result = ScanResult.load(callsites)
        cfg = resolve_config(config, callsites.parent)
        client = _make_client(cfg.provider.base_url, cfg.provider.api_key())
    except (SchemaError, ConfigError) as exc:
        _fail(str(exc))
        return

    evals_dir = evals if evals is not None else callsites.parent / "evals"
    results_dir = out if out is not None else callsites.parent / "results"
    if not evals_dir.is_dir():
        _fail(f"folder not found: {evals_dir}")
        return

    sites = result.call_sites
    if site:
        known = {s.id for s in sites}
        unknown = [s for s in site if s not in known]
        if unknown:
            _fail(f"unknown call site id(s): {', '.join(unknown)}")
            return
        sites = [s for s in sites if s.id in site]

    tasks = _load_run_tasks(sites, evals_dir)
    if not tasks:
        _fail("nothing to run: no call site has a valid eval file")
        return

    models = model or [cfg.models.baseline, *cfg.models.candidates]
    runner = Runner(
        client,
        results_dir=results_dir,
        judge=Judge(client, cfg.models.judge_model),
        limit=limit,
        warmup=warmup,
        on_case=_case_mark,
    )
    summaries: list[RunSummary] = []
    failed = False
    for name in models:
        for call_site, eval_set in tasks:
            typer.echo(f"{name}  {call_site.id}  ", nl=False)
            try:
                summary = runner.run_site(call_site, eval_set, name)
            except LLMError as exc:
                typer.echo("")
                typer.echo(f"error {name}: {exc}; skipping this model", err=True)
                failed = True
                break
            summaries.append(summary)
            typer.echo(f"  {summary.passed}/{summary.cases} passed, {summary.new} new")

    _print_run_summary(summaries)
    errors = sum(s.errors for s in summaries)
    typer.echo(f"{len(summaries)} site/model runs, {errors} errors. Results in {results_dir}")
    if failed or errors:
        raise typer.Exit(code=1)


def _load_run_tasks(sites: list[CallSite], evals_dir: Path) -> list[tuple[CallSite, EvalSet]]:
    tasks: list[tuple[CallSite, EvalSet]] = []
    for call_site in sites:
        path = evals_dir / f"{slug_for(call_site.id)}{EVAL_SUFFIX}"
        if not path.is_file():
            typer.echo(f"skip {call_site.id}: no eval file at {path}")
            continue
        try:
            eval_set = load_eval_set(path)
        except EvalError as exc:
            typer.echo(f"skip {call_site.id}: {exc}")
            continue
        report = validate_eval_set(eval_set, call_site)
        if report.errors:
            typer.echo(
                f"skip {call_site.id}: {len(report.errors)} eval errors (run downshift check-evals)"
            )
            continue
        tasks.append((call_site, eval_set))
    return tasks


def _case_mark(row: ResultRow) -> None:
    mark = "E" if row.error else ("." if row.passed else "x")
    typer.echo(mark, nl=False)


def _print_run_summary(summaries: list[RunSummary]) -> None:
    table = Table(title="Run results")
    table.add_column("Call site", overflow="fold")
    table.add_column("Model", no_wrap=True)
    table.add_column("Cases", justify="right")
    table.add_column("Passed", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Latency", justify="right")
    table.add_column("Tokens in/out", justify="right")
    table.add_column("Errors", justify="right")
    for s in summaries:
        rate = f"{s.passed}/{s.scored} ({s.pass_rate:.0%})" if s.pass_rate is not None else "-"
        score = f"{s.mean_score:.2f}" if s.mean_score is not None else "-"
        latency = f"{s.avg_latency_s:.2f}s" if s.avg_latency_s is not None else "-"
        tokens = (
            f"{s.avg_prompt_tokens:.0f}/{s.avg_completion_tokens:.0f}"
            if s.avg_prompt_tokens is not None and s.avg_completion_tokens is not None
            else "-"
        )
        errors = f"[red]{s.errors}[/red]" if s.errors else "0"
        table.add_row(s.site_id, s.model, str(s.cases), rate, score, latency, tokens, errors)
    Console().print(table)


# --- not implemented yet ------------------------------------------------------


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
