"""Backend parity: the same battery runs against SQLite AND Postgres (when
TEST_POSTGRES_URL is set) so the production RDS backend has feature parity with
the dev backend — needs_review, catalog, audit, cost, idempotency, uploads.

The Postgres params are skipped automatically when no test DB is configured, so
the offline suite stays green with zero infra.
"""
import os
import uuid

import pytest

from src.adapters.userstore import SQLiteUserStore

PG_URL = os.environ.get("TEST_POSTGRES_URL")


@pytest.fixture(params=["sqlite", "postgres"])
def store(request, tmp_path):
    if request.param == "sqlite":
        return SQLiteUserStore(db_path=str(tmp_path / "parity.db"))
    if not PG_URL:
        pytest.skip("TEST_POSTGRES_URL not set — skipping Postgres parity")
    from src.adapters.userstore import PostgresUserStore
    return PostgresUserStore(PG_URL)


@pytest.fixture
def uid() -> str:
    return f"pu-{uuid.uuid4().hex[:12]}"


def _txn(**kw):
    base = {"date": "2026-06-01", "description": "X", "amount": -1000.0,
            "category": "Other", "confidence": "low", "source": "csv", "needs_review": True}
    base.update(kw)
    return base


def test_add_get_roundtrip_with_needs_review(store, uid):
    tid = store.add_transaction(uid, _txn(description="HIGHLANDS", needs_review=False, confidence="high"))
    assert isinstance(tid, str)
    got = store.get_transaction(uid, tid)
    assert got["description"] == "HIGHLANDS"
    assert got["needs_review"] is False
    assert got["amount"] == -1000.0


def test_needs_review_persists_and_clears_on_recategorize(store, uid):
    tid = store.add_transaction(uid, _txn(needs_review=True))
    assert store.get_transaction(uid, tid)["needs_review"] is True
    store.update_transaction(uid, tid, {"category": "Food"})
    after = store.get_transaction(uid, tid)
    assert after["needs_review"] is False and after["category"] == "Food"


def test_list_filtered_by_category_and_search(store, uid):
    store.add_transaction(uid, _txn(description="GRAB RIDE", category="Transport"))
    store.add_transaction(uid, _txn(description="PHO LE", category="Food"))
    rows, total = store.list_filtered(uid, category="Food")
    assert total == 1 and rows[0]["description"] == "PHO LE"
    rows, total = store.list_filtered(uid, search="grab")
    assert total == 1 and rows[0]["category"] == "Transport"


def test_catalog_accumulates_and_reads_back(store, uid):
    h = "deadbeef"
    for _ in range(3):
        store.catalog_record(uid, h, "Food", 0.95)
    row = store.catalog_lookup(uid, h)
    assert row["sample_count"] == 3 and row["category"] == "Food"
    assert row["avg_confidence"] == pytest.approx(0.95, abs=0.001)
    store.catalog_record(uid, h, "Shopping", 0.9)
    row = store.catalog_lookup(uid, h)
    assert row["category"] == "Shopping" and row["sample_count"] == 1


def test_audit_record_and_list(store, uid):
    tid = store.add_transaction(uid, _txn())
    store.record_classification_audit(
        uid, tid, source="llm", category="Food", confidence="high",
        needs_review=False, prompt_version="v1", model_id="haiku")
    audit = store.list_classification_audit(uid, tid)
    assert audit and audit[0]["source"] == "llm" and audit[0]["model_id"] == "haiku"


def test_cost_log_aggregate_and_usage_stats(store, uid):
    store.log_cost({"ts": "2026-06-09T10:00:00", "user_id": uid, "flow": "csv",
                    "model_id": "haiku", "input_tokens": 100, "output_tokens": 20,
                    "cache_read_tokens": 0, "cache_write_tokens": 0,
                    "latency_ms": 50, "estimated_cost_usd": 0.0005})
    tid = store.add_transaction(uid, _txn(needs_review=True))
    store.record_classification_audit(uid, tid, source="cache", category="Other",
                                      confidence="high", needs_review=True,
                                      prompt_version="v1", model_id="local")
    agg = store.aggregate_costs(uid, "2026-06")
    assert agg["by_flow"].get("csv") == pytest.approx(0.0005)
    assert agg["tokens_total"]["input"] == 100
    stats = store.usage_stats(uid, "2026-06")
    assert stats["classifications"] == 1
    assert stats["by_source"].get("cache") == 1
    assert stats["needs_review_rate_pct"] == 100.0


def test_idempotency_roundtrip(store, uid):
    assert store.idempotency_get(uid, "k1", 2) is None
    store.idempotency_put(uid, "k1", '{"ok": true}', 2)
    assert store.idempotency_get(uid, "k1", 2) == '{"ok": true}'


def test_uploaded_file_and_delete_by_file(store, uid):
    fid = store.save_uploaded_file(uid, "hash123", "stmt.csv", "csv", 1024, 2)
    assert store.find_uploaded_file(uid, "hash123")["id"] == fid
    store.add_transaction(uid, _txn(file_id=fid))
    store.add_transaction(uid, _txn(file_id=fid))
    deleted = store.delete_transactions_by_file(uid, fid)
    assert deleted == 2


def test_budgets_roundtrip(store, uid):
    store.set_budget(uid, "Food", 2_000_000)
    store.set_budget(uid, "Food", 3_000_000)
    assert store.get_budgets(uid)["Food"] == 3_000_000
