"""PDF receipt flow — extract preview (not saved), then confirm-save."""

FAKE_PDF = b"%PDF-1.4 minimal"


def test_pdf_returns_editable_preview_not_saved(client, headers):
    r = client.post("/upload-pdf", files={"file": ("r.pdf", FAKE_PDF, "application/pdf")}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["saved"] is False
    assert body["merchant"]
    assert body["amount"] < 0
    assert isinstance(body["items"], list) and len(body["items"]) >= 1
    assert "extracted_raw" in body and "cost_estimate_usd" in body
    assert client.get("/transactions", headers=headers).json()["total"] == 0


def test_pdf_then_confirm_save(client, headers):
    preview = client.post(
        "/upload-pdf", files={"file": ("r.pdf", FAKE_PDF, "application/pdf")}, headers=headers
    ).json()
    txn = preview["transaction"]
    r = client.post("/transaction", json={**txn}, headers=headers)
    assert r.status_code == 200, r.text
    saved = r.json()["transaction"]
    assert saved["source"] == "pdf"
    assert client.get("/transactions", headers=headers).json()["total"] == 1
