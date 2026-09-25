"""Static resolution of model names and prompt templates.

Follows variables, imports, os.getenv defaults, dict lookups and parameter
defaults across the scanned modules. Anything that is only known at runtime
is reported as unresolved, never guessed.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import TypeAlias

from downshift.schema import ModelRef, PromptMessage

FunctionNode: TypeAlias = ast.FunctionDef | ast.AsyncFunctionDef

MAX_DEPTH = 10
ENV_GETTERS = frozenset({"os.getenv", "os.environ.get", "environ.get", "getenv"})
ENV_MAPPINGS = frozenset({"os.environ", "environ"})
MUTATING_METHODS = frozenset({"append", "extend", "insert"})


# --- module index -------------------------------------------------------------


def module_dotted(rel: str) -> str:
    """supportdesk/triage.py -> supportdesk.triage, pkg/__init__.py -> pkg."""
    path = rel[:-3] if rel.endswith(".py") else rel
    parts = path.split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _import_base(dotted: str, module: str | None, level: int, is_package: bool) -> str:
    if level == 0:
        return module or ""
    parts = dotted.split(".") if is_package else dotted.split(".")[:-1]
    parts = parts[: max(len(parts) - (level - 1), 0)]
    if module:
        parts.append(module)
    return ".".join(parts)


@dataclass
class Module:
    """One parsed file plus its module-level assignments and imports."""

    rel: str
    dotted: str
    tree: ast.Module
    assigns: dict[str, ast.expr] = field(default_factory=dict)
    imports: dict[str, tuple[str, str | None]] = field(default_factory=dict)

    @classmethod
    def build(cls, tree: ast.Module, rel: str) -> Module:
        module = cls(rel=rel, dotted=module_dotted(rel), tree=tree)
        is_package = rel.endswith("__init__.py")
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        module.assigns[target.id] = stmt.value
            elif (
                isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and stmt.value is not None
            ):
                module.assigns[stmt.target.id] = stmt.value
            elif isinstance(stmt, ast.ImportFrom):
                base = _import_base(module.dotted, stmt.module, stmt.level, is_package)
                for alias in stmt.names:
                    module.imports[alias.asname or alias.name] = (base, alias.name)
            elif isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    if alias.asname:
                        module.imports[alias.asname] = (alias.name, None)
                    else:
                        top = alias.name.split(".")[0]
                        module.imports[top] = (top, None)
        return module


class ModuleIndex:
    """Looks modules up by dotted name, tolerating a different package root."""

    def __init__(self, modules: list[Module]) -> None:
        self.modules = modules
        self._by_dotted = {m.dotted: m for m in modules}

    def find(self, dotted: str) -> Module | None:
        if dotted in self._by_dotted:
            return self._by_dotted[dotted]
        matches = [m for name, m in self._by_dotted.items() if name.endswith("." + dotted)]
        return matches[0] if len(matches) == 1 else None


# --- resolution ---------------------------------------------------------------


@dataclass(frozen=True)
class Ctx:
    """Where an expression lives: its module, enclosing function, and line."""

    module: Module
    func: FunctionNode | None
    line: int


@dataclass
class _Trail:
    """What happened while following a reference, used to label the source."""

    hops: int = 0
    dict_lookup: bool = False
    param_default: bool = False
    env_var: str | None = None
    defined_in: str | None = None


class Resolver:
    def __init__(self, index: ModuleIndex) -> None:
        self.index = index

    # model -------------------------------------------------------------------

    def resolve_model(self, call: ast.Call, ctx: Ctx) -> ModelRef:
        value = keyword_arg(call, "model")
        if value is not None:
            return self._model_from(value, ctx, ast.unparse(value), _Trail())

        for kw in call.keywords:
            if kw.arg is None:
                expression = "**" + ast.unparse(kw.value)
                trail = _Trail()
                target = self._follow(kw.value, ctx, trail, 0)
                if target is not None and isinstance(target[0], ast.Dict):
                    model_expr = _dict_get(target[0], "model")
                    if model_expr is not None:
                        trail.dict_lookup = True
                        ref = self._model_from(model_expr, target[1], expression, trail)
                        if ref.resolved:
                            return ref
                return ModelRef(value=None, source="kwargs", expression=expression)
        return ModelRef(value=None, source="missing", expression="")

    def _model_from(self, value: ast.expr, ctx: Ctx, expression: str, trail: _Trail) -> ModelRef:
        result = self._string(value, ctx, trail, 0)
        if trail.env_var is not None:
            source = "env_default" if result is not None else "env"
        elif result is None:
            source = "dynamic"
        elif trail.dict_lookup:
            source = "dict_lookup"
        elif trail.param_default:
            source = "parameter_default"
        elif trail.hops == 0:
            source = "literal"
        else:
            source = "constant"
        return ModelRef(
            value=result,
            source=source,
            expression=expression,
            env_var=trail.env_var,
            defined_in=trail.defined_in if result is not None else None,
        )

    def _string(self, expr: ast.expr, ctx: Ctx, trail: _Trail, depth: int) -> str | None:
        if depth > MAX_DEPTH:
            return None
        if isinstance(expr, ast.Constant):
            if isinstance(expr.value, str):
                trail.defined_in = ctx.module.rel
                return expr.value
            return None
        if isinstance(expr, (ast.Name, ast.Attribute)):
            target = self._definition(expr, ctx, trail, depth)
            if target is None:
                return None
            trail.hops += 1
            return self._string(target[0], target[1], trail, depth + 1)
        if isinstance(expr, ast.Call) and _dotted_name(expr.func) in ENV_GETTERS:
            if expr.args:
                trail.env_var = _constant_str(expr.args[0])
            default = expr.args[1] if len(expr.args) > 1 else keyword_arg(expr, "default")
            if default is None:
                return None
            return self._string(default, ctx, trail, depth + 1)
        if isinstance(expr, ast.Subscript):
            key = _constant_str(expr.slice)
            if _dotted_name(expr.value) in ENV_MAPPINGS:
                trail.env_var = key
                return None
            target = self._follow(expr.value, ctx, trail, depth + 1)
            if key is None or target is None or not isinstance(target[0], ast.Dict):
                return None
            value = _dict_get(target[0], key)
            if value is None:
                return None
            trail.dict_lookup = True
            return self._string(value, target[1], trail, depth + 1)
        return None

    # prompts -----------------------------------------------------------------

    def resolve_messages(self, call: ast.Call, api: str, ctx: Ctx) -> list[PromptMessage] | None:
        """Recover the prompt template, or None if the messages are built at runtime."""
        messages: list[PromptMessage] = []
        system = keyword_arg(call, "system", "instructions")
        if system is not None:
            messages.append(self._message("system", system, ctx))

        body = keyword_arg(call, "messages", "input")
        if body is None:
            return messages or None
        if isinstance(body, ast.Name) and ctx.func is not None and _is_mutated(ctx.func, body.id):
            return None

        target = self._follow(body, ctx, _Trail(), 0)
        if target is None:
            return None
        node, node_ctx = target
        if isinstance(node, ast.List):
            for element in node.elts:
                if not isinstance(element, ast.Dict):
                    return None
                role_expr = _dict_get(element, "role")
                content_expr = _dict_get(element, "content")
                role = _constant_str(role_expr) if role_expr is not None else None
                if role is None or content_expr is None:
                    return None
                messages.append(self._message(role, content_expr, node_ctx))
            return messages
        if api == "openai.responses":
            messages.append(self._message("user", body, ctx))
            return messages
        return None

    def _message(self, role: str, expr: ast.expr, ctx: Ctx) -> PromptMessage:
        content, resolved = self._template(expr, ctx, 0, inside=False)
        return PromptMessage(role=role, content=content, resolved=resolved)

    def _template(self, expr: ast.expr, ctx: Ctx, depth: int, inside: bool) -> tuple[str, bool]:
        """Render a prompt expression as text, with runtime values as {placeholders}.

        inside=True means we are inside a larger template, where any runtime value
        is just a placeholder. At the top level, an opaque value means the whole
        prompt is unknown.
        """
        placeholder = "{" + ast.unparse(expr) + "}"
        if depth > MAX_DEPTH:
            return placeholder, False
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return expr.value, True
        if isinstance(expr, ast.JoinedStr):
            parts: list[str] = []
            for value in expr.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    parts.append(value.value)
                elif isinstance(value, ast.FormattedValue):
                    parts.append("{" + ast.unparse(value.value) + "}")
            return "".join(parts), True
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
            left, left_ok = self._template(expr.left, ctx, depth + 1, inside=True)
            right, right_ok = self._template(expr.right, ctx, depth + 1, inside=True)
            return left + right, left_ok and right_ok
        if inside:
            return placeholder, True
        if isinstance(expr, ast.Name) and ctx.func is not None:
            is_param, _ = _parameter(ctx.func, expr.id)
            if is_param and _local_assignment(ctx.func, expr.id, ctx.line) is None:
                return placeholder, True
        if isinstance(expr, (ast.Name, ast.Attribute)):
            target = self._definition(expr, ctx, _Trail(), depth)
            if target is not None:
                return self._template(target[0], target[1], depth + 1, inside=False)
        return placeholder, False

    # following references ----------------------------------------------------

    def _follow(
        self, expr: ast.expr, ctx: Ctx, trail: _Trail, depth: int
    ) -> tuple[ast.expr, Ctx] | None:
        """Follow names until reaching the expression that defines them."""
        while isinstance(expr, (ast.Name, ast.Attribute)):
            if depth > MAX_DEPTH:
                return None
            target = self._definition(expr, ctx, trail, depth)
            if target is None:
                return None
            expr, ctx = target
            depth += 1
        return expr, ctx

    def _definition(
        self, expr: ast.expr, ctx: Ctx, trail: _Trail, depth: int
    ) -> tuple[ast.expr, Ctx] | None:
        if isinstance(expr, ast.Name):
            if ctx.func is not None:
                local = _local_assignment(ctx.func, expr.id, ctx.line)
                if local is not None:
                    return local, ctx
                is_param, default = _parameter(ctx.func, expr.id)
                if is_param:
                    if default is None:
                        return None
                    trail.param_default = True
                    return default, Ctx(ctx.module, None, 0)
            return self._module_name(ctx.module, expr.id, depth)
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
            module = self._module_alias(ctx.module, expr.value.id)
            if module is not None:
                return self._module_name(module, expr.attr, depth)
        return None

    def _module_name(self, module: Module, name: str, depth: int) -> tuple[ast.expr, Ctx] | None:
        if depth > MAX_DEPTH:
            return None
        if name in module.assigns:
            return module.assigns[name], Ctx(module, None, 0)
        imported = module.imports.get(name)
        if imported is None:
            return None
        base, attr = imported
        if attr is None:
            return None
        target = self.index.find(base)
        if target is None or target is module:
            return None
        return self._module_name(target, attr, depth + 1)

    def _module_alias(self, module: Module, alias: str) -> Module | None:
        imported = module.imports.get(alias)
        if imported is None:
            return None
        base, attr = imported
        return self.index.find(base if attr is None else f"{base}.{attr}")


# --- small ast helpers --------------------------------------------------------


def keyword_arg(call: ast.Call, *names: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg is not None and kw.arg in names:
            return kw.value
    return None


def _dotted_name(node: ast.expr) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _constant_str(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _dict_get(node: ast.Dict, key: str) -> ast.expr | None:
    for k, v in zip(node.keys, node.values, strict=True):
        if k is not None and _constant_str(k) == key:
            return v
    return None


def _parameter(func: FunctionNode, name: str) -> tuple[bool, ast.expr | None]:
    """Return (is a parameter, its default expression or None)."""
    args = func.args
    positional = [*args.posonlyargs, *args.args]
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults))
    defaults.extend(args.defaults)
    for arg, default in zip(positional, defaults, strict=True):
        if arg.arg == name:
            return True, default
    for arg, kw_default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        if arg.arg == name:
            return True, kw_default
    for special in (args.vararg, args.kwarg):
        if special is not None and special.arg == name:
            return True, None
    return False, None


def _local_assignment(func: FunctionNode, name: str, line: int) -> ast.expr | None:
    """The last assignment to name inside func before the given line."""
    best: tuple[int, ast.expr] | None = None
    for node in ast.walk(func):
        targets: list[ast.expr]
        value: ast.expr | None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        if value is None or node.lineno >= line:
            continue
        if any(isinstance(t, ast.Name) and t.id == name for t in targets) and (
            best is None or node.lineno > best[0]
        ):
            best = (node.lineno, value)
    return best[1] if best else None


def _is_mutated(func: FunctionNode, name: str) -> bool:
    """True if a list/dict variable is changed after creation (append, +=, x[k] = v)."""
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == name
            and node.func.attr in MUTATING_METHODS
        ):
            return True
        if (
            isinstance(node, ast.AugAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            return True
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.ctx, ast.Store)
            and isinstance(node.value, ast.Name)
            and node.value.id == name
        ):
            return True
    return False
