# AGENTS.md: Plan mode

## Non-obvious architectural constraints

- **`schema.py` is forward-only**: `schema_version` is checked on load and an unsupported version raises. No migration path.
- **`Resolver` is stateful within one `_scan_modules` call** (it holds a `ModuleIndex`); do not share one across `scan_path` invocations.
- **Cross-module resolution is one-pass**: `ModuleIndex` is built once before resolution. Circular imports are not followed.
- **Caller attribution is name-based**: `_attach_callers` matches function names as strings.
- **`ScanResult.write()` overwrites silently**: no merging, no locking.
- **`via`** is not set by the AST scanner. The Bob auditor sets it when it splits a shared helper (e.g. `supportdesk/llm.py::ask`) into one logical call site per feature; `via` holds the helper's call site id.
- **Bob auditor output is a separate file**, e.g. `examples/supportdesk/downshift.audit.json`. It never overwrites the scanner's `.downshift/callsites.json`; `downshift compare` reads both.
- **`bob/` holds shipped mode and skill definitions**, not audit output.
- **Plans stay small**: one job per task, touch only the files named in the request.
