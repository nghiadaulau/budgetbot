"""Idempotency-Key replay safety on POST /upload and /transaction (brief §Determinism)."""

CSV = b"date,description,amount\n2026-06-01,HIGHLANDS COFFEE,-65000\n"


def test_upload_replay_returns_cached_not_409(client, headers):
    h = {**headers, "Idempotency-Key": "upload-key-1"}
    r1 = client.post("/upload", files={"file": ("s.csv", CSV, "text/csv")}, headers=h)
    assert r1.status_code == 200, r1.text
    inserted = r1.json()["rows_inserted"]

    r2 = client.post("/upload", files={"file": ("s.csv", CSV, "text/csv")}, headers=h)
    assert r2.status_code == 200
    assert r2.json() == r1.json()

    listed = client.get("/transactions", headers=headers).json()
    assert listed["total"] == inserted


def test_transaction_replay_does_not_double_write(client, headers):
    body = {"date": "2026-06-01", "description": "Cafe ABC", "amount": -50000, "category": "Food"}
    h = {**headers, "Idempotency-Key": "txn-key-1"}

    r1 = client.post("/transaction?confirm=true", json=body, headers=h)
    assert r1.status_code == 200 and r1.json()["saved"] is True

    r2 = client.post("/transaction?confirm=true", json=body, headers=h)
    assert r2.json() == r1.json()

    listed = client.get("/transactions", headers=headers).json()
    assert listed["total"] == 1


def test_different_keys_are_independent(client, headers):
    body = {"date": "2026-06-01", "description": "Cafe XYZ", "amount": -40000, "category": "Food"}
    client.post("/transaction?confirm=true", json=body, headers={**headers, "Idempotency-Key": "k1"})
    client.post("/transaction?confirm=true", json=body, headers={**headers, "Idempotency-Key": "k2"})
    listed = client.get("/transactions", headers=headers).json()
    assert listed["total"] == 2
