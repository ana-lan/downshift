# AGENTS.md: Ask mode

## Non-obvious documentation context

- **`schema.py` is the shared contract** between the AST scanner and the Bob auditor. Both produce files in the same format.
- **Implemented vs stub commands**: check `cli.py`. Stubs call `_not_implemented()` and exit with code 1.
- **`examples/supportdesk/`** is the demo target and integration fixture, referenced in tests as `SUPPORTDESK`. Its data is synthetic.
- **Integration tests need local Ollama** and are excluded from the default run; use `python -m pytest -m integration`.
- **`downshift.example.yaml`** is the config template users copy to `downshift.yaml`.
- **`bob/` ships with the product**: the Downshift Auditor custom mode and the skills (`downshift-audit`, `downshift-evals`) plus install instructions.
- **`bob_sessions/`** holds screenshots of Bob tasks (hackathon evidence), not code.
- **Architecture overview**: `docs/architecture.md`.
