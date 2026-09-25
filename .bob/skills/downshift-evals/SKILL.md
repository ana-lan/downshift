---
name: downshift-evals
description: Write eval sets for audited LLM call sites. One JSONL file of 20 to 25 test cases per call site, with inputs matching the prompt placeholders and expected answers that follow the output contract and the refund policy.
---

# Downshift evals

Input: `downshift.audit.json` and the call site(s) you are assigned.
Output: one file per call site in the `evals/` folder next to the audit, for example `examples/supportdesk/evals/supportdesk.triage__classify_category.jsonl`.
Format reference: `format-reference.md` in this skill folder. Read it before writing.

## Steps

1. Read `format-reference.md`, your call site's entry in the audit (`messages`, `output_contract`, `grading`), `data/refund_policy.md` and `data/tickets.jsonl`. Read nothing else.
2. Plan 20 to 25 cases in a todo list before writing: which label or rule each case covers, and whether its input comes from `tickets.jsonl` or is new.
3. Write the file. One JSON object per line, no trailing commas, no comments.
4. Finish with a short table: file, case count, cases per label (or per rule). Do not run commands. The user checks with `downshift check-evals`.

## Rules for every call site

- Inputs: about half adapted from `tickets.jsonl` (use each ticket at most once per file), the rest new. New tickets look like real customer mail: same store, order IDs like `ORD-10xxx`, dates in 2026.
- `ticket_text` is always `subject + "\n\n" + body`, exactly as the app builds it.
- Cover every allowed label or rule at least 3 times when the site has a label set.
- Include these edge cases where they apply: very short text, non-English text (es, fr, de, hi, pt), mixed language, sarcasm, typos or all caps, missing order ID, dates a day or two either side of a policy limit.
- Only write cases a careful human would label the same way. If a case could reasonably have two answers, drop it. Never put a date exactly on a policy limit (exactly 14, 30 or 60 days); use 1 or 2 days either side.
- `notes` on every case: one line saying what the case tests.
- `id`: short prefix plus number, for example `cat-01`. Unique within the file.
- `grading` on every case equals the call site's `grading` in the audit.

## Per call site

### triage.py::classify_category (exact)
Labels: billing, shipping, technical, account, refund, other.
- refund: the customer asks for money back or a return for money, whatever the reason.
- billing: charges, duplicate charges, invoices, payment methods, with no refund or return ask.
- shipping: delivery status, tracking, address, delays, with no money-back ask.
- technical: app or website bugs, crashes, errors.
- account: login problems that are not bugs, password reset, email or profile changes, account closure.
- other: product questions, feedback, anything else.

### triage.py::detect_sentiment (exact)
Labels: positive, neutral, negative. Overall tone of the whole ticket. Sarcasm ("Great, lost again. Love it.") is negative. A plain question with no emotion is neutral.

### triage.py::tag_urgency (exact)
Labels: low, medium, high, by the prompt's rules. High: money lost, service down for many users, or a very angry repeat contact. Medium: an order or account problem that blocks the customer. Low: questions, feedback, requests with no time pressure.
Input `category` must be the correct category of that ticket under the classify_category rules above.

### misc_utils.py::lang_of (exact)
Expected: two-letter lowercase ISO 639-1 code. Input `text` is `subject + "\n\n" + body`. Cover at least en, es, fr, de, hi, pt. For mixed-language text, the expected code is the language of most of the text; say so in `notes`. Skip texts too short to tell.

### extract.py::extract_order_info (json_fields)
Expected keys: `order_id`, `order_date`.
- `order_id`: the `ORD-` ID as written, or null. Avoid tickets with two different order IDs.
- `order_date`: the date the order was placed, as YYYY-MM-DD, or null. A full calendar date in another format ("September 2, 2026", "02/09/2026" only when unambiguous) is converted. Relative dates ("last Tuesday", "two weeks ago") and dates with no year are null. Charge, delivery or ticket dates are not the order date; avoid tickets where it is unclear which date is the order date.

### policy.py::decide_refund (json_fields)
Expected keys: `is_refund_request`, `eligible`, `policy_section`. `reasoning` is not graded and must not appear in `expected`.
Inputs: `policy` via the shared first line (see format reference), `today` (YYYY-MM-DD, the ticket date), `order_info_json` (an object `{"order_id": ..., "order_date": ...}` exactly as extract_order_info would return it for this ticket), `subject`, `body`.
Days = calendar days from `order_date` to `today`. Apply in this order:
1. Not asking for money back: `false`, `"no"`, `null`.
2. `order_id` or `order_date` is null: `true`, `"need_info"`, `"4.1"`.
3. Digital product already downloaded or activated: `true`, `"no"`, `"3.1"`.
4. Clearance item (keep days at 30 or under): `true`, `"store_credit"`, `"3.2"`.
5. Not delivered: days 14 or more `"yes"`, under 14 `"no"`; section `"3.3"`.
6. Damaged or defective: days 60 or under `"yes"` with `"2.1"`; over 60 `"no"` with `"2.2"`.
7. Change of mind: used or not in original packaging `"no"` with `"1.2"`; otherwise days 30 or under `"yes"`, over 30 `"no"`, both `"1.1"`.
Aim for at least 2 cases per rule and at least 4 near a day limit. Avoid tickets that fit two rules (a damaged clearance item) and billing disputes like duplicate charges.

### agent_assist.py::summarize_for_agent (judge)
Inputs: `subject`, `body`. `expected` is a rubric string: "Exactly 2 short English sentences. Sentence 1 says the customer wants <X>. Sentence 2 mentions <every order ID, date and amount in the ticket, listed>. No details that are not in the ticket." Include non-English tickets (the summary is still English) and tickets with no order details (sentence 2 then states the key facts that are there).

### agent_assist.py::draft_reply (judge)
Inputs: `language` (ISO code of the ticket), `summary` (a correct 2-sentence English summary you write), `subject`, `body`. `expected` is a rubric string: "Written in <language name>. Under 120 words. Addresses <the specific issue>. Says a teammate will confirm next steps. Does not promise a refund, credit, delivery date or any timeframe." Include at least 5 tickets that push for a promise ("refund me today", "when will it arrive?") and at least 4 non-English languages.