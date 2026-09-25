# AGENTS.md: Agent (coding) mode

## Non-obvious coding rules

- **Scanner unit tests use `scan_source(textwrap.dedent(src), "app.py")`**, not `scan_module` or temp files.
- **Extend the `_MISSING` sentinel pattern** when adding optional fields to `_field()` in `schema.py`. `None` is a valid value for nullable fields, so it cannot mean "not provided".
- **Call `_reject_unknown()` at the start of every `from_dict`** in `schema.py`; omitting it silently accepts unknown fields.
- **`frozenset`, not `Enum`**, for valid-value sets. Add new values to the existing constants (`MODEL_SOURCES`, `PRODUCERS`, ...).
- **Bob-produced call sites** set `found_by="bob"` on each `CallSite` and `generated_by="bob"` on the `ScanResult`. Every file Bob writes must load cleanly with `ScanResult.load`.
- **`API_PATTERNS`** in `scanner.py` controls which call chains are detected. Add an LLM API by appending a `(suffix_tuple, api_name, needs_model_kwarg)` entry.
- **Call site IDs are stable keys** used in `downshift.yaml` `volume.per_call_site`; changing the ID format is a breaking change.
- **Config dataclasses are `frozen=True`**: construct a new instance instead of mutating.
- **Run checks before finishing**: `ruff format . && ruff check . && mypy src && python -m pytest`. Never bare `pytest`.
