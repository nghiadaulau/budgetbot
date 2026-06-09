"""Backend Cognito-JWT auth (P0-1). Default REQUIRE_AUTH=off keeps the
X-User-Id / single-user MVP behaviour; when on, only a verified Bearer passes."""
from src import app as app_module
from src.auth import verify_cognito_token
from src.config import config


class FakeReq:
    def __init__(self, headers=None, scope=None):
        self.headers = headers or {}
        self.scope = scope or {}


def _require_auth(flag: bool):
    object.__setattr__(config, "require_auth", flag)


def test_x_user_id_used_when_auth_off():
    assert app_module._resolve_user_id(FakeReq(), "alice") == "alice"


def test_verified_bearer_preferred_over_header(monkeypatch):
    monkeypatch.setattr(app_module, "verify_cognito_token", lambda t: {"sub": "u-cognito"})
    req = FakeReq(headers={"authorization": "Bearer tok"})
    assert app_module._resolve_user_id(req, "alice") == "u-cognito"


def test_invalid_bearer_falls_back_to_header_when_auth_off(monkeypatch):
    monkeypatch.setattr(app_module, "verify_cognito_token", lambda t: None)
    req = FakeReq(headers={"authorization": "Bearer bad"})
    assert app_module._resolve_user_id(req, "alice") == "alice"


def test_require_auth_blocks_missing_token():
    _require_auth(True)
    try:
        assert app_module._resolve_user_id(FakeReq(), "alice") is None
    finally:
        _require_auth(False)


def test_require_auth_blocks_invalid_token(monkeypatch):
    monkeypatch.setattr(app_module, "verify_cognito_token", lambda t: None)
    _require_auth(True)
    try:
        req = FakeReq(headers={"authorization": "Bearer bad"})
        assert app_module._resolve_user_id(req, "alice") is None
    finally:
        _require_auth(False)


def test_require_auth_allows_verified_token(monkeypatch):
    monkeypatch.setattr(app_module, "verify_cognito_token", lambda t: {"sub": "u9"})
    _require_auth(True)
    try:
        req = FakeReq(headers={"authorization": "Bearer ok"})
        assert app_module._resolve_user_id(req, None) == "u9"
    finally:
        _require_auth(False)


def test_verify_returns_none_when_pool_not_configured():
    assert verify_cognito_token("any.jwt.token") is None


def test_endpoint_401_when_auth_required_and_no_token(client):
    _require_auth(True)
    try:
        r = client.get("/transactions", headers={"X-User-Id": "alice"})
        assert r.status_code == 401
    finally:
        _require_auth(False)


def test_endpoint_ok_with_verified_token(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "verify_cognito_token", lambda t: {"sub": "u-ok"})
    _require_auth(True)
    try:
        r = client.get("/transactions", headers={"Authorization": "Bearer good"})
        assert r.status_code == 200
    finally:
        _require_auth(False)
