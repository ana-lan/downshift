# Plan: Analysis Cost and Payback — `downshift report`

## Overview

Add a one-time "analysis cost" section to `downshift report` so users can see
what the evaluation run cost and how quickly projected savings will pay it back.
Scope is four files touched + two new files:

| File | Change |
|---|---|
| `src/downshift/payback.py` | **NEW** — `AnalysisCost`, `Payback`, three functions |
| `src/downshift/report.py` | Add fields to `Report`; update `build_report`; update `render_markdown` |
| `src/downshift/cli.py` | Add `--audit-cost` to the `report` command |
| `src/downshift/export.py` | Add five keys to `summary_payload` |
| `tests/unit/test_payback.py` | **NEW** — unit tests for payback math and analysis_cost |
| `tests/unit/test_report.py` | Extend: section present/absent cases |
| `tests/cli/test_report_cli.py` | Extend: `--audit-cost` + negative rejection |
| `tests/unit/test_export.py` | Extend: new summary keys present |

**Do NOT edit** the report snapshot file (`tests/snapshots/supportdesk_report.md`
or `examples/supportdesk/downshift.report.md`). The user regenerates it manually.

---

## Sub-task 1 — `src/downshift/payback.py` (new module)

**Status:** `[ ] pending`

### Intent
Create a self-contained module for analysis-cost and payback calculations,
so `report.py` and `export.py` can import from it without circular dependencies.

### Expected Outcomes
- `payback.py` exists with correct module docstring and `from __future__ import annotations`.
- Two `@dataclass(frozen=True)` classes: `AnalysisCost` and `Payback`.
- Three public functions: `analysis_cost`, `payback`, `format_payback`.
- All arithmetic matches the spec exactly (see Relevant Context).
- Module is importable; mypy passes on it.

### Todo List

1. Create `src/downshift/payback.py` with module docstring:
   _"Analysis cost and payback for one downshift report run."_

2. Define module-level constants:
   ```
   JUDGE_EXTRA_PROMPT_TOKENS = 150
   JUDGE_COMPLETION_TOKENS = 200
   ```

3. Define `AnalysisCost` (frozen dataclass):
   - Fields: `model_calls: int`, `model_cost: float`, `judge_calls: int`,
     `judge_cost: float`, `judge_model: str | None`, `judge_priced_as: str | None`,
     `audit_cost: float = 0.0`
   - Property `total -> float` = `model_cost + judge_cost + audit_cost`

4. Define `Payback` (frozen dataclass):
   - Field: `hours: float | None`

5. Implement `analysis_cost(sites, results_dir, config, *, audit_cost=0.0) -> AnalysisCost`:
   - Import `load_results` and `results_path` from `runner.py` — do not write a new parser.
   - For each call site × each model: call `results_path(results_dir, site_id, model)`;
     if it does not exist, skip.
   - Call `load_results(path)` to get `dict[str, ResultRow]` (last row per case wins
     because that is how `load_results` works).
   - For each row (unique case_id → ResultRow):
     - Skip if `row.error is not None`.
     - Look up `config.pricing.get(row.model)` — skip silently if None (no price).
     - Add `decide.call_cost(price, row.prompt_tokens, row.completion_tokens)` to
       `model_cost`; increment `model_calls`.
   - For each row with `row.judge_model` set (and not an error):
     - Estimate prompt_tokens = `row.prompt_tokens + row.completion_tokens + JUDGE_EXTRA_PROMPT_TOKENS`
     - Estimate completion = `JUDGE_COMPLETION_TOKENS`
     - Look up judge price from `config.pricing.get(row.judge_model)`;
       if None, fall back to `config.pricing.get(baseline_model)` — set
       `judge_priced_as` to whichever model's price was used.
     - Add `decide.call_cost(judge_price, prompt_est, JUDGE_COMPLETION_TOKENS)` to
       `judge_cost`; increment `judge_calls`.
   - `audit_cost` must be `>= 0`; raise `ValueError` otherwise.
   - Return `AnalysisCost(...)`.
   - The `judge_model` field on `AnalysisCost` is the first judge model seen in
     any row (or `None` if no judge rows).

