# Case study: OrchestrAI

Downshift run on a real, public repository that it has never seen before.

| | |
|---|---|
| Repository | https://github.com/samshapley/OrchestrAI |
| License | MIT (Copyright 2023 Samuel Shapley) |
| Commit | `866deaad457de2d9bef2c8fb227cfa52338c31e3` |
| Audited | Sep 26, 2026 |
| Scope | `engineering_pipeline`, the pipeline set in `config.yml` |

OrchestrAI builds software with a pipeline of LLM "modules" (plan, write code, debug,
modify, write a README). No OrchestrAI code is copied into Downshift. The files in
[`docs/case-study/orchestrai/`](case-study/orchestrai/) are Downshift's own outputs; the
audit file quotes OrchestrAI's MIT-licensed prompt text.

## Why this repo

Every module goes through one shared helper, `AI.generate_response` in `ai.py`. The model
comes from YAML (`config.yml` default, overridden per module in the pipeline file) and each
prompt is loaded from `system_prompts/<module>.txt` at runtime. This is the pattern that
blinds static analysis, at real-world scale.

## Static analysis vs Bob

| Metric | ast scan | Bob audit |
|---|---|---|
| Call sites | 1 | 5 |
| Models resolved | 0 | 5 |
| Prompts resolved | 0 | 5 |
| Enriched (purpose, contract, grading) | 0 | 5 |

`downshift scan` finds the single `chat.completions.create` call and correctly reports
that its model and prompt are only known at runtime. The Bob auditor (custom mode +
`downshift-audit` skill, one task, **0.46 Bobcoins**) then:

- **Split the helper into 5 features**, one per module that calls the LLM: code_planner
  (dispatched through `modules.chameleon`), engineer, debugger, modify_codebase and
  create_readme. It confirmed `start_module` only reads user input and makes no LLM call.
- **Resolved every model**: `gpt-4-0613` from `config.yml` for four modules, and a
  per-module override to `gpt-3.5-turbo-16k` for debugger in the pipeline YAML.
- **Rebuilt every prompt** the way `helpers.load_system_prompt` assembles it (shared system
  text + module prompt), and the user message each caller really sends. debugger and
  modify_codebase build their own user message, not the pipeline input.
- **Found the volume multipliers**: debugger retries up to 3 times per run, and
  modify_codebase loops until the user stops, calling debugger again each round.

Files: [scan](case-study/orchestrai/downshift.scan.json),
[audit](case-study/orchestrai/downshift.audit.json).

## Cost projection

```bash
downshift estimate docs/case-study/orchestrai/downshift.audit.json \
  --base docs/case-study/orchestrai/downshift.scan.json \
  -c docs/case-study/orchestrai/downshift.yaml --completion-tokens 1500
```

| Feature | Model | Calls/day | Monthly |
|---|---|---|---|
| engineer | gpt-4-0613 | 200 | $587.70 |
| modify_codebase | gpt-4-0613 | 200 | $575.64 |
| code_planner (chameleon) | gpt-4-0613 | 200 | $566.10 |
| create_readme | gpt-4-0613 | 200 | $560.16 |
| debugger | gpt-3.5-turbo-16k | 600 | $119.39 |
| **Total (Bob view)** | | | **$2,408.99** |
| Static-only view (1 site, model assumed) | gpt-4-0613 | 200 | $540.00 |

Full output: [estimate.md](case-study/orchestrai/estimate.md).

**Findings**

1. **Static analysis alone underestimates this bill about 4.5x.** It sees one call where
   the app makes five (seven with debugger retries).
2. **95% of projected spend is four features on `gpt-4-0613`**, one of OpenAI's most
   expensive legacy models ($30 / $60 per 1M tokens).
3. **The author already downshifted once, by hand.** debugger, the loop-heavy step, runs on
   `gpt-3.5-turbo-16k`. On `gpt-4-0613` it would cost about $1,734/month instead of $119.
   Downshift makes that call per feature, backed by evals, instead of by gut.
4. **The default model needs replacing anyway.** A third-party pricing tracker lists
   `gpt-4-0613` as scheduled for deprecation on 2026-10-23. Downshift's eval step
   (`evalgen`, `run`, `report`) is how you would pick the replacement per feature.

## Assumptions and limitations

- **Projection, not a bill.** Prices are OpenAI list prices checked Sep 26, 2026. Volume
  is assumed: 200 pipeline runs/day, one call per module, debugger at its 3-attempt
  worst case, one modify round per run.
- **Output tokens are assumed** at 1,500 per call because every module has
  `max_tokens: null` and writes whole codebases (the default of 256 would badly
  undercount).
- **Input tokens are a floor.** Only the static system prompts are counted; the runtime
  request, plan and code passed in each call are not.
- **No evals were run on this repo.** That needs paid API calls, and this project has a $0
  budget. So there are no downgrade recommendations here, only the audit and projection.
  The SupportDesk demo shows the full eval loop.
- **One pipeline audited.** The four other pipelines (story, advertising, task,
  translation) use the same helper and pattern; they were left out to keep the Bob task
  small.

## Reproduce

```bash
git clone https://github.com/samshapley/OrchestrAI && cd OrchestrAI
git checkout 866deaad457de2d9bef2c8fb227cfa52338c31e3
downshift scan .
```

The Bob step runs the Downshift Auditor mode with the `downshift-audit` skill on
`.downshift/callsites.json` (see `.bob/` in this repo). Screenshots:
`bob_sessions/downshift_task10_case_study_a.png` to `_d.png`.
