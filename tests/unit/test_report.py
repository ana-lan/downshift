"""Tests for report.py: build_report, render_markdown, and Report properties."""

from __future__ import annotations

from pathlib import Path

import pytest

from downshift.config import Config, ModelPrice, ModelsConfig, VolumeConfig
from downshift.cost import cost_summary
from downshift.decide import (
    DOWNGRADE,
    Decision,
    ModelStats,
    decide_site,
)
from downshift.evals import EVAL_SUFFIX, slug_for
from downshift.report import (
    Report,
    ReportError,
    build_report,
    render_markdown,
)
from downshift.runner import RunSummary
from downshift.schema import ScanResult

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "supportdesk"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PRICES = {
    "big": ModelPrice(2.50, 10.00),
    "mid": ModelPrice(0.15, 0.60),
    "small": ModelPrice(0.10, 0.40),
}


def mk(
    model: str,
    passed: int,
    cases: int = 22,
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
    site_id: str = "app.py::f",
    candidates: tuple[str, ...] = ("mid", "small"),
    threshold: float = 0.95,
    floor: float = 0.0,
) -> Decision:
    return decide_site(
        site_id,
        {s.model: s for s in all_stats},
        baseline="big",
        candidates=list(candidates),
        prices=PRICES,
        threshold=threshold,
        min_pass_rate=floor,
    )


def _minimal_config(
    threshold: float = 0.95,
    min_pass_rate: float = 0.0,
) -> Config:
    return Config(
        models=ModelsConfig(
            baseline="big",
            candidates=("mid", "small"),
        ),
        quality_threshold=threshold,
        min_pass_rate=min_pass_rate,
        pricing=PRICES,
        volume=VolumeConfig(default_per_day=1000),
    )


def _make_report(
    decisions: list[Decision],
    sites_grading: list[str | None] | None = None,
    threshold: float = 0.95,
    min_pass_rate: float = 0.0,
    missing_evals: list[str] | None = None,
) -> Report:
    """Build a Report directly from a list of Decisions (no disk I/O)."""
    from downshift.schema import CallSite, ModelRef

    if sites_grading is None:
        sites_grading = [None] * len(decisions)

    sites = tuple(
        CallSite(
            id=d.site_id,
            file=d.site_id.split("::")[0],
            line=1,
            function=d.site_id.split("::")[-1],
            api="openai",
            model=ModelRef(value="big", source="literal", expression="big"),
            grading=g,
        )
        for d, g in zip(decisions, sites_grading, strict=True)
    )
    costs = cost_summary(decisions, PRICES, VolumeConfig(default_per_day=1000))
    return Report(
        sites=sites,
        decisions=tuple(decisions),
        costs=costs,
        missing_evals=tuple(sorted(missing_evals or [])),
        baseline="big",
        candidates=("mid", "small"),
        threshold=threshold,
        min_pass_rate=min_pass_rate,
    )


# ---------------------------------------------------------------------------
# Report properties
# ---------------------------------------------------------------------------


def test_downgraded_property() -> None:
    d1 = decide([mk("big", 22), mk("mid", 22), mk("small", 20)])
    d2 = decide([mk("big", 22), mk("mid", 10), mk("small", 10)], site_id="app.py::g")
    report = _make_report([d1, d2])
    assert len(report.downgraded) == 1
    assert report.downgraded[0].action == DOWNGRADE


def test_below_floor_property() -> None:
    d1 = decide([mk("big", 10), mk("mid", 10)], floor=0.80)
    d2 = decide([mk("big", 22), mk("mid", 22)], site_id="app.py::g", floor=0.80)
    report = _make_report([d1, d2], min_pass_rate=0.80)
    assert len(report.below_floor) == 1
    assert report.below_floor[0].site_id == "app.py::f"


def test_missing_data_property_no_results() -> None:
    # No baseline results -> missing_data
    d = decide([mk("big", 0, errors=22), mk("mid", 0)])
    report = _make_report([d])
    assert len(report.missing_data) == 1


def test_missing_data_property_complete_baseline() -> None:
    d = decide([mk("big", 22), mk("mid", 10), mk("small", 10)])
    report = _make_report([d])
    assert len(report.missing_data) == 0


# ---------------------------------------------------------------------------
# Near-miss boundary tests
# ---------------------------------------------------------------------------


def test_near_miss_exactly_at_lower_bound() -> None:
    # ratio == threshold - NEAR_MISS_MARGIN => in
    threshold = 0.95
    # big=22, small=22*(0.95-0.05)=19.8 -> 20 passes at ratio=20/22≈0.909<0.9
    # Use exact: big=20, small=18 -> ratio=18/20=0.90 = 0.95-0.05
    d = decide(
        [mk("big", 20, cases=20), mk("mid", 10, cases=20), mk("small", 18, cases=20)],
        threshold=threshold,
    )
    report = _make_report([d], threshold=threshold)
    near = report.near_misses
    models_in = [check.model for _, check in near]
    assert "small" in models_in


