"""Helpers for human support agents: summaries and draft replies."""

from __future__ import annotations

from typing import Any

from .llm import async_client, client
from .models import model_for


def summarize_for_agent(ticket: dict[str, Any]) -> str:
    """Two-sentence summary a human agent can read at a glance."""
    prompt = f"""Summarize this support ticket for a human support agent.
Write exactly 2 short sentences in English: what the customer wants,
and the key details (order ID, dates, amounts) if present.

Subject: {ticket["subject"]}
Message:
{ticket["body"]}
"""
    response = client.chat.completions.create(
        model=model_for("summarize_for_agent"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=120,
    )
    return (response.choices[0].message.content or "").strip()


async def draft_reply(ticket: dict[str, Any], summary: str, language: str) -> str:
    """Draft a reply to the customer, in the customer's language."""
    response = await async_client.chat.completions.create(
        model=model_for("draft_reply"),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a friendly, concise customer support agent for SupportDesk Store. "
                    "Never promise refunds, credits, or delivery dates. Say a teammate will "
                    "confirm next steps. Keep replies under 120 words."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Reply language (ISO 639-1): {language}\n"
                    f"Agent summary: {summary}\n\n"
                    f"Customer subject: {ticket['subject']}\n"
                    f"Customer message:\n{ticket['body']}"
                ),
            },
        ],
        temperature=0,
        max_tokens=250,
    )
    return (response.choices[0].message.content or "").strip()
