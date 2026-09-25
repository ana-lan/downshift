import textwrap
from pathlib import Path

import pytest

from downshift.config import ScanConfig
from downshift.scanner import scan_path, scan_source
from downshift.schema import CallSite

ROOT = Path(__file__).resolve().parents[2]
SUPPORTDESK = ROOT / "examples" / "supportdesk"


def scan(src: str) -> list[CallSite]:
    return scan_source(textwrap.dedent(src), "app.py")


def write_tree(root: Path, files: dict[str, str]) -> Path:
    for rel, src in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(src), encoding="utf-8")
    return root


LLM_CALL = """
from openai import OpenAI
client = OpenAI()

def classify(text):
    return client.chat.completions.create(model="gpt-big", messages=[])
"""


# --- detection ----------------------------------------------------------------


def test_finds_direct_openai_call() -> None:
    (site,) = scan(
        """
        from openai import OpenAI
        client = OpenAI()

        def classify(text):
            return client.chat.completions.create(
                model="gpt-big",
                messages=[{"role": "user", "content": text}],
                temperature=0,
                max_tokens=5,
            )
        """
    )
    assert site.id == "app.py::classify"
    assert site.file == "app.py"
    assert site.line == 6
    assert site.end_line == 11
    assert site.function == "classify"
    assert site.api == "openai.chat.completions"
    assert site.model.value == "gpt-big"
    assert site.model.source == "literal"
    assert site.is_async is False
    assert site.temperature == 0.0
    assert site.max_tokens == 5
    assert site.output_format == "text"
    assert site.found_by == "ast"


def test_module_level_call() -> None:
    (site,) = scan("client.chat.completions.create(model='m', messages=[])")
    assert site.function == "<module>"
    assert site.id == "app.py::<module>"


def test_class_method_and_nested_function_qualnames() -> None:
    sites = scan(
        """
        class Bot:
            def reply(self):
                return self.client.chat.completions.create(model="m", messages=[])

        def outer():
            def inner():
                return client.chat.completions.create(model="m", messages=[])
            return inner
        """
    )
    assert [s.id for s in sites] == ["app.py::Bot.reply", "app.py::outer.inner"]


def test_multiple_calls_in_one_function_get_unique_ids() -> None:
    sites = scan(
        """
        def pipeline():
            a = client.chat.completions.create(model="m", messages=[])
            b = client.chat.completions.create(model="m", messages=[])
            return a, b
        """
    )
    assert [s.id for s in sites] == ["app.py::pipeline", "app.py::pipeline#2"]


def test_awaited_call_is_async() -> None:
    (site,) = scan(
        """
        async def draft():
            return await async_client.chat.completions.create(model="m", messages=[])
        """
    )
    assert site.is_async is True


def test_openai_responses_api() -> None:
    (site,) = scan("client.responses.create(model='m', input='hi')")
    assert site.api == "openai.responses"


def test_anthropic_messages_api() -> None:
    (site,) = scan("anthropic.messages.create(model='claude', max_tokens=100, messages=[])")
    assert site.api == "anthropic.messages"
    assert site.max_tokens == 100


def test_structured_output_parse_is_json() -> None:
    (site,) = scan("client.beta.chat.completions.parse(model='m', messages=[], response_format=X)")
    assert site.api == "openai.chat.completions.parse"
    assert site.output_format == "json"


@pytest.mark.parametrize(
    "src",
    [
        "twilio.messages.create(body='hi', to='demo')",
        "client.responses.create(input='no model given')",
        "db.users.create(name='x')",
        "completions.create(model='m')",
        "create(model='m')",
    ],
)
def test_ignores_look_alikes(src: str) -> None:
    assert scan(src) == []


# --- arguments ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("response_format", "expected"),
    [
        ("{'type': 'json_object'}", "json"),
        ("{'type': 'json_schema', 'json_schema': {}}", "json"),
        ("{'type': 'text'}", "text"),
        ("FORMAT", "text"),
    ],
)
def test_output_format(response_format: str, expected: str) -> None:
    (site,) = scan(
        f"client.chat.completions.create(model='m', messages=[], response_format={response_format})"
    )
    assert site.output_format == expected


