"""AI categorization adapters. BudgetBot uses direct single-shot inference — no
RAG, no agentic loop.

Two interchangeable backends (selected by env via factory.make_ai):
  - BedrockAI: hybrid keyword fast-path → Bedrock Converse for ambiguous rows,
    falls back to LocalAI on any Bedrock error.
  - LocalAI:   pure rule-based keyword matching (offline, no AWS, $0 cost).

Both expose the same surface:
  categorize(description, amount, date, past_transactions=None) -> dict   # legacy
  classify_one(description, amount) -> (category, TokenUsage)
  classify_batch(rows) -> (list[dict], TokenUsage)
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

from botocore.exceptions import BotoCoreError, ClientError

from .. import prompts
from ..categories import CATEGORIES, DEFAULT_CATEGORY
from ..config import config
from ..metrics import put_metric
from ..models import ClassificationResult, validate_classification

__all__ = ["TokenUsage", "BedrockAI", "LocalAI", "CATEGORIES"]

_BEDROCK_ERRORS = (BotoCoreError, ClientError, KeyError, ValueError, json.JSONDecodeError)


def _usage_tuple(resp: dict) -> tuple[int, int, int, int]:
    """(input, output, cache_read, cache_write) tokens from a Converse response."""
    u = resp.get("usage", {})
    return (
        u.get("inputTokens", 0),
        u.get("outputTokens", 0),
        u.get("cacheReadInputTokens", 0) or u.get("cacheReadInputTokenCount", 0),
        u.get("cacheWriteInputTokens", 0) or u.get("cacheWriteInputTokenCount", 0),
    )


@dataclass(frozen=True)
class TokenUsage:
    """Token accounting for a single AI call (used by the cost tracker).

    `cache_read_tokens` / `cache_write_tokens` capture Bedrock prompt-caching
    usage so the cost estimate reflects the cheaper cache-read price.
    """

    input_tokens: int
    output_tokens: int
    model_id: str
    latency_ms: int
    estimated_cost_usd: float
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    CACHE_READ_MULT = 0.1
    CACHE_WRITE_MULT = 1.25

    @staticmethod
    def estimate_cost(
        input_tokens: int, output_tokens: int,
        cache_read: int = 0, cache_write: int = 0,
    ) -> float:
        inp = config.bedrock_input_cost_per_1m
        out = config.bedrock_output_cost_per_1m
        return round(
            input_tokens / 1_000_000 * inp
            + output_tokens / 1_000_000 * out
            + cache_read / 1_000_000 * inp * TokenUsage.CACHE_READ_MULT
            + cache_write / 1_000_000 * inp * TokenUsage.CACHE_WRITE_MULT,
            6,
        )

    @classmethod
    def for_bedrock(
        cls, model_id: str, input_tokens: int, output_tokens: int, latency_ms: int,
        cache_read: int = 0, cache_write: int = 0,
    ) -> TokenUsage:
        return cls(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_id=model_id,
            latency_ms=latency_ms,
            estimated_cost_usd=cls.estimate_cost(input_tokens, output_tokens, cache_read, cache_write),
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
        )

    @classmethod
    def local(cls, latency_ms: int = 0, model_id: str = "local-stub") -> TokenUsage:
        return cls(0, 0, model_id, latency_ms, 0.0)

    @staticmethod
    def zero() -> TokenUsage:
        return TokenUsage(0, 0, "none", 0, 0.0)

    def merge(self, other: TokenUsage) -> TokenUsage:
        """Sum two usages (model_id kept from whichever is non-local)."""
        model = self.model_id if self.input_tokens else other.model_id
        return TokenUsage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            model,
            self.latency_ms + other.latency_ms,
            round(self.estimated_cost_usd + other.estimated_cost_usd, 6),
            self.cache_read_tokens + other.cache_read_tokens,
            self.cache_write_tokens + other.cache_write_tokens,
        )


def _parse_json_block(text: str):
    """Extract the first JSON value (object or array) from an LLM response."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?|```$", "", text, flags=re.MULTILINE).strip()
    match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


