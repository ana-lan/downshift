# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Project scaffold: CLI stub, tooling, CI.
- `examples/supportdesk`: demo target app with 8 LLM call sites, 40 synthetic tickets, and a refund policy document.
- `LLMClient` interface with an OpenAI-compatible client and a `FakeLLMClient` for tests.
- `downshift.yaml` config with validation that reports every problem at once.
- `callsites.json` schema with strict validation, shared by the scanner and Bob.
- AST scanner for OpenAI chat/responses and Anthropic messages calls. Resolves model names through constants, imports, env var defaults, dict lookups, and parameter defaults; recovers prompt templates; records callers.
- `downshift scan` command.

### Changed
- CI: bump `actions/checkout` to v5 and `actions/setup-python` to v6 (Node 24).
