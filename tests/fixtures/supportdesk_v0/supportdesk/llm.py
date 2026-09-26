"""Shared LLM client setup for SupportDesk.

Every feature in this app defaults to the biggest model. Nobody has checked
whether that is actually needed. Downshift exists to answer that question.
"""

from __future__ import annotations

import os

from openai import AsyncOpenAI, OpenAI

BASE_URL = os.getenv("SUPPORTDESK_LLM_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("SUPPORTDESK_LLM_API_KEY", "ollama")

DEFAULT_MODEL = os.getenv("SUPPORTDESK_MODEL", "qwen2.5:7b")

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
async_client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)


def ask(prompt: str, *, system: str | None = None, max_tokens: int = 64) -> str:
    """Send one prompt to the default model and return the text reply.

    Several features call this helper, so a single call site here serves
    more than one product use case.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=messages,
        temperature=0,
        max_tokens=max_tokens,
    )
    return (response.choices[0].message.content or "").strip()
