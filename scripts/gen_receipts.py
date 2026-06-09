#!/usr/bin/env python3
"""Generate synthetic Vietnamese receipt PDFs for the PDF-upload demo (CC0).

Usage:  python scripts/gen_receipts.py
Outputs to sample_data/sample_receipts/.
"""
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A6
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent.parent / "sample_data" / "sample_receipts"

RECEIPTS = [
    {
        "file": "lotte_mart.pdf", "merchant": "LOTTE Mart Quan 7", "date": "2026-06-12",
        "items": [("Sua TH True Milk 1L", 2, 34000), ("Banh mi sandwich", 1, 25000),
                  ("Nuoc suoi Lavie", 6, 6000), ("Ca phe G7", 1, 78000)],
    },
    {
        "file": "highlands.pdf", "merchant": "Highlands Coffee Bui Vien", "date": "2026-06-12",
        "items": [("Phin Sua Da", 1, 45000), ("Banh Croissant", 1, 35000),
                  ("Tra Sen Vang", 1, 55000)],
    },
    {
        "file": "bigc.pdf", "merchant": "BigC Thang Long", "date": "2026-06-13",
        "items": [("Gao ST25 5kg", 1, 165000), ("Dau an Tuong An 1L", 2, 52000),
                  ("Thit ba chi 1kg", 1, 145000), ("Rau cu tong hop", 1, 68000)],
    },
]


def build(spec: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / spec["file"]
    c = canvas.Canvas(str(path), pagesize=A6)
    w, h = A6
    y = h - 30
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(w / 2, y, spec["merchant"])
    y -= 16
    c.setFont("Helvetica", 8)
    c.drawCentredString(w / 2, y, f"Ngay: {spec['date']}   HOA DON BAN LE")
    y -= 14
    c.line(20, y, w - 20, y)
    y -= 14
    total = 0
    c.setFont("Helvetica", 9)
    for name, qty, price in spec["items"]:
        line_total = qty * price
        total += line_total
        c.drawString(24, y, f"{name[:22]}")
        c.drawRightString(w - 24, y, f"{qty} x {price:,} = {line_total:,}")
        y -= 13
    y -= 4
    c.line(20, y, w - 20, y)
    y -= 16
    c.setFont("Helvetica-Bold", 11)
    c.drawString(24, y, "TONG CONG (VND)")
    c.drawRightString(w - 24, y, f"{total:,}")
    y -= 20
    c.setFont("Helvetica", 7)
    c.drawCentredString(w / 2, y, "Cam on quy khach - Synthetic CC0 sample")
    c.save()
    print(f"wrote {path}  (total {total:,} VND)")


def main() -> None:
    for spec in RECEIPTS:
        build(spec)


if __name__ == "__main__":
    sys.exit(main())
