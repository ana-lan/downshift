"""Downshift command line interface."""

import json
import os
import tempfile
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from downshift import __version__
from downshift.audit import Comparison, compare_scans, validate_file
from downshift.config import Config, ConfigError, resolve_config
from downshift.diff import diff_for_config
from downshift.diff import render_markdown as render_diff_markdown
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
from downshift.export import DEFAULT_EXAMPLES, build_export, write_export
from downshift.gitref import GitError, extract_ref, repo_root
from downshift.llm import LLMClient, LLMError, OpenAICompatClient
from downshift.report import ReportError, build_report, render_markdown
from downshift.runner import ResultRow, Runner, RunSummary, rescore_site, results_path
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


def _make_judge_client(base_url: str, api_key: str) -> LLMClient:
    """Client for a hosted judge; retries rate limits (429) with backoff."""
    from openai import OpenAI

    return OpenAICompatClient(
        base_url,
        api_key,
        client=OpenAI(base_url=base_url, api_key=api_key, timeout=120.0, max_retries=8),
    )


def _build_judge(
    client: LLMClient, model: str, base_url: str | None, key_env: str, max_tokens: int
) -> Judge:
    if base_url is None:
        return Judge(client, model, max_tokens=max_tokens)
    api_key = os.environ.get(key_env, "")
    if not api_key:
        raise ValueError(f"judge endpoint {base_url} needs an API key in ${key_env}")
    return Judge(_make_judge_client(base_url, api_key), model, max_tokens=max_tokens)


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
    judge_model: str | None = typer.Option(
        None, "--judge-model", help="Judge model. Default: models.judge or baseline."
    ),
    judge_base_url: str | None = typer.Option(
        None, "--judge-base-url", help="Separate OpenAI-compatible endpoint for the judge."
    ),
    judge_api_key_env: str = typer.Option(
        "JUDGE_API_KEY", "--judge-api-key-env", help="Env var with the judge API key."
    ),
    judge_max_tokens: int = typer.Option(
        1024, "--judge-max-tokens", min=16, help="Max tokens per judge reply."
    ),
) -> None:
    """Run each call site's evals on the baseline and candidate models, and score them."""
    try:
        result = ScanResult.load(callsites)
        cfg = resolve_config(config, callsites.parent)
        client = _make_client(cfg.provider.base_url, cfg.provider.api_key())
        judge = _build_judge(
            client,
            judge_model or cfg.models.judge_model,
            judge_base_url,
            judge_api_key_env,
            judge_max_tokens,
        )
    except (SchemaError, ConfigError, ValueError) as exc:
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
        judge=judge,
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


# --- rescore ------------------------------------------------------------------


