# Spec: `downshift report` (Phase 6c, Bob task B4)

Turn saved eval results into one markdown report: a decision per call site (keep or
downgrade), quality per model, projected monthly cost before vs after, and what needs
attention. The report becomes the Phase 7 PR description and feeds the web app.

## Building blocks (already implemented, do not change them)

- `decide.py`: `load_site_stats`, `decide_site`, `Decision`, `CandidateCheck`, `ModelStats`
  (`pass_rate`, `complete`, `avg_judge_score`, `summary`), `KEEP`, `DOWNGRADE`.
- `cost.py`: `cost_summary`, `CostSummary` (`sites`, `unknown`, `before_monthly`,
  `after_monthly`, `savings`, `savings_pct`), `SiteCost`.
- `config.py`: `Config` (`models.baseline`, `models.candidates`, `models.all_models`,
  `quality_threshold`, `min_pass_rate`, `pricing`, `volume`), `resolve_config`.
- `evals.py`: `load_eval_set`, `slug_for`, `EVAL_SUFFIX`. `schema.py`: `ScanResult.load`,
  `CallSite` (`id`, `grading`).

## Module `src/downshift/report.py`

- `NEAR_MISS_MARGIN = 0.05`
- `class ReportError(Exception)`
- `@dataclass(frozen=True) class Report` with fields:
  `sites: tuple[CallSite, ...]` (sites that have an eval set, sorted by id),
  `decisions: tuple[Decision, ...]` (same order as `sites`),
  `costs: CostSummary`,
  `missing_evals: tuple[str, ...]` (site ids with no eval file, sorted),
  `baseline: str`, `candidates: tuple[str, ...]`, `threshold: float`, `min_pass_rate: float`.
  Properties:
  - `downgraded -> tuple[Decision, ...]`
  - `below_floor -> tuple[Decision, ...]` (`decision.baseline_below_floor`)
  - `near_misses -> tuple[tuple[str, CandidateCheck], ...]`: (site id, check) for every check
    that did not pass, has a ratio, `threshold - NEAR_MISS_MARGIN <= ratio < threshold`,
    and `pass_rate >= min_pass_rate`.
  - `missing_data -> tuple[Decision, ...]`: decisions whose baseline stats are missing or
    not `complete`.
- `build_report(scan, config, evals_dir, results_dir, *, threshold=None, min_pass_rate=None)
  -> Report`. `None` means use the config value. For each call site sorted by id: eval file is
  `evals_dir / f"{slug_for(site.id)}{EVAL_SUFFIX}"`; missing file -> `missing_evals`; an eval
  set with problems -> raise `ReportError` naming the file and its first problem. Stats from
  `load_site_stats(site.id, eval_set, config.models.all_models, results_dir)`. Decision from
  `decide_site` with config baseline, candidates and pricing. Costs from
  `cost_summary(decisions, config.pricing, config.volume)`.
- `render_markdown(report) -> str`: deterministic (no dates, no version, no absolute paths),
  ends with exactly one newline.

## Markdown layout (follow exactly; numbers below are illustrative)

```markdown
# Downshift report

> Costs are projections: measured tokens per call x illustrative prices x assumed volume
> from the config. They are not a bill.

## Summary

| | Monthly cost |
|---|---:|
| Before (all on `qwen2.5:7b`) | $3,130.50 |
| After | $2,966.12 |
| Savings | $164.38 (5.3%) |

Downgraded **1 of 8** call sites.

Rule: a cheaper model must keep at least 95% of the baseline pass rate and pass at least
80% of cases on its own. Decisions use pass rate, not mean score.

## Decisions

| Call site | Grading | Decision | Model | Pass rate | Before / month | After / month |
|---|---|---|---|---|---:|---:|
| `supportdesk/misc_utils.py::lang_of` | exact | downgrade | `qwen2.5:1.5b` | 91% -> 91% | $174.00 | $10.44 |
| `supportdesk/policy.py::decide_refund` | json_fields | keep | `qwen2.5:7b` | 40% | $1,212.00 | $1,212.00 |

## Quality per model

| Call site | `qwen2.5:7b` | `qwen2.5:1.5b` | `qwen2.5:0.5b` |
|---|---|---|---|
| `supportdesk/agent_assist.py::draft_reply` | **3/22 (14%), judge 2.8/5** | 1/22 (5%), judge 2.1/5 | 0/22 (0%), judge 1.2/5 |
| `supportdesk/misc_utils.py::lang_of` | 20/22 (91%) | **20/22 (91%)** | 18/22 (82%) |

Judge-graded cases pass at 4/5 or higher; judge scores are averages on a 1 to 5 scale.

## Needs attention

### Baseline below the floor

- `supportdesk/policy.py::decide_refund`: baseline passes 40% of cases, below the 80% floor.
  Improve the prompt or model before downgrading.

### Near misses

- `supportdesk/triage.py::detect_sentiment`: `qwen2.5:0.5b` keeps 90% of the baseline pass
  rate (needs 95%).

### Missing data

- `supportdesk/x.py::y`: no eval set, not decided.
- `supportdesk/x.py::z`: baseline has incomplete results (1 errors, 21/22 scored).

## Details

<details>
<summary><code>supportdesk/misc_utils.py::lang_of</code>: downgrade to <code>qwen2.5:1.5b</code></summary>

- Decision: keeps 100% of baseline quality and costs less
- `qwen2.5:1.5b`: keeps 100% of baseline quality and costs less
- `qwen2.5:0.5b`: keeps 90% of baseline quality, needs 95%

</details>
```

