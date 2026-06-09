"""Async path dedup parity (tech-debt A): the SQS worker core now routes through
services.process_csv, so /enqueue gets the same file-hash + fingerprint dedup as
the synchronous /upload — no double-import on redelivery or re-enqueue."""
from src import handlers
from src.adapters.ai import LocalAI
from src.adapters.userstore import SQLiteUserStore

CSV = (
    b"date,description,amount\n"
    b"2026-06-01,HIGHLANDS COFFEE,-65000\n"
    b"2026-06-02,ZZZ UNKNOWN VENDOR 4412,-99000\n"
)


class FakeStorage:
    def __init__(self):
        self.objs = {}

    def put(self, key, data):
        self.objs[key] = data
        return key

    def get(self, key):
        return self.objs[key]


def _enqueue(store, storage, ai, content=CSV, filename="stmt.csv"):
    return handlers.handle_enqueue("u1", filename, content, storage, ai, store)


def test_async_import_persists_with_needs_review_and_audit(tmp_path):
    store = SQLiteUserStore(db_path=str(tmp_path / "a.db"))
    res = _enqueue(store, FakeStorage(), LocalAI())
    assert res["status"] == "COMPLETED" and res["rows_inserted"] == 2

    by_desc = {t["description"]: t for t in store.list_transactions("u1")}
    assert by_desc["ZZZ UNKNOWN VENDOR 4412"]["needs_review"] is True
    assert by_desc["HIGHLANDS COFFEE"]["needs_review"] is False
    assert store.list_classification_audit("u1", by_desc["HIGHLANDS COFFEE"]["id"])
    assert "csv" in store.aggregate_costs("u1")["by_flow"]


def test_async_reupload_same_file_does_not_double_import(tmp_path):
    store = SQLiteUserStore(db_path=str(tmp_path / "a.db"))
    storage, ai = FakeStorage(), LocalAI()

    first = _enqueue(store, storage, ai)
    assert first["rows_inserted"] == 2

    second = _enqueue(store, storage, ai)
    assert second["status"] == "COMPLETED"
    assert second["rows_inserted"] == 0
    assert len(store.list_transactions("u1")) == 2


def test_async_fingerprint_dedup_on_overlapping_rows(tmp_path):
    store = SQLiteUserStore(db_path=str(tmp_path / "a.db"))
    storage, ai = FakeStorage(), LocalAI()
    _enqueue(store, storage, ai, content=CSV, filename="jun.csv")

    overlap = (
        b"date,description,amount\n"
        b"2026-06-02,ZZZ UNKNOWN VENDOR 4412,-99000\n"
        b"2026-06-03,NEW MERCHANT,-12000\n"
    )
    res = _enqueue(store, storage, ai, content=overlap, filename="jul.csv")
    assert res["rows_inserted"] == 1
    assert len(store.list_transactions("u1")) == 3