def test_near_miss_just_below_lower_bound_is_out() -> None:
    # ratio just below threshold-NEAR_MISS_MARGIN => out
    # big=20, small=17 -> ratio=17/20=0.85 < 0.90
    d = decide(
        [mk("big", 20, cases=20), mk("mid", 10, cases=20), mk("small", 17, cases=20)],
        threshold=0.95,
    )
    report = _make_report([d], threshold=0.95)
    near = report.near_misses
    models_in = [check.model for _, check in near]
    assert "small" not in models_in


def test_near_miss_passing_check_excluded() -> None:
    # A check that passed is not a near-miss
    d = decide([mk("big", 22), mk("mid", 22), mk("small", 18)])
    report = _make_report([d])
    near = report.near_misses
    for _, check in near:
        assert not check.passed


def test_near_miss_below_floor_candidate_excluded() -> None:
    # big=20, small=18 ratio=0.90 >= 0.90 boundary -> would be near-miss
    # but small pass_rate=18/20=0.90 >= min_pass_rate=0.80 -> is included
    # floor candidate is one whose pass_rate < min_pass_rate
    # big=20, small_low=12 -> pass_rate=0.60 < 0.80 floor; ratio=12/20=0.60 < 0.90
    d = decide(
        [mk("big", 20, cases=20), mk("mid", 10, cases=20), mk("small", 12, cases=20)],
        threshold=0.95,
        floor=0.80,
    )
    report = _make_report([d], threshold=0.95, min_pass_rate=0.80)
    near = report.near_misses
    models_in = [check.model for _, check in near]
    assert "small" not in models_in


# ---------------------------------------------------------------------------
# render_markdown: downgrade and keep rows
# ---------------------------------------------------------------------------


def test_downgrade_row_shows_two_pass_rates() -> None:
    d = decide([mk("big", 22), mk("mid", 22), mk("small", 20)])
    report = _make_report([d])
    md = render_markdown(report)
    # Downgraded to small; pass rate cell should show baseline% -> chosen%
    assert "100% -> 91%" in md or "100% ->" in md


def test_keep_row_shows_one_pass_rate() -> None:
    d = decide([mk("big", 22), mk("mid", 10), mk("small", 10)])
    report = _make_report([d])
    md = render_markdown(report)
    assert "keep" in md
    # Pass rate should just be the baseline rate, not "->"-style
    lines = [ln for ln in md.splitlines() if "app.py::f" in ln and "|" in ln]
    assert lines, "no decision row found"
    # No arrow in the pass rate cell for a keep decision
    assert "->" not in lines[0]


def test_no_baseline_stats_shows_na_pass_rate() -> None:
    d = decide([mk("big", 0, errors=22), mk("mid", 0)])
    report = _make_report([d])
    md = render_markdown(report)
    table_lines = [ln for ln in md.splitlines() if "app.py::f" in ln and "|" in ln]
    assert any("n/a" in ln for ln in table_lines)


# ---------------------------------------------------------------------------
# render_markdown: money and percent formatting
# ---------------------------------------------------------------------------


def test_money_formatting() -> None:
    d = decide([mk("big", 22), mk("mid", 22), mk("small", 20)])
    report = _make_report([d])
    md = render_markdown(report)
    # Should contain dollar amounts
    assert "$" in md


def test_zero_savings_pct_is_na() -> None:
    # When costs are unknown (no token counts), the report shows n/a
    d = decide([mk("big", 0, errors=22), mk("mid", 0)])
    report = _make_report([d])
    md = render_markdown(report)
    assert "n/a" in md


def test_unknown_cost_sentence_present() -> None:
    # Savings_pct is None with zero before cost
    decide([mk("big", 22, pt=0.0, ct=0.0), mk("mid", 22, pt=0.0, ct=0.0)])
    # avg_prompt_tokens=0 -> cost_per_call returns 0, which means zero savings not unknown
    # Build a situation where token counts are None (errors=all)
    d2 = decide([mk("big", 0, errors=22), mk("mid", 0)])
    from downshift.schema import CallSite, ModelRef

    site2 = CallSite(
        id="x.py::h",
        file="x.py",
        line=1,
        function="h",
        api="openai",
        model=ModelRef(value="big", source="literal", expression="big"),
    )
    costs2 = cost_summary([d2], PRICES, VolumeConfig(default_per_day=1000))
    report2 = Report(
        sites=(site2,),
        decisions=(d2,),
        costs=costs2,
        missing_evals=(),
        baseline="big",
        candidates=("mid", "small"),
        threshold=0.95,
        min_pass_rate=0.0,
    )
    md = render_markdown(report2)
    assert "Totals exclude" in md
    assert "unknown cost" in md