def test_max_completion_tokens_and_odd_temperatures() -> None:
    (site,) = scan(
        "client.chat.completions.create(model='m', messages=[], max_completion_tokens=40, "
        "temperature=True)"
    )
    assert site.max_tokens == 40
    assert site.temperature is None


def test_model_from_variable_is_dynamic_for_now() -> None:
    (site,) = scan("client.chat.completions.create(model=MODEL, messages=[])")
    assert site.model.value is None
    assert site.model.source == "dynamic"
    assert site.model.expression == "MODEL"


def test_model_passed_via_kwargs() -> None:
    (site,) = scan("client.chat.completions.create(**params)")
    assert site.model.source == "kwargs"
    assert site.model.expression == "**params"
    assert "**params" in site.notes[0]


def test_missing_model() -> None:
    (site,) = scan("client.chat.completions.create(messages=[])")
    assert site.model.source == "missing"
    assert site.notes == ["no model argument found at this call"]


# --- walking a repository -----------------------------------------------------


def test_scan_path_walks_repo_and_skips_noise(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "pkg/a.py": LLM_CALL,
            "pkg/b.py": LLM_CALL,
            "pkg/no_llm.py": "x = 1\n",
            ".venv/lib/site.py": LLM_CALL,
            "node_modules/thing.py": LLM_CALL,
            ".hidden/secret.py": LLM_CALL,
            "tests/test_app.py": LLM_CALL,
            "broken.py": "def oops(:\n",
            "notes.txt": LLM_CALL,
        },
    )
    result = scan_path(tmp_path, ScanConfig(exclude=("tests/*",)))

    assert [s.id for s in result.call_sites] == ["pkg/a.py::classify", "pkg/b.py::classify"]
    assert result.files_scanned == 4  # broken.py, pkg/a.py, pkg/b.py, pkg/no_llm.py
    assert len(result.warnings) == 1
    assert result.warnings[0].startswith("broken.py:1: syntax error")
    assert result.root == tmp_path.name


def test_include_patterns_limit_the_scan(tmp_path: Path) -> None:
    write_tree(tmp_path, {"pkg/a.py": LLM_CALL, "pkg/b.py": LLM_CALL})
    result = scan_path(tmp_path, ScanConfig(include=("pkg/a.py",)))
    assert [s.file for s in result.call_sites] == ["pkg/a.py"]


def test_unreadable_file_becomes_warning(tmp_path: Path) -> None:
    (tmp_path / "latin1.py").write_bytes(b"x = '\xff'\n")
    result = scan_path(tmp_path)
    assert result.call_sites == []
    assert "could not read file" in result.warnings[0]


def test_scan_single_file(tmp_path: Path) -> None:
    path = write_tree(tmp_path, {"one.py": LLM_CALL}) / "one.py"
    result = scan_path(path)
    assert [s.id for s in result.call_sites] == ["one.py::classify"]
    assert result.files_scanned == 1


def test_scan_missing_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        scan_path(tmp_path / "nope")


# --- the demo app -------------------------------------------------------------


def test_supportdesk_physical_call_sites() -> None:
    result = scan_path(SUPPORTDESK)
    by_function = {s.function: s for s in result.call_sites}

    assert result.warnings == []
    assert result.files_scanned == 9
    assert sorted(by_function) == [
        "ask",
        "classify_category",
        "decide_refund",
        "draft_reply",
        "extract_order_info",
        "lang_of",
        "summarize_for_agent",
    ]
    assert by_function["classify_category"].model.source == "literal"
    assert by_function["lang_of"].model.source == "kwargs"
    assert [f for f, s in by_function.items() if s.is_async] == ["draft_reply"]
    json_sites = sorted(f for f, s in by_function.items() if s.output_format == "json")
    assert json_sites == ["decide_refund", "extract_order_info"]
