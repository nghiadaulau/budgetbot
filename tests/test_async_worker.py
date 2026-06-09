"""Async worker core (handlers.process_job): completes, is idempotent under SQS
at-least-once redelivery, and raises on failure (→ retry/DLQ)."""
import pytest

from src import handlers
from src.adapters.ai import LocalAI
from src.adapters.userstore import SQLiteUserStore

CSV = b"date,description,amount\n2026-06-01,HIGHLANDS COFFEE,-65000\n2026-06-02,GRAB,-48000\n"


class FakeStorage:
    """In-memory object store (stands in for S3/LocalStorage)."""

    def __init__(self):
        self.objs: dict[str, bytes] = {}

    def put(self, key, data):
        self.objs[key] = data
        return key

    def get(self, key):
        return self.objs[key]


def _setup(tmp_path):
    store = SQLiteUserStore(db_path=str(tmp_path / "w.db"))
    storage = FakeStorage()
    return store, storage, LocalAI()


def _msg(job_id="j1"):
    return {"job_id": job_id, "user_id": "u1", "s3_key": "k1", "filename": "s.csv"}


def test_process_job_completes_and_persists(tmp_path):
    store, storage, ai = _setup(tmp_path)
    storage.put("k1", CSV)
    store.create_job("j1", "u1", "k1", "s.csv")

    res = handlers.process_job(_msg(), storage, ai, store)
    assert res["status"] == "COMPLETED" and res["rows_inserted"] == 2
    assert store.get_job("j1")["status"] == "COMPLETED"
    assert len(store.list_transactions("u1")) == 2


def test_process_job_idempotent_skips_completed(tmp_path):
    store, storage, ai = _setup(tmp_path)
    storage.put("k1", CSV)
    store.create_job("j1", "u1", "k1", "s.csv")
    store.update_job_status("j1", "COMPLETED", rows_inserted=2)

    res = handlers.process_job(_msg(), storage, ai, store)
    assert res.get("skipped") is True
    assert store.list_transactions("u1") == []


def test_process_job_failure_marks_failed_and_raises(tmp_path):
    store, storage, ai = _setup(tmp_path)
    store.create_job("j1", "u1", "missing-key", "s.csv")

    with pytest.raises(KeyError):
        handlers.process_job(
            {"job_id": "j1", "user_id": "u1", "s3_key": "missing-key", "filename": "s.csv"},
            storage, ai, store,
        )
    assert store.get_job("j1")["status"] == "FAILED"
