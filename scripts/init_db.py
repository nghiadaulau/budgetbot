#!/usr/bin/env python3
"""Initialise the database for the configured backend (auto-detected from env).

Usage:  python scripts/init_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.adapters import factory
from src.config import config


def main() -> None:
    store = factory.make_userstore()
    print(f"DB backend: {config.resolved_db_backend}")
    if hasattr(store, "migrate"):
        result = store.migrate()
        print(f"Schema ready · migrate(): {result}")
    else:
        print("Schema ready (no migrate() for this backend)")


if __name__ == "__main__":
    main()
