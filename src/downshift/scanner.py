"""Find LLM call sites in Python source code using the ast module."""

from __future__ import annotations

import ast
import fnmatch
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from downshift.config import ScanConfig
from downshift.resolve import Ctx, FunctionNode, Module, ModuleIndex, Resolver, keyword_arg
from downshift.schema import CallSite, ModelRef, PromptMessage, ScanResult

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

    modules: list[Module] = []
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
        modules.append(Module.build(tree, rel))

    return ScanResult(
        root=root.name,
        files_scanned=files_scanned,
        call_sites=_scan_modules(modules),
        warnings=warnings,
    )


def scan_source(source: str, rel: str = "<string>") -> list[CallSite]:
    """Scan one module's source text. Handy for tests and editor integrations."""
    return scan_module(ast.parse(source, filename=rel), rel)


def scan_module(tree: ast.Module, rel: str) -> list[CallSite]:
    """Return the call sites in one parsed module, resolving names within it only."""
    return _scan_modules([Module.build(tree, rel)])


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


# --- scanning -----------------------------------------------------------------


def _scan_modules(modules: list[Module]) -> list[CallSite]:
    resolver = Resolver(ModuleIndex(modules))
    sites: list[CallSite] = []
    calls: list[tuple[str, str]] = []
    for module in modules:
        finder = _CallFinder()
        finder.visit(module.tree)
        calls.extend((f"{module.rel}::{caller}", callee) for caller, callee in finder.calls)
        sites.extend(_build_sites(module, finder.found, resolver))
    _attach_callers(sites, calls)
    sites.sort(key=lambda site: (site.file, site.line))
    return sites


def _build_sites(module: Module, found: list[_FoundCall], resolver: Resolver) -> list[CallSite]:
    sites: list[CallSite] = []
    seen: dict[str, int] = {}
    for item in found:
        base_id = f"{module.rel}::{item.qualname}"
        seen[base_id] = seen.get(base_id, 0) + 1
        site_id = base_id if seen[base_id] == 1 else f"{base_id}#{seen[base_id]}"

        ctx = Ctx(module, item.func, item.node.lineno)
        model = resolver.resolve_model(item.node, ctx)
        messages = resolver.resolve_messages(item.node, item.api, ctx)
        sites.append(
            CallSite(
                id=site_id,
                file=module.rel,
                line=item.node.lineno,
                end_line=item.node.end_lineno,
                function=item.qualname,
                api=item.api,
                model=model,
                is_async=item.is_async,
                messages=messages,
                output_format=_output_format(item.node, item.api),
                temperature=_temperature(item.node),
                max_tokens=_max_tokens(item.node),
                notes=_notes(model, messages),
            )
        )
    return sites


def _attach_callers(sites: list[CallSite], calls: list[tuple[str, str]]) -> None:
    """Name-based: record which functions call the function containing each call site."""
    for site in sites:
        if site.function == "<module>":
            continue
        short = site.function.split(".")[-1]
        own = f"{site.file}::{site.function}"
        site.callers = sorted(
            {caller for caller, callee in calls if callee == short and caller != own}
        )
        if len(site.callers) > 1 and site.messages is None:
            site.notes.append(
                f"shared helper called from {len(site.callers)} places; each caller may be "
                "a separate feature with its own prompt"
            )


@dataclass
class _FoundCall:
    node: ast.Call
    api: str
    qualname: str
    func: FunctionNode | None
    is_async: bool


class _CallFinder(ast.NodeVisitor):
    """Walks a module, recording LLM calls and every function call's caller/callee."""

    def __init__(self) -> None:
        self.scope: list[str] = []
        self.functions: list[FunctionNode] = []
        self.found: list[_FoundCall] = []
        self.calls: list[tuple[str, str]] = []
        self._awaited: set[int] = set()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: FunctionNode) -> None:
        self.scope.append(node.name)
        self.functions.append(node)
        self.generic_visit(node)
        self.functions.pop()
        self.scope.pop()

    def visit_Await(self, node: ast.Await) -> None:
        if isinstance(node.value, ast.Call):
            self._awaited.add(id(node.value))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        qualname = ".".join(self.scope) or "<module>"
        if isinstance(node.func, ast.Name):
            self.calls.append((qualname, node.func.id))
        elif isinstance(node.func, ast.Attribute):
            self.calls.append((qualname, node.func.attr))

        api = _match_api(node)
        if api is not None:
            func = self.functions[-1] if self.functions else None
            self.found.append(_FoundCall(node, api, qualname, func, id(node) in self._awaited))
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


def _output_format(call: ast.Call, api: str) -> str:
    if api.endswith(".parse"):
        return "json"
    fmt = keyword_arg(call, "response_format")
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
    value = keyword_arg(call, "temperature")
    if isinstance(value, ast.Constant) and isinstance(value.value, (int, float)):
        if isinstance(value.value, bool):
            return None
        return float(value.value)
    return None


def _max_tokens(call: ast.Call) -> int | None:
    value = keyword_arg(call, *MAX_TOKEN_KWARGS)
    if (
        isinstance(value, ast.Constant)
        and isinstance(value.value, int)
        and not isinstance(value.value, bool)
        and value.value >= 1
    ):
        return value.value
    return None


def _notes(model: ModelRef, messages: list[PromptMessage] | None) -> list[str]:
    notes: list[str] = []
    if model.source == "kwargs":
        notes.append(f"model is passed via {model.expression} and could not be resolved statically")
    elif model.source == "missing":
        notes.append("no model argument found at this call")
    elif model.source == "env_default":
        notes.append(f"model comes from env var {model.env_var}; assuming default {model.value!r}")
    elif model.source == "env":
        notes.append(f"model comes from env var {model.env_var} with no default")
    elif model.source == "dynamic":
        notes.append(f"model is computed at runtime ({model.expression})")

    if messages is None:
        notes.append("messages are built at runtime; the prompt template could not be recovered")
    elif not all(m.resolved for m in messages):
        notes.append("part of the prompt comes from a runtime value the scanner could not see")
    return notes
