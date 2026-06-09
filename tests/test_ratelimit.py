"""API rate limiting — in-memory + Redis/Valkey backends, and the 429 path."""
import os

import pytest

from src import app as app_module
from src.config import config
from src.ratelimit import LocalRateLimiter, RedisRateLimiter, make_rate_limiter

REDIS_URL = os.environ.get("TEST_REDIS_URL")


def test_local_allows_up_to_limit_then_denies():
    rl = LocalRateLimiter(per_minute=3)
    decisions = [rl.allow("u1")[0] for _ in range(5)]
    assert decisions == [True, True, True, False, False]


def test_local_isolated_per_key():
    rl = LocalRateLimiter(per_minute=1)
    assert rl.allow("a")[0] is True
    assert rl.allow("a")[0] is False
    assert rl.allow("b")[0] is True


def test_local_returns_retry_after():
    rl = LocalRateLimiter(per_minute=1)
    _, retry = rl.allow("u")
    assert 0 < retry <= 60


def test_endpoint_returns_429_over_limit(client):
    original = app_module.rate_limiter
    app_module.rate_limiter = LocalRateLimiter(per_minute=2)
    object.__setattr__(config, "rate_limit_enabled", True)
    body = {"date": "2026-06-01", "description": "Cafe", "amount": -1000, "category": "Food"}
    h = {"X-User-Id": "rl-user"}
    try:
        assert client.post("/transaction?confirm=true", json=body, headers=h).status_code == 200
        assert client.post("/transaction?confirm=true", json=body, headers=h).status_code == 200
        r = client.post("/transaction?confirm=true", json=body, headers=h)
        assert r.status_code == 429
        assert r.headers.get("Retry-After")
        assert r.json()["error"] == "rate_limited"
    finally:
        object.__setattr__(config, "rate_limit_enabled", False)
        app_module.rate_limiter = original


@pytest.mark.skipif(not REDIS_URL, reason="TEST_REDIS_URL not set")
def test_redis_allows_then_denies():
    import uuid

    rl = RedisRateLimiter(REDIS_URL, per_minute=2)
    key = f"u-{uuid.uuid4().hex[:8]}"
    assert rl.allow(key)[0] is True
    assert rl.allow(key)[0] is True
    assert rl.allow(key)[0] is False


def test_make_rate_limiter_defaults_to_local():
    assert isinstance(make_rate_limiter(), LocalRateLimiter)
