"""Data format for LLM call sites (callsites.json).

The ast scanner writes it, the Bob auditor enriches it, and every later
command reads it. Everything goes through this module so both producers
are validated the same way.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from downshift import __version__

SCHEMA_VERSION = 1

# How the scanner learned the model name.
MODEL_SOURCES = frozenset(
    {
        "literal",  # model="gpt-4o" at the call
        "constant",  # a named constant, possibly imported from another module
        "env_default",  # os.getenv("X", "default"): the default is used
        "env",  # os.getenv("X") with no default: unknown until runtime
        "dict_lookup",  # MODELS["key"] on a dict literal
        "parameter_default",  # def f(model="gpt-4o")
        "kwargs",  # passed through **params and not resolvable
        "missing",  # no model argument at all
        "dynamic",  # anything else computed at runtime
        "manual",  # set by a human or by Bob
    }
)
OUTPUT_FORMATS = frozenset({"text", "json"})
DIFFICULTIES = frozenset({"easy", "medium", "hard"})
GRADINGS = frozenset({"exact", "json_fields", "judge"})
PRODUCERS = frozenset({"ast", "bob", "manual"})


class SchemaError(ValueError):
    """Raised when callsites data does not match the schema."""


@dataclass
class ModelRef:
    value: str | None
    source: str
    expression: str
    env_var: str | None = None
    defined_in: str | None = None

    @property
    def resolved(self) -> bool:
        return self.value is not None


@dataclass
class PromptMessage:
    role: str
    content: str
    resolved: bool = True


@dataclass
class CallSite:
    # Where it is
    id: str
    file: str
    line: int
    function: str
    api: str
    model: ModelRef
    end_line: int | None = None
    is_async: bool = False
    # What it sends
    messages: list[PromptMessage] | None = None
    output_format: str = "text"
    temperature: float | None = None
    max_tokens: int | None = None
    # How it is reached
    via: str | None = None
    callers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # Enrichment (Bob or a human); None when produced by the ast scanner
    purpose: str | None = None
    output_contract: str | None = None
    difficulty: str | None = None
    grading: str | None = None
    found_by: str = "ast"

    @property
    def prompt_resolved(self) -> bool:
        return self.messages is not None and all(m.resolved for m in self.messages)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any, path: str = "call_site") -> CallSite:
        if not isinstance(data, dict):
            raise SchemaError(f"{path}: expected an object, got {type(data).__name__}")
        _reject_unknown(data, {f.name for f in fields(cls)}, path)

        model_data = _field(data, "model", path, _is_dict, "an object")
        return cls(
            id=_field(data, "id", path, _is_nonempty_str, "a non-empty string"),
            file=_field(data, "file", path, _is_nonempty_str, "a non-empty string"),
            line=_field(data, "line", path, _is_positive_int, "a line number >= 1"),
            function=_field(data, "function", path, _is_nonempty_str, "a non-empty string"),
            api=_field(data, "api", path, _is_nonempty_str, "a non-empty string"),
            model=_model_from_dict(model_data, f"{path}.model"),
            end_line=_field(data, "end_line", path, _opt(_is_positive_int), "a line number", None),
            is_async=_field(data, "is_async", path, _is_bool, "true or false", False),
            messages=_messages_from_dict(data.get("messages"), f"{path}.messages"),
            output_format=_field(
                data,
                "output_format",
                path,
                _one_of(OUTPUT_FORMATS),
                _choices(OUTPUT_FORMATS),
                "text",
            ),
            temperature=_field(data, "temperature", path, _opt(_is_number), "a number", None),
            max_tokens=_field(
                data, "max_tokens", path, _opt(_is_positive_int), "an integer >= 1", None
            ),
            via=_field(data, "via", path, _opt(_is_nonempty_str), "a call site id", None),
            callers=_field(data, "callers", path, _is_str_list, "a list of strings", []),
            notes=_field(data, "notes", path, _is_str_list, "a list of strings", []),
            purpose=_field(data, "purpose", path, _opt(_is_str), "a string", None),
            output_contract=_field(data, "output_contract", path, _opt(_is_str), "a string", None),
            difficulty=_field(
                data,
                "difficulty",
                path,
                _opt(_one_of(DIFFICULTIES)),
                _choices(DIFFICULTIES),
                None,
            ),
            grading=_field(
                data,
                "grading",
                path,
                _opt(_one_of(GRADINGS)),
                _choices(GRADINGS),
                None,
            ),
            found_by=_field(
                data,
                "found_by",
                path,
                _one_of(PRODUCERS),
                _choices(PRODUCERS),
                "ast",
            ),
        )


@dataclass
class ScanResult:
    root: str
    files_scanned: int
    call_sites: list[CallSite]
    warnings: list[str] = field(default_factory=list)
    generated_by: str = "ast"
    tool_version: str = __version__

    def summary(self) -> dict[str, int]:
        return {
            "files_scanned": self.files_scanned,
            "call_sites": len(self.call_sites),
            "models_resolved": sum(1 for s in self.call_sites if s.model.resolved),
            "prompts_resolved": sum(1 for s in self.call_sites if s.prompt_resolved),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "tool": "downshift",
            "tool_version": self.tool_version,
            "generated_by": self.generated_by,
            "root": self.root,
            "summary": self.summary(),
            "warnings": list(self.warnings),
            "call_sites": [site.to_dict() for site in self.call_sites],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: Any) -> ScanResult:
        if not isinstance(data, dict):
            raise SchemaError("callsites: expected a JSON object at the top level")
        version = data.get("schema_version")
        if version != SCHEMA_VERSION:
            raise SchemaError(
                f"schema_version: unsupported value {version!r} (expected {SCHEMA_VERSION})"
            )
        raw_sites = data.get("call_sites")
        if not isinstance(raw_sites, list):
            raise SchemaError("call_sites: expected a list")
        sites = [CallSite.from_dict(item, f"call_sites[{i}]") for i, item in enumerate(raw_sites)]

        seen: set[str] = set()
        for site in sites:
            if site.id in seen:
                raise SchemaError(f"call_sites: duplicate id {site.id!r}")
            seen.add(site.id)

        return cls(
            root=_field(data, "root", "callsites", _is_str, "a string", "."),
            files_scanned=_summary_files(data),
            call_sites=sites,
            warnings=_field(data, "warnings", "callsites", _is_str_list, "a list of strings", []),
            generated_by=_field(
                data,
                "generated_by",
                "callsites",
                _one_of(PRODUCERS),
                _choices(PRODUCERS),
                "ast",
            ),
            tool_version=_field(
                data, "tool_version", "callsites", _is_str, "a string", __version__
            ),
        )

    @classmethod
    def load(cls, path: Path) -> ScanResult:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise SchemaError(f"callsites file not found: {path}") from None
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SchemaError(f"{path}: invalid JSON: {exc}") from exc
        return cls.from_dict(data)


# --- helpers ------------------------------------------------------------------

_MISSING: Any = object()


def _field(
    data: dict[str, Any],
    key: str,
    path: str,
    check: Callable[[Any], bool],
    expected: str,
    default: Any = _MISSING,
) -> Any:
    if key not in data:
        if default is _MISSING:
            raise SchemaError(f"{path}.{key}: missing required field")
        return default
    value = data[key]
    if not check(value):
        raise SchemaError(f"{path}.{key}: expected {expected}, got {value!r}")
    return value


def _reject_unknown(data: dict[str, Any], allowed: set[str], path: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise SchemaError(f"{path}: unknown field(s) {', '.join(unknown)}")


def _model_from_dict(data: dict[str, Any], path: str) -> ModelRef:
    _reject_unknown(data, {f.name for f in fields(ModelRef)}, path)
    return ModelRef(
        value=_field(data, "value", path, _opt(_is_nonempty_str), "a model name or null"),
        source=_field(data, "source", path, _one_of(MODEL_SOURCES), _choices(MODEL_SOURCES)),
        expression=_field(data, "expression", path, _is_str, "a string"),
        env_var=_field(data, "env_var", path, _opt(_is_nonempty_str), "a string", None),
        defined_in=_field(data, "defined_in", path, _opt(_is_nonempty_str), "a string", None),
    )


def _messages_from_dict(data: Any, path: str) -> list[PromptMessage] | None:
    if data is None:
        return None
    if not isinstance(data, list):
        raise SchemaError(f"{path}: expected a list or null")
    messages = []
    for i, item in enumerate(data):
        item_path = f"{path}[{i}]"
        if not isinstance(item, dict):
            raise SchemaError(f"{item_path}: expected an object")
        _reject_unknown(item, {f.name for f in fields(PromptMessage)}, item_path)
        messages.append(
            PromptMessage(
                role=_field(item, "role", item_path, _is_nonempty_str, "a non-empty string"),
                content=_field(item, "content", item_path, _is_str, "a string"),
                resolved=_field(item, "resolved", item_path, _is_bool, "true or false", True),
            )
        )
    return messages


def _summary_files(data: dict[str, Any]) -> int:
    summary = data.get("summary")
    if isinstance(summary, dict) and _is_nonneg_int(summary.get("files_scanned")):
        return int(summary["files_scanned"])
    return 0


def _choices(options: frozenset[str]) -> str:
    return "one of " + ", ".join(sorted(options))


def _is_str(value: Any) -> bool:
    return isinstance(value, str)


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _is_dict(value: Any) -> bool:
    return isinstance(value, dict)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _is_nonneg_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _opt(check: Callable[[Any], bool]) -> Callable[[Any], bool]:
    return lambda value: value is None or check(value)


def _one_of(options: frozenset[str]) -> Callable[[Any], bool]:
    return lambda value: isinstance(value, str) and value in options
