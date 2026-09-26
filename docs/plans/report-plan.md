# Plan: `downshift report` (Phase 6c, Bob task B4)

## Overview

Implement `src/downshift/report.py` and the `downshift report` CLI command.
The module assembles decisions, costs, and quality stats from already-implemented
building blocks into a `Report` dataclass, then renders them as a deterministic
Markdown string. The CLI wires the module to disk and stdout.

No existing modules (`decide.py`, `cost.py`, `config.py`, `evals.py`, `schema.py`,
`runner.py`, example eval or result files) are modified.

---

## Sub-Task 1 — `src/downshift/report.py`: data layer

**Status:** [ ] pending

### Intent
Define the `Report` dataclass and the `build_report` function that assemble all
inputs (scan, config, evals, results) into a single in-memory object ready to render.
This is the pure-data half of the module; no string formatting here.

### Expected Outcomes
- `report.py` exists and passes `ruff` + `mypy`.
- `ReportError` is importable.
- `build_report(scan, config, evals_dir, results_dir)` produces a `Report` with
  correct `sites`, `decisions`, `costs`, `missing_evals`, and derived properties.
- Missing eval files go to `missing_evals`; invalid eval files raise `ReportError`
  (first problem, naming the file).
- `threshold` and `min_pass_rate` keyword args override the config values.
- `NEAR_MISS_MARGIN = 0.05`.

### Todo List
1. Add `from __future__ import annotations` + module docstring.
2. Define `NEAR_MISS_MARGIN = 0.05` and `class ReportError(Exception)`.
3. Define `@dataclass(frozen=True) class Report` with all required fields and properties:
   - `downgraded`: decisions where `action == DOWNGRADE`.
   - `below_floor`: decisions where `baseline_below_floor` is True.
   - `near_misses`: (site_id, CandidateCheck) pairs for failed checks whose ratio is in
     `[threshold - NEAR_MISS_MARGIN, threshold)` and `pass_rate >= min_pass_rate`.
   - `missing_data`: decisions whose baseline stats are missing or `not complete`.
4. Implement `build_report`:
   - Sort call sites by `site.id`.
   - For each site: check eval file existence → `missing_evals`; load with `load_eval_set`;
     any `EvalError` → `ReportError(f"{path}: {problems[0]}")`.
   - Call `load_site_stats`, `decide_site`, `cost_summary`.
   - Collect `sites`, `decisions`, `costs`, `missing_evals`, propagate threshold/min_pass_rate.

### Relevant Context
- [`src/downshift/decide.py`](src/downshift/decide.py): `load_site_stats`, `decide_site`,
  `KEEP`, `DOWNGRADE`, `Decision`, `CandidateCheck`, `ModelStats`.
- [`src/downshift/cost.py`](src/downshift/cost.py): `cost_summary`, `CostSummary`.
- [`src/downshift/config.py`](src/downshift/config.py): `Config`, `resolve_config`.
- [`src/downshift/evals.py`](src/downshift/evals.py): `load_eval_set`, `slug_for`,
  `EVAL_SUFFIX`, `EvalError`.
- [`src/downshift/schema.py`](src/downshift/schema.py): `ScanResult`, `CallSite`.
- `decide_site` signature: `(site_id, stats, *, baseline, candidates, prices, threshold, min_pass_rate)`.
- `cost_summary` signature: `(decisions, prices, volume)`.

---

## Sub-Task 2 — `src/downshift/report.py`: `render_markdown`

**Status:** [ ] pending

### Intent
Implement `render_markdown(report) -> str` that turns a `Report` into the exact
Markdown layout defined in the spec. All formatting rules must be followed precisely
so the snapshot test can pass without manual editing.

### Expected Outcomes
- Output is deterministic (no dates, no version numbers, no absolute paths).
- Output ends with exactly one newline character.
- Every section follows the spec layout (Summary table, Decisions table, Quality table,
  Needs attention, Details).
