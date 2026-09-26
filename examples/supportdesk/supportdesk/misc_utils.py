"""Assorted helpers."""

from __future__ import annotations

from typing import Any

from .llm import client
from .models import model_for

_LANG_REQUEST: dict[str, Any] = {"temperature": 0, "max_tokens": 5}


def lang_of(text: str) -> str:
    """Return the two-letter ISO 639-1 code of the text's language."""
    params = dict(_LANG_REQUEST)
    params["model"] = model_for("lang_of")
    params["messages"] = [
        {
            "role": "user",
            "content": (
                "Which language is this text written in? Reply with the two-letter "
                "ISO 639-1 code only (for example: en, es, fr).\n\n"
                f"Text:\n{text}"
            ),
        }
    ]
    response = client.chat.completions.create(**params)
    return (response.choices[0].message.content or "").strip().lower()[:2]
