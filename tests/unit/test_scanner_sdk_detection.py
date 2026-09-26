"""Scanner fixes found on real repos: BOM files and SDK calls that pass the model via **kwargs."""

import textwrap
from pathlib import Path

from downshift.scanner import scan_path, scan_source
from downshift.schema import CallSite


def scan(src: str) -> list[CallSite]:
    return scan_source(textwrap.dedent(src), "app.py")


def test_anthropic_splat_with_import_inside_try() -> None:
    (site,) = scan(
        """
        try:
            import anthropic
        except ImportError:
            raise

        class LLM:
            def __init__(self):
                self.client = anthropic.Anthropic()

            def generate(self, params):
                return self.client.messages.create(**params)
        """
    )
    assert site.api == "anthropic.messages"
    assert site.function == "LLM.generate"


def test_anthropic_splat_with_from_import() -> None:
    (site,) = scan(
        """
        from anthropic import Anthropic
        client = Anthropic()

        def ask(params):
            return client.messages.create(**params)
        """
    )
    assert site.api == "anthropic.messages"


def test_openai_responses_splat_with_openai_import() -> None:
    (site,) = scan(
        """
        from openai import OpenAI
        client = OpenAI()

        def ask(kwargs):
            return client.responses.create(**kwargs)
        """
    )
    assert site.api == "openai.responses"


def test_splat_without_sdk_import_is_ignored() -> None:
    # e.g. Twilio: client.messages.create(**sms) is not an LLM call
    assert (
        scan(
            """
            from twilio.rest import Client
            client = Client()

            def send(sms):
                return client.messages.create(**sms)
            """
        )
        == []
    )


def test_splat_with_wrong_sdk_is_ignored() -> None:
    # openai imported, but messages.create is the Anthropic API
    assert (
        scan(
            """
            import openai

            def send(kw):
                return thing.messages.create(**kw)
            """
        )
        == []
    )


def test_file_with_byte_order_mark_is_scanned(tmp_path: Path) -> None:
    src = textwrap.dedent(
        """
        from openai import OpenAI
        client = OpenAI()

        def classify(text):
            return client.chat.completions.create(model="gpt-big", messages=[])
        """
    )
    (tmp_path / "app.py").write_bytes(b"\xef\xbb\xbf" + src.encode("utf-8"))
    result = scan_path(tmp_path)
    assert result.warnings == []
    assert [s.api for s in result.call_sites] == ["openai.chat.completions"]
