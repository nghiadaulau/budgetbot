"""Normalisation + fingerprinting for deduplication.

The transaction fingerprint deliberately EXCLUDES the date so that the same
purchase recorded a day apart (timezone / posting-delay) can still be matched
with a configurable date tolerance. Within-batch exact duplicates additionally
share the same date, so date proximity is checked separately by DedupService.
"""
from __future__ import annotations

import hashlib
import re

_TXN_ID_RE = re.compile(r"\*\d+|#\d+|-\d{6,}|\bid[:#]?\s*\w+", re.IGNORECASE)
_DATE_RE = re.compile(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_description(description: str) -> str:
    """Lowercase, drop transaction IDs / dates / punctuation, sort tokens.

    Token sorting makes "Highlands Coffee BV" and "BV Highlands Coffee" match.
    """
    text = (description or "").lower()
    text = _TXN_ID_RE.sub(" ", text)
    text = _DATE_RE.sub(" ", text)
    text = _PUNCT_RE.sub(" ", text)
    tokens = sorted(t for t in _WS_RE.split(text) if t)
    return " ".join(tokens)


def normalize_amount(amount: float) -> int:
    """Round to whole VND (amounts are integer-VND in this domain)."""
    return int(round(float(amount)))


def transaction_fingerprint(user_id: str, amount: float, description: str) -> str:
    """Date-less fingerprint: sha256(user_id | amount | normalized_description)."""
    key = f"{user_id}|{normalize_amount(amount)}|{normalize_description(description)}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def file_hash(content: bytes) -> str:
    """SHA-256 of raw file content (file-level dedup)."""
    return hashlib.sha256(content).hexdigest()


def receipt_fingerprint(user_id: str, merchant: str, date: str, total_amount: float) -> str:
    """Strong receipt fingerprint from extracted fields (catches re-scans)."""
    key = (
        f"{user_id}|{normalize_description(merchant)}|{date[:10]}|"
        f"{normalize_amount(total_amount)}"
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
