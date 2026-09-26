"""Structured extraction of order details."""

from __future__ import annotations

import json

from .llm import DEFAULT_MODEL, client

EXTRACTION_MODEL = DEFAULT_MODEL

EXTRACTION_INSTRUCTIONS = (
    "Extract the order ID and the order date from the support ticket.\n"
    "Order IDs look like ORD-12345.\n"
    "Return JSON with exactly two keys: order_id and order_date.\n"
    "order_date must be YYYY-MM-DD. Use null for anything not stated explicitly."
)


def extract_order_info(ticket_text: str) -> dict[str, str | None]:
    """Return {"order_id": ..., "order_date": ...}; missing values are None."""
    response = client.chat.completions.create(
        model=EXTRACTION_MODEL,
        messages=[
            {"role": "system", "content": EXTRACTION_INSTRUCTIONS},
            {"role": "user", "content": ticket_text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=60,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {"order_id": data.get("order_id"), "order_date": data.get("order_date")}
