import textwrap
from pathlib import Path

import pytest

from downshift.scanner import scan_path, scan_source
from downshift.schema import CallSite

ROOT = Path(__file__).resolve().parents[2]
SUPPORTDESK = ROOT / "tests" / "fixtures" / "supportdesk_v0"


def one(src: str) -> CallSite:
    (site,) = scan_source(textwrap.dedent(src), "app.py")
    return site


def write_tree(root: Path, files: dict[str, str]) -> Path:
    for rel, src in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(src), encoding="utf-8")
    return root


def model_of(site: CallSite) -> tuple[str | None, str]:
    return site.model.value, site.model.source


# --- models -------------------------------------------------------------------


def test_module_constant() -> None:
    site = one(
        """
        MODEL = "m-small"

        def f():
            return client.chat.completions.create(model=MODEL, messages=[])
        """
    )
    assert model_of(site) == ("m-small", "constant")
    assert site.model.defined_in == "app.py"
    assert site.model.expression == "MODEL"


def test_annotated_and_chained_constants() -> None:
    site = one(
        """
        BASE: str = "m-base"
        MODEL = BASE
        client.chat.completions.create(model=MODEL, messages=[])
        """
    )
    assert model_of(site) == ("m-base", "constant")


@pytest.mark.parametrize(
    "expr",
    [
        'os.getenv("LLM_MODEL", "m-env")',
        'os.environ.get("LLM_MODEL", "m-env")',
        'getenv("LLM_MODEL", default="m-env")',
    ],
)
def test_env_var_with_default(expr: str) -> None:
    site = one(f"import os\nMODEL = {expr}\nclient.chat.completions.create(model=MODEL)\n")
    assert model_of(site) == ("m-env", "env_default")
    assert site.model.env_var == "LLM_MODEL"
    assert "LLM_MODEL" in site.notes[0]


def test_env_var_inline_at_call() -> None:
    site = one('client.chat.completions.create(model=os.getenv("M", "m-inline"))')
    assert model_of(site) == ("m-inline", "env_default")


@pytest.mark.parametrize("expr", ['os.getenv("LLM_MODEL")', 'os.environ["LLM_MODEL"]'])
def test_env_var_without_default(expr: str) -> None:
    site = one(f"import os\nMODEL = {expr}\nclient.chat.completions.create(model=MODEL)\n")
    assert model_of(site) == (None, "env")
    assert site.model.env_var == "LLM_MODEL"


def test_dict_lookup() -> None:
    site = one(
        """
        MODELS = {"fast": "m-small", "smart": "m-big"}
        client.chat.completions.create(model=MODELS["smart"], messages=[])
        """
    )
    assert model_of(site) == ("m-big", "dict_lookup")


def test_dict_lookup_missing_key_is_dynamic() -> None:
    site = one(
        """
        MODELS = {"fast": "m-small"}
        client.chat.completions.create(model=MODELS["nope"], messages=[])
        """
    )
    assert model_of(site) == (None, "dynamic")


def test_parameter_default() -> None:
    site = one(
        """
        def f(text, model="m-default"):
            return client.chat.completions.create(model=model, messages=[])
        """
    )
    assert model_of(site) == ("m-default", "parameter_default")


def test_parameter_without_default_is_dynamic() -> None:
    site = one(
        """
        def f(model):
            return client.chat.completions.create(model=model, messages=[])
        """
    )
    assert model_of(site) == (None, "dynamic")
    assert "computed at runtime" in site.notes[0]


def test_local_variable_uses_last_assignment_before_call() -> None:
    site = one(
        """
        def f():
            model = "m-first"
            result = client.chat.completions.create(model=model, messages=[])
            model = "m-later"
            return result
        """
    )
    assert model_of(site) == ("m-first", "constant")


def test_circular_constants_do_not_hang() -> None:
    site = one("A = B\nB = A\nclient.chat.completions.create(model=A, messages=[])\n")
    assert model_of(site) == (None, "dynamic")


def test_kwargs_from_module_dict() -> None:
    site = one(
        """
        DEFAULTS = {"model": "m-kw", "temperature": 0}
        client.chat.completions.create(**DEFAULTS, messages=[])
        """
    )
    assert model_of(site) == ("m-kw", "dict_lookup")
    assert site.model.expression == "**DEFAULTS"


def test_kwargs_built_at_runtime_stay_unresolved() -> None:
    site = one(
        """
        def f():
            params = dict(BASE)
            return client.chat.completions.create(**params)
        """
    )
    assert model_of(site) == (None, "kwargs")


def test_cross_module_imports(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/settings.py": (
                'import os\nMODEL = os.getenv("PKG_MODEL", "m-env")\nFAST = "m-fast"\n'
            ),
            "pkg/relative.py": (
                "from .settings import MODEL\n"
                "client.chat.completions.create(model=MODEL, messages=[])\n"
            ),
            "pkg/absolute.py": (
                "from pkg.settings import FAST\n"
                "client.chat.completions.create(model=FAST, messages=[])\n"
            ),
            "pkg/alias.py": (
                "from pkg import settings\n"
                "client.chat.completions.create(model=settings.FAST, messages=[])\n"
            ),
            "pkg/aliased_import.py": (
                "import pkg.settings as s\n"
                "client.chat.completions.create(model=s.MODEL, messages=[])\n"
            ),
        },
    )
    models = {s.file: s.model for s in scan_path(tmp_path).call_sites}

    assert (models["pkg/relative.py"].value, models["pkg/relative.py"].source) == (
        "m-env",
        "env_default",
    )
    assert models["pkg/relative.py"].defined_in == "pkg/settings.py"
    assert (models["pkg/absolute.py"].value, models["pkg/absolute.py"].source) == (
        "m-fast",
        "constant",
    )
    assert models["pkg/alias.py"].value == "m-fast"
    assert models["pkg/aliased_import.py"].value == "m-env"


