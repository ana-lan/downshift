# downshift.audit.json field reference

Same format as the scan file. Top-level keys: copy them from the scan file; set `generated_by` to `bob`.

## CallSite (every field required on every entry)

| Field | Type | Notes |
|---|---|---|
| id | string | `path/to/file.py::qualname`, duplicates get `#2` |
| file | string | relative POSIX path |
| line | int | >= 1 |
| end_line | int or null | |
| function | string | qualified name, `<module>` for top level |
| api | string | copy from the scan file, never invent new values |
| model | ModelRef | below |
| is_async | bool | |
| messages | list of PromptMessage, or null | |
| output_format | string | `text` or `json` |
| temperature | number or null | |
| max_tokens | int or null | |
| via | string or null | id of the shared helper, only on split entries |
| callers | list of strings | call site ids |
| notes | list of strings | Bob notes start with `Bob:` |
| purpose | string or null | |
| output_contract | string or null | |
| difficulty | string or null | `easy`, `medium`, `hard` |
| grading | string or null | `exact`, `json_fields`, `judge` |
| found_by | string | `ast`, `bob`, `manual` |

## ModelRef

| Field | Type | Notes |
|---|---|---|
| value | string or null | the model name |
| source | string | `literal`, `constant`, `env_default`, `env`, `dict_lookup`, `parameter_default`, `kwargs`, `missing`, `dynamic`, `manual` (use `manual` when Bob resolves it) |
| expression | string | source text of the model argument, keep as scanned |
| env_var | string or null | |
| defined_in | string or null | file where the model string lives |

## PromptMessage

| Field | Type | Notes |
|---|---|---|
| role | string | `system`, `user`, `assistant` |
| content | string | template text, runtime values as `{placeholder}` |
| resolved | bool | true once Bob has resolved it |

## Example: one entry split from a shared helper

```json
{
  "id": "app/billing.py::summarize_invoice",
  "file": "app/billing.py",
  "line": 42,
  "end_line": 45,
  "function": "summarize_invoice",
  "api": "openai.chat.completions",
  "model": {
    "value": "gpt-4o-mini",
    "source": "manual",
    "expression": "MODEL",
    "env_var": null,
    "defined_in": "app/llm.py"
  },
  "is_async": false,
  "messages": [
    {"role": "system", "content": "Summarize the invoice in one sentence.", "resolved": true},
    {"role": "user", "content": "{invoice_text}", "resolved": true}
  ],
  "output_format": "text",
  "temperature": 0.0,
  "max_tokens": null,
  "via": "app/llm.py::complete",
  "callers": [],
  "notes": ["Bob: split from shared helper app/llm.py::complete; this caller builds its own prompt."],
  "purpose": "Summarize an invoice for the billing dashboard.",
  "output_contract": "One sentence, under 30 words, mentions the total amount, no speculation.",
  "difficulty": "easy",
  "grading": "judge",
  "found_by": "bob"
}
```
