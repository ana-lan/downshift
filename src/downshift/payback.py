"""Analysis cost and payback for one downshift report run.

`analysis_cost` prices the eval-model calls and judge calls that were made
to produce a downshift report. `payback` converts a one-time cost plus a
monthly savings figure into a payback period. `format_payback` renders the
period as a human-readable string.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from downshift.config import Config
from downshift.cost import HOURS_PER_MONTH
from downshift.decide import call_cost
from downshift.runner import load_results, results_path
from downshift.schema import CallSite

JUDGE_EXTRA_PROMPT_TOKENS = 150
JUDGE_COMPLETION_TOKENS = 200


@dataclass(frozen=True)
class AnalysisCost:
    """One-time cost of the evaluation run that produced a downshift report."""

    model_calls: int
    model_cost: float
    judge_calls: int
    judge_cost: float
    judge_model: str | None  # most-frequent judge model seen in results
    judge_priced_as: str | None  # model whose price was used for judge calls
    audit_cost: float = 0.0

    @property
    def total(self) -> float:
        return self.model_cost + self.judge_cost + self.audit_cost


@dataclass(frozen=True)
class Payback:
    """Payback period expressed in hours (None when monthly savings <= 0)."""

    hours: float | None


def analysis_cost(
    sites: Sequence[CallSite],
    results_dir: Path,
    config: Config,
    *,
    audit_cost: float = 0.0,
) -> AnalysisCost:
    """Compute the one-time cost of running evals for *sites*.

    For each call site × each model (baseline + candidates), the last result
    row per case is used (that is how :func:`runner.load_results` works). Rows
    with ``error`` set are skipped. Models without a price entry in
    ``config.pricing`` are also skipped silently.

    The judge model is the most frequent ``judge_model`` value seen across all
    non-error rows; ties are broken alphabetically. All judge rows are priced
    with that model's price, or the baseline model's price when the judge model
    has no price entry.

    *audit_cost* is a user-supplied one-time amount in USD (e.g. the cost of an
    AI-assisted audit session). It must be >= 0.
    """
    if audit_cost < 0:
        raise ValueError(f"audit_cost must be >= 0, got {audit_cost}")

    models = list(config.models.all_models)
    pricing = config.pricing
    baseline = config.models.baseline

    model_calls = 0
    model_cost_total = 0.0
    judge_calls = 0
    judge_cost_total = 0.0
    judge_model_counter: Counter[str] = Counter()

    # First pass: accumulate model costs and count judge models.
    # We also collect judge rows to price in a second pass once the dominant
    # judge model is known.
    judge_rows: list[tuple[int, int, str]] = []  # (prompt_tok, compl_tok, judge_model_name)

    for site in sites:
        for model in models:
            path = results_path(results_dir, site.id, model)
            if not path.is_file():
                continue
            rows = load_results(path)
            for row in rows.values():
                if row.error is not None:
                    continue
                # Model call cost
                price = pricing.get(row.model)
                if price is not None:
                    model_cost_total += call_cost(price, row.prompt_tokens, row.completion_tokens)
                    model_calls += 1
                # Judge call accounting
                if row.judge_model is not None:
                    judge_model_counter[row.judge_model] += 1
                    prompt_est = (
                        row.prompt_tokens + row.completion_tokens + JUDGE_EXTRA_PROMPT_TOKENS
                    )
                    judge_rows.append((prompt_est, JUDGE_COMPLETION_TOKENS, row.judge_model))

    # Resolve dominant judge model (most frequent; ties → alphabetically first).
    dominant_judge: str | None = None
    judge_priced_as: str | None = None
    if judge_model_counter:
        dominant_judge = min(
            judge_model_counter,
            key=lambda m: (-judge_model_counter[m], m),
        )
        # Determine which model's price to use.
        if pricing.get(dominant_judge) is not None:
            judge_priced_as = dominant_judge
        elif pricing.get(baseline) is not None:
            judge_priced_as = baseline
        # else no price available at all; judge cost stays 0

        if judge_priced_as is not None:
            judge_price = pricing[judge_priced_as]
            for prompt_est, compl_est, _jm in judge_rows:
                judge_cost_total += call_cost(judge_price, prompt_est, compl_est)
                judge_calls += 1

    return AnalysisCost(
        model_calls=model_calls,
        model_cost=model_cost_total,
        judge_calls=judge_calls,
        judge_cost=judge_cost_total,
        judge_model=dominant_judge,
        judge_priced_as=judge_priced_as,
        audit_cost=audit_cost,
    )


def payback(total_one_time: float, monthly_savings: float) -> Payback:
    """Return the payback period for a one-time cost given a monthly saving.

    Returns ``Payback(hours=None)`` when *monthly_savings* <= 0.
    """
    if monthly_savings <= 0:
        return Payback(hours=None)
    hours = total_one_time / (monthly_savings / HOURS_PER_MONTH)
    return Payback(hours=hours)


def format_payback(p: Payback) -> str:
    """Render a :class:`Payback` as a human-readable string.

    - ``None`` → ``"no payback (no projected savings)"``
    - < 1 hour → ``"N minutes"`` (ceil, minimum 1)
    - < 48 hours → ``"X.Y hours"`` (one decimal)
    - >= 48 hours → ``"N days"`` (ceil)
    """
    if p.hours is None:
        return "no payback (no projected savings)"
    if p.hours < 1.0:
        minutes = max(1, math.ceil(p.hours * 60))
        return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
    if p.hours < 48.0:
        return f"{p.hours:.1f} hours"
    days = math.ceil(p.hours / 24)
    return f"{days} days"
