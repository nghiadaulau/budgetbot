"""Concurrency: the stores must survive concurrent request threads (FastAPI runs
sync routes in a thread pool) — no 'database is locked' / cursor races, no lost
writes. SQLite uses thread-local connections; Postgres a ThreadedConnectionPool."""
import os
import threading
import uuid

import pytest

from src.adapters.userstore import SQLiteUserStore

PG_URL = os.environ.get("TEST_POSTGRES_URL")


def _txn(i: int) -> dict:
    return {"date": "2026-06-01", "description": f"t{i}", "amount": -1000.0,
            "category": "Other", "confidence": "low", "needs_review": False}


def test_concurrent_writes_no_errors_no_lost_rows(tmp_path):
    store = SQLiteUserStore(db_path=str(tmp_path / "c.db"))
    errors: list[Exception] = []
    THREADS, PER = 8, 25

    def worker(n: int):
        try:
            for i in range(PER):
                store.add_transaction(f"u{n}", _txn(i))
        except Exception as exc:  # noqa: BLE001 — collect any race error
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    total = sum(len(store.list_transactions(f"u{n}")) for n in range(THREADS))
    assert total == THREADS * PER


def test_concurrent_reads_and_writes_mixed(tmp_path):
    store = SQLiteUserStore(db_path=str(tmp_path / "rw.db"))
    errors: list[Exception] = []

    def writer():
        try:
            for i in range(40):
                store.add_transaction("u1", _txn(i))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def reader():
        try:
            for _ in range(40):
                store.list_filtered("u1", page=1, page_size=10)
                store.summary("u1")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer) for _ in range(3)] + [
        threading.Thread(target=reader) for _ in range(3)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(store.list_transactions("u1")) == 120


@pytest.mark.skipif(not PG_URL, reason="TEST_POSTGRES_URL not set")
def test_postgres_pool_concurrent_writes():
    from src.adapters.userstore import PostgresUserStore

    store = PostgresUserStore(PG_URL, minconn=2, maxconn=8)
    prefix = f"cc-{uuid.uuid4().hex[:8]}"
    errors: list[Exception] = []
    THREADS, PER = 8, 20

    def worker(n: int):
        try:
            for i in range(PER):
                store.add_transaction(f"{prefix}-{n}", _txn(i))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    total = sum(len(store.list_transactions(f"{prefix}-{n}")) for n in range(THREADS))
    assert total == THREADS * PER
