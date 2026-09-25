"""Find LLM call sites in Python source code using the ast module."""

from __future__ import annotations

import ast
import fnmatch
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from downshift.config import ScanConfig
from downshift.schema import CallSite, ModelRef, ScanResult

SKIP_DIRS = frozenset(
    {
        ".venv",
        "venv",
        "env",
        ".git",
        "node_modules",
        "__pycache__",
        "site-packages",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "dist",
        ".downshift",
    }
)

# (attribute suffix, api name, only counts if a model= keyword is present)
API_PATTERNS: tuple[tuple[tuple[str, ...], str, bool], ...] = (
    (("chat", "completions", "create"), "openai.chat.completions", False),
    (("chat", "completions", "parse"), "openai.chat.completions.parse", False),
    (("responses", "create"), "openai.responses", True),
    (("messages", "create"), "anthropic.messages", True),
)

MAX_TOKEN_KWARGS = ("max_tokens", "max_completion_tokens", "max_output_tokens")
JSON_FORMAT_TYPES = frozenset({"json_object", "json_schema"})


# --- public API ---------------------------------------------------------------


def scan_path(root: Path, scan_config: ScanConfig | None = None) -> ScanResult:
    """Scan a directory (or a single .py file) for LLM call sites."""
    scan_config = scan_config or ScanConfig()
    if not root.exists():
        raise FileNotFoundError(f"path does not exist: {root}")
    root = root.resolve()

    sites: list[CallSite] = []
    warnings: list[str] = []
    files_scanned = 0
    for path, rel in iter_python_files(root, scan_config):
        files_scanned += 1
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            warnings.append(f"{rel}: could not read file, skipped ({exc})")
            continue
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            warnings.append(f"{rel}:{exc.lineno}: syntax error, skipped ({exc.msg})")
            continue
        sites.extend(scan_module(tree, rel))

    sites.sort(key=lambda site: (site.file, site.line))
    return ScanResult(
        root=root.name, files_scanned=files_scanned, call_sites=sites, warnings=warnings
    )


def scan_source(source: str, rel: str = "<string>") -> list[CallSite]:
    """Scan one module's source text. Handy for tests and editor integrations."""
    return scan_module(ast.parse(source, filename=rel), rel)


def scan_module(tree: ast.Module, rel: str) -> list[CallSite]:
    """Return the call sites in one parsed module."""
    finder = _CallFinder()
    finder.visit(tree)

    sites: list[CallSite] = []
    seen: dict[str, int] = {}
    for found in finder.found:
        base_id = f"{rel}::{found.qualname}"
        seen[base_id] = seen.get(base_id, 0) + 1
        site_id = base_id if seen[base_id] == 1 else f"{base_id}#{seen[base_id]}"

        model = _model_ref(found.node)
        sites.append(
            CallSite(
                id=site_id,
                file=rel,
                line=found.node.lineno,
                end_line=found.node.end_lineno,
                function=found.qualname,
                api=found.api,
                model=model,
                is_async=found.is_async,
                output_format=_output_format(found.node, found.api),
                temperature=_temperature(found.node),
                max_tokens=_max_tokens(found.node),
                notes=_notes(model),
            )
        )
    return sites


def iter_python_files(root: Path, scan_config: ScanConfig) -> Iterator[tuple[Path, str]]:
    """Yield (absolute path, posix path relative to root) for files to scan."""
    if root.is_file():
        yield root, root.name
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            if not any(fnmatch.fnmatch(rel, pattern) for pattern in scan_config.include):
                continue
            if any(fnmatch.fnmatch(rel, pattern) for pattern in scan_config.exclude):
                continue
            yield path, rel


# --- finding calls ------------------------------------------------------------


@dataclass
class _FoundCall:
    node: ast.Call
    api: str
    qualname: str
    is_async: bool


class _CallFinder(ast.NodeVisitor):
    """Walks a module and records LLM calls with their enclosing scope."""

    def __init__(self) -> None:
        self.scope: list[str] = []
        self.found: list[_FoundCall] = []
        self._awaited: set[int] = set()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Await(self, node: ast.Await) -> None:
        if isinstance(node.value, ast.Call):
            self._awaited.add(id(node.value))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        api = _match_api(node)
        if api is not None:
            qualname = ".".join(self.scope) or "<module>"
            self.found.append(_FoundCall(node, api, qualname, id(node) in self._awaited))
        self.generic_visit(node)


def _attribute_chain(node: ast.expr) -> list[str]:
    """client.chat.completions.create -> ["chat", "completions", "create"]."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    parts.reverse()
    return parts


def _match_api(call: ast.Call) -> str | None:
    chain = _attribute_chain(call.func)
    for suffix, api, needs_model in API_PATTERNS:
        if len(chain) >= len(suffix) and tuple(chain[-len(suffix) :]) == suffix:
            if needs_model and not any(kw.arg == "model" for kw in call.keywords):
                return None
            return api
    return None


# --- reading call arguments ---------------------------------------------------


def _keyword(call: ast.Call, *names: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg in names:
            return kw.value
    return None


def _model_ref(call: ast.Call) -> ModelRef:
    """Resolve the model argument. 2d handles literals only; 2e adds the rest."""
    value = _keyword(call, "model")
    if value is not None:
        expression = ast.unparse(value)
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return ModelRef(value=value.value, source="literal", expression=expression)
        return ModelRef(value=None, source="dynamic", expression=expression)

    unpacked = [kw for kw in call.keywords if kw.arg is None]
    if unpacked:
        return ModelRef(
            value=None, source="kwargs", expression="**" + ast.unparse(unpacked[0].value)
        )
    return ModelRef(value=None, source="missing", expression="")


def _output_format(call: ast.Call, api: str) -> str:
    if api.endswith(".parse"):
        return "json"
    fmt = _keyword(call, "response_format")
    if isinstance(fmt, ast.Dict):
        for key, val in zip(fmt.keys, fmt.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and key.value == "type"
                and isinstance(val, ast.Constant)
                and val.value in JSON_FORMAT_TYPES
            ):
                return "json"
    return "text"


def _temperature(call: ast.Call) -> float | None:
    value = _keyword(call, "temperature")
    if isinstance(value, ast.Constant) and isinstance(value.value, (int, float)):
        if isinstance(value.value, bool):
            return None
        return float(value.value)
    return None


def _max_tokens(call: ast.Call) -> int | None:
    value = _keyword(call, *MAX_TOKEN_KWARGS)
    if (
        isinstance(value, ast.Constant)
        and isinstance(value.value, int)
        and not isinstance(value.value, bool)
        and value.value >= 1
    ):
        return value.value
    return None


def _notes(model: ModelRef) -> list[str]:
    if model.source == "kwargs":
        return [f"model is passed via {model.expression} and could not be resolved statically"]
    if model.source == "missing":
        return ["no model argument found at this call"]
    return []
