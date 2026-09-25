# Eval file format

One file per call site: `<slug>.jsonl` in the `evals/` folder next to `downshift.audit.json`.

Slug: take the call site id, drop `.py`, replace `/` with `.` and `::` with `__`.
`supportdesk/triage.py::classify_category` becomes `supportdesk.triage__classify_category.jsonl`.

## Lines

Each line is one JSON object. Blank lines are ignored.

Optional first line, only for long inputs that every case shares:

```json
{"shared": {"policy": {"file": "../data/refund_policy.md"}}}
```

A shared value is any JSON value, or `{"file": "path"}` relative to the eval file. A case's own inputs override shared ones.

Every other line is a case with exactly these keys:

| key | type | rule |
|---|---|---|
| `id` | string | unique in the file |
| `inputs` | object | keys are exactly the prompt's `{placeholders}`, minus shared ones |
| `expected` | depends on grading | see below |
| `grading` | string | same as the call site's `grading` in the audit |
| `notes` | string | what this case tests |

## expected by grading

- `exact`: a string. When the output contract says "from the set {...}", it must be one of those labels, spelled exactly.
- `json_fields`: an object whose keys are exactly the fields after "Graded fields:" in the output contract. No other keys.
- `judge`: a rubric string a grader can check point by point.

## Inputs per call site

| file | inputs |
|---|---|
| supportdesk.triage__classify_category | ticket_text |
| supportdesk.triage__detect_sentiment | ticket_text |
| supportdesk.triage__tag_urgency | category, ticket_text |
| supportdesk.misc_utils__lang_of | text |
| supportdesk.extract__extract_order_info | ticket_text |
| supportdesk.policy__decide_refund | policy (shared), today, order_info_json, subject, body |
| supportdesk.agent_assist__summarize_for_agent | subject, body |
| supportdesk.agent_assist__draft_reply | language, summary, subject, body |

## Examples

```json
{"id": "cat-01", "inputs": {"ticket_text": "Charged twice\n\nI was charged twice for ORD-10733. Please fix it."}, "expected": "billing", "grading": "exact", "notes": "duplicate charge, no refund ask"}
{"id": "ext-01", "inputs": {"ticket_text": "Late order\n\nOrder ORD-10588 placed on August 28, 2026 hasn't arrived."}, "expected": {"order_id": "ORD-10588", "order_date": "2026-08-28"}, "grading": "json_fields", "notes": "written-out date converted"}
{"id": "ref-01", "inputs": {"today": "2026-09-19", "order_info_json": {"order_id": "ORD-10588", "order_date": "2026-08-28"}, "subject": "Where is my package??", "body": "Order ORD-10588 placed on 2026-08-28 still hasn't arrived. I want my money back."}, "expected": {"is_refund_request": true, "eligible": "yes", "policy_section": "3.3"}, "grading": "json_fields", "notes": "not delivered after 22 days"}
```