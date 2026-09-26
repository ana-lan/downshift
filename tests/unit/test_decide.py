"""Tests for decide.py: downgrade rules, guards and the real SupportDesk results."""

from __future__ import annotations

from pathlib import Path

import pytest

from downshift.config import ModelPrice, load_config
from downshift.decide import (
    DOWNGRADE,
    KEEP,
    CandidateCheck,
    Decision,
    ModelStats,
    call_cost,
    decide_site,
    load_site_stats,
    stats_for,
)
from downshift.evals import EVAL_SUFFIX, load_eval_set, slug_for
from downshift.runner import ResultRow, RunSummary
from downshift.schema import ScanResult

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "supportdesk"

PRICES = {
    "big": ModelPrice(2.50, 10.00),
    "mid": ModelPrice(0.15, 0.60),
    "small": ModelPrice(0.10, 0.40),
    "twin_a": ModelPrice(0.15, 0.60),
    "twin_b": ModelPrice(0.15, 0.60),
    "pricey": ModelPrice(5.00, 20.00),
}


def mk(
    model: str,
    passed: int,
    cases: int = 20,
    *,
    errors: int = 0,
    pt: float = 100.0,
    ct: float = 10.0,
    judge: float | None = None,
) -> ModelStats:
    scored = cases - errors
    summary = RunSummary(
        site_id="app.py::f",
        model=model,
        cases=cases,
        scored=scored,
        passed=passed,
        errors=errors,
        new=0,
        mean_score=passed / scored if scored else None,
        avg_latency_s=0.1 if scored else None,
        avg_prompt_tokens=pt if scored else None,
        avg_completion_tokens=ct if scored else None,
    )
    return ModelStats(summary=summary, avg_judge_score=judge)


def decide(
    all_stats: list[ModelStats],
    candidates: tuple[str, ...] = ("mid", "small"),
    threshold: float = 0.95,
    floor: float = 0.0,
) -> Decision:
    return decide_site(
        "app.py::f",
        {s.model: s for s in all_stats},
        baseline="big",
        candidates=list(candidates),
        prices=PRICES,
        threshold=threshold,
        min_pass_rate=floor,
    )


def check(decision: Decision, model: str) -> CandidateCheck:
    return next(c for c in decision.checks if c.model == model)


# --- cost --------------------------------------------------------------------


def test_call_cost_hand_computed() -> None:
    # 100 in x $2.50/M + 10 out x $10/M = (250 + 100) / 1e6
    assert call_cost(PRICES["big"], 100, 10) == pytest.approx(0.00035)


def test_cost_per_call_none_without_tokens() -> None:
    assert mk("big", 0, cases=5, errors=5).cost_per_call(PRICES["big"]) is None


# --- threshold ---------------------------------------------------------------


def test_at_threshold_picks_cheapest() -> None:
    d = decide([mk("big", 20), mk("mid", 20), mk("small", 19)])  # small ratio 0.95
    assert d.action == DOWNGRADE
    assert d.downgraded
    assert d.model == "small"
    assert check(d, "small").ratio == pytest.approx(0.95)


def test_below_threshold_falls_back_to_next_cheapest() -> None:
    d = decide([mk("big", 20), mk("mid", 20), mk("small", 18)])
    assert d.model == "mid"
    assert not check(d, "small").passed
    assert "needs 95%" in check(d, "small").reason


def test_all_below_threshold_keeps_baseline() -> None:
    d = decide([mk("big", 20), mk("mid", 15), mk("small", 10)])
    assert d.action == KEEP
    assert d.model == "big"
    assert d.reason == "no cheaper model passed the checks"
    assert len(d.checks) == 2


def test_candidate_better_than_baseline() -> None:
    d = decide([mk("big", 16), mk("mid", 18), mk("small", 10)])
    assert d.model == "mid"
    assert check(d, "mid").ratio == pytest.approx(18 / 16)


