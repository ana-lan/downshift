"""Projected LLM cost change between two scans (Phase 8).

Static estimate, no model calls: prompt tokens are words in the resolved prompt text,
completion tokens are max_tokens (or a default), prices and volume come from config.
A model that static analysis cannot resolve is priced as the baseline and marked assumed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from downshift.config import Config, ModelPrice
from downshift.llm import estimate_tokens
from downshift.schema import CallSite

DAYS_PER_MONTH = 30
DEFAULT_COMPLETION_TOKENS = 256

ADDED = "added"
REMOVED = "removed"
CHANGED = "changed"
UNCHANGED = "unchanged"
_ORDER = {ADDED: 0, CHANGED: 1, REMOVED: 2, UNCHANGED: 3}

MARK_MODEL = "†"
MARK_OUTPUT = "‡"
MARK_PROMPT = "§"


@dataclass(frozen=True)
class SiteEstimate:
    """Projected cost of one call site at one ref."""

    site_id: str
    model: str
    model_assumed: bool
    prompt_tokens: int
    prompt_partial: bool
    completion_tokens: int
    completion_assumed: bool
    calls_per_day: int
    per_call: float | None
    days: int = DAYS_PER_MONTH

    @property
    def known(self) -> bool:
        return self.per_call is not None

    @property
    def monthly(self) -> float | None:
        if self.per_call is None:
            return None
        return self.per_call * self.calls_per_day * self.days


def resolved_model(site: CallSite) -> str | None:
    """The model name static analysis found, or None."""
    ref = site.model
    if ref is None or not ref.resolved or not ref.value:
        return None
    return ref.value


def prompt_estimate(site: CallSite) -> tuple[int, bool]:
    """(estimated prompt tokens, partial) from the resolved message text."""
    if not site.messages:
        return 0, True
    tokens = 0
    partial = False
    for message in site.messages:
        if message.resolved:
            tokens += estimate_tokens(message.content)
        else:
            partial = True
    return tokens, partial


def estimate_site(
    site: CallSite,
    *,
    prices: Mapping[str, ModelPrice],
    baseline: str,
    calls_per_day: Callable[[str], int],
    days: int = DAYS_PER_MONTH,
    default_completion: int = DEFAULT_COMPLETION_TOKENS,
) -> SiteEstimate:
    found = resolved_model(site)
    model = found if found is not None else baseline
    prompt_tokens, partial = prompt_estimate(site)
    if site.max_tokens is not None:
        completion, completion_assumed = site.max_tokens, False
    else:
        completion, completion_assumed = default_completion, True
    price = prices.get(model)
    per_call = price.cost(prompt_tokens, completion) if price is not None else None
    return SiteEstimate(
        site_id=site.id,
        model=model,
        model_assumed=found is None,
        prompt_tokens=prompt_tokens,
        prompt_partial=partial,
        completion_tokens=completion,
        completion_assumed=completion_assumed,
        calls_per_day=calls_per_day(site.id),
        per_call=per_call,
        days=days,
    )


def _monthly(estimate: SiteEstimate | None) -> float:
    if estimate is None:
        return 0.0
    return estimate.monthly or 0.0


def _model_label(estimate: SiteEstimate) -> str:
    return estimate.model + (MARK_MODEL if estimate.model_assumed else "")


def _reasons(before: SiteEstimate, after: SiteEstimate) -> tuple[str, ...]:
    reasons: list[str] = []
    if before.model != after.model or before.model_assumed != after.model_assumed:
        reasons.append(f"model {_model_label(before)} -> {_model_label(after)}")
    if before.prompt_tokens != after.prompt_tokens:
        reasons.append(f"prompt ~{before.prompt_tokens} -> ~{after.prompt_tokens} tokens")
    if before.completion_tokens != after.completion_tokens:
        reasons.append(f"max output {before.completion_tokens} -> {after.completion_tokens} tokens")
    if before.calls_per_day != after.calls_per_day:
        reasons.append(f"calls/day {before.calls_per_day:,} -> {after.calls_per_day:,}")
    return tuple(reasons)


@dataclass(frozen=True)
class SiteDiff:
    site_id: str
    status: str
    before: SiteEstimate | None
    after: SiteEstimate | None
    reasons: tuple[str, ...] = ()

    @property
    def known(self) -> bool:
        sides = [e for e in (self.before, self.after) if e is not None]
        return all(e.known for e in sides)

    @property
    def delta(self) -> float | None:
        if not self.known:
            return None
        return _monthly(self.after) - _monthly(self.before)

    @property
    def model_assumed(self) -> bool:
        return any(e is not None and e.model_assumed for e in (self.before, self.after))

    @property
    def completion_assumed(self) -> bool:
        return any(e is not None and e.completion_assumed for e in (self.before, self.after))

    @property
    def prompt_partial(self) -> bool:
        return any(e is not None and e.prompt_partial for e in (self.before, self.after))


@dataclass(frozen=True)
class CostDiff:
    sites: tuple[SiteDiff, ...]
    baseline: str
    days: int = DAYS_PER_MONTH
    default_completion: int = DEFAULT_COMPLETION_TOKENS

    def _with(self, status: str) -> list[SiteDiff]:
        return [s for s in self.sites if s.status == status]

    @property
    def added(self) -> list[SiteDiff]:
        return self._with(ADDED)

    @property
    def removed(self) -> list[SiteDiff]:
        return self._with(REMOVED)

    @property
    def changed(self) -> list[SiteDiff]:
        return self._with(CHANGED)

    @property
    def unchanged(self) -> list[SiteDiff]:
        return self._with(UNCHANGED)

    @property
    def has_changes(self) -> bool:
        return any(s.status != UNCHANGED for s in self.sites)

    @property
    def unknown(self) -> list[SiteDiff]:
        return [s for s in self.sites if not s.known]

    @property
    def before_monthly(self) -> float:
        return sum(_monthly(s.before) for s in self.sites if s.known)

    @property
    def after_monthly(self) -> float:
        return sum(_monthly(s.after) for s in self.sites if s.known)

    @property
    def delta(self) -> float:
        return self.after_monthly - self.before_monthly

    @property
    def delta_pct(self) -> float | None:
        if self.before_monthly <= 0:
            return None
        return self.delta / self.before_monthly * 100


def diff_sites(
    base: Sequence[CallSite],
    head: Sequence[CallSite],
    *,
    prices: Mapping[str, ModelPrice],
    baseline: str,
    calls_per_day: Callable[[str], int],
    days: int = DAYS_PER_MONTH,
    default_completion: int = DEFAULT_COMPLETION_TOKENS,
) -> CostDiff:
    """Compare two sets of call sites by id and price both sides."""

    def est(site: CallSite) -> SiteEstimate:
        return estimate_site(
            site,
            prices=prices,
            baseline=baseline,
            calls_per_day=calls_per_day,
            days=days,
            default_completion=default_completion,
        )

    before = {s.id: est(s) for s in base}
    after = {s.id: est(s) for s in head}
    diffs: list[SiteDiff] = []
    for site_id in sorted(set(before) | set(after)):
        b = before.get(site_id)
        a = after.get(site_id)
        if b is None:
            diffs.append(SiteDiff(site_id, ADDED, None, a))
        elif a is None:
            diffs.append(SiteDiff(site_id, REMOVED, b, None))
        else:
            reasons = _reasons(b, a)
            status = CHANGED if reasons else UNCHANGED
            diffs.append(SiteDiff(site_id, status, b, a, reasons))
    diffs.sort(key=lambda d: (_ORDER[d.status], d.site_id))
    return CostDiff(
        sites=tuple(diffs), baseline=baseline, days=days, default_completion=default_completion
    )


def diff_for_config(
    base: Sequence[CallSite],
    head: Sequence[CallSite],
    config: Config,
    *,
    days: int = DAYS_PER_MONTH,
    default_completion: int = DEFAULT_COMPLETION_TOKENS,
) -> CostDiff:
    return diff_sites(
        base,
        head,
        prices=config.pricing,
        baseline=config.models.baseline,
        calls_per_day=config.volume.calls_per_day,
        days=days,
        default_completion=default_completion,
    )


def _money(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"${value:,.2f}"


def _signed(value: float | None) -> str:
    if value is None:
        return "unknown"
    if abs(value) < 0.005:
        return "$0.00"
    sign = "+" if value > 0 else "-"
    return f"{sign}${abs(value):,.2f}"


def _tokens(estimate: SiteEstimate) -> str:
    prompt = f"{estimate.prompt_tokens}{MARK_PROMPT if estimate.prompt_partial else ''}"
    out = f"{estimate.completion_tokens}{MARK_OUTPUT if estimate.completion_assumed else ''}"
    return f"{prompt} + {out}"


def _pair(before: str | None, after: str | None) -> str:
    if before is None:
        return after or ""
    if after is None:
        return before
    return before if before == after else f"{before} -> {after}"


def _row(site: SiteDiff) -> str:
    b, a = site.before, site.after
    model = _pair(_model_label(b) if b else None, _model_label(a) if a else None)
    tokens = _pair(_tokens(b) if b else None, _tokens(a) if a else None)
    calls = _pair(f"{b.calls_per_day:,}" if b else None, f"{a.calls_per_day:,}" if a else None)
    if b is None:
        monthly = _money(a.monthly if a else None)
    elif a is None:
        monthly = f"{_money(b.monthly)} -> $0.00"
    else:
        monthly = f"{_money(b.monthly)} -> {_money(a.monthly)}"
    cells = [site.status, f"`{site.site_id}`", model, tokens, calls, monthly, _signed(site.delta)]
    return "| " + " | ".join(cells) + " |"


def render_markdown(diff: CostDiff, *, base: str = "main", head: str = "HEAD") -> str:
    """Deterministic markdown for a PR comment."""
    counts = (
        f"{len(diff.added)} added, {len(diff.changed)} changed, "
        f"{len(diff.removed)} removed, {len(diff.unchanged)} unchanged"
    )
    lines = ["## Downshift cost diff", ""]
    if not diff.has_changes:
        lines.append(
            f"No LLM call site cost changes in `{head}` vs `{base}` ({counts}). "
            f"Projected monthly cost stays at **{_money(diff.after_monthly)}**."
        )
        lines.append("")
    else:
        pct = diff.delta_pct
        pct_text = "" if pct is None else f", {'+' if pct > 0 else ''}{pct:.1f}%"
        lines.append(
            f"Projected monthly LLM cost, `{head}` vs `{base}`: "
            f"**{_money(diff.before_monthly)} -> {_money(diff.after_monthly)} "
            f"({_signed(diff.delta)}{pct_text})**"
        )
        lines.append("")
        lines.append(f"Call sites: {counts}.")
        lines.append("")
        lines.append(
            "| Change | Call site | Model | Tokens/call (in + out) | Calls/day | Monthly | Delta |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        lines.extend(_row(s) for s in diff.sites if s.status != UNCHANGED)
        lines.append("")

    shown = [s for s in diff.sites if s.status != UNCHANGED]
    notes: list[str] = []
    if any(s.model_assumed for s in shown):
        notes.append(
            f"{MARK_MODEL} Model not resolved by static analysis; priced as the baseline "
            f"`{diff.baseline}`. Run the Bob auditor for exact models."
        )
    if any(s.completion_assumed for s in shown):
        notes.append(f"{MARK_OUTPUT} No max_tokens set; assumed {diff.default_completion}.")
    if any(s.prompt_partial for s in shown):
        notes.append(f"{MARK_PROMPT} Prompt only partly resolved; unresolved text not counted.")
    if diff.unknown:
        notes.append(
            f"{len(diff.unknown)} call site(s) use a model with no configured price "
            "and are left out of the totals."
        )
    for note in notes:
        lines.append(f"- {note}")
    if notes:
        lines.append("")
    lines.append(
        "_Projection, not a bill: tokens estimated from source (words in resolved prompt "
        f"text; output = max_tokens, or {diff.default_completion} if unset) x illustrative "
        f"prices x configured calls/day x {diff.days} days._"
    )
    return "\n".join(lines) + "\n"
