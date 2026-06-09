"""Image import flow — bank/e-wallet transfer screenshots (PNG/JPG/WEBP).

Offline (LocalStub) can't OCR, so it returns an editable empty preview flagged
offline_stub. The real extraction (PDF_BACKEND=bedrock) reads any bank layout via
the vision prompt; that path isn't exercised here (no AWS).
"""
import io

from PIL import Image


def _png_bytes(size=(64, 64), color=(240, 240, 240)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def test_upload_image_returns_editable_preview(client, headers):
    r = client.post(
        "/upload-image",
        files={"file": ("transfer.png", _png_bytes(), "image/png")},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["saved"] is False
    assert any(w["type"] == "offline_stub" for w in body.get("warnings", []))
    assert "amount" in body and "transaction" in body


def test_upload_pdf_route_accepts_image_too(client, headers):
    r = client.post(
        "/upload-pdf",
        files={"file": ("vcb.jpg", _png_bytes(), "image/jpeg")},
        headers=headers,
    )
    assert r.status_code == 200, r.text


def test_upload_receipt_rejects_unknown_type(client, headers):
    r = client.post(
        "/upload-receipt",
        files={"file": ("note.txt", b"hello", "text/plain")},
        headers=headers,
    )
    assert r.status_code == 415


def test_image_then_confirm_save(client, headers):
    preview = client.post(
        "/upload-image",
        files={"file": ("t.png", _png_bytes(), "image/png")},
        headers=headers,
    ).json()
    txn = {**preview["transaction"]}
    txn["amount"] = -523000
    txn["description"] = "DINH QUOC HAN BIDV"
    r = client.post("/transaction", json=txn, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["transaction"]["source"] == "pdf"
