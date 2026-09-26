# Downshift report

> Costs are projections: measured tokens per call x illustrative prices x assumed volume
> from the config. They are not a bill.

## Summary

| | Monthly cost |
|---|---:|
| Before (all on `qwen2.5:7b`) | $3,137.26 |
| After | $2,973.38 |
| Savings | $163.88 (5.2%) |

Downgraded **1 of 8** call sites.

Rule: a cheaper model must keep at least 95% of the baseline pass rate and pass at least 80% of cases on its own. Decisions use pass rate, not mean score.

## Decisions

| Call site | Grading | Decision | Model | Pass rate | Before / month | After / month |
|---|---|---|---|---|---:|---:|
| `supportdesk/agent_assist.py::draft_reply` | judge | keep | `qwen2.5:7b` | 14% | $531.75 | $531.75 |
| `supportdesk/agent_assist.py::summarize_for_agent` | judge | keep | `qwen2.5:7b` | 59% | $400.64 | $400.64 |
| `supportdesk/extract.py::extract_order_info` | json_fields | keep | `qwen2.5:7b` | 95% | $335.00 | $335.00 |
| `supportdesk/misc_utils.py::lang_of` | exact | downgrade | `qwen2.5:1.5b` | 91% -> 91% | $174.34 | $10.46 |
| `supportdesk/policy.py::decide_refund` | json_fields | keep | `qwen2.5:7b` | 40% | $1,212.72 | $1,212.72 |
| `supportdesk/triage.py::classify_category` | exact | keep | `qwen2.5:7b` | 84% | $140.40 | $140.40 |
| `supportdesk/triage.py::detect_sentiment` | exact | keep | `qwen2.5:7b` | 91% | $141.34 | $141.34 |
| `supportdesk/triage.py::tag_urgency` | exact | keep | `qwen2.5:7b` | 73% | $201.07 | $201.07 |

## Quality per model

| Call site | `qwen2.5:7b` | `qwen2.5:1.5b` | `qwen2.5:0.5b` |
|---|--- | --- | ---|
| `supportdesk/agent_assist.py::draft_reply` | **3/22 (14%), judge 2.8/5** | 1/22 (5%), judge 2.1/5 | 0/22 (0%), judge 1.6/5 |
| `supportdesk/agent_assist.py::summarize_for_agent` | **13/22 (59%), judge 3.6/5** | 0/22 (0%), judge 1.1/5 | 1/22 (5%), judge 1.4/5 |
| `supportdesk/extract.py::extract_order_info` | **20/21 (95%)** | 17/21 (81%) | 15/21 (71%) |
| `supportdesk/misc_utils.py::lang_of` | 20/22 (91%) | **20/22 (91%)** | 18/22 (82%) |
| `supportdesk/policy.py::decide_refund` | **10/25 (40%)** | 7/25 (28%) | 0/25 (0%) |
| `supportdesk/triage.py::classify_category` | **21/25 (84%)** | 18/25 (72%) | 12/25 (48%) |
| `supportdesk/triage.py::detect_sentiment` | **20/22 (91%)** | 14/22 (64%) | 18/22 (82%) |
| `supportdesk/triage.py::tag_urgency` | **16/22 (73%)** | 9/22 (41%) | 6/22 (27%) |

Judge-graded cases pass at 4/5 or higher; judge scores are averages on a 1 to 5 scale.

## Needs attention

### Baseline below the floor

- `supportdesk/agent_assist.py::draft_reply`: baseline passes 14% of cases, below the 80% floor.  Improve the prompt or model before downgrading.
- `supportdesk/agent_assist.py::summarize_for_agent`: baseline passes 59% of cases, below the 80% floor.  Improve the prompt or model before downgrading.
- `supportdesk/policy.py::decide_refund`: baseline passes 40% of cases, below the 80% floor.  Improve the prompt or model before downgrading.
- `supportdesk/triage.py::tag_urgency`: baseline passes 73% of cases, below the 80% floor.  Improve the prompt or model before downgrading.

### Near misses

- `supportdesk/misc_utils.py::lang_of`: `qwen2.5:0.5b` keeps 90% of the baseline pass rate (needs 95%).
- `supportdesk/triage.py::detect_sentiment`: `qwen2.5:0.5b` keeps 90% of the baseline pass rate (needs 95%).

## Details

<details>
<summary><code>supportdesk/agent_assist.py::draft_reply</code>: keep <code>qwen2.5:7b</code></summary>

- Decision: no cheaper model passed the checks
- `qwen2.5:1.5b`: keeps 33% of baseline quality, needs 95%
- `qwen2.5:0.5b`: keeps 0% of baseline quality, needs 95%

</details>
<details>
<summary><code>supportdesk/agent_assist.py::summarize_for_agent</code>: keep <code>qwen2.5:7b</code></summary>

- Decision: no cheaper model passed the checks
- `qwen2.5:1.5b`: keeps 0% of baseline quality, needs 95%
- `qwen2.5:0.5b`: keeps 8% of baseline quality, needs 95%

</details>
<details>
<summary><code>supportdesk/extract.py::extract_order_info</code>: keep <code>qwen2.5:7b</code></summary>

- Decision: no cheaper model passed the checks
- `qwen2.5:1.5b`: keeps 85% of baseline quality, needs 95%
- `qwen2.5:0.5b`: keeps 75% of baseline quality, needs 95%

</details>
<details>
<summary><code>supportdesk/misc_utils.py::lang_of</code>: downgrade to <code>qwen2.5:1.5b</code></summary>

- Decision: keeps 100% of baseline quality and costs less
- `qwen2.5:1.5b`: keeps 100% of baseline quality and costs less
- `qwen2.5:0.5b`: keeps 90% of baseline quality, needs 95%

</details>
<details>
<summary><code>supportdesk/policy.py::decide_refund</code>: keep <code>qwen2.5:7b</code></summary>

- Decision: no cheaper model passed the checks
- `qwen2.5:1.5b`: keeps 70% of baseline quality, needs 95%
- `qwen2.5:0.5b`: keeps 0% of baseline quality, needs 95%

</details>
<details>
<summary><code>supportdesk/triage.py::classify_category</code>: keep <code>qwen2.5:7b</code></summary>

- Decision: no cheaper model passed the checks
- `qwen2.5:1.5b`: keeps 86% of baseline quality, needs 95%
- `qwen2.5:0.5b`: keeps 57% of baseline quality, needs 95%

</details>
<details>
<summary><code>supportdesk/triage.py::detect_sentiment</code>: keep <code>qwen2.5:7b</code></summary>

- Decision: no cheaper model passed the checks
- `qwen2.5:1.5b`: keeps 70% of baseline quality, needs 95%
- `qwen2.5:0.5b`: keeps 90% of baseline quality, needs 95%

</details>
<details>
<summary><code>supportdesk/triage.py::tag_urgency</code>: keep <code>qwen2.5:7b</code></summary>

- Decision: no cheaper model passed the checks
- `qwen2.5:1.5b`: keeps 56% of baseline quality, needs 95%
- `qwen2.5:0.5b`: keeps 37% of baseline quality, needs 95%

</details>
