"""Cost instrumentation. Every AI call is recorded (tokens, latency, estimated
USD) to the `cost_log` table and emitted as a structured, PII-safe log line.

The /admin/cost-report endpoint and scripts/cost_estimate.py read this data.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from .adapters.ai import TokenUsage

try:  # pragma: no cover - trivial import guard
    from loguru import logger as _loguru

    def _emit(payload: dict) -> None:
        _loguru.bind(**payload).info(payload.get("event", "ai_cost"))
except ImportError:  # pragma: no cover
    _std = logging.getLogger("budgetbot.cost")

    def _emit(payload: dict) -> None:
        _std.info(json.dumps(payload, ensure_ascii=False))


def mask_user_id(user_id: str) -> str:
    """PII-safe: keep the first 3 chars, mask the rest ('alice' → 'ali***')."""
    if not user_id:
        return "***"
    return f"{user_id[:3]}***"


@dataclass
class CostEntry:
    ts: str
    user_id: str
    flow: str
    model_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    estimated_cost_usd: float
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class CostTracker:
    """Persists cost entries to the store and emits a structured log line.

    `store` must implement `log_cost(entry: dict)`; failures are swallowed so
    instrumentation never breaks a request.
    """

    def __init__(self, store) -> None:
        self._store = store

    def record(self, user_id: str, flow: str, usage: TokenUsage) -> CostEntry:
        entry = CostEntry(
            ts=datetime.now(UTC).isoformat(),
            user_id=user_id,
            flow=flow,
            model_id=usage.model_id,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=usage.latency_ms,
            estimated_cost_usd=usage.estimated_cost_usd,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
        )
        try:
            if hasattr(self._store, "log_cost"):
                self._store.log_cost(asdict(entry))
        except Exception:  # noqa: BLE001 — never break a request on logging
            pass

        _emit({
            "event": "ai_cost",
            "ts": entry.ts,
            "user": mask_user_id(user_id),
            "flow": flow,
            "model": usage.model_id,
            "tokens_in": usage.input_tokens,
            "tokens_out": usage.output_tokens,
            "latency_ms": usage.latency_ms,
            "cost_usd": usage.estimated_cost_usd,
        })
        return entry
