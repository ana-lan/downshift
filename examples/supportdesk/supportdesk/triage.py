"""Ticket triage: category, sentiment, urgency."""

from __future__ import annotations

from .llm import ask, client

CATEGORIES = ("billing", "shipping", "technical", "account", "refund", "other")


def classify_category(ticket_text: str) -> str:
    """Classify a ticket into one of CATEGORIES."""
    response = client.chat.completions.create(
        model="qwen2.5:7b",
        messages=[
            {"role": "system", "content": "You are a support ticket classifier."},
            {
                "role": "user",
                "content": (
                    "Classify this support ticket into exactly one category: "
                    + ", ".join(CATEGORIES)
                    + ".\nReply with the category name only.\n\nTicket:\n"
                    + ticket_text
                ),
            },
        ],
        temperature=0,
        max_tokens=5,
    )
    return (response.choices[0].message.content or "").strip().lower()


def detect_sentiment(ticket_text: str) -> str:
    """Return positive, neutral, or negative."""
    reply = ask(
        "What is the customer's overall sentiment? "
        "Reply with one word: positive, neutral, or negative.\n\n"
        f"Ticket:\n{ticket_text}",
        max_tokens=3,
    )
    return reply.lower().strip(".")


def tag_urgency(ticket_text: str, category: str) -> str:
    """Return low, medium, or high."""
    prompt = (
        f"This is a '{category}' support ticket.\n"
        "Rate its urgency as low, medium, or high.\n"
        "High: money lost, service down for many users, or a very angry repeat contact.\n"
        "Medium: an order or account problem that blocks the customer.\n"
        "Low: questions, feedback, and requests with no time pressure.\n"
        "Reply with one word.\n\n"
        f"Ticket:\n{ticket_text}"
    )
    reply = ask(prompt, system="You are a support operations lead.", max_tokens=3)
    return reply.lower().strip(".")
