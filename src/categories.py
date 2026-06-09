"""Canonical transaction categories — the single source of truth for the
backend. The frontend mirrors this exact list in `frontend/src/lib/categories.ts`.

Keep the two in sync if you change anything here.
"""
from __future__ import annotations

CATEGORIES: list[str] = [
    "Food",
    "Transport",
    "Shopping",
    "Bills",
    "Entertainment",
    "Health",
    "Education",
    "Salary",
    "Transfer",
    "Other",
]

CATEGORY_SET: frozenset[str] = frozenset(CATEGORIES)

DEFAULT_CATEGORY = "Other"
INCOME_CATEGORY = "Salary"

CATEGORY_ALIASES: dict[str, str] = {
    "ăn uống": "Food", "an uong": "Food", "food": "Food", "đồ ăn": "Food",
    "di chuyển": "Transport", "di chuyen": "Transport", "transport": "Transport",
    "đi lại": "Transport",
    "mua sắm": "Shopping", "mua sam": "Shopping", "shopping": "Shopping",
    "hóa đơn": "Bills", "hoa don": "Bills", "bills": "Bills",
    "tiện ích": "Bills", "tien ich": "Bills", "utilities": "Bills",
    "đăng ký": "Bills", "dang ky": "Bills", "subscriptions": "Bills",
    "giải trí": "Entertainment", "giai tri": "Entertainment",
    "entertainment": "Entertainment",
    "sức khỏe": "Health", "suc khoe": "Health", "health": "Health",
    "giáo dục": "Education", "giao duc": "Education", "education": "Education",
    "học phí": "Education", "hoc phi": "Education",
    "lương": "Salary", "luong": "Salary", "salary": "Salary",
    "thu nhập": "Salary", "thu nhap": "Salary", "income": "Salary",
    "chuyển khoản": "Transfer", "chuyen khoan": "Transfer", "transfer": "Transfer",
    "khác": "Other", "khac": "Other", "other": "Other",
}


def normalize_category(raw: str | None) -> str:
    """Map a possibly-localised category string to a canonical value.

    Returns DEFAULT_CATEGORY when the input is empty or unknown.
    """
    if not raw:
        return DEFAULT_CATEGORY
    value = raw.strip()
    if value in CATEGORY_SET:
        return value
    return CATEGORY_ALIASES.get(value.lower(), DEFAULT_CATEGORY)


def is_valid_category(raw: str | None) -> bool:
    return bool(raw) and raw in CATEGORY_SET