class LocalAI:
    """Rule-based categorizer. Keyword matching only — deterministic, offline, free.

    Keyword order matters: more specific categories are checked first so that
    "grab food" → Food (not Transport) and "lotte cinema" → Entertainment
    (not Food). First match wins.
    """

    KEYWORDS: dict[str, list[str]] = {
        "Salary": [
            "salary", "lương", "luong", "payroll", "thu nhập", "thu nhap",
            "freelance", "payout", "tien luong",
        ],
        "Transfer": [
            "transfer", "chuyển khoản", "chuyen khoan", "vnpay", "atm",
            "withdrawal", "rut tien", "ck ", "napas",
        ],
        "Bills": [
            "evn", "tien dien", "tiền điện", "điện", "nước", "nuoc", "water",
            "internet", "fpt", "vnpt", "viettel", "gas", "petrolimex",
            "hóa đơn", "hoa don", "bill", "tien nha", "tiền nhà", "rent",
        ],
        "Health": [
            "pharmacy", "pharmacity", "guardian", "long châu", "long chau",
            "hospital", "bệnh viện", "benh vien", "clinic", "thuốc", "thuoc",
            "medlatec", "nha khoa",
        ],
        "Education": [
            "education", "học phí", "hoc phi", "tuition", "course", "khóa học",
            "khoa hoc", "udemy", "coursera", "trường", "truong", "school",
        ],
        "Entertainment": [
            "galaxy cinema", "lotte cinema", "cgv", "cinema", "rạp", "rap phim",
            "game", "netflix", "spotify", "youtube", "concert", "steam",
        ],
        "Food": [
            "highlands", "phúc long", "phuc long", "coffee", "cafe", "cà phê",
            "ca phe", "phở", "pho ", "grab food", "grabfood", "shopee food",
            "shopeefood", "lotte mart", "lotte", "bigc", "big c", "vinmart",
            "winmart", "co.opmart", "coopmart", "mm mega", "kfc", "pizza",
            "lunch", "dinner", "nhà hàng", "nha hang", "trà sữa", "tra sua",
            "bún", "cơm", "com tam", "food",
        ],
        "Transport": [
            "grab", "uber", "xanh sm", " be ", "taxi", "metro", "bus",
            "xăng", "xang", "fuel", "vinfast", "parking", "gửi xe", "gui xe",
        ],
        "Shopping": [
            "shopee", "lazada", "tiki", "amazon", "uniqlo", "vincom", "mall",
            "store", "mua sắm", "mua sam", "the gioi di dong", "dien may",
        ],
    }

    def _match(self, description: str) -> str | None:
        desc = f" {description.lower()} "
        for category in self.KEYWORDS:
            for kw in self.KEYWORDS[category]:
                if kw in desc:
                    return category
        return None

    def categorize(self, description: str, amount: float) -> dict:
        """Keyword-rule classification → {category, confidence}. The engine the
        hybrid BedrockAI and the validators build on."""
        category = self._match(description)
        if category:
            return {"category": category, "confidence": "medium"}
        try:
            if float(amount) > 0:
                return {"category": "Salary", "confidence": "low"}
        except (TypeError, ValueError):
            pass
        return {"category": DEFAULT_CATEGORY, "confidence": "low"}

    def classify_one(self, description: str, amount: float) -> tuple[ClassificationResult, TokenUsage]:
        return validate_classification(self.categorize(description, amount)), TokenUsage.local()

    def classify_batch(self, rows: list[dict]) -> tuple[list[dict], TokenUsage]:
        out = []
        for i, r in enumerate(rows):
            res = validate_classification(self.categorize(r.get("description", ""), r.get("amount", 0)))
            out.append({
                "idx": i,
                "category": res.category,
                "confidence": res.confidence,
                "needs_review": res.needs_review,
                "source": "rule",
            })
        return out, TokenUsage.local()


