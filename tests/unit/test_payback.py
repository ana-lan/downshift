"""Tests for payback.py: AnalysisCost, Payback, and the three public functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from downshift.config import Config, ModelPrice, ModelsConfig
from downshift.cost import HOURS_PER_MONTH
from downshift.decide import call_cost
from downshift.payback import (
    JUDGE_COMPLETION_TOKENS,
    JUDGE_EXTRA_PROMPT_TOKENS,
    AnalysisCost,
    Payback,
    analysis_cost,
    format_payback,
    payback,
)
from downshift.runner import ResultRow, append_row, results_path
from downshift.schema import CallSite, ModelRef

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PRICES = {
    "big": ModelPrice(2.50, 10.00),
    "mid": ModelPrice(0.15, 0.60),
}


def _config(
    baseline: str = "big",
    candidates: tuple[str, ...] = ("mid",),
    pricing: dict[str, ModelPrice] | None = None,
) -> Config:
    return Config(
        models=ModelsConfig(baseline=baseline, candidates=candidates),
        pricing=pricing if pricing is not None else PRICES,
    )


def _site(site_id: str = "app.py::classify") -> CallSite:
    return CallSite(
        id=site_id,
        file=site_id.split("::")[0],
        line=1,
        function=site_id.split("::")[-1],
        api="openai",
        model=ModelRef(value="big", source="literal", expression="big"),
    )


def _ok_row(
    case_id: str,
    model: str,
    prompt_tokens: int = 100,
    completion_tokens: int = 20,
    judge_model: str | None = None,
) -> ResultRow:
    return ResultRow(
        case_id=case_id,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        score=1.0,
        passed=True,
        judge_model=judge_model,
    )


def _err_row(case_id: str, model: str) -> ResultRow:
    return ResultRow(case_id=case_id, model=model, error="boom")


# ---------------------------------------------------------------------------
# payback()
# ---------------------------------------------------------------------------


def test_payback_zero_savings_gives_none() -> None:
    assert payback(100.0, 0.0).hours is None


def test_payback_negative_savings_gives_none() -> None:
    assert payback(100.0, -5.0).hours is None


def test_payback_formula() -> None:
    # total=730, monthly=730 → hours = 730 / (730/730) = 730
    result = payback(730.0, 730.0)
    assert result.hours == pytest.approx(HOURS_PER_MONTH)


def test_payback_formula_general() -> None:
    # total=10, monthly=20 → hours = 10 / (20/730) = 10 * 730/20 = 365
    result = payback(10.0, 20.0)
    assert result.hours == pytest.approx(10.0 / (20.0 / HOURS_PER_MONTH))


# ---------------------------------------------------------------------------
# format_payback()
# ---------------------------------------------------------------------------


def test_format_payback_none_hours() -> None:
    assert format_payback(Payback(hours=None)) == "no payback (no projected savings)"


def test_format_payback_minutes() -> None:
    # 0.2 h → ceil(0.2*60)=12 minutes
    assert format_payback(Payback(hours=0.2)) == "12 minutes"


def test_format_payback_minimum_one_minute() -> None:
    # Very short but > 0 hours → at least 1 minute
    result = format_payback(Payback(hours=0.001))
    assert result == "1 minutes"


def test_format_payback_hours_one_decimal() -> None:
    # 1.04 h < 48 h → "1.0 hours"
    assert format_payback(Payback(hours=1.04)) == "1.0 hours"


def test_format_payback_just_below_48h() -> None:
    # 47.9 h < 48 → hours format
    assert format_payback(Payback(hours=47.9)) == "47.9 hours"


def test_format_payback_days() -> None:
    # 50 h → ceil(50/24)=3 days
    assert format_payback(Payback(hours=50.0)) == "3 days"


def test_format_payback_exactly_48h() -> None:
    # 48.0 h → ceil(48/24)=2 days
    assert format_payback(Payback(hours=48.0)) == "2 days"


# ---------------------------------------------------------------------------
# AnalysisCost.total
# ---------------------------------------------------------------------------


def test_analysis_cost_total_property() -> None:
    ac = AnalysisCost(
        model_calls=10,
        model_cost=1.0,
        judge_calls=5,
        judge_cost=0.5,
        judge_model=None,
        judge_priced_as=None,
        audit_cost=0.25,
    )
    assert ac.total == pytest.approx(1.75)


def test_analysis_cost_total_default_audit_cost() -> None:
    ac = AnalysisCost(
        model_calls=1,
        model_cost=2.0,
        judge_calls=0,
        judge_cost=0.0,
        judge_model=None,
        judge_priced_as=None,
    )
    assert ac.total == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# analysis_cost(): audit_cost validation
# ---------------------------------------------------------------------------


def test_analysis_cost_negative_audit_cost_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="audit_cost"):
        analysis_cost([], tmp_path, _config(), audit_cost=-0.01)


def test_analysis_cost_zero_audit_cost_ok(tmp_path: Path) -> None:
    ac = analysis_cost([], tmp_path, _config(), audit_cost=0.0)
    assert ac.audit_cost == 0.0


# ---------------------------------------------------------------------------
# analysis_cost(): main logic
# ---------------------------------------------------------------------------


def test_analysis_cost_empty_sites(tmp_path: Path) -> None:
    ac = analysis_cost([], tmp_path, _config())
    assert ac.model_calls == 0
    assert ac.judge_calls == 0
    assert ac.model_cost == pytest.approx(0.0)
    assert ac.judge_cost == pytest.approx(0.0)
    assert ac.judge_model is None
    assert ac.judge_priced_as is None


def test_analysis_cost_skips_missing_files(tmp_path: Path) -> None:
    site = _site()
    # No files written → all skipped
    ac = analysis_cost([site], tmp_path, _config())
    assert ac.model_calls == 0


def test_analysis_cost_basic_model_cost(tmp_path: Path) -> None:
    """Two cases on 'big', no errors, no judge → model_cost should match hand calc."""
    site = _site()
    cfg = _config()
    path = results_path(tmp_path, site.id, "big")
    row1 = _ok_row("c1", "big", prompt_tokens=100, completion_tokens=20)
    row2 = _ok_row("c2", "big", prompt_tokens=200, completion_tokens=30)
    append_row(path, row1)
    append_row(path, row2)

    ac = analysis_cost([site], tmp_path, cfg)
    price = PRICES["big"]
    expected = call_cost(price, 100, 20) + call_cost(price, 200, 30)
    assert ac.model_calls == 2
    assert ac.model_cost == pytest.approx(expected)
    assert ac.judge_calls == 0
    assert ac.judge_cost == pytest.approx(0.0)


def test_analysis_cost_skips_error_rows(tmp_path: Path) -> None:
    """Error rows must not contribute to model_calls or model_cost."""
    site = _site()
    path = results_path(tmp_path, site.id, "big")
    append_row(path, _ok_row("c1", "big", 100, 20))
    append_row(path, _err_row("c2", "big"))

    ac = analysis_cost([site], tmp_path, _config())
    assert ac.model_calls == 1  # only c1


def test_analysis_cost_skips_model_with_no_price(tmp_path: Path) -> None:
    """A model absent from config.pricing is silently skipped."""
    site = _site()
    # 'mid' is in candidates but not in pricing
    cfg = _config(pricing={"big": PRICES["big"]})  # 'mid' has no price
    path_big = results_path(tmp_path, site.id, "big")
    path_mid = results_path(tmp_path, site.id, "mid")
    append_row(path_big, _ok_row("c1", "big", 100, 20))
    append_row(path_mid, _ok_row("c2", "mid", 50, 10))

    ac = analysis_cost([site], tmp_path, cfg)
    # 'mid' row skipped; only 'big' row counted
    assert ac.model_calls == 1
    price = PRICES["big"]
    assert ac.model_cost == pytest.approx(call_cost(price, 100, 20))


def test_analysis_cost_judge_priced_at_judge_model(tmp_path: Path) -> None:
    """Judge row is priced with judge model's price when available."""
    site = _site()
    judge_model = "mid"
    cfg = _config(pricing={"big": PRICES["big"], "mid": PRICES["mid"]})
    path_big = results_path(tmp_path, site.id, "big")
    row = _ok_row("c1", "big", prompt_tokens=100, completion_tokens=20, judge_model=judge_model)
    append_row(path_big, row)

    ac = analysis_cost([site], tmp_path, cfg)
    assert ac.judge_calls == 1
    assert ac.judge_model == judge_model
    assert ac.judge_priced_as == judge_model

    prompt_est = 100 + 20 + JUDGE_EXTRA_PROMPT_TOKENS
    expected_judge_cost = call_cost(PRICES[judge_model], prompt_est, JUDGE_COMPLETION_TOKENS)
    assert ac.judge_cost == pytest.approx(expected_judge_cost)


