"""Per-user API rate limiting (fixed window per minute).

Backend chosen by env (adapter pattern, like everything else):
  - LocalRateLimiter — in-memory, per-process. Fine for local/dev and a single
    Fargate task.
  - RedisRateLimiter — shared counter in Redis/**Valkey** (ElastiCache). Needed so
    the limit holds ACROSS Fargate tasks. Valkey speaks the Redis wire protocol, so
    redis-py connects unchanged (use rediss:// for TLS).

Both fail **open** (allow) on an internal error — a limiter outage must never take
the API down. `allow(key) → (allowed, retry_after_seconds)`.
"""
from __future__ import annotations

import threading
import time

from loguru import logger

from .config import config


class LocalRateLimiter:
    def __init__(self, per_minute: int) -> None:
        self._limit = per_minute
        self._lock = threading.Lock()
        self._hits: dict[tuple[str, int], int] = {}

    def allow(self, key: str) -> tuple[bool, int]:
        now = int(time.time())
        window = now // 60
        retry_after = 60 - (now % 60)
        with self._lock:
            count = self._hits.get((key, window), 0) + 1
            self._hits[(key, window)] = count
            if len(self._hits) > 10_000:
                self._hits = {k: v for k, v in self._hits.items() if k[1] >= window}
        return count <= self._limit, retry_after


class RedisRateLimiter:
    def __init__(self, url: str, per_minute: int) -> None:
        import redis

        self._redis = redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)
        self._limit = per_minute

    def allow(self, key: str) -> tuple[bool, int]:
        now = int(time.time())
        window = now // 60
        retry_after = 60 - (now % 60)
        redis_key = f"rl:{key}:{window}"
        try:
            count = self._redis.incr(redis_key)
            if count == 1:
                self._redis.expire(redis_key, 70)
        except Exception:  # noqa: BLE001 — fail open: never block on a limiter outage
            logger.warning("rate limiter (redis) unavailable; allowing request")
            return True, 0
        return count <= self._limit, retry_after


def make_rate_limiter():
    """Redis/Valkey when REDIS_URL is set, else in-memory."""
    if config.redis_url:
        try:
            return RedisRateLimiter(config.redis_url, config.rate_limit_per_minute)
        except ImportError:
            logger.warning("redis not installed; falling back to in-memory rate limiter")
    return LocalRateLimiter(config.rate_limit_per_minute)
