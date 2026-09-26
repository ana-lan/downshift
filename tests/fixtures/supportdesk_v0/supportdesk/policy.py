"""Refund eligibility decisions against the written refund policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .llm import client

POLICY_PATH = Path(__file__).resolve().parent.parent / "data" / "refund_policy.md"

MODELS = {"refund_decision": "qwen2.5:7b"}


def decide_refund(ticket: dict[str, Any], order_info: dict[str, str | None]) -> dict[str, Any]:
    """Apply the refund policy to a ticket.

    Returns {"is_refund_request", "eligible", "policy_section", "reasoning"}.
    """
    policy = POLICY_PATH.read_text(encoding="utf-8")
    response = client.chat.completions.create(
        model=MODELS["refund_decision"],
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a refund policy assistant. Apply the policy exactly as written. "
                    "Count days carefully between the order date and today's date."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Refund policy:\n{policy}\n\n"
                    f"Today's date: {ticket['created_at']}\n"
                    f"Extracted order info: {json.dumps(order_info)}\n\n"
                    f"Ticket subject: {ticket['subject']}\n"
                    f"Ticket message:\n{ticket['body']}\n\n"
                    "Return JSON with these keys, in this order:\n"
                    '  "reasoning": 1-3 sentences applying the policy,\n'
                    '  "is_refund_request": true or false,\n'
                    '  "eligible": "yes", "no", "store_credit", or "need_info",\n'
                    '  "policy_section": the section number you applied, e.g. "2.1".\n'
                    'If it is not a refund request, set eligible to "no" and policy_section '
                    "to null."
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=220,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {
        "is_refund_request": data.get("is_refund_request"),
        "eligible": data.get("eligible"),
        "policy_section": data.get("policy_section"),
        "reasoning": data.get("reasoning"),
    }
