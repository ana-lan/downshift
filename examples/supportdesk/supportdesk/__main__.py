"""Command line entry point: python -m supportdesk."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pipeline import DATA_PATH, load_tickets, process_ticket


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="supportdesk", description="Run SupportDesk's LLM features on tickets."
    )
    parser.add_argument("--ticket", help="Ticket ID to process, e.g. T001.")
    parser.add_argument("--limit", type=int, default=1, help="Process the first N tickets.")
    parser.add_argument("--data", type=Path, default=DATA_PATH, help="Path to tickets.jsonl.")
    args = parser.parse_args(argv)

    tickets = load_tickets(args.data)
    if args.ticket:
        tickets = [t for t in tickets if t["id"] == args.ticket]
        if not tickets:
            print(f"Ticket {args.ticket} not found in {args.data}", file=sys.stderr)
            return 1
    else:
        tickets = tickets[: args.limit]

    for ticket in tickets:
        result = process_ticket(ticket)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        total = sum(result["timings_s"].values())
        print(f"{ticket['id']}: 8 LLM calls in {total:.1f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
