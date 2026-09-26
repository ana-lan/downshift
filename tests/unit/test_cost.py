"""Tests for cost.py: hand-computed monthly costs, totals and self-host break-even."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from downshift.config import ModelPrice, VolumeConfig, load_config
from downshift.cost import (
    HOURS_PER_MONTH,
    SelfHost,
    break_even,
    cost_summary,
    cost_summary_for,
    gpus_needed,
    site_cost,
)
from downshift.decide import Decision, ModelStats, decide_site, load_site_stats
from downshift.evals import EVAL_SUFFIX, load_eval_set, slug_for
from downshift.runner import RunSummary
from downshift.schema import ScanResult

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "supportdesk"

PRICES = {
    "big": ModelPrice(2.50, 10.00),
    "small": ModelPrice(0.10, 0.40),
}


def mk(model: str, passed: int, *, pt: float = 100.0, ct: float = 10.0) -> ModelStats:
    summary = RunSummary(
        site_id="x",
        model=model,
        cases=20,
        scored=20,
        passed=passed,
        errors=0,
        new=0,
        mean_score=passed / 20,
        avg_latency_s=0.1,
        avg_prompt_tokens=pt,
        avg_completion_tokens=ct,
    )
    return ModelStats(summary=summary)


def decision(site_id: str, small_passed: int, *, small_pt: float = 100.0) -> Decision:
    stats = {"big": mk("big", 20), "small": mk("small", small_passed, pt=small_pt)}
    return decide_site(
        site_id, stats, baseline="big", candidates=["small"], prices=PRICES, threshold=0.95
    )


# --- one site ----------------------------------------------------------------


def test_downgraded_site_hand_computed() -> None:
    c = site_cost(decision("a.py::f", 20), PRICES, calls_per_day=1000)
    # big: (100 x 2.50 + 10 x 10.00) / 1e6 = 0.00035 per call; 30,000 calls = $10.50
    # small: (100 x 0.10 + 10 x 0.40) / 1e6 = 0.000014 per call; 30,000 calls = $0.42
    assert c.after_model == "small"
    assert c.calls_per_month == 30_000
    assert c.before_monthly == pytest.approx(10.50)
    assert c.after_monthly == pytest.approx(0.42)
    assert c.savings == pytest.approx(10.08)
    assert c.savings_pct == pytest.approx(0.96)
    assert c.known


def test_kept_site_has_no_savings() -> None:
    c = site_cost(decision("a.py::f", 10), PRICES, calls_per_day=1000)
    assert c.after_model == "big"
    assert c.after_monthly == c.before_monthly
    assert c.savings == 0


def test_after_uses_the_candidates_own_tokens() -> None:
    c = site_cost(decision("a.py::f", 20, small_pt=200.0), PRICES, calls_per_day=1000)
    # small: (200 x 0.10 + 10 x 0.40) / 1e6 = 0.000024 x 30,000 = $0.72
    assert c.after_monthly == pytest.approx(0.72)


def test_custom_days() -> None:
    c = site_cost(decision("a.py::f", 20), PRICES, calls_per_day=1000, days=1)
    assert c.before_monthly == pytest.approx(0.35)


def test_unknown_cost_without_baseline_stats() -> None:
    d = decide_site(
        "a.py::f", {}, baseline="big", candidates=["small"], prices=PRICES, threshold=0.95
    )
    c = site_cost(d, PRICES, calls_per_day=1000)
    assert not c.known
    assert c.before_monthly is None
    assert c.after_monthly is None
    assert c.savings is None
    assert c.savings_pct is None


def test_zero_volume_has_no_pct() -> None:
    c = site_cost(decision("a.py::f", 20), PRICES, calls_per_day=0)
    assert c.before_monthly == 0
    assert c.savings_pct is None


@pytest.mark.parametrize(("calls", "days"), [(-1, 30), (10, 0)])
def test_bad_inputs_raise(calls: int, days: int) -> None:
    with pytest.raises(ValueError):
        site_cost(decision("a.py::f", 20), PRICES, calls_per_day=calls, days=days)


def test_missing_price_raises() -> None:
    with pytest.raises(ValueError, match="no pricing for model 'big'"):
        site_cost(decision("a.py::f", 20), {"small": PRICES["small"]}, calls_per_day=10)


# --- totals ------------------------------------------------------------------


def test_summary_totals_and_per_site_volume() -> None:
    volume = VolumeConfig(default_per_day=1000, per_call_site={"b.py::g": 2000})
    s = cost_summary([decision("a.py::f", 20), decision("b.py::g", 10)], PRICES, volume)
    # a: 10.50 -> 0.42; b (kept, 60,000 calls): 21.00 -> 21.00
    assert s.before_monthly == pytest.approx(31.50)
    assert s.after_monthly == pytest.approx(21.42)
    assert s.savings == pytest.approx(10.08)
    assert s.savings_pct == pytest.approx(10.08 / 31.50)
    assert s.unknown == ()


def test_summary_skips_unknown_sites() -> None:
    empty = decide_site(
        "c.py::h", {}, baseline="big", candidates=["small"], prices=PRICES, threshold=0.95
    )
    s = cost_summary([decision("a.py::f", 20), empty], PRICES, VolumeConfig(1000))
    assert s.unknown == ("c.py::h",)
    assert s.before_monthly == pytest.approx(10.50)


def test_empty_summary() -> None:
    s = cost_summary([], PRICES, VolumeConfig(1000))
    assert s.before_monthly == 0
    assert s.savings_pct is None


# --- self-host ---------------------------------------------------------------


def test_self_host_hand_computed() -> None:
    host = SelfHost(gpu_hourly_usd=1.0, tokens_per_second=1000, utilization=0.5)
    assert host.monthly_cost_per_gpu == pytest.approx(HOURS_PER_MONTH)  # $730
    # 1000 tok/s x 0.5 x 730 h x 3600 s = 1,314,000,000 tokens
    assert host.tokens_per_month_per_gpu == pytest.approx(1_314_000_000)

    be = break_even(api_cost_per_call=0.00035, tokens_per_call=110, host=host)
    # 730 / (30 x 0.00035) = 69,523.8 calls/day; capacity 1.314e9 / (110 x 30) = 398,181.8
    assert be.calls_per_day == pytest.approx(69_523.81, rel=1e-6)
    assert be.capacity_calls_per_day == pytest.approx(398_181.82, rel=1e-6)
    assert be.self_host_can_win


def test_self_host_cannot_win_when_api_is_cheap() -> None:
    host = SelfHost(gpu_hourly_usd=1.0, tokens_per_second=1000, utilization=0.5)
    be = break_even(api_cost_per_call=0.000014, tokens_per_call=110, host=host)
    assert not be.self_host_can_win


def test_free_api_never_breaks_even() -> None:
    host = SelfHost(gpu_hourly_usd=1.0, tokens_per_second=1000)
    assert math.isinf(break_even(0.0, 100, host).calls_per_day)


def test_gpus_needed() -> None:
    host = SelfHost(gpu_hourly_usd=1.0, tokens_per_second=1000, utilization=0.5)
    assert gpus_needed(0, host) == 1
    assert gpus_needed(1_314_000_000, host) == 1
    assert gpus_needed(1_314_000_001, host) == 2
    with pytest.raises(ValueError):
        gpus_needed(-1, host)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"gpu_hourly_usd": 0, "tokens_per_second": 10},
        {"gpu_hourly_usd": 1, "tokens_per_second": 0},
        {"gpu_hourly_usd": 1, "tokens_per_second": 10, "utilization": 0},
        {"gpu_hourly_usd": 1, "tokens_per_second": 10, "utilization": 1.5},
    ],
)
def test_bad_self_host_raises(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        SelfHost(**kwargs)


@pytest.mark.parametrize(("tokens", "days"), [(0, 30), (100, 0)])
def test_bad_break_even_inputs(tokens: float, days: int) -> None:
    host = SelfHost(gpu_hourly_usd=1.0, tokens_per_second=1000)
    with pytest.raises(ValueError):
        break_even(0.001, tokens, host, days=days)


# --- real SupportDesk ----------------------------------------------------------


def test_real_supportdesk_cost() -> None:
    cfg = load_config(EXAMPLE / "downshift.yaml")
    scan = ScanResult.load(EXAMPLE / "downshift.audit.json")
    decisions = []
    for site in scan.call_sites:
        eval_set = load_eval_set(EXAMPLE / "evals" / f"{slug_for(site.id)}{EVAL_SUFFIX}")
        stats = load_site_stats(site.id, eval_set, cfg.models.all_models, EXAMPLE / "results")
        decisions.append(
            decide_site(
                site.id,
                stats,
                baseline=cfg.models.baseline,
                candidates=cfg.models.candidates,
                prices=cfg.pricing,
                threshold=cfg.quality_threshold,
                min_pass_rate=cfg.min_pass_rate,
            )
        )
    s = cost_summary_for(decisions, cfg)
    assert s.unknown == ()
    assert len(s.sites) == 8
    assert all(c.calls_per_day == 20_000 for c in s.sites)  # stale llm.py::ask entry gone
    saving = [c.site_id for c in s.sites if (c.savings or 0) > 0]
    assert saving == ["supportdesk/misc_utils.py::lang_of"]
    assert 0 < s.savings < s.before_monthly
