"""Projected monthly cost before vs after the decisions.

These are projections, not bills: measured avg tokens per call (from the eval runs,
per model) x configured prices x configured calls per day x days. Judge calls are
not part of the app's cost and are never counted.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from downshift.config import Config, ModelPrice, VolumeConfig
from downshift.decide import Decision, ModelStats

DAYS_PER_MONTH = 30
HOURS_PER_MONTH = 730
SECONDS_PER_HOUR = 3600


def _per_call(
    stats: Mapping[str, ModelStats], model: str, prices: Mapping[str, ModelPrice]
) -> float | None:
    s = stats.get(model)
    if s is None:
        return None
    price = prices.get(model)
    if price is None:
        raise ValueError(f"no pricing for model {model!r}")
    return s.cost_per_call(price)


@dataclass(frozen=True)
class SiteCost:
    """Monthly cost of one call site before and after its decision."""

    site_id: str
    before_model: str
    after_model: str
    calls_per_day: int
    before_per_call: float | None
    after_per_call: float | None
    days: int = DAYS_PER_MONTH

    @property
    def calls_per_month(self) -> int:
        return self.calls_per_day * self.days

    @property
    def known(self) -> bool:
        return self.before_per_call is not None and self.after_per_call is not None

    @property
    def before_monthly(self) -> float | None:
        if self.before_per_call is None:
            return None
        return self.before_per_call * self.calls_per_month

    @property
    def after_monthly(self) -> float | None:
        if self.after_per_call is None:
            return None
        return self.after_per_call * self.calls_per_month

    @property
    def savings(self) -> float | None:
        before, after = self.before_monthly, self.after_monthly
        if before is None or after is None:
            return None
        return before - after

    @property
    def savings_pct(self) -> float | None:
        before, savings = self.before_monthly, self.savings
        if before is None or savings is None or before == 0:
            return None
        return savings / before


def site_cost(
    decision: Decision,
    prices: Mapping[str, ModelPrice],
    calls_per_day: int,
    days: int = DAYS_PER_MONTH,
) -> SiteCost:
    """Cost of one site; each model is priced with its own measured tokens."""
    if calls_per_day < 0:
        raise ValueError(f"calls_per_day must be >= 0, got {calls_per_day}")
    if days <= 0:
        raise ValueError(f"days must be > 0, got {days}")
    before = _per_call(decision.stats, decision.baseline, prices)
    if decision.model == decision.baseline:
        after = before
    else:
        after = _per_call(decision.stats, decision.model, prices)
    return SiteCost(
        site_id=decision.site_id,
        before_model=decision.baseline,
        after_model=decision.model,
        calls_per_day=calls_per_day,
        before_per_call=before,
        after_per_call=after,
        days=days,
    )


@dataclass(frozen=True)
class CostSummary:
    """Totals over the sites whose cost is known (unknown sites are listed, not guessed)."""

    sites: tuple[SiteCost, ...]

    @property
    def unknown(self) -> tuple[str, ...]:
        return tuple(s.site_id for s in self.sites if not s.known)

    @property
    def before_monthly(self) -> float:
        return sum(s.before_monthly or 0.0 for s in self.sites if s.known)

    @property
    def after_monthly(self) -> float:
        return sum(s.after_monthly or 0.0 for s in self.sites if s.known)

    @property
    def savings(self) -> float:
        return self.before_monthly - self.after_monthly

    @property
    def savings_pct(self) -> float | None:
        before = self.before_monthly
        return self.savings / before if before else None


def cost_summary(
    decisions: Iterable[Decision],
    prices: Mapping[str, ModelPrice],
    volume: VolumeConfig,
    days: int = DAYS_PER_MONTH,
) -> CostSummary:
    return CostSummary(
        tuple(site_cost(d, prices, volume.calls_per_day(d.site_id), days) for d in decisions)
    )


def cost_summary_for(decisions: Iterable[Decision], config: Config) -> CostSummary:
    """cost_summary with prices and volumes from the config."""
    return cost_summary(decisions, config.pricing, config.volume)


# --- self-host break-even (a calculation from stated assumptions) -----------------


@dataclass(frozen=True)
class SelfHost:
    """Assumptions for serving a model yourself on a rented GPU (e.g. with vLLM)."""

    gpu_hourly_usd: float
    tokens_per_second: float  # sustained throughput of one GPU, prompt + completion
    utilization: float = 0.5  # share of the month the GPU does useful work

    def __post_init__(self) -> None:
        if self.gpu_hourly_usd <= 0:
            raise ValueError("gpu_hourly_usd must be > 0")
        if self.tokens_per_second <= 0:
            raise ValueError("tokens_per_second must be > 0")
        if not 0 < self.utilization <= 1:
            raise ValueError("utilization must be in (0, 1]")

    @property
    def monthly_cost_per_gpu(self) -> float:
        return self.gpu_hourly_usd * HOURS_PER_MONTH

    @property
    def tokens_per_month_per_gpu(self) -> float:
        return self.tokens_per_second * self.utilization * HOURS_PER_MONTH * SECONDS_PER_HOUR


@dataclass(frozen=True)
class BreakEven:
    calls_per_day: float  # volume where one GPU costs the same as the API
    capacity_calls_per_day: float  # what one GPU can serve at this call size
    monthly_cost_per_gpu: float

    @property
    def self_host_can_win(self) -> bool:
        """False when one GPU saturates before it gets cheaper than the API."""
        return self.calls_per_day <= self.capacity_calls_per_day


def break_even(
    api_cost_per_call: float,
    tokens_per_call: float,
    host: SelfHost,
    days: int = DAYS_PER_MONTH,
) -> BreakEven:
    if tokens_per_call <= 0:
        raise ValueError("tokens_per_call must be > 0")
    if days <= 0:
        raise ValueError(f"days must be > 0, got {days}")
    gpu = host.monthly_cost_per_gpu
    calls = math.inf if api_cost_per_call <= 0 else gpu / (days * api_cost_per_call)
    capacity = host.tokens_per_month_per_gpu / (tokens_per_call * days)
    return BreakEven(calls_per_day=calls, capacity_calls_per_day=capacity, monthly_cost_per_gpu=gpu)


def gpus_needed(tokens_per_month: float, host: SelfHost) -> int:
    """GPUs needed for a monthly token volume (at least 1)."""
    if tokens_per_month < 0:
        raise ValueError("tokens_per_month must be >= 0")
    return max(1, math.ceil(tokens_per_month / host.tokens_per_month_per_gpu))
