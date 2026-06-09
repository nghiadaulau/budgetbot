"""Merchant catalog — a persistent description→category cache that lets repeat
merchants skip the LLM entirely.

This module is the *persistent* tier (a per-user table accumulating category /
confidence / count). The in-upload memo tier — collapsing duplicate descriptions
within one batch — lives in ``services._classify_rows`` where rows are deduped by
``description_hash`` before classification.

Once a normalized description has been seen ``catalog_min_samples`` times with an
average confidence ≥ ``catalog_min_confidence``, classification short-circuits to
the catalog and no Bedrock call is made.
"""
from __future__ import annotations

import hashlib
import re

from .config import config
from .models import confidence_score

_WS = re.compile(r"\s+")
_NONWORD = re.compile(r"[^0-9a-zà-ỹ ]", re.IGNORECASE)


def normalize_description(description: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — a stable cache key."""
    s = (description or "").lower().strip()
    s = _NONWORD.sub(" ", s)
    return _WS.sub(" ", s).strip()


def description_hash(description: str) -> str:
    """SHA-1 of the normalized description (the catalog key)."""
    return hashlib.sha1(normalize_description(description).encode("utf-8")).hexdigest()


class CatalogService:
    """Per-user, per-upload view over the merchant catalog.

    Disabled (every lookup misses, every record no-ops) when the store doesn't
    implement the catalog interface or CATALOG_ENABLED is false — so non-SQLite
    backends degrade gracefully to always-classify.
    """

    def __init__(self, store, user_id: str, cfg=config) -> None:
        self._store = store
        self._user_id = user_id
        self._cfg = cfg
        self.enabled = bool(cfg.catalog_enabled and hasattr(store, "catalog_lookup"))

    def lookup(self, description: str) -> dict | None:
        """Return a confident cached classification, or None to classify fresh."""
        if not self.enabled:
            return None
        row = self._store.catalog_lookup(self._user_id, description_hash(description))
        if (
            row
            and row["sample_count"] >= self._cfg.catalog_min_samples
            and row["avg_confidence"] >= self._cfg.catalog_min_confidence
        ):
            return {"category": row["category"], "confidence": "high",
                    "needs_review": False, "source": "cache"}
        return None

    def record(self, description: str, category: str, confidence: str) -> None:
        """Persist a fresh classification so future identical merchants hit cache.

        Weak guesses (confidence below the catalog threshold) are not persisted —
        we never want the cache to harden a low-quality categorization.
        """
        if not self.enabled:
            return
        score = confidence_score(confidence)
        if score < self._cfg.catalog_min_confidence:
            return
        self._store.catalog_record(self._user_id, description_hash(description), category, score)
