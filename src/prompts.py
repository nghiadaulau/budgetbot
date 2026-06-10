"""Centralised LLM prompts for BudgetBot.

Keeping prompts in one file makes them reviewable, diff-friendly, and A/B-testable
via PROMPT_VERSION. All prompts are single-shot (no agentic multi-step).
"""
from __future__ import annotations

from .categories import CATEGORIES

PROMPT_VERSION = "2026-06-09.1"

_CATEGORY_LINE = ", ".join(CATEGORIES)


def _sanitize(text: object) -> str:
    """Flatten an untrusted transaction description before it enters a prompt.

    Collapses newlines/whitespace and neutralises double-quotes so a crafted
    description cannot break out of the prompt structure or forge instructions.
    Length-capped — descriptions are short by nature.
    """
    return " ".join(str(text).split()).replace('"', "'")[:200]

CSV_CLASSIFY_SYSTEM = (
    "You are a Vietnamese personal-finance transaction categorizer. "
    f"Classify each transaction into exactly one of: {_CATEGORY_LINE}. "
    "Vietnamese merchants are common (Highlands, GRAB, Shopee, VinMart, EVN, FPT, "
    "Lotte, BigC, KFC). Income/payroll → Salary. Bank/ATM transfers → Transfer. "
    "Electricity/water/internet/phone bills → Bills. Unclear codes → Other. "
    'Respond ONLY with a JSON array: [{"idx": <int>, "category": "<Category>", '
    '"confidence": "high|medium|low"}]. No prose.'
)

CSV_CLASSIFY_FEWSHOT = (
    "Example input:\n"
    "1. HIGHLANDS COFFEE BUI VIEN | -65000\n"
    "2. SALARY JUNE 2026 | 28000000\n"
    "3. EVN HCMC TIEN DIEN T5 | -850000\n"
    "Example output:\n"
    '[{"idx": 1, "category": "Food", "confidence": "high"}, '
    '{"idx": 2, "category": "Salary", "confidence": "high"}, '
    '{"idx": 3, "category": "Bills", "confidence": "high"}]'
)


def build_csv_classify_user(rows: list[dict]) -> str:
    """Render a numbered `description | amount` list for batch classification."""
    lines = [
        f"{i + 1}. {_sanitize(r.get('description', ''))} | {r.get('amount', 0)}"
        for i, r in enumerate(rows)
    ]
    return (
        f"{CSV_CLASSIFY_FEWSHOT}\n\n"
        "Now classify these transactions:\n" + "\n".join(lines)
    )


MANUAL_CLASSIFY_SYSTEM = (
    "You are a Vietnamese transaction categorizer. "
    f"Choose exactly one category from: {_CATEGORY_LINE}. "
    "Respond with ONLY the category word, nothing else."
)


def build_manual_classify_user(description: str, amount: float) -> str:
    return f'Transaction: "{_sanitize(description)}"\nAmount (VND): {amount}\nCategory:'


PDF_EXTRACT_SYSTEM = (
    "You read a Vietnamese bank/e-wallet transfer confirmation OR a store receipt "
    "from an image. It may come from any app (MB, Vietcombank, VietinBank, "
    "Techcombank, BIDV, VIB, OCB, Timo, ACB, MoMo, ZaloPay, ...). "
    "Return ONLY JSON with this shape:\n"
    '{"merchant": <string|null>, "counterparty": <string|null>, '
    '"direction": "out"|"in", "date": "YYYY-MM-DD", "total_amount": <number>, '
    '"currency": "VND", "bank": <string|null>, "account": <string|null>, '
    '"content": <string|null>, "reference": <string|null>, '
    '"items": [{"name": <string>, "qty": <number>, "price": <number>}]}\n'
    "Rules:\n"
    "- total_amount: the main amount as a POSITIVE integer in VND (strip dots/commas).\n"
    "- direction: 'out' when money is sent/spent (e.g. 'Chuyển tiền thành công', a "
    "minus sign, 'Từ tài khoản' is the user); 'in' when money is received.\n"
    "- merchant: the store for receipts; for transfers use the recipient "
    "(người nhận / 'Đến') as merchant and also fill counterparty.\n"
    "- content: the transfer note/message ('Nội dung'). reference: 'Mã giao dịch' / "
    "'Mã tham chiếu'. items: only for store receipts (else []).\n"
    "- Use null for any field you cannot read. Respond with JSON only, no prose."
)

PDF_EXTRACT_USER = (
    "Extract the transaction from this image. Respond with JSON only."
)
