"""needs_review end-to-end (brief §AI/ML.2): an unsure classification is flagged
through upload → list, and a manual re-categorize clears the flag."""


def _upload(client, headers, desc: str, amount: int = -99000):
    csv = f"date,description,amount\n2026-06-10,{desc},{amount}\n".encode()
    r = client.post("/upload", files={"file": ("u.csv", csv, "text/csv")}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_unknown_merchant_flagged_and_persisted(client, headers):
    body = _upload(client, headers, "ZZZ OBSCURE VENDOR 9931")
    assert body["transactions"][0]["needs_review"] is True
    assert body["summary"]["needs_review"] >= 1

    listed = client.get("/transactions", headers=headers).json()
    assert any(t.get("needs_review") for t in listed["transactions"])


def test_known_merchant_not_flagged(client, headers):
    body = _upload(client, headers, "HIGHLANDS COFFEE BUI VIEN", -65000)
    assert body["transactions"][0]["needs_review"] is False


def test_recategorize_clears_needs_review(client, headers):
    tx = _upload(client, headers, "ZZZ OBSCURE VENDOR 7777")["transactions"][0]
    assert tx["needs_review"] is True

    upd = client.put(f"/transaction/{tx['id']}", json={"category": "Food"}, headers=headers)
    assert upd.status_code == 200, upd.text

    listed = client.get("/transactions", headers=headers).json()
    row = next(t for t in listed["transactions"] if t["id"] == tx["id"])
    assert row["needs_review"] is False and row["category"] == "Food"