def test_float_edge_at_exact_threshold() -> None:
    # 18/22 vs 20/22 is 0.9 but not exactly in floating point
    d = decide([mk("big", 20, cases=22), mk("small", 18, cases=22)], ("small",), threshold=0.90)
    assert d.model == "small"


# --- floor -------------------------------------------------------------------


def test_floor_blocks_downgrade_of_weak_baseline() -> None:
    d = decide([mk("big", 10), mk("mid", 10), mk("small", 4)], floor=0.80)
    assert d.action == KEEP
    assert d.baseline_below_floor
    assert d.baseline_pass_rate == pytest.approx(0.5)
    assert "below the floor 80%" in check(d, "mid").reason


def test_no_floor_by_default() -> None:
    d = decide([mk("big", 10), mk("mid", 10), mk("small", 4)])
    assert d.model == "mid"
    assert not d.baseline_below_floor


def test_candidate_above_floor_passes() -> None:
    d = decide([mk("big", 20), mk("mid", 19), mk("small", 10)], floor=0.80)
    assert d.model == "mid"
    assert not d.baseline_below_floor


# --- ties and price ----------------------------------------------------------


def test_tie_on_cost_prefers_higher_pass_rate() -> None:
    d = decide([mk("big", 20), mk("twin_a", 19), mk("twin_b", 20)], ("twin_a", "twin_b"))
    assert d.model == "twin_b"


def test_full_tie_prefers_list_order() -> None:
    d = decide([mk("big", 20), mk("twin_a", 20), mk("twin_b", 20)], ("twin_b", "twin_a"))
    assert d.model == "twin_b"


def test_more_tokens_can_make_a_cheap_model_lose() -> None:
    # small is cheaper per token but far more verbose here
    d = decide([mk("big", 20), mk("mid", 20), mk("small", 20, pt=1000, ct=1000)])
    assert d.model == "mid"


def test_pricier_candidate_is_rejected() -> None:
    d = decide([mk("big", 20), mk("pricey", 20)], ("pricey",))
    assert d.action == KEEP
    assert check(d, "pricey").reason == "not cheaper than the baseline"


def test_baseline_in_candidates_is_ignored() -> None:
    d = decide([mk("big", 20), mk("mid", 20)], ("big", "mid"))
    assert [c.model for c in d.checks] == ["mid"]


def test_no_candidates() -> None:
    d = decide([mk("big", 20)], ())
    assert d.action == KEEP
    assert d.reason == "no candidate models"


def test_missing_price_raises() -> None:
    with pytest.raises(ValueError, match="no pricing for model 'ghost'"):
        decide([mk("big", 20), mk("ghost", 20)], ("ghost",))


@pytest.mark.parametrize(("threshold", "floor"), [(0.0, 0.0), (1.5, 0.0), (0.9, -0.1), (0.9, 2)])
def test_bad_settings_raise(threshold: float, floor: float) -> None:
    with pytest.raises(ValueError):
        decide([mk("big", 20)], threshold=threshold, floor=floor)


# --- guards ------------------------------------------------------------------


def test_candidate_with_errors_is_skipped() -> None:
    d = decide([mk("big", 20), mk("mid", 19), mk("small", 19, errors=1)])
    assert d.model == "mid"
    assert check(d, "small").reason == "incomplete results (1 errors, 19/20 scored)"


def test_missing_candidate_results() -> None:
    d = decide([mk("big", 20), mk("mid", 20)])
    assert check(d, "small").reason == "no results"
    assert d.model == "mid"


def test_baseline_with_errors_keeps() -> None:
    d = decide([mk("big", 18, errors=1), mk("mid", 20)])
    assert d.action == KEEP
    assert d.reason.startswith("baseline has incomplete results")
    assert d.checks == ()


def test_missing_baseline_keeps() -> None:
    d = decide([mk("mid", 20)])
    assert d.action == KEEP
    assert d.reason == "no baseline results"
    assert d.baseline_pass_rate is None


