"""Assemble eval results into a Report and render it as Markdown.

`build_report` reads eval sets and result files for every call site in a ScanResult,
calls decide_site and cost_summary, and returns a Report.
`render_markdown` turns a Report into a deterministic Markdown string (no dates,
no version numbers, no absolute paths).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from downshift.config import Config
from downshift.cost import CostSummary, cost_summary
from downshift.decide import (
    DOWNGRADE,
    CandidateCheck,
    Decision,
    ModelStats,
    decide_site,
    load_site_stats,
)
from downshift.evals import EVAL_SUFFIX, EvalError, load_eval_set, slug_for
from downshift.schema import CallSite, ScanResult

NEAR_MISS_MARGIN = 0.05


class ReportError(Exception):
    """Raised when an eval file cannot be loaded for a call site."""


@dataclass(frozen=True)
class Report:
    """All data needed to render the report."""

    sites: tuple[CallSite, ...]
    decisions: tuple[Decision, ...]
    costs: CostSummary
    missing_evals: tuple[str, ...]  # site ids with no eval file, sorted
    baseline: str
    candidates: tuple[str, ...]
    threshold: float
    min_pass_rate: float

    @property
    def downgraded(self) -> tuple[Decision, ...]:
        return tuple(d for d in self.decisions if d.action == DOWNGRADE)

    @property
    def below_floor(self) -> tuple[Decision, ...]:
        return tuple(d for d in self.decisions if d.baseline_below_floor)

    @property
    def near_misses(self) -> tuple[tuple[str, CandidateCheck], ...]:
        """(site_id, CandidateCheck) for failed checks near the threshold."""
        result: list[tuple[str, CandidateCheck]] = []
        low = self.threshold - NEAR_MISS_MARGIN
        for decision in self.decisions:
            for check in decision.checks:
                if check.passed:
                    continue
                if check.ratio is None:
                    continue
                if not (low <= check.ratio < self.threshold):
                    continue
                if check.pass_rate is None or check.pass_rate < self.min_pass_rate:
                    continue
                result.append((decision.site_id, check))
        return tuple(result)

    @property
    def missing_data(self) -> tuple[Decision, ...]:
        """Decisions whose baseline stats are missing or incomplete."""
        result: list[Decision] = []
        for decision in self.decisions:
            base = decision.stats.get(decision.baseline)
            if base is None or not base.complete:
                result.append(decision)
        return tuple(result)


def build_report(
    scan: ScanResult,
    config: Config,
    evals_dir: Path,
    results_dir: Path,
    *,
    threshold: float | None = None,
    min_pass_rate: float | None = None,
) -> Report:
    """Assemble a Report from disk.

    For each call site in the scan (sorted by id): if the eval file is missing
    the site goes into missing_evals; if the file has problems, ReportError is raised.
    """
    eff_threshold = threshold if threshold is not None else config.quality_threshold
    eff_min_pass_rate = min_pass_rate if min_pass_rate is not None else config.min_pass_rate

    sites_sorted = sorted(scan.call_sites, key=lambda s: s.id)

    decided_sites: list[CallSite] = []
    decisions: list[Decision] = []
    missing_evals: list[str] = []

    for site in sites_sorted:
        eval_path = evals_dir / f"{slug_for(site.id)}{EVAL_SUFFIX}"
        if not eval_path.is_file():
            missing_evals.append(site.id)
            continue

        try:
            eval_set = load_eval_set(eval_path)
        except EvalError as exc:
            raise ReportError(f"{eval_path}: {exc}") from exc
        if eval_set.problems:
            raise ReportError(f"{eval_path}: {eval_set.problems[0]}")

        stats = load_site_stats(site.id, eval_set, config.models.all_models, results_dir)
        decision = decide_site(
            site.id,
            stats,
            baseline=config.models.baseline,
            candidates=list(config.models.candidates),
            prices=config.pricing,
            threshold=eff_threshold,
            min_pass_rate=eff_min_pass_rate,
        )
        decided_sites.append(site)
        decisions.append(decision)

    costs = cost_summary(decisions, config.pricing, config.volume)

    return Report(
        sites=tuple(decided_sites),
        decisions=tuple(decisions),
        costs=costs,
        missing_evals=tuple(sorted(missing_evals)),
        baseline=config.models.baseline,
        candidates=config.models.candidates,
        threshold=eff_threshold,
        min_pass_rate=eff_min_pass_rate,
    )


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _fmt_money(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"${x:,.2f}"


def _fmt_savings_pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{x:.1%}"


def _fmt_pass_rate(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{x:.0%}"


def render_markdown(report: Report) -> str:
    """Render a Report as a deterministic Markdown string ending with one newline."""
    lines: list[str] = []

    # ------------------------------------------------------------------ header
    lines.append("# Downshift report")
    lines.append("")
    lines.append(
        "> Costs are projections: measured tokens per call x illustrative prices x assumed volume"
    )
    lines.append("> from the config. They are not a bill.")
    lines.append("")

    # ------------------------------------------------------------------ summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| | Monthly cost |")
    lines.append("|---|---:|")

    costs = report.costs
    before = _fmt_money(costs.before_monthly if costs.sites else None)
    after = _fmt_money(costs.after_monthly if costs.sites else None)

    # Only show a number when we actually have known costs
    known_sites = [s for s in costs.sites if s.known]
    if known_sites:
        before = _fmt_money(costs.before_monthly)
        after = _fmt_money(costs.after_monthly)
    else:
        before = "n/a"
        after = "n/a"

    lines.append(f"| Before (all on `{report.baseline}`) | {before} |")
    lines.append(f"| After | {after} |")

    savings_str = _fmt_money(costs.savings if known_sites else None)
    savings_pct_str = _fmt_savings_pct(costs.savings_pct)
    lines.append(f"| Savings | {savings_str} ({savings_pct_str}) |")
    lines.append("")

    total_decided = len(report.decisions)
    n_down = len(report.downgraded)
    lines.append(f"Downgraded **{n_down} of {total_decided}** call sites.")
    lines.append("")

    rule = (
        f"Rule: a cheaper model must keep at least {report.threshold:.0%} of the baseline pass rate"
    )
    if report.min_pass_rate > 0:
        rule += (
            f" and pass at least {report.min_pass_rate:.0%} of cases on its own."
            " Decisions use pass rate, not mean score."
        )
    else:
        rule += ". Decisions use pass rate, not mean score."
    lines.append(rule)
    lines.append("")

    if costs.unknown:
        n_unknown = len(costs.unknown)
        lines.append(
            f"Totals exclude {n_unknown} call sites with unknown cost (see Needs attention)."
        )
        lines.append("")

    # ------------------------------------------------------------------ decisions table
    lines.append("## Decisions")
    lines.append("")
    lines.append(
        "| Call site | Grading | Decision | Model | Pass rate | Before / month | After / month |"
    )
    lines.append("|---|---|---|---|---|---:|---:|")

    for site, decision in zip(report.sites, report.decisions, strict=True):
        grading = site.grading or "-"
        action = decision.action
        model = f"`{decision.model}`"

        base_rate = decision.baseline_pass_rate
        if action == DOWNGRADE:
            # chosen model pass rate
            chosen_stats = decision.stats.get(decision.model)
            chosen_rate = chosen_stats.pass_rate if chosen_stats is not None else None
            pass_rate_cell = f"{_fmt_pass_rate(base_rate)} -> {_fmt_pass_rate(chosen_rate)}"
        else:
            pass_rate_cell = _fmt_pass_rate(base_rate)

        site_cost_obj = next((c for c in costs.sites if c.site_id == decision.site_id), None)
        before_m = _fmt_money(site_cost_obj.before_monthly if site_cost_obj else None)
        after_m = _fmt_money(site_cost_obj.after_monthly if site_cost_obj else None)

        lines.append(
            f"| `{site.id}` | {grading} | {action} | {model}"
            f" | {pass_rate_cell} | {before_m} | {after_m} |"
        )

    lines.append("")

    # ------------------------------------------------------------------ quality table
    all_models = (report.baseline, *report.candidates)
    lines.append("## Quality per model")
    lines.append("")
    model_headers = " | ".join(f"`{m}`" for m in all_models)
    lines.append(f"| Call site | {model_headers} |")
    sep_cols = " | ".join("---" for _ in all_models)
    lines.append(f"|---|{sep_cols}|")

    has_judge = False
    for site in report.sites:
        if site.grading == "judge":
            has_judge = True
            break

    for site, decision in zip(report.sites, report.decisions, strict=True):
        cells: list[str] = []
        for model in all_models:
            ms: ModelStats | None = decision.stats.get(model)
            if ms is None or ms.summary.scored == 0:
                cell = "n/a"
            else:
                s = ms.summary
                cell = f"{s.passed}/{s.scored} ({_fmt_pass_rate(ms.pass_rate)})"
                if ms.avg_judge_score is not None:
                    cell += f", judge {ms.avg_judge_score:.1f}/5"
                if s.errors > 0:
                    cell += f", {s.errors} errors"
            # Bold the chosen model's cell
            chosen = decision.model
            if model == chosen:
                cell = f"**{cell}**"
            cells.append(cell)

        row = " | ".join(cells)
        lines.append(f"| `{site.id}` | {row} |")

    lines.append("")
    if has_judge:
        lines.append(
            "Judge-graded cases pass at 4/5 or higher; judge scores are averages on a 1 to 5 scale."
        )
        lines.append("")

    # ------------------------------------------------------------------ needs attention
    lines.append("## Needs attention")
    lines.append("")

    below_floor = report.below_floor
    near_misses = report.near_misses
    missing_data_decisions = report.missing_data
    missing_evals = report.missing_evals

    has_floor_section = report.min_pass_rate > 0 and bool(below_floor)
    has_near_miss = bool(near_misses)
    has_missing = bool(missing_evals) or bool(missing_data_decisions)

    if not has_floor_section and not has_near_miss and not has_missing:
        lines.append("Nothing needs attention.")
        lines.append("")
    else:
        if has_floor_section:
            lines.append("### Baseline below the floor")
            lines.append("")
            for decision in below_floor:
                base_rate = decision.baseline_pass_rate
                lines.append(
                    f"- `{decision.site_id}`: baseline passes"
                    f" {_fmt_pass_rate(base_rate)} of cases,"
                    f" below the {_fmt_pass_rate(report.min_pass_rate)} floor."
                    "  Improve the prompt or model before downgrading."
                )
            lines.append("")

        if has_near_miss:
            lines.append("### Near misses")
            lines.append("")
            for site_id, check in near_misses:
                lines.append(
                    f"- `{site_id}`: `{check.model}` keeps"
                    f" {_fmt_pass_rate(check.ratio)} of the baseline pass"
                    f" rate (needs {_fmt_pass_rate(report.threshold)})."
                )
            lines.append("")

        if has_missing:
            lines.append("### Missing data")
            lines.append("")
            for sid in missing_evals:
                lines.append(f"- `{sid}`: no eval set, not decided.")
            for decision in missing_data_decisions:
                lines.append(f"- `{decision.site_id}`: {decision.reason}.")
            lines.append("")

    # ------------------------------------------------------------------ details
    lines.append("## Details")
    lines.append("")
    for site, decision in zip(report.sites, report.decisions, strict=True):
        action_text = (
            f"downgrade to <code>{decision.model}</code>"
            if decision.action == DOWNGRADE
            else f"keep <code>{decision.model}</code>"
        )
        lines.append("<details>")
        lines.append(f"<summary><code>{site.id}</code>: {action_text}</summary>")
        lines.append("")
        lines.append(f"- Decision: {decision.reason}")
        for check in decision.checks:
            lines.append(f"- `{check.model}`: {check.reason}")
        lines.append("")
        lines.append("</details>")

    return "\n".join(lines) + "\n"