@app.command()
def rescore(
    callsites: Path = typer.Option(..., "--callsites", help="Audit (or callsites) JSON."),
    evals: Path | None = typer.Option(
        None, "--evals", help="Eval folder. Default: evals/ next to --callsites."
    ),
    results: Path | None = typer.Option(
        None, "--results", help="Results folder. Default: results/ next to --callsites."
    ),
    model: list[str] = typer.Option(
        [], "--model", help="Only these models' results. Default: baseline + candidates."
    ),
    site: list[str] = typer.Option([], "--site", help="Only this call site id. Repeatable."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Config file."),
    judge_model: str | None = typer.Option(
        None, "--judge-model", help="Judge model. Default: models.judge or baseline."
    ),
    judge_base_url: str | None = typer.Option(
        None, "--judge-base-url", help="Separate OpenAI-compatible endpoint for the judge."
    ),
    judge_api_key_env: str = typer.Option(
        "JUDGE_API_KEY", "--judge-api-key-env", help="Env var with the judge API key."
    ),
    judge_max_tokens: int = typer.Option(
        1024, "--judge-max-tokens", min=16, help="Max tokens per judge reply."
    ),
) -> None:
    """Re-grade saved outputs of judge-graded call sites with the configured judge."""
    try:
        result = ScanResult.load(callsites)
        cfg = resolve_config(config, callsites.parent)
        client = _make_client(cfg.provider.base_url, cfg.provider.api_key())
        judge = _build_judge(
            client,
            judge_model or cfg.models.judge_model,
            judge_base_url,
            judge_api_key_env,
            judge_max_tokens,
        )
    except (SchemaError, ConfigError, ValueError) as exc:
        _fail(str(exc))
        return

    evals_dir = evals if evals is not None else callsites.parent / "evals"
    results_dir = results if results is not None else callsites.parent / "results"
    if not evals_dir.is_dir():
        _fail(f"folder not found: {evals_dir}")
        return

    known = {s.id for s in result.call_sites}
    unknown = [s for s in site if s not in known]
    if unknown:
        _fail(f"unknown call site id(s): {', '.join(unknown)}")
        return
    sites = [s for s in result.call_sites if s.grading == "judge" and (not site or s.id in site)]
    tasks = _load_run_tasks(sites, evals_dir)
    if not tasks:
        _fail("nothing to rescore: no judge-graded call site with a valid eval file")
        return

    models = model or [cfg.models.baseline, *cfg.models.candidates]
    typer.echo(f"judge: {judge.model}")
    pairs: list[tuple[RunSummary, RunSummary]] = []
    for name in models:
        for call_site, eval_set in tasks:
            if not results_path(results_dir, call_site.id, name).is_file():
                typer.echo(f"skip {name} {call_site.id}: no results (run downshift run first)")
                continue
            typer.echo(f"{name}  {call_site.id}  ", nl=False)
            before, after = rescore_site(
                call_site,
                eval_set,
                name,
                results_dir=results_dir,
                judge=judge,
                on_case=_case_mark,
            )
            pairs.append((before, after))
            typer.echo(
                f"  {before.passed}/{before.scored} -> {after.passed}/{after.scored} passed, "
                f"{after.new} rescored"
            )

    _print_rescore_summary(pairs, judge.model)
    errors = sum(after.errors for _, after in pairs)
    typer.echo(f"{len(pairs)} site/model results rescored, {errors} errors. Saved in {results_dir}")
    if errors:
        raise typer.Exit(code=1)


def _rate(summary: RunSummary) -> str:
    if summary.pass_rate is None:
        return "-"
    return f"{summary.passed}/{summary.scored} ({summary.pass_rate:.0%})"


def _print_rescore_summary(pairs: list[tuple[RunSummary, RunSummary]], judge_model: str) -> None:
    table = Table(title=f"Rescored with {judge_model}")
    table.add_column("Call site", overflow="fold")
    table.add_column("Model", no_wrap=True)
    table.add_column("Before", justify="right")
    table.add_column("After", justify="right")
    table.add_column("Rescored", justify="right")
    table.add_column("Errors", justify="right")
    for before, after in pairs:
        errors = f"[red]{after.errors}[/red]" if after.errors else "0"
        table.add_row(
            after.site_id, after.model, _rate(before), _rate(after), str(after.new), errors
        )
    Console().print(table)


# --- not implemented yet ------------------------------------------------------


@app.command()
def report(
    callsites: Path = typer.Option(..., "--callsites", help="Audit (or callsites) JSON."),
    evals: Path | None = typer.Option(
        None, "--evals", help="Eval folder. Default: evals/ next to --callsites."
    ),
    results: Path | None = typer.Option(
        None, "--results", help="Results folder. Default: results/ next to --callsites."
    ),
    config: Path | None = typer.Option(None, "--config", "-c", help="Config file."),
    threshold: float | None = typer.Option(
        None,
        "--threshold",
        min=0.0,
        max=1.0,
        help="Quality threshold override (0,1]. Default: from config.",
    ),
    min_pass_rate: float | None = typer.Option(
        None,
        "--min-pass-rate",
        min=0.0,
        max=1.0,
        help="Minimum pass rate override [0,1]. Default: from config.",
    ),
    out: Path | None = typer.Option(None, "--out", help="Write Markdown to this file."),
) -> None:
    """Render the cost and quality report."""
    if threshold is not None and threshold <= 0:
        _fail("--threshold must be greater than 0")
        return
    try:
        scan = ScanResult.load(callsites)
        cfg = resolve_config(config, callsites.parent)
    except (SchemaError, ConfigError) as exc:
        _fail(str(exc))
        return

    evals_dir = evals if evals is not None else callsites.parent / "evals"
    results_dir = results if results is not None else callsites.parent / "results"

    try:
        rep = build_report(
            scan,
            cfg,
            evals_dir,
            results_dir,
            threshold=threshold,
            min_pass_rate=min_pass_rate,
        )
    except ReportError as exc:
        _fail(str(exc))
        return

    md = render_markdown(rep)

    if out is None:
        typer.echo(md, nl=False)
        return

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")

    costs = rep.costs
    n_down = len(rep.downgraded)
    n_total = len(rep.decisions)
    savings = costs.savings if costs.sites else 0.0
    savings_pct = costs.savings_pct
    pct_str = f"{savings_pct:.1%}" if savings_pct is not None else "n/a"
    typer.echo(
        f"Wrote {out}: downgraded {n_down} of {n_total} call sites,"
        f" projected savings ${savings:,.2f}/month ({pct_str})."
    )


def _sites_at(root: Path, ref: str, rel: Path, dest: Path, cfg: Config) -> list[CallSite]:
    target = extract_ref(root, ref, rel, dest)
    if target is None:
        return []
    return list(scan_path(target, cfg.scan).call_sites)


def _signed_dollars(value: float) -> str:
    if abs(value) < 0.005:
        return "$0.00"
    return f"{'+' if value > 0 else '-'}${abs(value):,.2f}"


@app.command()
def diff(
    path: Path = typer.Argument(Path("."), help="Directory to scan, inside a git repo."),
    base: str = typer.Option("main", "--base", help="Git ref to compare against."),
    head: str | None = typer.Option(
        None, "--head", help="Git ref to compare. Default: the working tree."
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file (used for both sides). Default: downshift.yaml in PATH.",
    ),
    out: Path | None = typer.Option(None, "--out", "-o", help="Write Markdown to this file."),
    fail_above: float | None = typer.Option(
        None,
        "--fail-above",
        min=0.0,
        help="Exit 1 if the projected monthly increase is above this many dollars.",
    ),
) -> None:
    """Show the projected LLM cost change between two git refs."""
    try:
        cfg = resolve_config(config, path)
        root = repo_root(path)
        rel = path.resolve().relative_to(root)
        with tempfile.TemporaryDirectory() as tmp:
            base_sites = _sites_at(root, base, rel, Path(tmp) / "base", cfg)
            if head is None:
                head_sites = list(scan_path(path, cfg.scan).call_sites)
            else:
                head_sites = _sites_at(root, head, rel, Path(tmp) / "head", cfg)
    except (ConfigError, GitError, FileNotFoundError, ValueError) as exc:
        _fail(str(exc))
        return

    cost = diff_for_config(base_sites, head_sites, cfg)
    md = render_diff_markdown(cost, base=base, head=head or "working tree")
    delta = _signed_dollars(cost.delta)

    if out is None:
        typer.echo(md, nl=False)
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        n = len(cost.added) + len(cost.changed) + len(cost.removed)
        typer.echo(f"Wrote {out}: {n} call site change(s), projected {delta}/month.")

    if fail_above is not None and cost.delta > fail_above:
        typer.echo(
            f"Projected increase {delta}/month is above --fail-above ${fail_above:,.2f}.",
            err=True,
        )
        raise typer.Exit(code=1)


@app.command()
def export(
    path: Path = typer.Argument(
        Path("."), help="Folder with downshift.audit.json, evals/ and results/."
    ),
    out: Path = typer.Option(Path("downshift-export"), "--out", "-o", help="Output folder."),
    callsites: Path | None = typer.Option(
        None, "--callsites", help="Audit JSON. Default: PATH/downshift.audit.json."
    ),
    ast_file: Path | None = typer.Option(
        None, "--ast", help="Ast scan JSON. Default: PATH/downshift.scan.json if present."
    ),
    ast_after_file: Path | None = typer.Option(
        None,
        "--ast-after",
        help="Ast scan after refactor. Default: PATH/downshift.scan.after.json if present.",
    ),
    config: Path | None = typer.Option(None, "--config", "-c", help="Config file."),
    examples: int = typer.Option(
        DEFAULT_EXAMPLES, "--examples", min=0, help="Example eval cases per call site."
    ),
    name: str | None = typer.Option(None, "--name", help="Project name. Default: PATH name."),
) -> None:
    """Export JSON and the report for the demo web app."""
    audit_path = callsites if callsites is not None else path / "downshift.audit.json"
    ast_path = ast_file if ast_file is not None else path / "downshift.scan.json"
    after_path = (
        ast_after_file if ast_after_file is not None else path / "downshift.scan.after.json"
    )
    for required, explicit in (
        (audit_path, True),
        (ast_path, ast_file is not None),
        (after_path, ast_after_file is not None),
    ):
        if explicit and not required.exists():
            _fail(f"File not found: {required}")
            return

    try:
        audit = ScanResult.load(audit_path)
        ast_scan = ScanResult.load(ast_path) if ast_path.exists() else None
        after_scan = ScanResult.load(after_path) if after_path.exists() else None
        cfg = resolve_config(config, audit_path.parent)
    except (SchemaError, ConfigError) as exc:
        _fail(str(exc))
        return

    evals_dir = audit_path.parent / "evals"
    results_dir = audit_path.parent / "results"
    try:
        rep = build_report(audit, cfg, evals_dir, results_dir)
    except ReportError as exc:
        _fail(str(exc))
        return

    payloads = build_export(
        rep,
        cfg,
        audit=audit,
        evals_dir=evals_dir,
        results_dir=results_dir,
        ast=ast_scan,
        ast_after=after_scan,
        project=name or path.resolve().name,
        examples=examples,
    )
    written = write_export(out, payloads, render_markdown(rep))
    savings = rep.costs.savings if rep.costs.sites else 0.0
    typer.echo(
        f"Wrote {len(written)} files to {out}: downgraded {len(rep.downgraded)} of"
        f" {len(rep.decisions)} call sites, projected savings ${savings:,.2f}/month."
    )


def main() -> None:
    app()
