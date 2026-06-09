"""Cognito JWT verification — real backend auth (closes the X-User-Id IDOR gap).

When a Cognito user pool is configured, an ``Authorization: Bearer <token>`` is
verified against the pool's JWKS (RS256 signature) plus issuer / expiry /
token_use / client_id, and the caller's identity is taken from the ``sub`` claim.

Returns ``None`` (never raises) when not configured or the token is invalid — the
route layer decides whether that means 401 (``REQUIRE_AUTH=true``) or a fallback
to the ``X-User-Id`` header (local/demo, single-user MVP default).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from loguru import logger

from .config import config


def _region() -> str:
    return config.cognito_region or config.aws_region


def _issuer() -> str:
    return f"https://cognito-idp.{_region()}.amazonaws.com/{config.cognito_user_pool_id}"


@lru_cache(maxsize=1)
def _jwks_client() -> Any:
    """Cached PyJWKClient for the pool's JWKS endpoint (keys fetched once + cached)."""
    import jwt

    url = f"{_issuer()}/.well-known/jwks.json"
    return jwt.PyJWKClient(url)


def verify_cognito_token(token: str) -> dict | None:
    """Validate a Cognito access/id token → claims dict, or None if unverifiable."""
    if not config.cognito_user_pool_id:
        return None
    try:
        import jwt

        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=_issuer(),
            options={"verify_aud": False},
        )
    except Exception as exc:  # noqa: BLE001 — any failure ⇒ unauthenticated, never 500
        logger.warning("cognito jwt verification failed: {}", type(exc).__name__)
        return None

    if config.cognito_client_id:
        use = claims.get("token_use")
        if use == "id" and claims.get("aud") != config.cognito_client_id:
            return None
        if use == "access" and claims.get("client_id") != config.cognito_client_id:
            return None
    return claims