6. Implement `payback(total_one_time: float, monthly_savings: float) -> Payback`:
   - Import `HOURS_PER_MONTH` from `cost.py`.
   - Return `Payback(hours=None)` if `monthly_savings <= 0`.
   - Otherwise: `hours = total_one_time / (monthly_savings / HOURS_PER_MONTH)`.

7. Implement `format_payback(p: Payback) -> str`:
   - `None` → `"no payback (no projected savings)"`
   - `< 1 hour` → `"N minutes"` (`math.ceil(hours * 60)`, minimum 1)
   - `< 48 hours` → `"X.Y hours"` (one decimal, e.g. `"1.5 hours"`)
   - `>= 48 hours` → `"N days"` (`math.ceil(hours / 24)`)

### Relevant Context
- `runner.load_results(path)` → `dict[str, ResultRow]`; last row wins; already skips
  unreadable lines.
- `runner.results_path(results_dir, site_id, model)` returns the JSONL path.
- `decide.call_cost(price, prompt_tokens, completion_tokens)` computes USD per call.
- `cost.HOURS_PER_MONTH = 730` — import directly, do not duplicate.
- `config.pricing` is a `Mapping[str, ModelPrice]`; `.get(model)` returns `None`
  when the model has no price.
- Baseline model is `config.models.baseline`.

---

## Sub-task 2 — `src/downshift/report.py` (edit)

**Status:** `[ ] pending`

### Intent
Thread `AnalysisCost | None` and `Payback | None` through `Report`, compute them
in `build_report`, and render the new section in `render_markdown`.

### Expected Outcomes
- `Report` has two new optional fields; all existing tests still pass.
- `build_report` accepts `audit_cost: float = 0.0` and populates the new fields.
- `render_markdown` emits the "What this analysis cost" section right after
  the Summary section, conditional on `report.analysis is not None`.

### Todo List

1. Add imports at the top of `report.py`:
   ```python
   from downshift.payback import AnalysisCost, Payback
   from downshift.payback import analysis_cost as _analysis_cost
   from downshift.payback import format_payback, payback as _payback
   ```

2. Add two fields to the `Report` dataclass (after `min_pass_rate`):
   ```python
   analysis: AnalysisCost | None = None
   payback: Payback | None = None
   ```
   These are optional (default `None`) so all existing code that builds `Report`
   directly (in tests) continues to work without changes.

3. In `build_report`, add parameter `audit_cost: float = 0.0` (keyword-only after the
   existing keyword args).
   After `cost_summary(...)`:
   ```python
   ac = _analysis_cost(decided_sites, results_dir, config, audit_cost=audit_cost)
   pb = _payback(ac.total, costs.savings)
   ```
   Pass both to the `Report(...)` constructor.

4. In `render_markdown`, insert the new section immediately after the blank line
   that follows the Summary section (i.e., after the "Downgraded N of M" paragraph).
   Only emit when `report.analysis is not None`.

   Section template:
   ```markdown
   ## What this analysis cost

   | | One-time cost |
   |---|---:|
   | Eval model calls (N) | $X |
   | Judge calls, estimated (M) | $Y |       <- omit when judge_calls == 0
   | Assistant audit | $Z |                  <- omit when audit_cost == 0
   | **Total** | **$T** |

   Pays back in **<format_payback>** of projected savings.

   > Priced at the same illustrative prices as the rest of the report. Judge tokens are not
   > recorded, so each judge call is estimated as (case prompt + output + 150) tokens in and
   > 200 out, priced as `<judge_priced_as>`. Retries and warm-up calls are not counted.
   > Local Ollama runs cost $0 in practice.
   ```
   - Reuse the existing `_fmt_money` helper for all dollar values.
   - Drop the judge row **and** the judge sentence in the blockquote when `judge_calls == 0`.
   - The `judge_priced_as` model name goes in the backtick span in the blockquote.

### Relevant Context
- `_fmt_money(x)` already exists in `report.py` and handles `None`.
- The summary section ends at the blank line after the "Downgraded N of M …" paragraph
  (line 214 area in the current file). The new section is inserted there.
