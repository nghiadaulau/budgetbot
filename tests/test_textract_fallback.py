"""PDF vision → Textract → manual-entry fallback chain (brief §AI/ML.6)."""
from fakes import FakeBedrockRuntime, throttling_error

from src.adapters.pdf_extractor import BedrockPDFExtractor

TEXTRACT_RESP = {
    "ExpenseDocuments": [
        {
            "SummaryFields": [
                {"Type": {"Text": "TOTAL"}, "ValueDetection": {"Text": "1.290.000 đ"}},
                {"Type": {"Text": "VENDOR_NAME"}, "ValueDetection": {"Text": "WinMart"}},
                {"Type": {"Text": "INVOICE_RECEIPT_DATE"}, "ValueDetection": {"Text": "24/06/2026"}},
            ]
        }
    ]
}


def _extractor_with_failing_vision():
    bot = BedrockPDFExtractor(region="us-east-1", model_id="haiku")
    bot.runtime = FakeBedrockRuntime(raise_exc=throttling_error())
    return bot


def test_vision_fail_textract_enabled_parses_receipt(monkeypatch):
    bot = _extractor_with_failing_vision()
    bot.textract_enabled = True
    monkeypatch.setattr(bot, "_analyze_expense", lambda content: TEXTRACT_RESP)

    receipt, usage = bot.extract(b"%PDF-fake", media_type="application/pdf")
    assert receipt.extraction_source == "textract"
    assert receipt.total_amount == 1_290_000
    assert receipt.merchant == "WinMart"
    assert receipt.date == "2026-06-24"
    assert usage.model_id == "textract-fallback"


def test_vision_fail_textract_disabled_degrades_to_stub():
    bot = _extractor_with_failing_vision()
    bot.textract_enabled = False
    receipt, usage = bot.extract(b"%PDF-fake", media_type="application/pdf")
    assert receipt.offline_stub is True
    assert receipt.extraction_source == "stub"
    assert receipt.total_amount == 0


def test_vision_fail_textract_returns_nothing_degrades_to_stub(monkeypatch):
    bot = _extractor_with_failing_vision()
    bot.textract_enabled = True
    monkeypatch.setattr(bot, "_analyze_expense", lambda content: None)
    receipt, _ = bot.extract(b"%PDF-fake", media_type="application/pdf")
    assert receipt.extraction_source == "stub"
