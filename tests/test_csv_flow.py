"""CSV upload flow — parse, classify, save, cost-track."""
from conftest import SAMPLE_CSV


def _big_csv(n: int = 35) -> bytes:
    lines = ["date,description,amount"]
    for i in range(n):
        day = (i % 27) + 1
        lines.append(f"2026-06-{day:02d},Merchant {i} GRAB,-{(i + 1) * 1000}")
    return ("\n".join(lines) + "\n").encode()


def test_upload_saves_and_classifies(client, headers):
    r = client.post("/upload", files={"file": ("s.csv", SAMPLE_CSV, "text/csv")}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_inserted"] == 5
    cats = {t["category"] for t in body["transactions"]}
    assert "Salary" in cats and "Bills" in cats and "Transport" in cats
    assert body["tokens"] == {"input": 0, "output": 0}
    assert "cost_estimate_usd" in body


def test_upload_30_plus_rows(client, headers):
    r = client.post("/upload", files={"file": ("big.csv", _big_csv(35), "text/csv")}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["rows_inserted"] == 35
    listed = client.get("/transactions?page=1&page_size=100", headers=headers).json()
    assert listed["total"] == 35


def test_upload_all_transactions_have_source_csv(client, headers):
    client.post("/upload", files={"file": ("s.csv", SAMPLE_CSV, "text/csv")}, headers=headers)
    rows = client.get("/transactions", headers=headers).json()["transactions"]
    assert rows and all(t["source"] == "csv" for t in rows)
