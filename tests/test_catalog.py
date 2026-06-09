"""Merchant catalog cache + in-upload dedup reduce Bedrock calls (brief §AI/ML.3)."""
from src import services
from src.adapters.ai import TokenUsage
from src.adapters.userstore import SQLiteUserStore


class CountingAI:
    """Fake categorizer that counts how many rows actually reach the 'LLM'."""

    def __init__(self, category="Food", confidence="high"):
        self.batch_calls = 0
        self.rows_seen = 0
        self._category = category
        self._confidence = confidence

    def classify_batch(self, rows):
        self.batch_calls += 1
        self.rows_seen += len(rows)
        out = [
            {"idx": i, "category": self._category, "confidence": self._confidence, "needs_review": False}
            for i, _ in enumerate(rows)
        ]
        return out, TokenUsage.for_bedrock("haiku", 50, 10, 0)


def _store(tmp_path):
    return SQLiteUserStore(db_path=str(tmp_path / "cat.db"))


def test_in_upload_dedup_classifies_each_description_once(tmp_path):
    store = _store(tmp_path)
    ai = CountingAI()
    rows = [{"description": "MYSTERY VENDOR X", "amount": -1000 * (i + 1)} for i in range(5)]
    results, _ = services._classify_rows(ai, rows, store, "u1")
    assert len(results) == 5
    assert all(r["category"] == "Food" for r in results)
    assert ai.rows_seen == 1


def test_catalog_hit_skips_llm_after_enough_samples(tmp_path):
    store = _store(tmp_path)
    ai = CountingAI()
    row = [{"description": "REPEAT MERCHANT Z", "amount": -50000}]

    for _ in range(3):
        services._classify_rows(ai, list(row), store, "u1")
    assert ai.batch_calls == 3

    results, _ = services._classify_rows(ai, list(row), store, "u1")
    assert ai.batch_calls == 3
    assert results[0]["category"] == "Food" and results[0]["needs_review"] is False


def test_low_confidence_not_cached(tmp_path):
    store = _store(tmp_path)
    ai = CountingAI(confidence="low")
    row = [{"description": "FLAKY MERCHANT", "amount": -1000}]
    for _ in range(4):
        services._classify_rows(ai, list(row), store, "u1")
    assert ai.batch_calls == 4