- Existing field order in `Report`: `sites`, `decisions`, `costs`, `missing_evals`,
  `baseline`, `candidates`, `threshold`, `min_pass_rate`. New fields append after.

---

## Sub-task 3 — `src/downshift/cli.py` (edit)

**Status:** `[ ] pending`

### Intent
Expose `--audit-cost` on the `report` command so users can pass the cost of an
AI-assisted audit session.

### Expected Outcomes
- `downshift report --audit-cost 0.5` passes `audit_cost=0.5` to `build_report`.
- `downshift report --audit-cost -1` is rejected (typer `min=0.0`).
- The summary echo line in `--out` mode is unchanged.

### Todo List

1. Add to the `report` command's parameter list:
   ```python
   audit_cost: float = typer.Option(
       0.0,
       "--audit-cost",
       min=0.0,
       help="One-time cost of an assistant audit, in USD, added to the analysis cost.",
   )
   ```

2. Pass `audit_cost=audit_cost` to the `build_report(...)` call inside the `report`
   command body.

### Relevant Context
- `report` command is defined at line 668 in `cli.py`.
- The `build_report` call is at line 709. Add `audit_cost=audit_cost` as a
  keyword argument.
- All other `build_report` call sites (`export` command) do not receive `--audit-cost`;
  they use the default `0.0`.

---

## Sub-task 4 — `src/downshift/export.py` (edit)

**Status:** `[ ] pending`

### Intent
Add the five new payback keys to the `summary.json` payload so the web app can
display them.

### Expected Outcomes
- `summary_payload` returns a dict with five additional keys under a new
  `"analysis"` sub-object (or flat, per spec — see Relevant Context).
- All existing `test_export.py` assertions still pass.

### Todo List

1. Add imports in `export.py`:
   ```python
   from downshift.payback import (
       AnalysisCost,
       Payback,
       analysis_cost as _analysis_cost,
       payback as _payback,
   )
   ```

2. Change `summary_payload` signature to accept the new fields. The cleanest
   approach is to read them directly from `report.analysis` and `report.payback`
   (both already `None`-safe).

3. Add the following keys to the returned dict in `summary_payload` (flat, as the
   spec says):
   ```python
   "analysis_cost_total":  _round(report.analysis.total, 4) if report.analysis else None,
   "analysis_model_cost":  _round(report.analysis.model_cost, 4) if report.analysis else None,
   "analysis_judge_cost":  _round(report.analysis.judge_cost, 4) if report.analysis else None,
   "analysis_calls":       (report.analysis.model_calls + report.analysis.judge_calls)
                           if report.analysis else None,
   "payback_hours":        _round(report.payback.hours, 2) if report.payback else None,
   ```

### Relevant Context
- `summary_payload` is at line 106 in `export.py`.
- `report.analysis` and `report.payback` are `None` if `build_report` was called
  without `results_dir` having any results — treat as `None` gracefully.
- The spec says "float or null" for `payback_hours`; `Payback.hours` is already
  `float | None`.

---

## Sub-task 5 — `tests/unit/test_payback.py` (new)

**Status:** `[ ] pending`

### Intent
Unit-test `payback.py` in isolation: math correctness, edge cases, and the
`analysis_cost` function with a synthetic results folder.

### Expected Outcomes
- All tests pass with no network access and no model calls.
- `analysis_cost` tests use `tmp_path` + `runner.append_row` to write real JSONL files.

### Todo List

1. Test `payback` math:
   - Zero monthly savings → `Payback(hours=None)`.
   - Negative monthly savings → `Payback(hours=None)`.
   - Hand-computed case: `total=730.0, monthly=730.0` → `hours=730.0`.
   - Check formula: `hours = total / (monthly / 730)`.

2. Test `format_payback`:
   - `Payback(hours=None)` → `"no payback (no projected savings)"`.
   - `Payback(hours=0.2)` → `"12 minutes"` (ceil(0.2*60)=12).
   - `Payback(hours=1.04)` → `"1.0 hours"`.
   - `Payback(hours=47.9)` → `"47.9 hours"`.
   - `Payback(hours=50.0)` → `"3 days"` (ceil(50/24)=3).

