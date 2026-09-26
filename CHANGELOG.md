# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-09-26

First public release.

### Added
- `downshift scan`: AST scanner for OpenAI (v1 SDK) chat/responses and Anthropic messages calls. Resolves models through constants, imports, env var defaults, dict lookups and parameter defaults; recovers prompt templates; records callers.
- `callsites.json` schema with strict validation, shared by the scanner and Bob.
- `downshift validate` and `downshift compare`: check a Bob audit and compare it with the ast scan.
- IBM Bob integration in `.bob/`: Downshift Auditor and Downshift Eval Writer custom modes with the `downshift-audit` and `downshift-evals` skills.
- Eval sets (`evals/<call_site>.jsonl`), `downshift check-evals`, and `downshift evalgen` to write evals with any configured model.
- `downshift run`: runs each call site's evals on the baseline and candidate models. Resumable, with warm-up and token and latency tracking.
- Scoring by exact match, JSON fields, or an LLM judge, plus `downshift rescore` with a separate hosted judge.
- Decisions (cheapest model that keeps the quality threshold and minimum pass rate), monthly cost projections, and `downshift report`.
- `downshift diff` and a composite GitHub Action (`action.yml`) that comments the projected monthly cost change on every PR, with an optional `fail-above` limit.
- `downshift estimate`: price a scan or audit file, or compare two, without running evals.
- `downshift export` and a demo web app (Next.js, deployed at https://downshift-llm.vercel.app/).
- `examples/supportdesk`: demo app with 8 LLM features, 40 synthetic tickets and a refund policy document.
- Case studies on OrchestrAI (MIT) and mem0 (Apache-2.0).
- End-to-end pipeline smoke test; CI fails below 80% coverage.

### Fixed
- Scanner reads files with a UTF-8 BOM.
- Scanner detects SDK calls that pass the model through `**kwargs` when the SDK is imported.

### Notes
- `diff` and `estimate` are static projections for per-PR deltas, not absolute spend.
- The GitHub Action now installs `downshift>=0.1.0` by default.

## [0.1.0.dev0] - 2026-09-26

### Added
- Pre-release to claim the PyPI name and test Trusted Publishing.

[Unreleased]: https://github.com/ana-lan/downshift/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ana-lan/downshift/compare/v0.1.0.dev0...v0.1.0
[0.1.0.dev0]: https://github.com/ana-lan/downshift/releases/tag/v0.1.0.dev0
