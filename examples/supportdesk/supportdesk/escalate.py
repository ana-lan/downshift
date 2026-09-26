"""Escalation notes for the tier-2 support team."""

from __future__ import annotations

from typing import Any

from .llm import client


def escalation_note(ticket: dict[str, Any], summary: str) -> str:
    """Detailed hand-off note for tier-2 support, written for every ticket."""
    response = client.chat.completions.create(
        model="qwen2.5:7b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior support lead at SupportDesk Store. Write a detailed "
                    "escalation note for the tier-2 team: customer history, the problem, what "
                    "was tried, risks, and a recommended next step. Be thorough."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Agent summary: {summary}\n\n"
                    f"Subject: {ticket['subject']}\n"
                    f"Message:\n{ticket['body']}"
                ),
            },
        ],
        temperature=0,
        max_tokens=1024,
    )
    return (response.choices[0].message.content or "").strip()