3. Test `analysis_cost` with a tmp results folder:
   - Setup: two models (`"big"`, `"mid"`), one call site (`"app.py::classify"`),
     two eval cases.
   - Write real JSONL rows via `runner.append_row`.
   - Include one row with `error="boom"` → must be skipped.
   - Include one row where model is not in `config.pricing` → must be skipped
     (model_calls unchanged, no crash).
   - Include one judge row whose `judge_model` has no price → falls back to
     baseline price, sets `judge_priced_as` to baseline.
   - Verify `model_calls`, `judge_calls`, `model_cost`, `judge_cost` with
     hand-computed values.

4. Test `audit_cost >= 0` constraint:
   - `analysis_cost(..., audit_cost=-0.01)` raises `ValueError`.
   - `analysis_cost(..., audit_cost=0.0)` is fine.

5. Test `AnalysisCost.total`:
   - Hand-verify `model_cost + judge_cost + audit_cost`.

### Relevant Context
- `runner.append_row(path, row)` creates the file and parent dir automatically.
- `runner.ResultRow` constructor: `(case_id, model, prompt_tokens=…, completion_tokens=…, score=…, passed=…, judge_model=…, error=…)`.
- Use `Config(pricing={...}, models=ModelsConfig(baseline="big"))` for a minimal config.
- `decide.call_cost(price, p, c)` is the same function `analysis_cost` uses.

---

## Sub-task 6 — Extend existing tests

**Status:** `[ ] pending`

### Intent
Extend `tests/unit/test_report.py`, `tests/cli/test_report_cli.py`, and
`tests/unit/test_export.py` to cover the new behaviour.

### Expected Outcomes
- `render_markdown` tests verify section presence/absence.
- CLI test verifies `--audit-cost` and negative value rejection.
- Export test verifies five new keys exist in `summary_payload`.

### Todo List

#### `tests/unit/test_report.py` additions

1. `test_analysis_cost_section_present` — build a report with a real (or mock)
   `AnalysisCost` on `report.analysis`; call `render_markdown`; assert
   `"## What this analysis cost"` is in the output.

2. `test_judge_row_absent_when_no_judge_calls` — set `judge_calls=0` on
   `AnalysisCost`; assert the judge row is not in the markdown.

3. `test_audit_row_only_when_audit_cost_nonzero` — set `audit_cost=0.0`;
   assert `"Assistant audit"` is not in the markdown. Then set `audit_cost=1.5`;
   assert it is present.

4. For `test_analysis_cost_section_absent_when_no_analysis` — set
   `report.analysis = None`; assert section is absent.

#### `tests/cli/test_report_cli.py` additions

5. `test_audit_cost_flag_accepted` — invoke with `--audit-cost 0.5`; assert
   exit code 0 and `"## What this analysis cost"` in output.

6. `test_audit_cost_negative_rejected` — invoke with `--audit-cost -0.01`;
   assert exit code 2.

#### `tests/unit/test_export.py` additions

7. `test_summary_analysis_keys_present` — using the existing `data` fixture,
   assert the five keys (`analysis_cost_total`, `analysis_model_cost`,
   `analysis_judge_cost`, `analysis_calls`, `payback_hours`) are all present
   in the summary payload (value may be `None` or numeric — just assert key exists).

### Relevant Context
- In `test_report.py`, the `_make_report` helper builds `Report` directly.
  The new optional fields default to `None`, so existing helper calls stay unchanged.
  Add overloads / direct construction only in the new tests.
- `test_analysis_cost_section_present` can construct `AnalysisCost` directly
  (`from downshift.payback import AnalysisCost`) and set it on `report = Report(..., analysis=ac)`.
- CLI tests use the real supportdesk fixture in `EXAMPLE`, which has a real
  `results/` folder, so `analysis` will be non-None.
- `test_audit_cost_flag_accepted` calls the real pipeline end-to-end; the
  `"## What this analysis cost"` section must appear.
