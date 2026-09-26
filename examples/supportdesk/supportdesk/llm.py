"""Shared LLM client setup for SupportDesk.

Callers must pass a feature name so the correct model is resolved from
models.yaml at call time.
"""

from __future__ import annotations

import os

from openai import AsyncOpenAI, OpenAI

from .models import model_for

BASE_URL = os.getenv("SUPPORTDESK_LLM_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("SUPPORTDESK_LLM_API_KEY", "ollama")

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
async_client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)


def ask(prompt: str, *, feature: str, system: str | None = None, max_tokens: int = 64) -> str:
    """Send one prompt to the model for *feature* and return the text reply."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model_for(feature),
        messages=messages,
        temperature=0,
        max_tokens=max_tokens,
    )
    return (response.choices[0].message.content or "").strip()
