#!/usr/bin/env python3
"""Apply the dedup schema migration (fingerprint column + uploaded_files +
receipt_extractions + cost_log) and backfill fingerprints for existing rows.

Idempotent — safe to run repeatedly.

Usage:  python scripts/migrate_add_dedup.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.adapters import factory
from src.config import config


def main() -> None:
    store = factory.make_userstore()
    if not hasattr(store, "migrate"):
        print(f"Backend '{config.resolved_db_backend}' has no migrate() — "
              "implement it on the store before deploying dedup there.")
        return
    result = store.migrate()
    print(f"Migration applied on '{config.resolved_db_backend}': {result}")


if __name__ == "__main__":
    main()
