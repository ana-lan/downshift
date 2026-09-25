# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project

Python CLI tool (`downshift`) that finds LLM call sites in Python repos via AST analysis, evaluates cheaper models per call site, and projects cost impact per PR. Package lives in `src/downshift/`, installed editably from `pyproject.toml`. Architecture overview: `docs/architecture.md`.

## Commands

```bash
# Install (dev)
pip install -e ".[dev]"

# Checks before every commit, in this order
ruff format . && ruff check . && mypy src

# All tests (excludes integration by default). Always python -m pytest, never bare pytest.
python -m pytest

# Single file / single test
python -m pytest tests/unit/test_scanner.py
python -m pytest tests/unit/test_scanner.py::test_finds_direct_openai_call

# Integration tests (requires local Ollama)
python -m pytest -m integration
```

## Critical patterns

- **`from __future__ import annotations`** in every source module under `src/downshift/`.
- **Validation collects all problems**: gather issues into a `list[str]`, then raise one exception with all of them. Never raise on the first error. See `parse_config()` and `CallSite.from_dict()`.
- **`_MISSING` sentinel**: `schema.py` uses `_MISSING: Any = object()` instead of `None` as the not-provided signal in `_field()`, because `None` is a valid value for nullable fields.
- **`frozenset` for allowed values**: `MODEL_SOURCES`, `OUTPUT_FORMATS`, `DIFFICULTIES`, `GRADINGS`, `PRODUCERS` are module-level `frozenset[str]`, not enums.
- **Dataclasses only**: all data objects are `@dataclass` (often `frozen=True`). No Pydantic, attrs or TypedDict.

## Testing

- Tests ship in the same commit as the code they cover. Coverage target >= 80% on `src/downshift/`.
- Default test run has no network and no models: use `FakeLLMClient` from `llm.py`. Anything needing Ollama is marked `@pytest.mark.integration`.
- Scanner unit tests use `scanner.scan_source(textwrap.dedent(src), "app.py")` on inline strings. Use `tmp_path` only where real files are needed (CLI tests, temp git repos).
- CLI commands are tested with typer's `CliRunner`. Report markdown uses snapshot tests.

## Code style

- Line length 100. Ruff rules `E, F, I, B, UP, SIM`. Use `zip(..., strict=True)`.
- `typer.Option` / `typer.Argument` are in `extend-immutable-calls` so bugbear won't flag them.
- Every source module has a docstring describing its purpose and who produces/consumes its data.
- Private helpers are prefixed `_`; keep the public API minimal.
- Conventional commits: `feat`, `fix`, `test`, `docs`, `ci`, `chore`.

## Architecture

```
CLI (cli.py) -> resolve_config() -> scan_path() -> ScanResult (schema.py)
                                        |
                           Module / ModuleIndex / Resolver (resolve.py)
                                        |
                            _CallFinder (AST visitor, scanner.py)
```

- `schema.py` is the shared data contract: the AST scanner and the Bob auditor both write and read through it.
- `ScanResult.write()` auto-creates parent directories. Scan output defaults to `<scanned-dir>/.downshift/callsites.json` (gitignored).
- `SKIP_DIRS` in `scanner.py` lists directories the walker never enters (`.venv`, `__pycache__`, `.downshift`, ...).
- Call site IDs are `<rel_path>::<qualname>` (e.g. `app/triage.py::classify`); duplicates get `#2`, `#3`.

## Config (`downshift.yaml`)

- Optional; auto-discovered next to the scanned path. Absent config means all defaults.
- `schema_version: 1` (callsites JSON) and `version: 1` (config YAML) are separate fields.
- Pricing uses `input`/`output` keys in YAML; the dataclass fields are `input_per_mtok`/`output_per_mtok`.
