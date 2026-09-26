# SupportDesk (example app)

A small customer support backend used as Downshift's demo target. It is **deliberately wasteful**: every LLM feature uses the largest model (`qwen2.5:7b`), because that was the safe default and nobody checked.

All data here is synthetic. There are no real customers, names, or contact details.

## LLM features

| # | Feature | Where | Output |
|---|---|---|---|
| 1 | Detect language | `misc_utils.lang_of` | ISO 639-1 code |
| 2 | Classify category | `triage.classify_category` | one of 6 labels |
| 3 | Detect sentiment | `triage.detect_sentiment` (via `llm.ask`) | positive / neutral / negative |
| 4 | Tag urgency | `triage.tag_urgency` (via `llm.ask`) | low / medium / high |
| 5 | Extract order info | `extract.extract_order_info` | JSON: order_id, order_date |
| 6 | Summarize for agent | `agent_assist.summarize_for_agent` | 2 sentences |
| 7 | Draft customer reply | `agent_assist.draft_reply` (async) | free text |
| 8 | Refund decision | `policy.decide_refund` | JSON, applies `data/refund_policy.md` |

The call sites are written the way real code tends to look, so finding them is not a simple text search:

- a direct call with a hardcoded model name
- a shared helper (`llm.ask`) used by two features
- model names from a module variable, an environment variable, and a config dict
- a multi-line f-string prompt
- an async client call
- a call made with `**kwargs` in a vaguely named utils file

## Run it

Needs a local Ollama server with `qwen2.5:7b` pulled.

```bash
cd examples/supportdesk
python -m supportdesk --ticket T001
python -m supportdesk --limit 3
```

Environment variables: `SUPPORTDESK_LLM_BASE_URL` (default `http://localhost:11434/v1`), `SUPPORTDESK_LLM_API_KEY`.

## Models

`models.yaml` (in this directory) controls which model each feature uses. The assignments were chosen from `downshift.report.md`:

| Feature | Model |
|---|---|
| `classify_category` | `qwen2.5:7b` |
| `detect_sentiment` | `qwen2.5:7b` |
| `tag_urgency` | `qwen2.5:7b` |
| `lang_of` | `qwen2.5:1.5b` |
| `extract_order_info` | `qwen2.5:7b` |
| `decide_refund` | `qwen2.5:7b` |
| `summarize_for_agent` | `qwen2.5:7b` |
| `draft_reply` | `qwen2.5:7b` |

To use a different file, set `SUPPORTDESK_MODELS_FILE` to its absolute path before running the app.

## Data

- `data/tickets.jsonl`: 40 synthetic tickets in English, Spanish, French, German, Portuguese, and Hindi, including refund edge cases (outside the window, digital goods, clearance, missing order ID).
- `data/refund_policy.md`: the fictional policy the refund feature applies.
