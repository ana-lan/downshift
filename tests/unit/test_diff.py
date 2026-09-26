from pathlib import Path

import pytest

from downshift.config import ModelPrice, resolve_config
from downshift.diff import (
    ADDED,
    CHANGED,
    DEFAULT_COMPLETION_TOKENS,
    REMOVED,
    UNCHANGED,
    diff_for_config,
    diff_sites,
    estimate_site,
    render_markdown,
)
from downshift.scanner import scan_source

SUPPORTDESK = Path(__file__).resolve().parents[2] / "examples" / "supportdesk"

PRICES = {
    "big": ModelPrice(input_per_mtok=10.0, output_per_mtok=20.0, tier="premium"),
    "small": ModelPrice(input_per_mtok=1.0, output_per_mtok=2.0, tier="budget"),
}


def per_day(_site_id: str) -> int:
    return 1000


def make_site(
    *,
    name="classify",
    model='"big"',
    messages='[{"role": "user", "content": "Classify this ticket please"}]',
    max_tokens=10,
):
    mt = f"        max_tokens={max_tokens},\n" if max_tokens is not None else ""
    source = (
        "from openai import OpenAI\n\nclient = OpenAI()\n\n\n"
        f"def {name}(text):\n"
        "    return client.chat.completions.create(\n"
        f"        model={model},\n"
        f"        messages={messages},\n"
        f"{mt}"
        "    )\n"
    )
    sites = scan_source(source, "app.py")
    assert len(sites) == 1
    return sites[0]


def est(site, baseline="big"):
    return estimate_site(site, prices=PRICES, baseline=baseline, calls_per_day=per_day)


def diff(base, head, baseline="big"):
    return diff_sites(base, head, prices=PRICES, baseline=baseline, calls_per_day=per_day)


# (4 prompt * $10 + 10 out * $20) / 1M = 2.4e-4 per call; x 1000/day x 30 = $7.20
BIG_MONTHLY = 7.2
SMALL_MONTHLY = 0.72


def test_estimate_literal_model():
    e = est(make_site())
    assert e.model == "big"
    assert not e.model_assumed
    assert e.prompt_tokens == 4
    assert not e.prompt_partial
    assert e.completion_tokens == 10
    assert not e.completion_assumed
    assert e.calls_per_day == 1000
    assert e.monthly == pytest.approx(BIG_MONTHLY)


def test_estimate_small_model():
    assert est(make_site(model='"small"')).monthly == pytest.approx(SMALL_MONTHLY)


def test_unresolved_model_falls_back_to_baseline():
    e = est(make_site(model="pick_model()"), baseline="small")
    assert e.model == "small"
    assert e.model_assumed
    assert e.monthly == pytest.approx(SMALL_MONTHLY)


def test_missing_max_tokens_uses_default():
    e = est(make_site(max_tokens=None))
    assert e.completion_tokens == DEFAULT_COMPLETION_TOKENS
    assert e.completion_assumed
    assert e.monthly == pytest.approx((40 + 256 * 20) / 1e6 * 30_000)


def test_unresolved_prompt_is_partial():
    e = est(make_site(messages="build_messages(text)"))
    assert e.prompt_tokens == 0
    assert e.prompt_partial


def test_unpriced_model_is_unknown():
    e = est(make_site(model='"mystery"'))
    assert not e.known
    assert e.per_call is None
    assert e.monthly is None


def test_added_site():
    d = diff([], [make_site()])
    (s,) = d.sites
    assert s.status == ADDED
    assert s.delta == pytest.approx(BIG_MONTHLY)
    assert d.before_monthly == 0
    assert d.after_monthly == pytest.approx(BIG_MONTHLY)
    assert d.delta_pct is None
    assert d.has_changes


def test_removed_site():
    d = diff([make_site()], [])
    (s,) = d.sites
    assert s.status == REMOVED
    assert s.delta == pytest.approx(-BIG_MONTHLY)


def test_changed_model():
    d = diff([make_site(model='"small"')], [make_site(model='"big"')])
    (s,) = d.sites
    assert s.status == CHANGED
    assert s.reasons[0] == "model small -> big"
    assert s.delta == pytest.approx(BIG_MONTHLY - SMALL_MONTHLY)
    assert d.delta_pct == pytest.approx(900.0)


def test_changed_max_tokens():
    d = diff([make_site(max_tokens=10)], [make_site(max_tokens=1024)])
    (s,) = d.sites
    assert s.status == CHANGED
    assert "max output 10 -> 1024 tokens" in s.reasons


def test_unchanged_site():
    d = diff([make_site()], [make_site()])
    (s,) = d.sites
    assert s.status == UNCHANGED
    assert s.delta == 0
    assert not d.has_changes
    assert d.before_monthly == pytest.approx(BIG_MONTHLY)


def test_unknown_left_out_of_totals():
    d = diff([], [make_site(model='"mystery"'), make_site(name="other")])
    assert len(d.unknown) == 1
    assert d.after_monthly == pytest.approx(BIG_MONTHLY)
    unknown = next(s for s in d.sites if not s.known)
    assert unknown.delta is None


def test_order_added_changed_removed_unchanged():
    base = [
        make_site(name="b_changed", model='"small"'),
        make_site(name="c_removed"),
        make_site(name="d_same"),
    ]
    head = [make_site(name="b_changed"), make_site(name="a_added"), make_site(name="d_same")]
    d = diff(base, head)
    assert [s.status for s in d.sites] == [ADDED, CHANGED, REMOVED, UNCHANGED]


def test_render_added():
    site = make_site()
    md = render_markdown(diff([], [site]), base="main", head="HEAD")
    assert md.startswith("## Downshift cost diff\n")
    assert "**$0.00 -> $7.20 (+$7.20)**" in md
    assert f"`{site.id}`" in md
    assert "| + |" in md
    assert "4 + 10" in md
    assert "Projection, not a bill" in md


def test_render_decrease_and_pct():
    md = render_markdown(diff([make_site()], [make_site(model='"small"')]))
    assert "-$6.48" in md
    assert "-90.0%" in md
    assert "big -> small" in md
    assert "$7.20 -> $0.72" in md


def test_render_no_changes():
    md = render_markdown(diff([make_site()], [make_site()]))
    assert "No LLM call site cost changes" in md
    assert "$7.20" in md
    assert "| Call site |" not in md


def test_render_marks_and_notes():
    head = [make_site(model="pick_model()", max_tokens=None, messages="build(text)")]
    md = render_markdown(diff([], head, baseline="small"))
    assert "small†" in md
    assert "0§ + 256‡" in md
    assert "priced as the baseline `small`" in md
    assert "No max_tokens set; assumed 256" in md
    assert "Prompt only partly resolved" in md


def test_render_unknown_note():
    md = render_markdown(diff([], [make_site(model='"mystery"')]))
    assert "left out of the totals" in md
    assert "unknown" in md


def test_diff_for_config_uses_config():
    cfg = resolve_config(None, SUPPORTDESK)
    site = make_site(model="pick_model()")
    d = diff_for_config([], [site], cfg)
    after = d.sites[0].after
    assert after is not None
    assert after.model == cfg.models.baseline
    assert after.model_assumed
    assert after.calls_per_day == cfg.volume.calls_per_day(site.id)
    assert after.known
