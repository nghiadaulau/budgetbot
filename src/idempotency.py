"""Idempotency for mutating endpoints (brief §Determinism.3).

A client may send an ``Idempotency-Key`` header on POST /upload and
POST /transaction; the first successful response is cached and any replay with
the same (user, scope, key) returns it verbatim instead of re-processing — so a
retried upload never double-imports.

No-ops gracefully when the store doesn't implement the interface or no key is
supplied (the endpoint simply runs normally).
"""
from __future__ import annotations

import json
from typing import Any

from .config import config


class IdempotencyService:
    def __init__(self, store: Any) -> None:
        self._store = store
        self._ttl_days = config.idempotency_ttl_days
        self.enabled = hasattr(store, "idempotency_get")

    def get(self, user_id: str, scope: str, key: str | None) -> dict | None:
        """Return a previously cached response for this key (within TTL), or None."""
        if not (self.enabled and key):
            return None
        raw = self._store.idempotency_get(user_id, f"{scope}:{key}", self._ttl_days)
        return json.loads(raw) if raw else None

    def put(self, user_id: str, scope: str, key: str | None, response: dict) -> None:
        """Cache a successful response so future replays return it verbatim."""
        if not (self.enabled and key):
            return
        try:
            payload = json.dumps(response, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return
        self._store.idempotency_put(user_id, f"{scope}:{key}", payload, self._ttl_days)
