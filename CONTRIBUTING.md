# Contributing

## Setup
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## Checks
```bash
ruff check . && ruff format --check .
mypy src
pytest
```

Integration tests need a local Ollama server: `pytest -m integration`.

## Workflow
Branch per change, open a PR, CI must pass. Use conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `ci:`, `chore:`).
