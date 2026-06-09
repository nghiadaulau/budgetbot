#!/usr/bin/env python3
"""Seed the DB with the sample statement for local development.

Usage:  python scripts/seed_db.py --user-id demo --count 50
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.adapters import factory
from src.cost_tracker import CostTracker
from src import services

SAMPLE = Path(__file__).resolve().parent.parent / "sample_data" / "sample_statement.csv"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default="demo")
    parser.add_argument("--count", type=int, default=0, help="0 = all rows")
    args = parser.parse_args()

    content = SAMPLE.read_bytes()
    if args.count:
        lines = content.decode().splitlines()
        content = ("\n".join(lines[: args.count + 1]) + "\n").encode()

    store = factory.make_userstore()
    if hasattr(store, "migrate"):
        store.migrate()
    ai_client = factory.make_ai()
    cost = CostTracker(store)

    result = services.process_csv(
        user_id=args.user_id, filename="sample_statement.csv", content=content,
        store=store, ai_client=ai_client, cost_tracker=cost, force="append",
    )
    print(f"Seeded user '{args.user_id}': "
          f"{result['rows_inserted']} saved, "
          f"{result['summary']['duplicates_skipped']} duplicates skipped.")


if __name__ == "__main__":
    main()