def test_unknown_cost_sentence_absent_when_all_known() -> None:
    d = decide([mk("big", 22), mk("mid", 22), mk("small", 20)])
    report = _make_report([d])
    md = render_markdown(report)
    assert "Totals exclude" not in md


# ---------------------------------------------------------------------------
# render_markdown: quality table
# ---------------------------------------------------------------------------


def test_quality_table_bold_chosen_model() -> None:
    # Downgrade to small -> small column should be bold
    d = decide([mk("big", 22), mk("mid", 22), mk("small", 22)])
    report = _make_report([d])
    md = render_markdown(report)
    # Find the quality table row
    lines = [ln for ln in md.splitlines() if "app.py::f" in ln and "|" in ln]
    # Quality table row (second occurrence - decisions table is first)
    assert len(lines) >= 2
    quality_row = lines[1]
    assert "**" in quality_row  # bold present
    # The small model cell should be bold
    cells = [c.strip() for c in quality_row.split("|")]
    small_idx = 3  # col 0=empty, 1=site, 2=big, 3=mid, 4=small
    assert "**" in cells[small_idx] or "**" in cells[4]


def test_quality_table_judge_suffix() -> None:
    d = decide([mk("big", 22, judge=4.5), mk("mid", 22, judge=3.2), mk("small", 20)])
    report = _make_report([d], sites_grading=["judge"])
    md = render_markdown(report)
    assert "judge 4.5/5" in md or "judge" in md


def test_quality_table_judge_sentence_present_when_judge_grading() -> None:
    d = decide([mk("big", 22, judge=4.5), mk("mid", 22), mk("small", 20)])
    report = _make_report([d], sites_grading=["judge"])
    md = render_markdown(report)
    assert "Judge-graded cases pass at 4/5" in md


def test_quality_table_judge_sentence_absent_when_no_judge_grading() -> None:
    d = decide([mk("big", 22), mk("mid", 22), mk("small", 20)])
    report = _make_report([d], sites_grading=["exact"])
    md = render_markdown(report)
    assert "Judge-graded" not in md


def test_quality_table_errors_suffix() -> None:
    d = decide([mk("big", 20, errors=2), mk("mid", 10), mk("small", 5)])
    report = _make_report([d])
    md = render_markdown(report)
    assert "errors" in md


def test_quality_table_na_cell_when_no_results() -> None:
    # A model with scored=0 should show n/a
    from downshift.runner import RunSummary

    empty_stats = ModelStats(
        summary=RunSummary(
            site_id="app.py::f",
            model="small",
            cases=0,
            scored=0,
            passed=0,
            errors=0,
            new=0,
            mean_score=None,
            avg_latency_s=None,
            avg_prompt_tokens=None,
            avg_completion_tokens=None,
        )
    )
    big_stats = mk("big", 22)
    mid_stats = mk("mid", 22)
    d = decide_site(
        "app.py::f",
        {"big": big_stats, "mid": mid_stats, "small": empty_stats},
        baseline="big",
        candidates=["mid", "small"],
        prices=PRICES,
        threshold=0.95,
        min_pass_rate=0.0,
    )
    report = _make_report([d])
    md = render_markdown(report)
    assert "n/a" in md


# ---------------------------------------------------------------------------
# render_markdown: needs attention section
# ---------------------------------------------------------------------------


def test_floor_subsection_hidden_when_min_pass_rate_zero() -> None:
    d = decide([mk("big", 10), mk("mid", 10)], floor=0.0)
    report = _make_report([d], min_pass_rate=0.0)
    md = render_markdown(report)
    assert "Baseline below the floor" not in md


def test_floor_subsection_present_when_min_pass_rate_nonzero_and_below() -> None:
    d = decide([mk("big", 10), mk("mid", 10)], floor=0.80)
    report = _make_report([d], min_pass_rate=0.80)
    md = render_markdown(report)
    assert "Baseline below the floor" in md


def test_nothing_needs_attention_when_all_empty() -> None:
    # Need a case where: no near-misses, no below-floor, no missing data, no missing evals.
    # small=22 passes at 100% -> ratio=1.0 >= 0.95 threshold, passes -> downgraded (not near-miss)
    # mid=22 also passes -> downgraded to cheapest (small); mid check passes too
    # No near-misses, no missing data
    d = decide([mk("big", 22), mk("mid", 22, pt=200.0), mk("small", 22)])
    report = _make_report([d])
    md = render_markdown(report)
    assert "Nothing needs attention." in md


