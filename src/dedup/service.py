"""DedupService — orchestrates the 4 levels of duplicate detection.

Level 1: file hash (whole upload already processed) → DuplicateFileError.
Level 2: transaction fingerprint, within-batch + across DB (± date tolerance).
Level 3: manual-entry soft warning (wider window, doesn't block).
Level 4: PDF receipt fingerprint (re-scan of the same receipt).

All checks are no-ops when config.dedup_enabled is False.
"""
from __future__ import annotations

from datetime import date, timedelta

from .normalize import (
    file_hash,
    receipt_fingerprint,
    transaction_fingerprint,
)


class DuplicateFileError(Exception):
    """Raised when an identical file (same hash) was already processed."""

    def __init__(self, existing: dict) -> None:
        self.existing = existing
        super().__init__("duplicate_file")


def _within_days(a: str, b: str, tolerance: int) -> bool:
    try:
        da = date.fromisoformat(a[:10])
        db = date.fromisoformat(b[:10])
    except (ValueError, TypeError):
        return a[:10] == b[:10]
    return abs((da - db).days) <= tolerance


class DedupService:
    """Stateless helper over a store that implements the dedup query methods."""

    def __init__(self, store, config) -> None:
        self._store = store
        self._cfg = config

    @property
    def enabled(self) -> bool:
        return bool(getattr(self._cfg, "dedup_enabled", True))

    def check_file(self, user_id: str, content: bytes) -> str:
        """Return the file hash; raise DuplicateFileError if already processed."""
        digest = file_hash(content)
        if self.enabled and hasattr(self._store, "find_uploaded_file"):
            existing = self._store.find_uploaded_file(user_id, digest)
            if existing:
                raise DuplicateFileError(existing)
        return digest

    def partition_transactions(self, user_id: str, rows: list[dict]) -> tuple[list[dict], list[dict]]:
        """Split parsed rows into (new, duplicates).

        Adds a `fingerprint` to each new row. Duplicates carry `matched_existing_id`
        (or `matched_row` for within-batch hits) and the original row index.
        """
        if not self.enabled:
            for r in rows:
                r["fingerprint"] = transaction_fingerprint(
                    user_id, r.get("amount", 0), r.get("description", "")
                )
            return rows, []

        tol = self._cfg.dedup_date_tolerance_days
        new_rows: list[dict] = []
        duplicates: list[dict] = []
        seen: list[dict] = []

        for idx, row in enumerate(rows):
            fp = transaction_fingerprint(user_id, row.get("amount", 0), row.get("description", ""))
            row["fingerprint"] = fp
            row_date = str(row.get("date", ""))

            batch_hit = next(
                (s for s in seen if s["fingerprint"] == fp and _within_days(s["date"], row_date, tol)),
                None,
            )
            if batch_hit:
                duplicates.append({**_dup_view(idx, row), "matched_existing_id": None,
                                   "matched_in_batch": True})
                continue

            existing = self._find_existing(user_id, fp, row_date, tol)
            if existing:
                duplicates.append({**_dup_view(idx, row),
                                   "matched_existing_id": existing.get("id")})
                continue

            seen.append({"fingerprint": fp, "date": row_date})
            new_rows.append(row)

        return new_rows, duplicates

    def _find_existing(self, user_id: str, fingerprint: str, around_date: str, tol: int):
        if not hasattr(self._store, "find_transactions_by_fingerprint"):
            return None
        candidates = self._store.find_transactions_by_fingerprint(user_id, fingerprint)
        for c in candidates:
            if _within_days(str(c.get("date", "")), around_date, tol):
                return c
        return None

    def check_manual_warning(self, user_id: str, txn: dict) -> list[dict]:
        """Return matching transactions within the wider manual window (no block)."""
        if not self.enabled or not hasattr(self._store, "find_transactions_by_fingerprint"):
            return []
        fp = transaction_fingerprint(user_id, txn.get("amount", 0), txn.get("description", ""))
        window = self._cfg.dedup_manual_warn_days
        return [
            c for c in self._store.find_transactions_by_fingerprint(user_id, fp)
            if _within_days(str(c.get("date", "")), str(txn.get("date", "")), window)
        ]

    def receipt_fingerprint(self, user_id: str, merchant: str, date_str: str, total: float) -> str:
        return receipt_fingerprint(user_id, merchant, date_str, total)

    def check_receipt(self, user_id: str, merchant: str, date_str: str, total: float) -> list[dict]:
        if not self.enabled or not hasattr(self._store, "find_receipt_by_fingerprint"):
            return []
        fp = self.receipt_fingerprint(user_id, merchant, date_str, total)
        return self._store.find_receipt_by_fingerprint(user_id, fp)


def _dup_view(idx: int, row: dict) -> dict:
    return {
        "row": idx + 1,
        "description": row.get("description"),
        "amount": row.get("amount"),
        "date": row.get("date"),
    }


__all__ = ["DedupService", "DuplicateFileError", "date", "timedelta"]
