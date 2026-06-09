"""Receipt / bank-transfer extraction adapters (image OR PDF).

A single vision prompt handles screenshots from ANY Vietnamese bank or e-wallet
(MB, Vietcombank, VietinBank, Techcombank, BIDV, VIB, OCB, Timo, MoMo, ZaloPay…)
as well as store receipts — layout-agnostic, no per-bank parsing.

- Images (PNG/JPEG/WEBP) are sent straight to Claude vision.
- PDFs are rasterised (first page → PNG via PyMuPDF) then sent to vision.
- The local stub keeps the app fully offline: it returns a store-receipt mock for
  PDFs and an empty editable preview for images (flagged so the UI nudges the user
  to enable vision or fill the fields in).

Interface:
    extract(content, media_type) -> (ExtractedReceipt, TokenUsage)
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from botocore.exceptions import BotoCoreError, ClientError
from loguru import logger

from .. import prompts
from ..config import config
from .ai import _BEDROCK_ERRORS, TokenUsage, _parse_json_block

PDF_MEDIA = "application/pdf"
IMAGE_MEDIA = {"image/png", "image/jpeg", "image/jpg", "image/webp"}

_VISION_ERRORS = _BEDROCK_ERRORS + (ImportError, RuntimeError, OSError)


@dataclass
class ReceiptItem:
    name: str
    qty: float = 1
    price: float = 0.0


@dataclass
class ExtractedReceipt:
    """Normalised fields from a receipt or transfer screenshot (VND, positive)."""

    merchant: str
    date: str
    total_amount: float
    currency: str = "VND"
    direction: str = "out"
    counterparty: str | None = None
    bank: str | None = None
    account: str | None = None
    content: str | None = None
    reference: str | None = None
    items: list[ReceiptItem] = field(default_factory=list)
    raw_text: str = ""
    offline_stub: bool = False
    extraction_source: str = "vision"

    def to_dict(self) -> dict:
        return {
            "merchant": self.merchant,
            "date": self.date,
            "total_amount": self.total_amount,
            "currency": self.currency,
            "direction": self.direction,
            "counterparty": self.counterparty,
            "bank": self.bank,
            "account": self.account,
            "content": self.content,
            "reference": self.reference,
            "items": [{"name": i.name, "qty": i.qty, "price": i.price} for i in self.items],
            "offline_stub": self.offline_stub,
        }


def detect_image_format(content: bytes) -> str | None:
    """Sniff PNG/JPEG/WEBP from magic bytes (Bedrock needs the exact format)."""
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if content[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    return None


def media_to_format(media_type: str, content: bytes) -> str | None:
    """Map a media type (or sniffed bytes) to a Bedrock image format string."""
    mt = (media_type or "").lower()
    if mt in ("image/png",):
        return "png"
    if mt in ("image/jpeg", "image/jpg"):
        return "jpeg"
    if mt in ("image/webp",):
        return "webp"
    return detect_image_format(content)


class PDFExtractor(ABC):
    @abstractmethod
    def extract(self, content: bytes, media_type: str = PDF_MEDIA) -> tuple[ExtractedReceipt, TokenUsage]:
        """Extract structured fields from a receipt/transfer image or PDF."""
        raise NotImplementedError


ReceiptExtractor = PDFExtractor


class LocalStubPDFExtractor(PDFExtractor):
    """Offline stub. PDF → a sample store receipt; image → empty editable preview
    (flagged offline_stub so the UI prompts the user to enable vision / fill in)."""

    def extract(self, content: bytes, media_type: str = PDF_MEDIA) -> tuple[ExtractedReceipt, TokenUsage]:
        is_pdf = (media_type or "").lower() == PDF_MEDIA or media_to_format(media_type, content) is None
        if is_pdf:
            raw_text = ""
            try:
                import io

                import pdfplumber

                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    raw_text = "\n".join((p.extract_text() or "") for p in pdf.pages[:2]).strip()
            except Exception:  # noqa: BLE001
                raw_text = ""
            receipt = ExtractedReceipt(
                merchant="WinMart Nguyễn Trãi", date=_today(), total_amount=347_000,
                direction="out", content="Mua sắm siêu thị",
                items=[
                    ReceiptItem("Sữa tươi TH 1L x2", 2, 68_000),
                    ReceiptItem("Trứng gà 10 quả", 1, 42_000),
                    ReceiptItem("Rau củ tổng hợp", 1, 55_000),
                    ReceiptItem("Thịt heo 500g", 1, 98_000),
                    ReceiptItem("Nước giặt", 1, 84_000),
                ],
                raw_text=raw_text,
            )
            return receipt, TokenUsage.local(model_id="local-stub-pdf")

        receipt = ExtractedReceipt(
            merchant="", date=_today(), total_amount=0, direction="out",
            content="", raw_text="offline-stub-image", offline_stub=True,
        )
        return receipt, TokenUsage.local(model_id="local-stub-image")


class BedrockPDFExtractor(PDFExtractor):
    """Claude Haiku vision. Images go straight in; PDFs are rasterised first."""

    def __init__(self, region: str, model_id: str):
        from .bedrock_client import make_runtime

        self.runtime = make_runtime(region)
        self.model_id = model_id
        self._region = region
        self.textract_enabled = config.textract_enabled

    def extract(self, content: bytes, media_type: str = PDF_MEDIA) -> tuple[ExtractedReceipt, TokenUsage]:
        """Vision first; on failure fall back to Textract (if enabled), then to a
        flagged manual-entry preview — never raises to the caller."""
        try:
            return self._extract_vision(content, media_type)
        except _VISION_ERRORS:
            logger.warning("pdf_vision_failed; trying fallback chain")
            if self.textract_enabled:
                receipt = self._textract_fallback(content)
                if receipt is not None:
                    return receipt, TokenUsage.local(model_id="textract-fallback")
            stub = ExtractedReceipt(
                merchant="", date=_today(), total_amount=0, direction="out",
                content="", raw_text="vision-failed", offline_stub=True,
                extraction_source="stub",
            )
            return stub, TokenUsage.local(model_id="vision-failed")

    def _textract_fallback(self, content: bytes) -> ExtractedReceipt | None:
        """AWS Textract AnalyzeExpense → normalized receipt (best-effort)."""
        resp = self._analyze_expense(content)
        if not resp:
            return None
        merchant: str | None = None
        date_s: str | None = None
        total = 0.0
        for doc in resp.get("ExpenseDocuments", []):
            for f in doc.get("SummaryFields", []):
                ftype = (f.get("Type", {}).get("Text") or "").upper()
                value = (f.get("ValueDetection", {}).get("Text") or "").strip()
                if not value:
                    continue
                if ftype == "TOTAL":
                    total = _parse_amount(value)
                elif ftype == "VENDOR_NAME":
                    merchant = value
                elif ftype in ("INVOICE_RECEIPT_DATE", "ORDER_DATE"):
                    date_s = _normalize_date(value)
        if not total:
            return None
        return ExtractedReceipt(
            merchant=merchant or "Unknown", date=date_s or _today(),
            total_amount=total, direction="out", raw_text="textract",
            extraction_source="textract",
        )

    def _analyze_expense(self, content: bytes) -> dict | None:
        """Call Textract AnalyzeExpense; None on any client/transport error."""
        try:
            import boto3

            client = boto3.client("textract", region_name=self._region)
            return client.analyze_expense(Document={"Bytes": content})
        except (BotoCoreError, ClientError, KeyError, ValueError):
            logger.exception("textract_analyze_expense_failed")
            return None

    def _pdf_first_page_png(self, content: bytes) -> bytes:
        try:
            import fitz
        except ImportError as exc:  # pragma: no cover - optional dep
            raise ImportError(
                "Bedrock PDF vision needs page rasterisation: pip install pymupdf"
            ) from exc
        doc = fitz.open(stream=content, filetype="pdf")
        return doc.load_page(0).get_pixmap(dpi=150).tobytes("png")

    def _extract_vision(self, content: bytes, media_type: str = PDF_MEDIA) -> tuple[ExtractedReceipt, TokenUsage]:
        import time

        fmt = media_to_format(media_type, content)
        if fmt is None:
            png = self._pdf_first_page_png(content)
            img_bytes, img_fmt = png, "png"
        else:
            img_bytes, img_fmt = content, fmt

        start = time.time()
        resp = self.runtime.converse(
            modelId=self.model_id,
            system=[{"text": prompts.PDF_EXTRACT_SYSTEM}],
            messages=[{"role": "user", "content": [
                {"text": prompts.PDF_EXTRACT_USER},
                {"image": {"format": img_fmt, "source": {"bytes": img_bytes}}},
            ]}],
            inferenceConfig={"maxTokens": 700, "temperature": 0.0},
        )
        latency = int((time.time() - start) * 1000)
        u = resp.get("usage", {})
        usage = TokenUsage.for_bedrock(
            self.model_id, u.get("inputTokens", 0), u.get("outputTokens", 0), latency
        )
        data = _parse_json_block(resp["output"]["message"]["content"][0]["text"]) or {}
        items = [
            ReceiptItem(it.get("name", ""), it.get("qty", 1) or 1, it.get("price", 0) or 0)
            for it in (data.get("items") or []) if isinstance(it, dict)
        ]
        receipt = ExtractedReceipt(
            merchant=data.get("merchant") or data.get("counterparty") or "Unknown",
            date=data.get("date") or _today(),
            total_amount=float(data.get("total_amount") or 0),
            currency=data.get("currency") or "VND",
            direction=(data.get("direction") or "out").lower(),
            counterparty=data.get("counterparty"),
            bank=data.get("bank"),
            account=data.get("account"),
            content=data.get("content"),
            reference=data.get("reference"),
            items=items,
            raw_text=json.dumps(data, ensure_ascii=False),
        )
        return receipt, usage


BedrockReceiptExtractor = BedrockPDFExtractor
LocalStubReceiptExtractor = LocalStubPDFExtractor


def _today() -> str:
    from datetime import date

    return date.today().isoformat()


def _parse_amount(text: str) -> float:
    """Best-effort VND amount from a Textract value ('1.290.000 đ' → 1290000)."""
    digits = re.sub(r"[^\d]", "", text or "")
    return float(digits) if digits else 0.0


def _normalize_date(text: str) -> str | None:
    """Coerce a Textract date string to YYYY-MM-DD; None if unparseable."""
    s = (text or "").strip()
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        y, mo, d = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", s)
    if m:
        d, mo, y = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    return None
