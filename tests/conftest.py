"""Shared pytest fixtures. Forces fully-local backends (LocalAI + SQLite +
LocalStub PDF) at import time so the suite never touches AWS.
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="budgetbot-tests-")
os.environ.setdefault("AI_BACKEND", "local")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("DB_BACKEND", "sqlite")
os.environ.setdefault("PDF_BACKEND", "local")
os.environ.setdefault("SERVE_FRONTEND", "false")
os.environ.setdefault("DB_PATH", str(Path(_TMP) / "test.db"))
os.environ.setdefault("STORAGE_LOCAL_DIR", str(Path(_TMP) / "uploads"))
os.environ.setdefault("DEDUP_ENABLED", "true")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402  (must follow the env + sys.path setup above)
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def app_module():
    import src.app as app_module
    return app_module


@pytest.fixture(scope="session")
def client(app_module):
    return TestClient(app_module.app, raise_server_exceptions=False)


@pytest.fixture
def uid() -> str:
    """A unique user id per test → isolation without a fresh DB each time."""
    return f"u-{uuid.uuid4().hex[:10]}"


@pytest.fixture
def headers(uid):
    return {"X-User-Id": uid}


SAMPLE_CSV = (
    b"date,description,amount\n"
    b"2026-06-01,SALARY JUNE 2026,28000000\n"
    b"2026-06-02,HIGHLANDS COFFEE BUI VIEN,-65000\n"
    b"2026-06-03,EVN HCMC TIEN DIEN,-850000\n"
    b"2026-06-04,GRAB CITY,-48000\n"
    b"2026-06-05,SHOPEE ORDER,-450000\n"
)