- Formatting rules:
  - Money: `f"${x:,.2f}"`; unknown → `n/a`.
  - Savings %: one decimal place.
  - Pass rates: no decimal places (`:.0%`).
  - Rule sentence drops "and pass at least N%…" clause when `min_pass_rate == 0`.
  - Unknown-cost footnote printed only when `costs.unknown` is non-empty.
  - Decisions table pass rate column: downgrade → `baseline% -> chosen%`; keep → `baseline%`; no baseline → `n/a`.
  - Quality table: bold the cell for the model the site ends up on; `n/a` when no results;
    `, judge X.X/5` suffix when `avg_judge_score` is not None; `, N errors` when errors > 0.
    Judge footer sentence only when at least one site uses judge grading.
  - Needs attention: only print subsections with entries; `Nothing needs attention.` if all empty.
    Floor subsection omitted when `min_pass_rate == 0`.
    `missing_evals` and `missing_data` share the Missing data subsection (evals first with
    "no eval set, not decided."; data decisions use `decision.reason`).
  - Details: one `<details>` block per decided site; blank line after `<summary>` and before
    `</details>`; first bullet `Decision: {reason}`; then one bullet per `CandidateCheck`.

### Todo List
1. Implement `_fmt_money(x: float | None) -> str` helper.
2. Implement `_fmt_pct(x: float | None) -> str` helper (one decimal, e.g. `5.3%`).
3. Implement `render_markdown(report) -> str` building each section with a list of lines
   joined at the end, ensuring exactly one trailing newline.
4. Summary table section.
5. Decisions table section.
6. Quality per model section (all models in `config.models.all_models` order).
7. Needs attention section (with conditional subsections).
8. Details section (one `<details>` per decided site).

### Relevant Context
- Spec section "Markdown layout" in [`docs/specs/report.md`](docs/specs/report.md): the
  exact column headers and cell formats are the ground truth.
- `CostSummary.savings_pct` is `None` when `before_monthly == 0`.
- `ModelStats.complete` and `ModelStats.avg_judge_score` from
  [`src/downshift/decide.py`](src/downshift/decide.py).
- `RunSummary` fields: `passed`, `scored`, `errors` from
  [`src/downshift/runner.py`](src/downshift/runner.py).

---

## Sub-Task 3 — `tests/unit/test_report.py`

**Status:** [ ] pending

### Intent
Unit tests for `build_report` and `render_markdown` using synthetic data (following the
`mk` / `decide` helper pattern from `test_decide.py`) plus one real `build_report` call
on `examples/supportdesk`. Target 100% coverage of `report.py`.

### Expected Outcomes
- All cases listed in the spec's Tests section are covered.
- Tests are self-contained (no network, no Ollama).
- `build_report` on the real SupportDesk example runs without error.

### Todo List
Cover these cases (one or more test functions each):

1. **Downgrade and keep rows** in the Decisions table (pass rate formatting, model column).
2. **Money formatting**: `$1,234.56`, zero savings, `n/a` unknown cost.
3. **Unknown-cost sentence** included/excluded.
4. **`n/a` pass rate** cell when no baseline stats.
5. **Bold chosen model** in Quality table.
6. **Judge suffix** (`judge X.X/5`) and judge footer sentence present/absent.
7. **Errors suffix** (`, N errors`) in Quality table cell.
8. **Near-miss boundaries**: ratio exactly at `threshold - 0.05` is in; just below is out;
   passing checks are excluded; below-floor candidates are excluded.
9. **Floor subsection hidden** when `min_pass_rate == 0`.
10. **"Nothing needs attention."** when all attention subsections are empty.
11. **Missing eval file** → `missing_evals` populated, appears in report.
12. **Invalid eval file** → `ReportError` raised (with file name and first problem).
13. **Exactly one trailing newline** in the output.
14. **`threshold` and `min_pass_rate` overrides** change decisions vs config values.
15. **Real SupportDesk `build_report`** runs to completion without error.

### Relevant Context
- Helper pattern: [`tests/unit/test_decide.py`](tests/unit/test_decide.py) `mk()` and
  `decide()` builder functions.
- SupportDesk fixture: `EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "supportdesk"`.
- Use `tmp_path` for fake eval/results dirs in unit tests that need files.
- `EvalError` for the invalid-file test.

