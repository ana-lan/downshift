# Spec: analysis cost and payback in `downshift report`

## Why
The report shows monthly savings but not what it cost to find them. Add a one-time
"analysis cost" (eval model calls + judge calls, priced from the config) and a payback
time, so users can see the tool pays for itself.

## Scope (files)
- NEW `src/downshift/payback.py`
- EDIT `src/downshift/report.py` (Report field, build_report, render_markdown)
- EDIT `src/downshift/cli.py` (`report` gets `--audit-cost`)
- EDIT `src/downshift/export.py` (summary gets the new fields)
- NEW `tests/unit/test_payback.py`; extend existing report, export and CLI tests
- Do NOT edit the report snapshot file. The user regenerates it.

## payback.py
Constants:
- `JUDGE_EXTRA_PROMPT_TOKENS = 150`  (rubric + instructions around the case)
- `JUDGE_COMPLETION_TOKENS = 200`    (matches the judge's max_tokens default in scorer.py)

Dataclasses (frozen):
- `AnalysisCost`: `model_calls: int`, `model_cost: float`, `judge_calls: int`,
  `judge_cost: float`, `judge_model: str | None`, `judge_priced_as: str | None`,
  `audit_cost: float` (default 0.0). Property `total` = model_cost + judge_cost + audit_cost.
- `Payback`: `hours: float | None` (None when monthly savings <= 0).

Functions:
- `analysis_cost(sites, results_dir, config, *, audit_cost=0.0) -> AnalysisCost`
  - For every call site and every model with a results file, read rows with the EXISTING
    results loader in `runner.py` (last row per case wins). Do not write a new JSONL parser.
  - Model cost: for each row, `decide.call_cost(price, row.prompt_tokens, row.completion_tokens)`
    with `config.price_for(row_model)`. Count one call per row. Skip models with no price
    (do not crash), and skip rows with an error.
  - Judge cost: for each row with `judge_model` set, estimate
    prompt = row.prompt_tokens + row.completion_tokens + JUDGE_EXTRA_PROMPT_TOKENS,
    completion = JUDGE_COMPLETION_TOKENS. Price with the judge model's price if it is in
    `config.pricing`, otherwise with the baseline model's price, and set `judge_priced_as`
    to the model whose price was used.
  - `audit_cost` is a user-supplied one-time amount in USD (e.g. what an AI-assistant audit
    cost). Must be >= 0.
- `payback(total_one_time: float, monthly_savings: float) -> Payback`
  - hours = total / (monthly_savings / cost.HOURS_PER_MONTH). None if monthly_savings <= 0.
- `format_payback(p: Payback) -> str`
  - None -> "no payback (no projected savings)"
  - < 1 hour -> "N minutes" (round up, minimum 1)
  - < 48 hours -> "X.Y hours" (one decimal)
  - otherwise -> "N days" (round up)

## report.py
- `Report` gets `analysis: AnalysisCost | None` and `payback: Payback | None`.
- `build_report` computes both from the same results folder and config it already uses,
  and accepts `audit_cost: float = 0.0`.
- `render_markdown` adds this section right after the Summary section:

```
## What this analysis cost

| | One-time cost |
|---|---:|
| Eval model calls (N) | $X |
| Judge calls, estimated (M) | $Y |
| Assistant audit | $Z |        <- only when audit_cost > 0
| **Total** | **$T** |

Pays back in **<format_payback>** of projected savings.

> Priced at the same illustrative prices as the rest of the report. Judge tokens are not
> recorded, so each judge call is estimated as (case prompt + output + 150) tokens in and
> 200 out, priced as `<judge_priced_as>`. Retries and warm-up calls are not counted.
> Local Ollama runs cost $0 in practice.
```
- Money uses the existing `_fmt_money`. With M = 0, drop the judge row and the judge sentence.

## cli.py
- `downshift report --audit-cost USD` (float, min 0, default 0). Help: "One-time cost of an
  assistant audit, in USD, added to the analysis cost."

## export.py
- The summary JSON gets `analysis_cost_total`, `analysis_model_cost`, `analysis_judge_cost`,
  `analysis_calls` (model + judge), `payback_hours` (float or null).

## Tests
- payback math with hand-computed values; format_payback for None, 0.2 h, 1.04 h, 47.9 h, 50 h.
- analysis_cost with a tmp results folder: two models, one judge-graded site, one row with an
  error (skipped), a judge model with no price (priced as baseline), a model with no price (skipped).
- render_markdown: section present, judge row absent when there are no judge calls, audit row
  only when audit_cost > 0.
- CLI: `--audit-cost 0.5` shows the audit row; negative value is rejected.
- export: new keys present.
- Follow repo standards: ruff (E,F,I,B,UP,SIM, line length 100), mypy clean, `zip(strict=True)`,
  no network, FakeLLMClient not needed.