def test_analysis_cost_judge_falls_back_to_baseline_price(tmp_path: Path) -> None:
    """When judge model has no price entry, fall back to baseline price."""
    site = _site()
    judge_model = "judge-unknown"
    # judge_model not in pricing → fall back to baseline "big"
    cfg = _config(pricing={"big": PRICES["big"], "mid": PRICES["mid"]})
    path_big = results_path(tmp_path, site.id, "big")
    row = _ok_row("c1", "big", prompt_tokens=100, completion_tokens=20, judge_model=judge_model)
    append_row(path_big, row)

    ac = analysis_cost([site], tmp_path, cfg)
    assert ac.judge_calls == 1
    assert ac.judge_model == judge_model
    assert ac.judge_priced_as == "big"  # baseline

    prompt_est = 100 + 20 + JUDGE_EXTRA_PROMPT_TOKENS
    expected_judge_cost = call_cost(PRICES["big"], prompt_est, JUDGE_COMPLETION_TOKENS)
    assert ac.judge_cost == pytest.approx(expected_judge_cost)


def test_analysis_cost_judge_error_rows_skipped(tmp_path: Path) -> None:
    """Error rows with judge_model set are not counted as judge calls."""
    site = _site()
    path_big = results_path(tmp_path, site.id, "big")
    # ok row with judge
    append_row(path_big, _ok_row("c1", "big", judge_model="mid"))
    # error row with judge_model — should be skipped
    err_with_judge = ResultRow(
        case_id="c2",
        model="big",
        prompt_tokens=50,
        completion_tokens=10,
        judge_model="mid",
        error="scoring failed: timeout",
    )
    append_row(path_big, err_with_judge)

    ac = analysis_cost([site], tmp_path, _config())
    assert ac.judge_calls == 1  # only c1