def test_zero_baseline_keeps() -> None:
    d = decide([mk("big", 0), mk("mid", 5)], floor=0.5)
    assert d.action == KEEP
    assert "passes no cases" in d.reason
    assert d.baseline_below_floor


# --- stats_for ---------------------------------------------------------------


def row(case_id: str, *, passed: bool = True, judge: int | None = None, error: str | None = None):
    return ResultRow(
        case_id=case_id,
        model="big",
        output="" if error else "x",
        prompt_tokens=100,
        completion_tokens=10,
        latency_s=0.5,
        score=1.0 if passed else 0.0,
        passed=passed,
        detail="",
        judge_score=judge,
        error=error,
        judge_model=None,
    )


def test_stats_for_averages_judge_on_scored_rows_only() -> None:
    rows = {
        "c1": row("c1", judge=5),
        "c2": row("c2", passed=False, judge=3),
        "c3": row("c3", passed=False, error="boom"),
        "other": row("other", judge=1),  # not in case_ids
    }
    s = stats_for("app.py::f", "big", ["c1", "c2", "c3"], rows)
    assert s.avg_judge_score == pytest.approx(4.0)
    assert (s.summary.scored, s.summary.passed, s.summary.errors) == (2, 1, 1)
    assert not s.complete
    assert s.model == "big"
    assert s.pass_rate == pytest.approx(0.5)


def test_stats_for_no_judge_scores() -> None:
    s = stats_for("app.py::f", "big", ["c1"], {"c1": row("c1")})
    assert s.avg_judge_score is None
    assert s.complete


# --- real SupportDesk results (committed files, no network) ---------------------


@pytest.fixture(scope="module")
def real():
    cfg = load_config(EXAMPLE / "downshift.yaml")
    scan = ScanResult.load(EXAMPLE / "downshift.audit.json")
    return cfg, scan


def real_decision(
    real, function: str, threshold: float = 0.95, floor: float | None = None
) -> Decision:
    cfg, scan = real
    site = next(s for s in scan.call_sites if s.function == function)
    eval_set = load_eval_set(EXAMPLE / "evals" / f"{slug_for(site.id)}{EVAL_SUFFIX}")
    all_stats = load_site_stats(site.id, eval_set, cfg.models.all_models, EXAMPLE / "results")
    return decide_site(
        site.id,
        all_stats,
        baseline=cfg.models.baseline,
        candidates=cfg.models.candidates,
        prices=cfg.pricing,
        threshold=threshold,
        min_pass_rate=cfg.min_pass_rate if floor is None else floor,
    )


def test_real_lang_of_downgrades_to_1_5b(real) -> None:
    d = real_decision(real, "lang_of")
    assert d.action == DOWNGRADE
    assert d.model == "qwen2.5:1.5b"
    assert not check(d, "qwen2.5:0.5b").passed  # 18/22 vs 20/22 = 90%


def test_real_decide_refund_keeps_and_flags_floor(real) -> None:
    d = real_decision(real, "decide_refund")
    assert d.action == KEEP
    assert d.baseline_below_floor
    assert d.baseline_pass_rate == pytest.approx(10 / 25)


def test_real_sentiment_downgrades_at_0_90(real) -> None:
    assert real_decision(real, "detect_sentiment").action == KEEP
    d = real_decision(real, "detect_sentiment", threshold=0.90)
    assert d.model == "qwen2.5:0.5b"


def test_real_judge_average_uses_new_judge(real) -> None:
    d = real_decision(real, "draft_reply")
    assert d.action == KEEP
    # gpt-oss-120b grades: {1:1, 2:8, 3:10, 4:1, 5:2} -> 61 / 22
    assert d.stats["qwen2.5:7b"].avg_judge_score == pytest.approx(61 / 22)


def test_real_only_lang_of_downgrades(real) -> None:
    _, scan = real
    downgraded = [
        site.function for site in scan.call_sites if real_decision(real, site.function).downgraded
    ]
    assert downgraded == ["lang_of"]
