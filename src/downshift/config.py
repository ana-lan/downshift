"""Load and validate downshift.yaml."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILENAME = "downshift.yaml"
SUPPORTED_VERSION = 1


class ConfigError(Exception):
    """Raised when a config file is missing or invalid. The message lists every problem."""


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str = "http://localhost:11434/v1"
    api_key_env: str | None = None

    def api_key(self) -> str:
        if self.api_key_env is None:
            return "not-needed"
        value = os.environ.get(self.api_key_env)
        if not value:
            raise ConfigError(
                f"environment variable {self.api_key_env} is not set (provider.api_key_env)"
            )
        return value


@dataclass(frozen=True)
class ModelsConfig:
    baseline: str = "qwen2.5:7b"
    candidates: tuple[str, ...] = ("qwen2.5:1.5b", "qwen2.5:0.5b")
    judge: str | None = None

    @property
    def judge_model(self) -> str:
        return self.judge or self.baseline

    @property
    def all_models(self) -> tuple[str, ...]:
        return (self.baseline, *self.candidates)


@dataclass(frozen=True)
class ModelPrice:
    """Price in USD per one million tokens."""

    input_per_mtok: float
    output_per_mtok: float
    tier: str | None = None

    def cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (
            prompt_tokens * self.input_per_mtok + completion_tokens * self.output_per_mtok
        ) / 1_000_000


@dataclass(frozen=True)
class VolumeConfig:
    default_per_day: int = 1000
    per_call_site: Mapping[str, int] = field(default_factory=dict)

    def calls_per_day(self, call_site_id: str) -> int:
        return self.per_call_site.get(call_site_id, self.default_per_day)


@dataclass(frozen=True)
class ScanConfig:
    include: tuple[str, ...] = ("*.py",)
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class Config:
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    quality_threshold: float = 0.95
    pricing: Mapping[str, ModelPrice] = field(default_factory=dict)
    volume: VolumeConfig = field(default_factory=VolumeConfig)
    scan: ScanConfig = field(default_factory=ScanConfig)
    source: Path | None = None

    def price_for(self, model: str) -> ModelPrice:
        try:
            return self.pricing[model]
        except KeyError:
            where = f" in {self.source}" if self.source else ""
            raise ConfigError(
                f"no pricing for model {model!r}{where}; add it under 'pricing'"
            ) from None


# --- loading ------------------------------------------------------------------


def load_config(path: Path) -> Config:
    """Read and validate a config file."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
    return parse_config(data, source=path)


def find_config(start: Path) -> Path | None:
    """Return downshift.yaml next to start (a directory or a file), if it exists."""
    directory = start if start.is_dir() else start.parent
    candidate = directory / CONFIG_FILENAME
    return candidate if candidate.is_file() else None


def resolve_config(explicit: Path | None, search_from: Path) -> Config:
    """Use the explicit config if given, else a discovered one, else defaults."""
    if explicit is not None:
        return load_config(explicit)
    found = find_config(search_from)
    return load_config(found) if found else Config()


# --- validation ---------------------------------------------------------------

_TOP_LEVEL_KEYS = {
    "version",
    "provider",
    "models",
    "quality_threshold",
    "pricing",
    "volume",
    "scan",
}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _section(data: dict[str, Any], name: str, problems: list[str]) -> dict[str, Any] | None:
    value = data.get(name)
    if value is None:
        return {}
    if not isinstance(value, dict):
        problems.append(f"{name}: must be a mapping")
        return None
    return value


def _check_keys(
    mapping: dict[str, Any], allowed: set[str], prefix: str, problems: list[str]
) -> None:
    for key in mapping:
        if key not in allowed:
            problems.append(f"{prefix}{key}: unknown key (allowed: {', '.join(sorted(allowed))})")


def _str_list(value: Any, path: str, problems: list[str]) -> tuple[str, ...] | None:
    if not isinstance(value, list) or not all(_is_nonempty_str(v) for v in value):
        problems.append(f"{path}: must be a list of non-empty strings")
        return None
    return tuple(value)


def _parse_provider(data: dict[str, Any], problems: list[str]) -> ProviderConfig:
    section = _section(data, "provider", problems)
    if section is None:
        return ProviderConfig()
    _check_keys(section, {"base_url", "api_key_env"}, "provider.", problems)
    base_url = section.get("base_url", ProviderConfig.base_url)
    if not (_is_nonempty_str(base_url) and base_url.startswith(("http://", "https://"))):
        problems.append("provider.base_url: must be a URL starting with http:// or https://")
        base_url = ProviderConfig.base_url
    api_key_env = section.get("api_key_env")
    if api_key_env is not None and not _is_nonempty_str(api_key_env):
        problems.append("provider.api_key_env: must be an environment variable name or null")
        api_key_env = None
    return ProviderConfig(base_url=base_url, api_key_env=api_key_env)


