"""Export Downshift results as static JSON for the demo web app.

Reads what `downshift report` reads (audit, evals, results, config) plus the
optional ast scans, and returns JSON payloads. No scanning, no models, no
network. The web app only reads these files.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from downshift import __version__
from downshift.audit import METRIC_LABELS, compare_scans, metrics_for
from downshift.config import Config
from downshift.cost import DAYS_PER_MONTH, SiteCost
from downshift.decide import Decision
from downshift.evals import EVAL_SUFFIX, EvalCase, EvalError, EvalSet, load_eval_set, slug_for
from downshift.report import Report
from downshift.runner import ResultRow, load_results, results_path
from downshift.schema import CallSite, ScanResult

SUMMARY_FILE = "summary.json"
CALLSITES_FILE = "callsites.json"
AUDIT_FILE = "audit.json"
EVALS_FILE = "evals_summary.json"
REPORT_FILE = "report.md"
EXPORT_FILES = (SUMMARY_FILE, CALLSITES_FILE, AUDIT_FILE, EVALS_FILE, REPORT_FILE)
DEFAULT_EXAMPLES = 3

DISCLAIMER = (
    "Dollar figures are projections: measured token counts x illustrative per-model "
    "prices x an assumed call volume, all set in downshift.yaml. They are not a real bill."
)

# site_id -> model -> case_id -> row
Rows = dict[str, dict[str, dict[str, ResultRow]]]


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def _models(report: Report) -> list[str]:
    return [report.baseline, *[m for m in report.candidates if m != report.baseline]]


def load_eval_sets(evals_dir: Path, sites: Sequence[CallSite]) -> dict[str, EvalSet]:
    """Eval set per site id. Sites without a readable eval file are left out."""
    out: dict[str, EvalSet] = {}
    for site in sites:
        path = evals_dir / f"{slug_for(site.id)}{EVAL_SUFFIX}"
        if not path.exists():
            continue
        try:
            out[site.id] = load_eval_set(path)
        except EvalError:
            continue
    return out


def load_rows(results_dir: Path, sites: Sequence[CallSite], models: Sequence[str]) -> Rows:
    """Result rows per site and model. Missing result files give empty dicts."""
    out: Rows = {}
    for site in sites:
        per_model: dict[str, dict[str, ResultRow]] = {}
        for model in models:
            path = results_path(results_dir, site.id, model)
            per_model[model] = load_results(path) if path.exists() else {}
        out[site.id] = per_model
    return out


def judge_models(rows: Rows) -> list[str]:
    """Judge models actually recorded in the results (config may differ)."""
    found = {
        row.judge_model
        for per_model in rows.values()
        for model_rows in per_model.values()
        for row in model_rows.values()
        if row.judge_model
    }
    return sorted(found)


def mean_quality(decisions: Sequence[Decision]) -> tuple[float | None, float | None]:
    """Mean pass rate across sites: baseline model vs the model chosen for each site."""
    before: list[float] = []
    after: list[float] = []
    for decision in decisions:
        base = decision.stats.get(decision.baseline)
        chosen = decision.stats.get(decision.model)
        if base is None or chosen is None:
            continue
        if base.pass_rate is None or chosen.pass_rate is None:
            continue
        before.append(base.pass_rate)
        after.append(chosen.pass_rate)
    if not before:
        return None, None
    return sum(before) / len(before), sum(after) / len(after)


def summary_payload(report: Report, config: Config, rows: Rows, *, project: str) -> dict[str, Any]:
    costs = report.costs
    downgrades = [
        {"site_id": d.site_id, "from": d.baseline, "to": d.model}
        for d in report.decisions
        if d.downgraded
    ]
    before_q, after_q = mean_quality(report.decisions)
    delta_q = None if before_q is None or after_q is None else after_q - before_q
    pricing = []
    for model in _models(report):
        price = config.pricing.get(model)
        pricing.append(
            {
                "model": model,
                "input_per_mtok": price.input_per_mtok if price else None,
                "output_per_mtok": price.output_per_mtok if price else None,
                "tier": price.tier if price else None,
            }
        )
    return {
        "project": project,
        "tool_version": __version__,
        "baseline": report.baseline,
        "candidates": list(report.candidates),
        "judge_models": judge_models(rows),
        "threshold": report.threshold,
        "min_pass_rate": report.min_pass_rate,
        "calls_per_day": config.volume.default_per_day,
        "days_per_month": DAYS_PER_MONTH,
        "sites_total": len(report.decisions),
        "sites_downgraded": len(downgrades),
        "downgrades": downgrades,
        "missing_evals": list(report.missing_evals),
        "cost": {
            "before_monthly": _round(costs.before_monthly, 2),
            "after_monthly": _round(costs.after_monthly, 2),
            "savings": _round(costs.savings, 2),
            "savings_pct": _round(costs.savings_pct, 4),
        },
        "quality": {
            "baseline_pass_rate": _round(before_q, 4),
            "after_pass_rate": _round(after_q, 4),
            "delta": _round(delta_q, 4),
        },
        "pricing": pricing,
        "disclaimer": DISCLAIMER,
    }


def _messages(site: CallSite) -> list[dict[str, Any]] | None:
    if not site.messages:
        return None
    return [{"role": m.role, "content": m.content, "resolved": m.resolved} for m in site.messages]


def _decision_entry(decision: Decision | None) -> dict[str, Any] | None:
    if decision is None:
        return None
    return {
        "action": decision.action,
        "model": decision.model,
        "baseline": decision.baseline,
        "reason": decision.reason,
        "baseline_pass_rate": _round(decision.baseline_pass_rate, 4),
        "baseline_below_floor": decision.baseline_below_floor,
    }


def _model_entry(model: str, decision: Decision, config: Config) -> dict[str, Any]:
    stats = decision.stats.get(model)
    check = next((c for c in decision.checks if c.model == model), None)
    price = config.pricing.get(model)
    entry: dict[str, Any] = {
        "model": model,
        "tier": price.tier if price else None,
        "is_baseline": model == decision.baseline,
        "chosen": model == decision.model,
        "cases": None,
        "scored": None,
        "passed": None,
        "errors": None,
        "pass_rate": None,
        "mean_score": None,
        "avg_judge_score": None,
        "avg_prompt_tokens": None,
        "avg_completion_tokens": None,
        "avg_latency_s": None,
        "cost_per_call": None,
        "check": None,
    }
    if stats is not None:
        s = stats.summary
        entry.update(
            {
                "cases": s.cases,
                "scored": s.scored,
                "passed": s.passed,
                "errors": s.errors,
                "pass_rate": _round(stats.pass_rate, 4),
                "mean_score": _round(s.mean_score, 4),
                "avg_judge_score": _round(stats.avg_judge_score, 2),
                "avg_prompt_tokens": _round(s.avg_prompt_tokens, 1),
                "avg_completion_tokens": _round(s.avg_completion_tokens, 1),
                "avg_latency_s": _round(s.avg_latency_s, 3),
                "cost_per_call": _round(stats.cost_per_call(price), 8) if price else None,
            }
        )
    if check is not None:
        entry["check"] = {
            "ratio": _round(check.ratio, 4),
            "passed": check.passed,
            "reason": check.reason,
        }
    return entry


def _cost_entry(cost: SiteCost | None) -> dict[str, Any] | None:
    if cost is None:
        return None
    return {
        "before_model": cost.before_model,
        "after_model": cost.after_model,
        "calls_per_day": cost.calls_per_day,
        "before_monthly": _round(cost.before_monthly, 2),
        "after_monthly": _round(cost.after_monthly, 2),
        "savings": _round(cost.savings, 2),
        "savings_pct": _round(cost.savings_pct, 4),
    }


def callsites_payload(
    report: Report, config: Config, eval_sets: Mapping[str, EvalSet]
) -> list[dict[str, Any]]:
    decisions = {d.site_id: d for d in report.decisions}
    costs = {c.site_id: c for c in report.costs.sites}
    models = _models(report)
    out: list[dict[str, Any]] = []
    for site in report.sites:
        decision = decisions.get(site.id)
        eval_set = eval_sets.get(site.id)
        out.append(
            {
                "id": site.id,
                "slug": slug_for(site.id),
                "file": site.file,
                "line": site.line,
                "function": site.function,
                "api": site.api,
                "is_async": site.is_async,
                "found_by": site.found_by,
                "via": site.via,
                "purpose": site.purpose,
                "output_contract": site.output_contract,
                "difficulty": site.difficulty,
                "grading": site.grading,
                "output_format": site.output_format,
                "temperature": site.temperature,
                "max_tokens": site.max_tokens,
                "model_in_code": site.model.value,
                "messages": _messages(site),
                "eval_cases": len(eval_set.cases) if eval_set else 0,
                "decision": _decision_entry(decision),
                "models": ([_model_entry(m, decision, config) for m in models] if decision else []),
                "cost": _cost_entry(costs.get(site.id)),
            }
        )
    return out


def _site_brief(site: CallSite) -> dict[str, Any]:
    return {
        "id": site.id,
        "found_by": site.found_by,
        "via": site.via,
        "model": site.model.value,
        "model_source": site.model.source,
        "prompt_resolved": site.prompt_resolved,
    }


def audit_payload(
    audit: ScanResult, ast: ScanResult | None = None, ast_after: ScanResult | None = None
) -> dict[str, Any]:
    changes: list[dict[str, str]] = []
    if ast is not None:
        comparison = compare_scans(ast, audit)
        changes = [{"id": c.id, "kind": c.kind, "detail": c.detail} for c in comparison.changes]
    return {
        "labels": dict(METRIC_LABELS),
        "ast": metrics_for(ast) if ast is not None else None,
        "audit": metrics_for(audit),
        "ast_after": metrics_for(ast_after) if ast_after is not None else None,
        "changes": changes,
        "ast_sites": [_site_brief(s) for s in ast.call_sites] if ast is not None else [],
        "audit_sites": [_site_brief(s) for s in audit.call_sites],
    }


def _output_entry(row: ResultRow | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "output": row.output,
        "passed": row.passed,
        "score": _round(row.score, 4),
        "judge_score": row.judge_score,
        "detail": row.detail,
        "error": row.error,
    }


def _passed(model_rows: Mapping[str, ResultRow], case_id: str) -> bool | None:
    row = model_rows.get(case_id)
    return None if row is None else row.passed


def _example(
    eval_set: EvalSet,
    case: EvalCase,
    site_rows: Mapping[str, Mapping[str, ResultRow]],
    models: Sequence[str],
) -> dict[str, Any]:
    return {
        "id": case.id,
        "inputs": eval_set.inputs_for(case),
        "expected": case.expected,
        "notes": case.notes,
        "outputs": {m: _output_entry(site_rows.get(m, {}).get(case.id)) for m in models},
    }


def evals_payload(
    report: Report, eval_sets: Mapping[str, EvalSet], rows: Rows, *, examples: int
) -> list[dict[str, Any]]:
    models = _models(report)
    out: list[dict[str, Any]] = []
    for site in report.sites:
        eval_set = eval_sets.get(site.id)
        if eval_set is None:
            continue
        site_rows = rows.get(site.id, {})
        out.append(
            {
                "site_id": site.id,
                "slug": slug_for(site.id),
                "grading": site.grading,
                "cases": len(eval_set.cases),
                "models": models,
                "examples": [
                    _example(eval_set, case, site_rows, models)
                    for case in eval_set.cases[:examples]
                ],
                "grid": [
                    {
                        "id": case.id,
                        "passed": {m: _passed(site_rows.get(m, {}), case.id) for m in models},
                    }
                    for case in eval_set.cases
                ],
            }
        )
    return out


def build_export(
    report: Report,
    config: Config,
    *,
    audit: ScanResult,
    evals_dir: Path,
    results_dir: Path,
    ast: ScanResult | None = None,
    ast_after: ScanResult | None = None,
    project: str = "project",
    examples: int = DEFAULT_EXAMPLES,
) -> dict[str, Any]:
    """All JSON payloads, keyed by output file name."""
    if examples < 0:
        raise ValueError("examples must be >= 0")
    sites = list(report.sites)
    eval_sets = load_eval_sets(evals_dir, sites)
    rows = load_rows(results_dir, sites, _models(report))
    return {
        SUMMARY_FILE: summary_payload(report, config, rows, project=project),
        CALLSITES_FILE: callsites_payload(report, config, eval_sets),
        AUDIT_FILE: audit_payload(audit, ast, ast_after),
        EVALS_FILE: evals_payload(report, eval_sets, rows, examples=examples),
    }


def to_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def write_export(out_dir: Path, payloads: Mapping[str, Any], report_md: str) -> list[Path]:
    """Write every payload plus report.md into out_dir. Returns the written paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, payload in payloads.items():
        path = out_dir / name
        path.write_text(to_json(payload), encoding="utf-8")
        written.append(path)
    report_path = out_dir / REPORT_FILE
    report_path.write_text(report_md, encoding="utf-8")
    written.append(report_path)
    return written