class BedrockAI:
    """Hybrid: fast keyword match first, Bedrock Converse for ambiguous rows,
    graceful fallback to LocalAI on any Bedrock error."""

    def __init__(self, region: str, model_id: str):
        from .bedrock_client import make_runtime

        self.runtime = make_runtime(region)
        self.model_id = model_id
        self._local = LocalAI()

    def classify_one(self, description: str, amount: float) -> tuple[ClassificationResult, TokenUsage]:
        keyword = self._local._match(description)
        if keyword:
            return (
                ClassificationResult(category=keyword, confidence="high", needs_review=False),
                TokenUsage.local(model_id="keyword"),
            )
        try:
            start = time.time()
            resp = self.runtime.converse(
                modelId=self.model_id,
                system=[{"text": prompts.MANUAL_CLASSIFY_SYSTEM}],
                messages=[{"role": "user", "content": [
                    {"text": prompts.build_manual_classify_user(description, amount)}
                ]}],
                inferenceConfig={"maxTokens": 16, "temperature": 0.0},
            )
            latency = int((time.time() - start) * 1000)
            text = resp["output"]["message"]["content"][0]["text"]
            in_t, out_t, cr, cw = _usage_tuple(resp)
            tu = TokenUsage.for_bedrock(self.model_id, in_t, out_t, latency, cr, cw)
            return validate_classification({"category": text.strip(), "confidence": "medium"}), tu
        except _BEDROCK_ERRORS:
            put_metric("BedrockFailures", 1, "Count", route="classify_one")
            cat = self._local.categorize(description, amount)["category"]
            return (
                ClassificationResult(category=cat, confidence="low-fallback", needs_review=True),
                TokenUsage.local(model_id="local-fallback"),
            )

    def classify_batch(self, rows: list[dict]) -> tuple[list[dict], TokenUsage]:
        """Classify up to N rows in one Converse call; keyword-matched rows are
        resolved offline and excluded from the prompt to save tokens."""
        results: dict[int, dict] = {}
        ambiguous: list[tuple[int, dict]] = []
        for i, r in enumerate(rows):
            kw = self._local._match(r.get("description", ""))
            if kw:
                results[i] = {"idx": i, "category": kw, "confidence": "high",
                              "needs_review": False, "source": "keyword"}
            else:
                ambiguous.append((i, r))

        usage = TokenUsage.zero()
        if ambiguous:
            try:
                start = time.time()
                resp = self.runtime.converse(
                    modelId=self.model_id,
                    system=[{"text": prompts.CSV_CLASSIFY_SYSTEM}],
                    messages=[{"role": "user", "content": [
                        {"text": prompts.build_csv_classify_user([r for _, r in ambiguous])}
                    ]}],
                    inferenceConfig={"maxTokens": 400, "temperature": 0.0},
                )
                latency = int((time.time() - start) * 1000)
                in_t, out_t, cr, cw = _usage_tuple(resp)
                usage = TokenUsage.for_bedrock(self.model_id, in_t, out_t, latency, cr, cw)
                parsed = _parse_json_block(resp["output"]["message"]["content"][0]["text"]) or []
                by_idx = {int(p.get("idx", 0)): p for p in parsed if isinstance(p, dict)}
                for local_idx, (orig_idx, _row) in enumerate(ambiguous, start=1):
                    res = validate_classification(by_idx.get(local_idx))
                    results[orig_idx] = {
                        "idx": orig_idx,
                        "category": res.category,
                        "confidence": res.confidence,
                        "needs_review": res.needs_review,
                        "source": "llm",
                    }
            except _BEDROCK_ERRORS:
                put_metric("BedrockFailures", 1, "Count", route="classify_batch")
                for orig_idx, row in ambiguous:
                    cat = self._local.categorize(row.get("description", ""), row.get("amount", 0))["category"]
                    results[orig_idx] = {
                        "idx": orig_idx,
                        "category": cat,
                        "confidence": "low-fallback",
                        "needs_review": True,
                        "source": "fallback",
                    }

        ordered = [results[i] for i in range(len(rows))]
        return ordered, usage
