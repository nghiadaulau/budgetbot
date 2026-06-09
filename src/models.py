"""Pydantic request/response models — strict validation at the API boundary,
plus validation of *LLM output* (treated as an untrusted boundary too)."""
from __future__ import annotations

from datetime import date as _date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .categories import (
    CATEGORY_ALIASES,
    CATEGORY_SET,
    DEFAULT_CATEGORY,
    normalize_category,
)

Source = Literal["csv", "pdf", "manual"]

CONFIDENCE_SCORES: dict[str, float] = {
    "high": 0.95,
    "medium": 0.7,
    "low": 0.3,
    "low-fallback": 0.2,
}
NEEDS_REVIEW_THRESHOLD = 0.6


def confidence_score(confidence: str | None) -> float:
    """Numeric score for a string confidence label (unknown → low)."""
    return CONFIDENCE_SCORES.get((confidence or "").lower(), 0.3)


def _is_mappable(raw_category: Any) -> bool:
    """True when a raw LLM category maps to a canonical one (direct or alias)."""
    if not raw_category or not isinstance(raw_category, str):
        return False
    value = raw_category.strip()
    return value in CATEGORY_SET or value.lower() in CATEGORY_ALIASES


class ClassificationResult(BaseModel):
    """Validated output of an AI categorization call.

    `needs_review` is set when the model's category couldn't be mapped to the
    canonical enum, or its confidence is below NEEDS_REVIEW_THRESHOLD — those
    rows get a UI badge + quick re-categorize action instead of silently
    trusting a weak guess.
    """

    category: str
    confidence: str = "low"
    needs_review: bool = False


def validate_classification(raw: Any) -> ClassificationResult:
    """Coerce an arbitrary LLM result into a ClassificationResult — never raises.

    Malformed / non-dict / unknown-enum output degrades to `Other` + needs_review
    so a bad model response can never crash a request or store a bogus category.
    """
    if not isinstance(raw, dict):
        return ClassificationResult(category=DEFAULT_CATEGORY, confidence="low", needs_review=True)

    raw_cat = raw.get("category")
    category = normalize_category(raw_cat if isinstance(raw_cat, str) else None)
    confidence = str(raw.get("confidence", "low")).lower()
    if confidence not in CONFIDENCE_SCORES:
        confidence = "low"

    unmapped = bool(raw_cat) and not _is_mappable(raw_cat)
    needs_review = (
        not raw_cat
        or unmapped
        or confidence_score(confidence) < NEEDS_REVIEW_THRESHOLD
    )
    return ClassificationResult(category=category, confidence=confidence, needs_review=needs_review)


def _validate_iso_date(v: str) -> str:
    try:
        _date.fromisoformat(v[:10])
    except (ValueError, TypeError) as exc:
        raise ValueError("date must be ISO format YYYY-MM-DD") from exc
    return v[:10]


class TransactionCreate(BaseModel):
    """POST /transaction body."""

    date: str
    amount: float
    description: str = Field(min_length=1, max_length=500)
    category: str | None = None
    source: Source = "manual"

    @field_validator("date")
    @classmethod
    def _date_iso(cls, v: str) -> str:
        return _validate_iso_date(v)

    @field_validator("amount")
    @classmethod
    def _amount_nonzero(cls, v: float) -> float:
        if v == 0:
            raise ValueError("amount must not be 0")
        return v

    @field_validator("category")
    @classmethod
    def _category_known(cls, v: str | None) -> str | None:
        if v is not None and v not in CATEGORY_SET:
            raise ValueError(f"unknown category: {v}")
        return v


class TransactionUpdate(BaseModel):
    """PUT /transaction/{id} body — all fields optional (partial update)."""

    date: str | None = None
    amount: float | None = None
    description: str | None = Field(default=None, max_length=500)
    category: str | None = None

    @field_validator("date")
    @classmethod
    def _date_iso(cls, v: str | None) -> str | None:
        return _validate_iso_date(v) if v is not None else v

    @field_validator("amount")
    @classmethod
    def _amount_nonzero(cls, v: float | None) -> float | None:
        if v is not None and v == 0:
            raise ValueError("amount must not be 0")
        return v

    @field_validator("category")
    @classmethod
    def _category_known(cls, v: str | None) -> str | None:
        if v is not None and v not in CATEGORY_SET:
            raise ValueError(f"unknown category: {v}")
        return v

    def changed_fields(self) -> dict:
        """Only the explicitly-set fields (so partial updates stay partial)."""
        return self.model_dump(exclude_unset=True, exclude_none=True)
