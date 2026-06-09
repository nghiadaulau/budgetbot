"""Business logic for the v2 API contract.

Orchestrates parse → dedup → AI classify → persist → cost-track for the three
input flows (CSV / PDF / manual) plus summary and cost reporting. Routes
(app.py) stay thin and call into here; this layer depends only on the adapter
interfaces, never on a concrete backend.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from . import statement_parser
from .adapters.ai import LocalAI, TokenUsage
from .catalog import CatalogService, description_hash
from .categories import normalize_category
from .config import config
from .dedup import DedupService
from .dedup.normalize import transaction_fingerprint
from .dedup.service import DuplicateFileError
from .prompts import PROMPT_VERSION

__all__ = [
    "DuplicateFileError",
    "process_csv",
    "process_pdf",
    "create_transaction",
    "update_transaction",
    "delete_transaction",
    "list_transactions",
    "build_summary",
    "cost_report",
    "classification_audit",
    "usage_stats",
]


_LOCAL_AI = LocalAI()


def _audit_classification(store, user_id: str, txn_id: str | None, cls: dict) -> None:
    """Record how a transaction was categorized (source/version/model), if the
    store supports it. Best-effort — never breaks a save."""
    if not (txn_id and hasattr(store, "record_classification_audit")):
        return
    source = cls.get("source", "manual")
    store.record_classification_audit(
        user_id, txn_id,
        source=source,
        category=cls.get("category", "Other"),
        confidence=cls.get("confidence", "high"),
        needs_review=bool(cls.get("needs_review", False)),
        prompt_version=PROMPT_VERSION,
        model_id=config.ai_model_id if source == "llm" else "local",
    )


def _batched_classify(engine, rows: list[dict]) -> tuple[list[dict], TokenUsage]:
    """Run rows through classify_batch in config-sized chunks; merge token usage."""
    batch = max(1, config.csv_classify_batch_size)
    out_all: list[dict] = []
    usage = TokenUsage.zero()
    for start in range(0, len(rows), batch):
        out, u = engine.classify_batch(rows[start:start + batch])
        usage = usage.merge(u)
        out_all.extend(out)
    return out_all, usage


def _classify_rows(
    ai_client, rows: list[dict], store, user_id: str, *, force_local: bool = False,
) -> tuple[list[dict], TokenUsage]:
    """Classify rows with the merchant catalog (and in-upload dedup) in front of
    the LLM.

    Catalog hits skip Bedrock entirely; duplicate descriptions within this upload
    are classified once and fanned out; only the remaining distinct, unseen rows
    reach ``classify_batch`` (which itself keyword-matches first). Fresh results
    are written back to the catalog. ``force_local`` routes everything through
    LocalAI (budget guard).
    """
    catalog = CatalogService(store, user_id)
    results: list[dict | None] = [None] * len(rows)
    pending: list[tuple[int, dict]] = []

    for i, row in enumerate(rows):
        hit = catalog.lookup(row.get("description", ""))
        if hit:
            results[i] = dict(hit)
        else:
            pending.append((i, row))

    usage = TokenUsage.zero()
    if pending:
        order: list[str] = []
        representative: dict[str, dict] = {}
        members: dict[str, list[int]] = {}
        for idx, row in pending:
            h = description_hash(row.get("description", ""))
            if h not in representative:
                representative[h] = row
                members[h] = []
                order.append(h)
            members[h].append(idx)

        engine = _LOCAL_AI if force_local else ai_client
        out, usage = _batched_classify(engine, [representative[h] for h in order])

        for h, res in zip(order, out, strict=False):
            entry = {
                "category": normalize_category(res.get("category")),
                "confidence": res.get("confidence", "medium"),
                "needs_review": bool(res.get("needs_review", False)),
                "source": res.get("source", "llm"),
            }
            for idx in members[h]:
                results[idx] = dict(entry)
            catalog.record(representative[h].get("description", ""), entry["category"], entry["confidence"])

    return [r or {"category": "Other", "confidence": "low", "needs_review": True, "source": "fallback"} for r in results], usage


def _budget_guard(store, user_id: str, row_count: int) -> tuple[bool, dict | None]:
    """Decide whether to degrade to LocalAI before spending on Bedrock.

    Returns (force_local, warning). Trips when the estimated request cost exceeds
    MAX_COST_PER_REQUEST_USD, or the user's spend today already exceeds
    MAX_COST_PER_USER_PER_DAY_USD. Either cap at 0 disables that check.
    """
    cfg = config
    if cfg.max_cost_per_request_usd > 0:
        est = TokenUsage.estimate_cost(row_count * cfg.est_tokens_per_row, row_count * 8)
        if est > cfg.max_cost_per_request_usd:
            return True, {
                "type": "ai_budget_request",
                "message": "File quá lớn so với hạn mức chi phí AI mỗi lần — đã dùng "
                           "phân loại theo quy tắc (rule-based) để tránh phát sinh chi phí.",
            }
    if cfg.max_cost_per_user_per_day_usd > 0 and hasattr(store, "aggregate_costs"):
        report = store.aggregate_costs(user_id, None)
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        spent_today = next((d["cost_usd"] for d in report.get("by_day", []) if d["date"] == today), 0.0)
        if spent_today >= cfg.max_cost_per_user_per_day_usd:
            return True, {
                "type": "ai_budget_daily",
                "message": "Bạn đã đạt hạn mức chi phí AI trong ngày — tạm dùng phân loại "
                           "theo quy tắc. Hạn mức sẽ đặt lại vào ngày mai.",
            }
    return False, None


def _shift_month(month: str, delta: int) -> str:
    y, m = int(month[:4]), int(month[5:7])
    idx = (y * 12 + (m - 1)) + delta
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def _pct_change(current: float, previous: float) -> float | None:
    if not previous:
        return None
    return round((current - previous) / abs(previous) * 100, 1)


def process_csv(*, user_id: str, filename: str, content: bytes, store, ai_client,
                cost_tracker, force: str | None = None) -> dict:
    """Parse CSV → dedup → classify → save. Returns the v2 upload response.

    Raises DuplicateFileError (→ 409) when the same file was already processed,
    unless `force` is 'append' or 'replace'.
    """
    from .dedup.normalize import file_hash as _file_hash

    dedup = DedupService(store, config)
    file_digest = _file_hash(content)
    try:
        dedup.check_file(user_id, content)
    except DuplicateFileError as dup:
        if force not in ("append", "replace"):
            raise
        if force == "replace" and hasattr(store, "delete_transactions_by_file"):
            store.delete_transactions_by_file(user_id, dup.existing.get("id"))

    rows = statement_parser.parse_statement(content, filename)
    total_rows = len(rows)

    new_rows, duplicates = dedup.partition_transactions(user_id, rows)

    force_local, budget_warning = _budget_guard(store, user_id, len(new_rows))
    classified, usage = _classify_rows(ai_client, new_rows, store, user_id, force_local=force_local)

    file_id = store.save_uploaded_file(
        user_id, file_digest, filename, "csv", len(content), len(new_rows)
    ) if hasattr(store, "save_uploaded_file") else None

    saved: list[dict] = []
    for row, cls in zip(new_rows, classified, strict=False):
        txn = {
            "date": row["date"], "description": row["description"],
            "amount": row["amount"], "category": cls["category"],
            "confidence": cls["confidence"], "source": "csv",
            "needs_review": cls.get("needs_review", False),
            "fingerprint": row.get("fingerprint")
            or transaction_fingerprint(user_id, row["amount"], row["description"]),
            "file_id": file_id,
        }
        new_id = store.add_transaction(user_id, txn)
        txn["id"] = new_id if isinstance(new_id, str) else None
        _audit_classification(store, user_id, txn["id"], cls)
        saved.append({k: txn[k] for k in ("id", "date", "description", "amount", "category", "confidence", "needs_review", "source")})

    cost_tracker.record(user_id, "csv", usage)

    needs_review_count = sum(1 for t in saved if t.get("needs_review"))
    return {
        "transactions": saved,
        "rows_parsed": total_rows,
        "rows_inserted": len(saved),
        "ai_cost_usd": usage.estimated_cost_usd,
        "cost_estimate_usd": usage.estimated_cost_usd,
        "tokens": {"input": usage.input_tokens, "output": usage.output_tokens},
        "duplicates_skipped": duplicates,
        "ai_warning": budget_warning,
        "summary": {
            "total_rows": total_rows,
            "new_saved": len(saved),
            "duplicates_skipped": len(duplicates),
            "needs_review": needs_review_count,
            "errors": 0,
        },
    }


def process_pdf(*, user_id: str, filename: str, content: bytes, store,
                pdf_extractor, ai_client, cost_tracker,
                media_type: str = "application/pdf") -> dict:
    """Extract a receipt or bank-transfer screenshot (image OR PDF) → classify →
    return an editable PREVIEW (not saved).

    Works for any bank/e-wallet layout: a single vision prompt reads the image and
    returns normalised fields; the user reviews/edits before saving. Raises
    DuplicateFileError when the identical file was already processed.
    """
    dedup = DedupService(store, config)
    file_digest = dedup.check_file(user_id, content)
    ftype = "image" if (media_type or "").lower().startswith("image/") else "pdf"
    if hasattr(store, "save_uploaded_file"):
        store.save_uploaded_file(user_id, file_digest, filename, ftype, len(content), 0)

    receipt, extract_usage = pdf_extractor.extract(content, media_type)

    signed = 1 if receipt.direction == "in" else -1
    amount = signed * abs(float(receipt.total_amount))

    desc_for_class = receipt.content or receipt.merchant or ""
    cls_result, cls_usage = ai_client.classify_one(desc_for_class, amount)
    category = cls_result.category
    if category == "Other" and (receipt.account or receipt.bank or receipt.counterparty):
        category = "Transfer"
    usage = extract_usage.merge(cls_usage)
    cost_tracker.record(user_id, ftype, usage)

    warnings: list[dict] = []
    if receipt.offline_stub:
        warnings.append({
            "type": "offline_stub",
            "message": "Không tự đọc được ảnh khi offline. Bật AI vision "
                       "(PDF_BACKEND=bedrock) hoặc nhập tay các trường bên dưới.",
        })
    if getattr(receipt, "extraction_source", "vision") == "textract":
        warnings.append({
            "type": "textract_fallback",
            "message": "AI vision tạm lỗi — đã dùng Textract (dự phòng) để đọc. "
                       "Vui lòng kiểm tra lại các trường bên dưới.",
        })
    matches = dedup.check_receipt(user_id, receipt.merchant, receipt.date, receipt.total_amount)
    if matches:
        warnings.append({
            "type": "possible_duplicate_receipt",
            "message": f"Biên lai tương tự đã được trích xuất ({len(matches)} lần).",
            "matching": matches,
        })
    if hasattr(store, "save_receipt_extraction") and receipt.total_amount:
        receipt_fp = dedup.receipt_fingerprint(user_id, receipt.merchant, receipt.date, receipt.total_amount)
        store.save_receipt_extraction(
            user_id, file_digest, receipt_fp, json.dumps(receipt.to_dict(), ensure_ascii=False)
        )

    description = receipt.merchant or receipt.content or "Giao dịch"
    return {
        "merchant": receipt.merchant,
        "date": receipt.date,
        "amount": amount,
        "category": category,
        "items": [{"name": i.name, "amount": -abs(float(i.price))} for i in receipt.items],
        "ai_cost_usd": usage.estimated_cost_usd,
        "counterparty": receipt.counterparty,
        "bank": receipt.bank,
        "account": receipt.account,
        "content": receipt.content,
        "reference": receipt.reference,
        "direction": receipt.direction,
        "transaction": {
            "date": receipt.date, "description": description, "amount": amount,
            "category": category, "source": "pdf",
        },
        "extracted_raw": receipt.to_dict(),
        "cost_estimate_usd": usage.estimated_cost_usd,
        "tokens": {"input": usage.input_tokens, "output": usage.output_tokens},
        "warning": warnings[0] if warnings else None,
        "warnings": warnings,
        "saved": False,
    }


def create_transaction(*, user_id: str, body, confirm: bool, store, ai_client,
                       cost_tracker) -> dict:
    """Validate → (AI classify if needed) → manual dup warning → save."""
    dedup = DedupService(store, config)
    data = body.model_dump()
    usage = TokenUsage.zero()

    category = data.get("category")
    needs_review = False
    clf_source = "manual"
    if not category and data.get("source") != "csv":
        cls_result, usage = ai_client.classify_one(data["description"], data["amount"])
        category = cls_result.category
        needs_review = cls_result.needs_review
        clf_source = "llm" if usage.input_tokens else "keyword"
        cost_tracker.record(user_id, "manual", usage)
    category = normalize_category(category)

    txn_preview = {
        "date": data["date"], "description": data["description"],
        "amount": data["amount"], "category": category,
        "needs_review": needs_review,
        "source": data.get("source", "manual"),
    }

    if not confirm:
        matches = dedup.check_manual_warning(user_id, txn_preview)
        if matches:
            return {
                "transaction": txn_preview,
                "warning": {
                    "type": "possible_duplicate",
                    "message": "Có giao dịch tương tự gần đây. Vẫn lưu?",
                    "matching_transactions": matches,
                },
                "saved": False,
                "cost_estimate_usd": usage.estimated_cost_usd,
            }

    fp = transaction_fingerprint(user_id, data["amount"], data["description"])
    new_id = store.add_transaction(user_id, {**txn_preview, "confidence": "high", "fingerprint": fp})
    txn_id = new_id if isinstance(new_id, str) else None
    _audit_classification(store, user_id, txn_id, {
        "source": clf_source, "category": category,
        "confidence": "high", "needs_review": needs_review,
    })
    saved = {**txn_preview, "id": txn_id, "confidence": "high"}
    return {"transaction": saved, "saved": True, "cost_estimate_usd": usage.estimated_cost_usd}


def update_transaction(*, user_id: str, txn_id: str, fields: dict, store) -> dict | None:
    if fields.get("category"):
        fields = {**fields, "category": normalize_category(fields["category"])}
    return store.update_transaction(user_id, txn_id, fields)


def delete_transaction(*, user_id: str, txn_id: str, store) -> bool:
    existing = store.get_transaction(user_id, txn_id) if hasattr(store, "get_transaction") else None
    store.delete_transaction(user_id, txn_id)
    return existing is not None


def list_transactions(*, user_id: str, store, month=None, category=None, source=None,
                      search=None, page=1, page_size=50) -> dict:
    rows, total = store.list_filtered(
        user_id, month=month, category=category, source=source,
        search=search, page=page, page_size=page_size,
    )
    return {"transactions": rows, "total": total, "page": page, "page_size": page_size}


def build_summary(*, user_id: str, month: str, store) -> dict:
    txns = store.list_transactions(user_id, month=month)
    total_income = sum(t["amount"] for t in txns if t["amount"] > 0)
    total_expense = sum(-t["amount"] for t in txns if t["amount"] < 0)

    by_cat: dict[str, dict] = {}
    for t in txns:
        if t["amount"] >= 0:
            continue
        b = by_cat.setdefault(t["category"], {"amount": 0.0, "count": 0})
        b["amount"] += -t["amount"]
        b["count"] += 1
    by_category = sorted(
        (
            {
                "category": c, "amount": round(v["amount"]), "count": v["count"],
                "percentage": round(v["amount"] / total_expense * 100, 1) if total_expense else 0,
            }
            for c, v in by_cat.items()
        ),
        key=lambda x: x["amount"], reverse=True,
    )

    prev = _shift_month(month, -1)
    prev_txns = store.list_transactions(user_id, month=prev)
    prev_income = sum(t["amount"] for t in prev_txns if t["amount"] > 0)
    prev_expense = sum(-t["amount"] for t in prev_txns if t["amount"] < 0)
    net = total_income - total_expense
    prev_net = prev_income - prev_expense

    return {
        "month": month,
        "total_income": round(total_income),
        "total_expense": round(total_expense),
        "net": round(net),
        "by_category": by_category,
        "previous_month_comparison": {
            "expense_change_pct": _pct_change(total_expense, prev_expense),
            "income_change_pct": _pct_change(total_income, prev_income),
            "net_change_pct": _pct_change(net, prev_net),
        },
    }


def classification_audit(*, user_id: str, txn_id: str, store) -> dict:
    """Why was this transaction categorized the way it was? (source/version/model)."""
    rows = (
        store.list_classification_audit(user_id, txn_id)
        if hasattr(store, "list_classification_audit") else []
    )
    return {"transaction_id": txn_id, "audit": rows}


def cost_report(*, user_id: str, month: str | None, store) -> dict:
    if hasattr(store, "aggregate_costs"):
        return store.aggregate_costs(user_id, month)
    return {"total_cost_usd": 0.0, "by_flow": {}, "by_day": [], "tokens_total": {"input": 0, "output": 0}}


def usage_stats(*, user_id: str, month: str | None, store) -> dict:
    """Ops metrics: cost by flow, classification sources, catalog-hit %,
    needs-review %, latency p50/p95."""
    if hasattr(store, "usage_stats"):
        return store.usage_stats(user_id, month)
    return {
        "month": month, "total_cost_usd": 0.0, "by_flow": {},
        "tokens_total": {"input": 0, "output": 0}, "classifications": 0,
        "by_source": {}, "catalog_hit_rate_pct": 0.0, "needs_review_rate_pct": 0.0,
        "latency_ms": {"p50": 0, "p95": 0, "max": 0},
    }