def test_analysis_cost_most_frequent_judge_model(tmp_path: Path) -> None:
    """Most frequent judge_model wins; tie broken alphabetically."""
    site = _site()
    cfg = _config(
        pricing={"big": PRICES["big"], "mid": PRICES["mid"], "alpha": ModelPrice(1.0, 2.0)}
    )
    path_big = results_path(tmp_path, site.id, "big")
    # alpha appears once, mid appears twice → mid wins
    append_row(path_big, _ok_row("c1", "big", judge_model="alpha"))
    append_row(path_big, _ok_row("c2", "big", judge_model="mid"))
    append_row(path_big, _ok_row("c3", "big", judge_model="mid"))

    ac = analysis_cost([site], tmp_path, cfg)
    assert ac.judge_model == "mid"


def test_analysis_cost_most_frequent_tie_alphabetical(tmp_path: Path) -> None:
    """Tie in judge model frequency → alphabetically first wins."""
    site = _site()
    cfg = _config(
        pricing={"big": PRICES["big"], "alpha": ModelPrice(1.0, 2.0), "zeta": ModelPrice(1.0, 2.0)}
    )
    path_big = results_path(tmp_path, site.id, "big")
    append_row(path_big, _ok_row("c1", "big", judge_model="zeta"))
    append_row(path_big, _ok_row("c2", "big", judge_model="alpha"))

    ac = analysis_cost([site], tmp_path, cfg)
    assert ac.judge_model == "alpha"


def test_analysis_cost_two_sites(tmp_path: Path) -> None:
    """Rows across two sites are all accumulated."""
    site1 = _site("a.py::f1")
    site2 = _site("a.py::f2")
    cfg = _config()
    for site in (site1, site2):
        path = results_path(tmp_path, site.id, "big")
        append_row(path, _ok_row("c1", "big", 100, 20))

    ac = analysis_cost([site1, site2], tmp_path, cfg)
    assert ac.model_calls == 2


def test_analysis_cost_audit_cost_included_in_total(tmp_path: Path) -> None:
    ac = analysis_cost([], tmp_path, _config(), audit_cost=5.0)
    assert ac.audit_cost == pytest.approx(5.0)
    assert ac.total == pytest.approx(5.0)
