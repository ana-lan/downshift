"""Downgrade decisions: the cheapest model that keeps enough of the baseline's quality.

Decisions use pass rate (share of cases fully right), never mean score. A model can get
most JSON fields right and still fail most cases.

A candidate qualifies when all of these hold:
- its results are complete (every case scored, no error rows),
- pass rate / baseline pass rate >= threshold,
- pass rate >= min_pass_rate (absolute floor, 0 = off),
- it costs less per call than the baseline (priced with its own measured tokens).
The cheapest qualifying candidate wins; ties go to the higher pass rate, then list order.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from downshift.config import ModelPrice
from downshift.evals import EvalSet
from downshift.runner import ResultRow, RunSummary, load_results, results_path, summarize_rows

KEEP = "keep"
DOWNGRADE = "downgrade"
EPSILON = 1e-9  # 18/22 vs 20/22 must count as exactly 0.90


def call_cost(price: ModelPrice, prompt_tokens: float, completion_tokens: float) -> float:
    """USD for one call with these (average) token counts."""
    total = prompt_tokens * price.input_per_mtok + completion_tokens * price.output_per_mtok
    return total / 1_000_000


@dataclass(frozen=True)
class ModelStats:
    """Results of one model on one call site."""

    summary: RunSummary
    avg_judge_score: float | None = None

    @property
    def model(self) -> str:
        return self.summary.model

    @property
    def pass_rate(self) -> float | None:
        return self.summary.pass_rate

    @property
    def complete(self) -> bool:
        s = self.summary
        return s.cases > 0 and s.errors == 0 and s.scored == s.cases

    def cost_per_call(self, price: ModelPrice) -> float | None:
        s = self.summary
        if s.avg_prompt_tokens is None or s.avg_completion_tokens is None:
            return None
        return call_cost(price, s.avg_prompt_tokens, s.avg_completion_tokens)


def stats_for(
    site_id: str, model: str, case_ids: Sequence[str], rows: Mapping[str, ResultRow]
) -> ModelStats:
    """Stats for these case ids. Avg judge score counts only scored rows that have one."""
    summary = summarize_rows(site_id, model, case_ids, rows)
    judged = [
        float(rows[c].judge_score)  # type: ignore[arg-type]
        for c in case_ids
        if c in rows and rows[c].ok and rows[c].judge_score is not None
    ]
    avg = sum(judged) / len(judged) if judged else None
    return ModelStats(summary=summary, avg_judge_score=avg)


def load_site_stats(
    site_id: str, eval_set: EvalSet, models: Iterable[str], results_dir: Path
) -> dict[str, ModelStats]:
    """Stats per model for one site, from results files (last row per case wins)."""
    case_ids = [case.id for case in eval_set.cases]
    out: dict[str, ModelStats] = {}
    for model in models:
        rows = load_results(results_path(results_dir, site_id, model))
        out[model] = stats_for(site_id, model, case_ids, rows)
    return out


@dataclass(frozen=True)
class CandidateCheck:
    """Why one candidate did or did not qualify."""

    model: str
    pass_rate: float | None
    ratio: float | None
    cost_per_call: float | None
    passed: bool
    reason: str


@dataclass(frozen=True)
class Decision:
    site_id: str
    action: str  # KEEP or DOWNGRADE
    model: str  # the model to use after the decision
    baseline: str
    reason: str
    baseline_pass_rate: float | None
    baseline_below_floor: bool
    checks: tuple[CandidateCheck, ...]
    stats: Mapping[str, ModelStats]

    @property
    def downgraded(self) -> bool:
        return self.action == DOWNGRADE


def _price(prices: Mapping[str, ModelPrice], model: str) -> ModelPrice:
    try:
        return prices[model]
    except KeyError:
        raise ValueError(f"no pricing for model {model!r}") from None


def _incomplete(s: RunSummary) -> str:
    return f"incomplete results ({s.errors} errors, {s.scored}/{s.cases} scored)"


def _check(
    model: str,
    s: ModelStats | None,
    *,
    base_rate: float,
    base_cost: float | None,
    prices: Mapping[str, ModelPrice],
    threshold: float,
    min_pass_rate: float,
) -> CandidateCheck:
    if s is None or s.summary.scored == 0:
        return CandidateCheck(model, None, None, None, False, "no results")
    rate = s.pass_rate or 0.0
    ratio = rate / base_rate
    cost = s.cost_per_call(_price(prices, model))

    def fail(reason: str) -> CandidateCheck:
        return CandidateCheck(model, rate, ratio, cost, False, reason)

    if not s.complete:
        return fail(_incomplete(s.summary))
    if ratio < threshold - EPSILON:
        return fail(f"keeps {ratio:.0%} of baseline quality, needs {threshold:.0%}")
    if rate < min_pass_rate - EPSILON:
        return fail(f"pass rate {rate:.0%} is below the floor {min_pass_rate:.0%}")
    if cost is None or base_cost is None or cost >= base_cost:
        return fail("not cheaper than the baseline")
    return CandidateCheck(
        model, rate, ratio, cost, True, f"keeps {ratio:.0%} of baseline quality and costs less"
    )


def decide_site(
    site_id: str,
    stats: Mapping[str, ModelStats],
    *,
    baseline: str,
    candidates: Sequence[str],
    prices: Mapping[str, ModelPrice],
    threshold: float,
    min_pass_rate: float = 0.0,
) -> Decision:
    """Keep the baseline or downgrade to the cheapest qualifying candidate."""
    if not 0.0 < threshold <= 1.0:
        raise ValueError(f"threshold must be in (0, 1], got {threshold}")
    if not 0.0 <= min_pass_rate <= 1.0:
        raise ValueError(f"min_pass_rate must be in [0, 1], got {min_pass_rate}")

    def keep(
        reason: str,
        base_rate: float | None = None,
        below: bool = False,
        checks: tuple[CandidateCheck, ...] = (),
    ) -> Decision:
        return Decision(site_id, KEEP, baseline, baseline, reason, base_rate, below, checks, stats)

    base = stats.get(baseline)
    if base is None or base.summary.scored == 0:
        return keep("no baseline results")
    if not base.complete:
        return keep(f"baseline has {_incomplete(base.summary)}", base.pass_rate)
    base_rate = base.pass_rate or 0.0
    below = base_rate < min_pass_rate - EPSILON
    if base_rate == 0.0:
        return keep("baseline passes no cases; nothing to compare against", 0.0, below)

    base_cost = base.cost_per_call(_price(prices, baseline))
    checks = tuple(
        _check(
            model,
            stats.get(model),
            base_rate=base_rate,
            base_cost=base_cost,
            prices=prices,
            threshold=threshold,
            min_pass_rate=min_pass_rate,
        )
        for model in candidates
        if model != baseline
    )
    order = {c.model: i for i, c in enumerate(checks)}
    passing = [c for c in checks if c.passed]
    if not passing:
        reason = "no candidate models" if not checks else "no cheaper model passed the checks"
        return keep(reason, base_rate, below, checks)

    best = min(
        passing,
        key=lambda c: (c.cost_per_call or 0.0, -(c.pass_rate or 0.0), order[c.model]),
    )
    return Decision(
        site_id, DOWNGRADE, best.model, baseline, best.reason, base_rate, below, checks, stats
    )
