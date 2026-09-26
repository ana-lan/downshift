"""Runs one ticket through every LLM feature in SupportDesk."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from .agent_assist import draft_reply, summarize_for_agent
from .extract import extract_order_info
from .misc_utils import lang_of
from .policy import decide_refund
from .triage import classify_category, detect_sentiment, tag_urgency

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "tickets.jsonl"

T = TypeVar("T")


def load_tickets(path: Path = DATA_PATH) -> list[dict[str, Any]]:
    """Load tickets from a JSONL file."""
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _timed(step: str, timings: dict[str, float], fn: Callable[[], T]) -> T:
    start = time.perf_counter()
    result = fn()
    timings[step] = round(time.perf_counter() - start, 2)
    return result


def process_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    """Run all 8 LLM features on a ticket and return results plus per-step timings."""
    text = f"{ticket['subject']}\n\n{ticket['body']}"
    timings: dict[str, float] = {}

    language = _timed("detect_language", timings, lambda: lang_of(text))
    category = _timed("classify_category", timings, lambda: classify_category(text))
    sentiment = _timed("detect_sentiment", timings, lambda: detect_sentiment(text))
    urgency = _timed("tag_urgency", timings, lambda: tag_urgency(text, category))
    order_info = _timed("extract_order_info", timings, lambda: extract_order_info(text))
    summary = _timed("summarize_for_agent", timings, lambda: summarize_for_agent(ticket))
    refund = _timed("decide_refund", timings, lambda: decide_refund(ticket, order_info))
    reply = _timed(
        "draft_reply", timings, lambda: asyncio.run(draft_reply(ticket, summary, language))
    )

    return {
        "ticket_id": ticket["id"],
        "language": language,
        "category": category,
        "sentiment": sentiment,
        "urgency": urgency,
        "order_info": order_info,
        "summary": summary,
        "refund": refund,
        "reply": reply,
        "timings_s": timings,
    }