Rules for the layout:
- Money: `f"${x:,.2f}"`; unknown -> `n/a`. Savings % with one decimal; pass rates with none.
- The "Rule:" sentence omits the "and pass at least N% ... on its own" part when
  `min_pass_rate == 0`.
- If some sites have unknown cost, add under the summary table:
  `Totals exclude N call sites with unknown cost (see Needs attention).`
- Decisions table, Pass rate column: downgrade -> `baseline% -> chosen%`; keep -> `baseline%`;
  no baseline pass rate -> `n/a`.
- Quality table: one column per model in `config.models.all_models` order. Cell
  `passed/scored (pct%)`; add `, judge X.X/5` when `avg_judge_score` is not None; add
  `, N errors` when errors > 0; no results -> `n/a`. Bold the cell of the model the site
  ends up on. Print the judge sentence only if at least one site uses judge grading.
- Needs attention: print only the subsections that have entries; if none have entries print
  `Nothing needs attention.` Missing evals use `no eval set, not decided.`; missing-data
  decisions use their `decision.reason`. The floor subsection only exists when
  `min_pass_rate > 0`.
- Details: one `<details>` block per decided site, blank line after `<summary>` and before
  `</details>`. Summary text: `downgrade to <code>M</code>` or `keep <code>M</code>`. First
  bullet `Decision: {decision.reason}`, then one bullet per candidate check in order.

## CLI: `downshift report`

`downshift report --callsites FILE [--evals DIR] [--results DIR] [-c CONFIG]
[--threshold X] [--min-pass-rate X] [--out FILE]`

- Defaults and config resolution mirror `downshift rescore` in `cli.py`: `evals/` and
  `results/` next to `--callsites`, config via `resolve_config`.
- `--threshold` is `click.FloatRange(0, 1, min_open=True)`; `--min-pass-rate` is
  `click.FloatRange(0, 1)`.
- Without `--out`: print the markdown to stdout with `click.echo` (no rich, so it pipes).
- With `--out`: write the file (create parent dirs) and print one line:
  `Wrote <path>: downgraded N of M call sites, projected savings $X/month (Y%).`
- Exit 2 on a missing or invalid callsites file, a config error, or `ReportError`. Exit 0
  otherwise, even when data is missing (the report says so).
- Remove `report` from the stub commands in `cli.py` and from `NOT_IMPLEMENTED` in
  `tests/cli/test_cli_help.py`.

## Tests

- `tests/unit/test_report.py`: synthetic `Decision`s via `decide_site` (pattern in
  `tests/unit/test_decide.py`) and a real `build_report` on `examples/supportdesk`. Cover:
  downgrade and keep rows, money and percent formatting, `n/a` cells, bold chosen model,
  judge suffix and sentence, errors suffix, near-miss boundaries (exactly at
  `threshold - 0.05` is in, just below is out, passing checks are out, below-floor
  candidates are out), floor subsection hidden at `min_pass_rate == 0`, "Nothing needs
  attention.", missing eval file, invalid eval file raises `ReportError`, unknown-cost
  sentence, exactly one trailing newline, and the threshold/min_pass_rate overrides.
- Snapshot: `tests/snapshots/supportdesk_report.md` holds the real SupportDesk report
  (default config). `tests/unit/test_report_snapshot.py` compares `render_markdown` to it;
  with env var `UPDATE_SNAPSHOTS=1` it rewrites the file instead and passes.
- `tests/cli/test_report_cli.py` with `CliRunner`: stdout mode, `--out` mode with the summary
  line, `--threshold 0.9` changes the result, missing callsites file -> exit 2, invalid
  `--threshold` -> exit 2.
- Target 100% coverage of `report.py`.

## Constraints

- Do not modify `decide.py`, `cost.py`, `config.py`, `runner.py`, eval files or results.
- Ruff rules E,F,I,B,UP,SIM, line length 100, `zip(..., strict=True)`, mypy clean, no network.
- Run the checks at most once at the end; if anything fails, stop and report. No fix loops.
