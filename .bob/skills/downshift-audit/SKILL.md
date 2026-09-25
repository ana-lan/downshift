---
name: downshift-audit
description: Audit LLM call sites from a downshift scan file. Resolve models and prompts the static scanner missed, split shared LLM helpers into one call site per feature, add purpose, output_contract, difficulty and grading, and write downshift.audit.json.
---

# Downshift audit

Input: a scan file written by `downshift scan`, given as an @mention (for example `examples/supportdesk/downshift.scan.json`).
Output: `downshift.audit.json` in the same folder as the scan file.
Field reference: `schema-reference.md` in this skill folder. Read it before writing.

## Steps

1. Read the scan file and `schema-reference.md`. Do not re-scan the repo.
2. Build a worklist. A call site needs inspection if any of these is true:
   - `model.value` is null, or `model.source` is `kwargs`, `env`, `dynamic` or `missing`
   - `messages` is null, or any message has `resolved: false`
   - it has 2 or more `callers` and its prompt is built by the callers
3. For each worklist call site, read only its own file and the files of its `callers`. Read nothing else.
4. Resolve models. Set `model.value` to the real model string, `model.source` to `manual`, keep `expression` and `env_var`, set `defined_in` to the file where the model string lives, set `found_by` to `bob`, and add a note starting with `Bob:` that says how you resolved it.
5. Resolve prompts. Set `messages` to the full list as it is sent to the model. Write runtime values as `{placeholder}` using the variable name from the code. Set `resolved: true` on each message. Add a `Bob:` note.
6. Split shared helpers. If one helper serves several features with different prompts, replace the helper entry with one entry per calling feature:
   - `id`: the caller's id in the form `path/to/file.py::qualname`
   - `file`, `line`, `end_line`, `function`: the caller's call to the helper
   - `via`: the helper's id from the scan file
   - `api`, `model`, `is_async`, `temperature`, `max_tokens`: from the helper call, as this caller uses it
   - `messages`: the prompt this caller sends
   - `callers`: empty list. `found_by`: `bob`. Add a `Bob:` note naming the helper.
   The helper does not stay in the output as its own entry.
7. Enrich every call site, including ones that were already resolved: `purpose`, `output_contract`, `difficulty`, `grading` (rules below).
8. Write `downshift.audit.json`. Copy every top-level key and value from the scan file unchanged, except set `generated_by` to `bob` and replace `call_sites` with your list. Include every CallSite field on every entry. Sort call sites by `id`.
9. Finish with a short table: id, model, what changed (resolved model, resolved prompt, split from helper, metadata only). Do not run commands. The user validates with `downshift validate`.

## Enrichment rules

- `purpose`: one sentence naming the product feature. Example: "Classify a support ticket into one of five categories."
- `output_contract`: concrete, checkable rules taken from the prompt and from the code that parses the output. Exact JSON keys and allowed values, allowed labels, length limits, forbidden content. Evals will test exactly these rules.
- `difficulty`: `easy` for a single label or short extraction; `medium` for structured JSON or tightly constrained short text; `hard` for open-ended writing or policy reasoning.
- `grading`: `exact` for a single label or short fixed answer; `json_fields` when `output_format` is `json`; `judge` for free text.

## Hard rules

- Never edit source code or any file other than `downshift.audit.json`.
- Never invent. If something cannot be determined from the code, leave it null, keep the original `source`, and add a `Bob:` note saying what is missing.
- Use only the fields in `schema-reference.md`. Unknown fields fail validation.
- Keep the ids of call sites you do not split exactly as they are. They are keys in `downshift.yaml`.
- Call sites that were already fully resolved keep `found_by: "ast"`. Only add the enrichment fields.