# --- prompts ------------------------------------------------------------------


def test_prompt_from_literal_messages() -> None:
    site = one(
        """
        def classify(text):
            return client.chat.completions.create(
                model="m",
                messages=[
                    {"role": "system", "content": "You classify tickets."},
                    {"role": "user", "content": f"Ticket: {text}"},
                ],
            )
        """
    )
    assert site.messages is not None
    assert [(m.role, m.content, m.resolved) for m in site.messages] == [
        ("system", "You classify tickets.", True),
        ("user", "Ticket: {text}", True),
    ]
    assert site.prompt_resolved


def test_prompt_concatenation_keeps_placeholders() -> None:
    site = one(
        r"""
        def classify(text):
            return client.chat.completions.create(
                model="m",
                messages=[{"role": "user", "content": "Pick: " + ", ".join(LABELS) + "\n" + text}],
            )
        """
    )
    assert site.messages is not None
    assert site.messages[0].content == "Pick: {', '.join(LABELS)}\n{text}"
    assert site.prompt_resolved


def test_prompt_from_local_variable() -> None:
    site = one(
        """
        def summarize(ticket):
            prompt = f"Summarize: {ticket}"
            return client.chat.completions.create(
                model="m", messages=[{"role": "user", "content": prompt}]
            )
        """
    )
    assert site.messages is not None
    assert site.messages[0].content == "Summarize: {ticket}"


def test_prompt_from_module_constant() -> None:
    site = one(
        """
        SYSTEM = (
            "Line one. "
            "Line two."
        )

        def f(text):
            return client.chat.completions.create(
                model="m",
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": text},
                ],
            )
        """
    )
    assert site.messages is not None
    assert site.messages[0].content == "Line one. Line two."
    assert site.messages[1].content == "{text}"
    assert site.prompt_resolved


def test_messages_built_at_runtime() -> None:
    site = one(
        """
        def ask(prompt):
            messages = []
            messages.append({"role": "user", "content": prompt})
            return client.chat.completions.create(model="m", messages=messages)
        """
    )
    assert site.messages is None
    assert any("built at runtime" in note for note in site.notes)


def test_opaque_prompt_builder_is_unresolved() -> None:
    site = one(
        """
        def f(text):
            return client.chat.completions.create(
                model="m", messages=[{"role": "user", "content": build_prompt(text)}]
            )
        """
    )
    assert site.messages is not None
    assert site.messages[0].content == "{build_prompt(text)}"
    assert site.messages[0].resolved is False
    assert site.prompt_resolved is False


def test_messages_passed_in_as_parameter() -> None:
    site = one(
        """
        def f(messages):
            return client.chat.completions.create(model="m", messages=messages)
        """
    )
    assert site.messages is None


def test_anthropic_system_prompt() -> None:
    site = one(
        'anthropic.messages.create(model="c", system="Be brief.", max_tokens=10, '
        'messages=[{"role": "user", "content": "hi"}])'
    )
    assert site.messages is not None
    assert [(m.role, m.content) for m in site.messages] == [("system", "Be brief."), ("user", "hi")]


def test_responses_api_instructions_and_input() -> None:
    site = one('client.responses.create(model="m", instructions="Be brief.", input="hello")')
    assert site.messages is not None
    assert [(m.role, m.content) for m in site.messages] == [
        ("system", "Be brief."),
        ("user", "hello"),
    ]


# --- callers ------------------------------------------------------------------


def test_shared_helper_callers() -> None:
    site = one(
        """
        def ask(prompt):
            messages = []
            messages.append({"role": "user", "content": prompt})
            return client.chat.completions.create(model="m", messages=messages)

        def sentiment(text):
            return ask(f"Sentiment of {text}")

        def urgency(text):
            return ask(f"Urgency of {text}")
        """
    )
    assert site.callers == ["app.py::sentiment", "app.py::urgency"]
    assert any("shared helper called from 2 places" in note for note in site.notes)


# --- the demo app -------------------------------------------------------------


def test_supportdesk_resolution() -> None:
    result = scan_path(SUPPORTDESK)
    sites = {s.function: s for s in result.call_sites}
    summary = result.summary()

    assert summary["models_resolved"] == 6
    assert summary["prompts_resolved"] == 5

    expected = {
        "classify_category": ("qwen2.5:7b", "literal", None),
        "ask": ("qwen2.5:7b", "env_default", "SUPPORTDESK_MODEL"),
        "extract_order_info": ("qwen2.5:7b", "env_default", "SUPPORTDESK_MODEL"),
        "summarize_for_agent": ("qwen2.5:7b", "env_default", "SUMMARY_MODEL"),
        "draft_reply": ("qwen2.5:7b", "env_default", "SUPPORTDESK_MODEL"),
        "decide_refund": ("qwen2.5:7b", "dict_lookup", None),
        "lang_of": (None, "kwargs", None),
    }
    for function, (value, source, env_var) in expected.items():
        model = sites[function].model
        assert (model.value, model.source, model.env_var) == (value, source, env_var), function

    assert sites["extract_order_info"].model.defined_in == "supportdesk/llm.py"
    assert sites["ask"].messages is None
    assert sites["ask"].callers == [
        "supportdesk/triage.py::detect_sentiment",
        "supportdesk/triage.py::tag_urgency",
    ]
    assert sites["lang_of"].messages is None

    classify = sites["classify_category"].messages
    assert classify is not None
    assert "Classify this support ticket" in classify[-1].content
    assert "{ticket_text}" in classify[-1].content
