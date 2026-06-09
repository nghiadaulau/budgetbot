"""Error handling + validation + consistent JSON envelope."""


def test_missing_user_header_401(client):
    r = client.get("/transactions")
    assert r.status_code == 401
    assert r.json()["error"] == "unauthorized"


def test_oversize_csv_413(client, headers):
    big = b"x" * (11 * 1024 * 1024)
    r = client.post("/upload", files={"file": ("b.csv", big, "text/csv")}, headers=headers)
    assert r.status_code == 413


def test_wrong_mime_415(client, headers):
    r = client.post("/upload", files={"file": ("x.bin", b"a,b,c", "application/octet-stream")}, headers=headers)
    assert r.status_code == 415


def test_malformed_csv_400(client, headers):
    r = client.post("/upload", files={"file": ("x.csv", b"not,a,valid\nrow only two", "text/csv")}, headers=headers)
    assert r.status_code == 400


def test_invalid_transaction_amount_zero(client, headers):
    r = client.post("/transaction", json={"date": "2026-06-01", "description": "x", "amount": 0}, headers=headers)
    assert r.status_code == 400
    assert r.json()["error"] in ("validation_error", "bad_request")


def test_invalid_category_rejected(client, headers):
    r = client.post("/transaction", json={"date": "2026-06-01", "description": "x", "amount": -1, "category": "Nope"}, headers=headers)
    assert r.status_code == 400


def test_error_envelope_shape(client, headers):
    r = client.post("/transaction", json={"date": "bad", "description": "x", "amount": -1}, headers=headers)
    assert r.status_code == 400
    body = r.json()
    assert "error" in body and "message" in body