def _parse_models(data: dict[str, Any], problems: list[str]) -> ModelsConfig:
    section = _section(data, "models", problems)
    if section is None:
        return ModelsConfig()
    _check_keys(section, {"baseline", "candidates", "judge"}, "models.", problems)
    defaults = ModelsConfig()

    baseline = section.get("baseline", defaults.baseline)
    if not _is_nonempty_str(baseline):
        problems.append("models.baseline: must be a non-empty model name")
        baseline = defaults.baseline

    candidates = defaults.candidates
    if "candidates" in section:
        parsed = _str_list(section["candidates"], "models.candidates", problems)
        if parsed is not None:
            if not parsed:
                problems.append("models.candidates: list at least one cheaper model to try")
            if len(set(parsed)) != len(parsed):
                problems.append("models.candidates: contains duplicate model names")
            if baseline in parsed:
                problems.append("models.candidates: must not include the baseline model")
            candidates = parsed

    judge = section.get("judge")
    if judge is not None and not _is_nonempty_str(judge):
        problems.append("models.judge: must be a model name or null")
        judge = None
    return ModelsConfig(baseline=baseline, candidates=candidates, judge=judge)


def _parse_threshold(data: dict[str, Any], problems: list[str]) -> float:
    value = data.get("quality_threshold", 0.95)
    if not _is_number(value) or not 0 < value <= 1:
        problems.append("quality_threshold: must be a number greater than 0 and at most 1")
        return 0.95
    return float(value)


def _parse_pricing(data: dict[str, Any], problems: list[str]) -> dict[str, ModelPrice]:
    section = _section(data, "pricing", problems)
    if section is None:
        return {}
    prices: dict[str, ModelPrice] = {}
    for model, entry in section.items():
        path = f"pricing.{model}"
        if not isinstance(entry, dict):
            problems.append(f"{path}: must be a mapping with input and output prices")
            continue
        _check_keys(entry, {"input", "output", "tier"}, f"{path}.", problems)
        ok = True
        for key in ("input", "output"):
            if key not in entry:
                problems.append(f"{path}.{key}: missing (USD per 1M tokens)")
                ok = False
            elif not _is_number(entry[key]) or entry[key] < 0:
                problems.append(f"{path}.{key}: must be a number >= 0")
                ok = False
        tier = entry.get("tier")
        if tier is not None and not _is_nonempty_str(tier):
            problems.append(f"{path}.tier: must be a string")
            tier = None
        if ok:
            prices[str(model)] = ModelPrice(float(entry["input"]), float(entry["output"]), tier)
    return prices


def _parse_volume(data: dict[str, Any], problems: list[str]) -> VolumeConfig:
    section = _section(data, "volume", problems)
    if section is None:
        return VolumeConfig()
    _check_keys(section, {"default_per_day", "per_call_site"}, "volume.", problems)
    default = section.get("default_per_day", VolumeConfig.default_per_day)
    if not _is_int(default) or default < 0:
        problems.append("volume.default_per_day: must be a whole number >= 0")
        default = VolumeConfig.default_per_day

    overrides: dict[str, int] = {}
    raw = section.get("per_call_site") or {}
    if not isinstance(raw, dict):
        problems.append("volume.per_call_site: must be a mapping of call site id to calls/day")
    else:
        for site, count in raw.items():
            if not _is_int(count) or count < 0:
                problems.append(f"volume.per_call_site.{site}: must be a whole number >= 0")
            else:
                overrides[str(site)] = count
    return VolumeConfig(default_per_day=default, per_call_site=overrides)


def _parse_scan(data: dict[str, Any], problems: list[str]) -> ScanConfig:
    section = _section(data, "scan", problems)
    if section is None:
        return ScanConfig()
    _check_keys(section, {"include", "exclude"}, "scan.", problems)
    defaults = ScanConfig()
    include = defaults.include
    if "include" in section:
        parsed = _str_list(section["include"], "scan.include", problems)
        if parsed is not None:
            if not parsed:
                problems.append("scan.include: must list at least one pattern")
            else:
                include = parsed
    exclude = defaults.exclude
    if "exclude" in section:
        parsed = _str_list(section["exclude"], "scan.exclude", problems)
        if parsed is not None:
            exclude = parsed
    return ScanConfig(include=include, exclude=exclude)


def parse_config(data: Any, source: Path | None = None) -> Config:
    """Validate parsed YAML and build a Config. Raises ConfigError listing every problem."""
    label = f"invalid config {source}" if source else "invalid config"
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(f"{label}: the top level must be a mapping")

    problems: list[str] = []
    _check_keys(data, _TOP_LEVEL_KEYS, "", problems)
    version = data.get("version", SUPPORTED_VERSION)
    if version != SUPPORTED_VERSION:
        problems.append(f"version: unsupported value {version!r} (expected {SUPPORTED_VERSION})")

    config = Config(
        provider=_parse_provider(data, problems),
        models=_parse_models(data, problems),
        quality_threshold=_parse_threshold(data, problems),
        pricing=_parse_pricing(data, problems),
        volume=_parse_volume(data, problems),
        scan=_parse_scan(data, problems),
        source=source,
    )
    if problems:
        raise ConfigError(label + ":\n" + "\n".join(f"  - {p}" for p in problems))
    return config
