"""Budget guard degrades to LocalAI before overspending (brief §Cost-aware)."""
from datetime import UTC, datetime

from src import services
from src.adapters.userstore import SQLiteUserStore


class ExplodingAI:
    """A categorizer that must never be called when the guard forces local."""

    def classify_batch(self, rows):  # pragma: no cover - asserts via raise
        raise AssertionError("Bedrock should not be called when force_local=True")


def _store(tmp_path):
    return SQLiteUserStore(db_path=str(tmp_path / "g.db"))


def test_small_request_is_allowed(tmp_path):
    force_local, warning = services._budget_guard(_store(tmp_path), "u1", row_count=10)
    assert force_local is False and warning is None


def test_huge_request_trips_per_request_cap(tmp_path):
    force_local, warning = services._budget_guard(_store(tmp_path), "u1", row_count=1_000_000)
    assert force_local is True
    assert warning["type"] == "ai_budget_request"


def test_daily_cap_trips_after_spend(tmp_path):
    store = _store(tmp_path)
    store.log_cost({
        "ts": datetime.now(UTC).isoformat(),
        "user_id": "u1", "flow": "csv", "model_id": "haiku",
        "input_tokens": 0, "output_tokens": 0, "latency_ms": 0,
        "estimated_cost_usd": 2.50,
    })
    force_local, warning = services._budget_guard(store, "u1", row_count=10)
    assert force_local is True
    assert warning["type"] == "ai_budget_daily"


def test_force_local_routes_through_localai(tmp_path):
    store = _store(tmp_path)
    rows = [{"description": "QWERTY UNKNOWN VENDOR", "amount": -1000}]
    results, usage = services._classify_rows(ExplodingAI(), rows, store, "u1", force_local=True)
    assert len(results) == 1
    assert usage.input_tokens == 0