---

## Sub-Task 4 — `tests/snapshots/supportdesk_report.md` + `tests/unit/test_report_snapshot.py`

**Status:** [ ] pending

### Intent
Snapshot test: run `render_markdown` against the real SupportDesk data and compare to
a committed golden file. The `UPDATE_SNAPSHOTS=1` env var regenerates the file instead
of failing.

### Expected Outcomes
- `tests/snapshots/supportdesk_report.md` exists and contains the actual SupportDesk report.
- `test_report_snapshot.py` passes on a clean run (snapshot matches output).
- With `UPDATE_SNAPSHOTS=1`, the test rewrites the snapshot and passes.

### Todo List
1. Create `tests/snapshots/` directory (it doesn't exist yet).
2. Write `tests/unit/test_report_snapshot.py` with a single test that:
   - Calls `build_report` on the real SupportDesk audit, evals, and results.
   - Calls `render_markdown`.
   - When `UPDATE_SNAPSHOTS=1`: writes result to snapshot file, asserts True.
   - Otherwise: reads snapshot file and asserts output equals it.
3. Generate the initial `tests/snapshots/supportdesk_report.md` by running the test
   once with `UPDATE_SNAPSHOTS=1` (agent mode will do this).

### Relevant Context
- SupportDesk audit file: `examples/supportdesk/downshift.audit.json`.
- SupportDesk evals dir: `examples/supportdesk/evals/`.
- SupportDesk results dir: `examples/supportdesk/results/`.
- SupportDesk config: `examples/supportdesk/downshift.yaml`.

---

## Sub-Task 5 — `tests/cli/test_report_cli.py` + CLI wiring in `cli.py` + `test_cli_help.py`

**Status:** [ ] pending

### Intent
Wire up the `report` CLI command (replacing the stub) and test it via `CliRunner`.

### Expected Outcomes
- `downshift report --callsites FILE` prints Markdown to stdout and exits 0.
- `downshift report --callsites FILE --out PATH` writes the file, prints the summary
  line, and exits 0.
- `--threshold 0.9` overrides the config threshold and changes output.
- Missing callsites file → exit 2.
- Invalid `--threshold` (e.g. `0` or `1.5`) → exit 2.
- `report` is removed from `NOT_IMPLEMENTED` in `test_cli_help.py`.

### Todo List
1. In `cli.py`: replace the stub `report()` command with the full implementation:
   - Parameters: `--callsites FILE`, `--evals DIR`, `--results DIR`, `-c CONFIG`,
     `--threshold FLOAT (click.FloatRange(0,1,min_open=True))`,
     `--min-pass-rate FLOAT (click.FloatRange(0,1))`, `--out FILE`.
   - Default dirs: `evals/` and `results/` next to `--callsites`.
   - Config via `resolve_config`.
   - On error (`SchemaError`, `ConfigError`, `ReportError`) → `_fail(str(exc))` → exit 2.
   - Without `--out`: `click.echo(render_markdown(report))`.
   - With `--out`: write file (create parent dirs), print summary line.
2. In `tests/cli/test_cli_help.py`: remove `"report"` from `NOT_IMPLEMENTED`.
3. Write `tests/cli/test_report_cli.py` with `CliRunner` tests listed above.

### Relevant Context
- Existing CLI pattern: `rescore` command in [`src/downshift/cli.py`](src/downshift/cli.py)
  (same `--callsites`, `--evals`, `--results`, `-c` pattern).
- typer uses `typer.Option` with `click.FloatRange` via `min` kwarg for range validation;
  check the existing CLI source for exact syntax used here.
- `_fail` exits with code 2 per [`src/downshift/cli.py`](src/downshift/cli.py:69).
- Summary line format: `Wrote <path>: downgraded N of M call sites, projected savings $X/month (Y%).`
  When savings % is None (zero baseline cost), omit the percentage.
- `test_cli_help.py` `NOT_IMPLEMENTED` list: [`tests/cli/test_cli_help.py`](tests/cli/test_cli_help.py:9).
