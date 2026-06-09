"""Deduplication — 4 levels."""
import tempfile
import types
from pathlib import Path

from src.adapters.userstore import SQLiteUserStore
from src.dedup import DedupService, transaction_fingerprint

FAKE_PDF = b"%PDF-1.4 dedup"


def _csv(rows: list[tuple[str, str, int]]) -> bytes:
    body = "date,description,amount\n" + "\n".join(f"{d},{desc},{amt}" for d, desc, amt in rows)
    return (body + "\n").encode()


def test_same_csv_twice_returns_409(client, headers):
    data = _csv([("2026-06-01", "Coffee", -65000)])
    assert client.post("/upload", files={"file": ("s.csv", data, "text/csv")}, headers=headers).status_code == 200
    r2 = client.post("/upload", files={"file": ("s.csv", data, "text/csv")}, headers=headers)
    assert r2.status_code == 409
    assert r2.json()["error"] == "duplicate_file"
    assert "existing_upload" in r2.json()


def test_force_append_overrides_409(client, headers):
    data = _csv([("2026-06-01", "Coffee", -65000)])
    client.post("/upload", files={"file": ("s.csv", data, "text/csv")}, headers=headers)
    r = client.post("/upload?force=append", files={"file": ("s.csv", data, "text/csv")}, headers=headers)
    assert r.status_code == 200


def test_cross_file_transaction_dedup(client, headers):
    client.post("/upload", files={"file": ("a.csv", _csv([
        ("2026-06-01", "Coffee", -65000),
    ]), "text/csv")}, headers=headers)
    r = client.post("/upload", files={"file": ("b.csv", _csv([
        ("2026-06-01", "Coffee", -65000),
        ("2026-06-02", "Lunch", -55000),
    ]), "text/csv")}, headers=headers)
    body = r.json()
    assert body["rows_inserted"] == 1
    assert body["summary"]["duplicates_skipped"] == 1


def test_within_batch_dedup(client, headers):
    data = _csv([
        ("2026-06-01", "Coffee", -65000),
        ("2026-06-01", "Coffee", -65000),
        ("2026-06-01", "Coffee", -65000),
    ])
    r = client.post("/upload", files={"file": ("s.csv", data, "text/csv")}, headers=headers)
    assert r.json()["rows_inserted"] == 1
    assert r.json()["summary"]["duplicates_skipped"] == 2


def test_normalization_strips_transaction_ids():
    a = transaction_fingerprint("u", -65000, "Highlands Coffee #12345")
    b = transaction_fingerprint("u", -65000, "Highlands Coffee #67890")
    assert a == b


def test_token_order_normalized():
    a = transaction_fingerprint("u", -65000, "Highlands Coffee BV")
    b = transaction_fingerprint("u", -65000, "BV Highlands Coffee")
    assert a == b


def _store():
    return SQLiteUserStore(str(Path(tempfile.mkdtemp()) / "d.db"))


def _cfg(enabled=True, tol=1, warn=3):
    return types.SimpleNamespace(
        dedup_enabled=enabled, dedup_date_tolerance_days=tol, dedup_manual_warn_days=warn
    )


def test_date_tolerance():
    s = _store()
    fp = transaction_fingerprint("u", -65000, "Coffee")
    s.add_transaction("u", {"date": "2026-06-05", "description": "Coffee", "amount": -65000,
                            "category": "Food", "confidence": "high", "fingerprint": fp, "source": "csv"})
    ded = DedupService(s, _cfg(tol=1))
    new, dups = ded.partition_transactions("u", [{"date": "2026-06-06", "description": "Coffee", "amount": -65000}])
    assert len(dups) == 1 and len(new) == 0
    new, dups = ded.partition_transactions("u", [{"date": "2026-06-07", "description": "Coffee", "amount": -65000}])
    assert len(new) == 1 and len(dups) == 0


def test_dedup_disabled_skips_everything():
    s = _store()
    fp = transaction_fingerprint("u", -65000, "Coffee")
    s.add_transaction("u", {"date": "2026-06-05", "description": "Coffee", "amount": -65000,
                            "category": "Food", "confidence": "high", "fingerprint": fp, "source": "csv"})
    ded = DedupService(s, _cfg(enabled=False))
    new, dups = ded.partition_transactions("u", [{"date": "2026-06-05", "description": "Coffee", "amount": -65000}])
    assert len(new) == 1 and len(dups) == 0


def test_manual_warning_then_confirm(client, headers):
    base = {"date": "2026-06-08", "description": "Highlands", "amount": -65000,
            "category": "Food", "source": "manual"}
    assert client.post("/transaction", json=base, headers=headers).json()["saved"] is True
    warn = client.post("/transaction", json=base, headers=headers).json()
    assert warn["saved"] is False
    assert warn["warning"]["type"] == "possible_duplicate"
    confirmed = client.post("/transaction?confirm=true", json=base, headers=headers).json()
    assert confirmed["saved"] is True


def test_same_pdf_twice_409(client, headers):
    assert client.post("/upload-pdf", files={"file": ("r.pdf", FAKE_PDF, "application/pdf")}, headers=headers).status_code == 200
    r2 = client.post("/upload-pdf", files={"file": ("r.pdf", FAKE_PDF, "application/pdf")}, headers=headers)
    assert r2.status_code == 409


def test_pdf_different_file_same_receipt_warns(client, headers):
    client.post("/upload-pdf", files={"file": ("r1.pdf", b"%PDF-1.4 one", "application/pdf")}, headers=headers)
    r = client.post("/upload-pdf", files={"file": ("r2.pdf", b"%PDF-1.4 two", "application/pdf")}, headers=headers)
    assert r.status_code == 200
    assert r.json().get("warning", {}).get("type") == "possible_duplicate_receipt"