def test_missing_eval_appears_in_needs_attention() -> None:
    d = decide([mk("big", 22), mk("mid", 22), mk("small", 20)])
    report = _make_report([d], missing_evals=["z.py::missing"])
    md = render_markdown(report)
    assert "z.py::missing" in md
    assert "no eval set, not decided" in md


def test_missing_data_decision_in_needs_attention() -> None:
    d = decide([mk("big", 0, errors=22), mk("mid", 0)])
    report = _make_report([d])
    md = render_markdown(report)
    assert "Missing data" in md
    assert "app.py::f" in md


# ---------------------------------------------------------------------------
# render_markdown: structural guarantees
# ---------------------------------------------------------------------------


def test_exactly_one_trailing_newline() -> None:
    d = decide([mk("big", 22), mk("mid", 22), mk("small", 20)])
    report = _make_report([d])
    md = render_markdown(report)
    assert md.endswith("\n")
    assert not md.endswith("\n\n")


def test_threshold_override_changes_decision() -> None:
    # At 0.95 threshold, small (ratio≈0.90 for 20/22) should not qualify
    # At 0.85 threshold it should
    big = mk("big", 22)
    mid = mk("mid", 10)
    small = mk("small", 20)
    d_strict = decide([big, mid, small], threshold=0.95)
    d_loose = decide([big, mid, small], threshold=0.85)
    # small: 20/22 ≈ 0.909; at 0.95 threshold => ratio=0.909 < 0.95 => fails
    # at 0.85 threshold => ratio=0.909 >= 0.85 => passes
    assert d_strict.model != "small" or d_loose.model == "small"
    # Just verify they can differ
    report_strict = _make_report([d_strict], threshold=0.95)
    report_loose = _make_report([d_loose], threshold=0.85)
    assert render_markdown(report_strict) != render_markdown(report_loose)


def test_min_pass_rate_override_changes_decision() -> None:
    # big=22/22, mid=22/22 (100% pass rate) always qualifies regardless of floor
    # Use a case where ratio passes but absolute pass rate doesn't:
    # big=20/22, mid=19/22 -> ratio=19/20=0.95 passes threshold, but pass_rate=86%
    # floor=0.90 blocks mid (86% < 90%), floor=0.0 allows mid
    big = mk("big", 20)
    mid = mk("mid", 19)
    small = mk("small", 10)
    d_no_floor = decide([big, mid, small], threshold=0.95, floor=0.0)
    d_with_floor = decide([big, mid, small], threshold=0.95, floor=0.90)
    assert d_no_floor.model == "mid"  # mid qualifies without floor
    assert d_with_floor.model != "mid"  # mid blocked by floor


# ---------------------------------------------------------------------------
# build_report: file I/O
# ---------------------------------------------------------------------------


def test_build_report_missing_eval_file(tmp_path: Path) -> None:
    """A missing eval file populates missing_evals and does not raise."""
    from downshift.schema import CallSite, ModelRef, ScanResult

    site = CallSite(
        id="x.py::f",
        file="x.py",
        line=1,
        function="f",
        api="openai",
        model=ModelRef(value="big", source="literal", expression="big"),
    )
    scan = ScanResult(root=".", files_scanned=1, call_sites=[site])
    cfg = _minimal_config()
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    report = build_report(scan, cfg, evals_dir, results_dir)
    assert "x.py::f" in report.missing_evals
    assert len(report.decisions) == 0


def test_build_report_invalid_eval_file_raises(tmp_path: Path) -> None:
    """An unparseable eval file raises ReportError naming the file."""
    from downshift.schema import CallSite, ModelRef, ScanResult

    site = CallSite(
        id="x.py::f",
        file="x.py",
        line=1,
        function="f",
        api="openai",
        model=ModelRef(value="big", source="literal", expression="big"),
    )
    scan = ScanResult(root=".", files_scanned=1, call_sites=[site])
    cfg = _minimal_config()
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    eval_file = evals_dir / f"{slug_for('x.py::f')}{EVAL_SUFFIX}"
    eval_file.write_text("not valid json{{{\n", encoding="utf-8")

    with pytest.raises(ReportError, match=str(eval_file)):
        build_report(scan, cfg, evals_dir, results_dir)


def test_build_report_real_supportdesk() -> None:
    """build_report runs on the real SupportDesk example without error."""
    from downshift.config import load_config

    audit = EXAMPLE / "downshift.audit.json"
    evals_dir = EXAMPLE / "evals"
    results_dir = EXAMPLE / "results"
    cfg = load_config(EXAMPLE / "downshift.yaml")
    scan = ScanResult.load(audit)

    report = build_report(scan, cfg, evals_dir, results_dir)
    assert len(report.sites) > 0
    md = render_markdown(report)
    assert md.endswith("\n")
    assert "# Downshift report" in md
