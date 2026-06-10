"""Endpoint business logic for BudgetBot."""
import csv
import io
import json
import logging
import re
import uuid

from botocore.exceptions import BotoCoreError, ClientError

from .adapters.ai import TokenUsage
from .metrics import put_metric

logger = logging.getLogger(__name__)


CHAT_RECENT_MESSAGE_LIMIT = 8
CHAT_SUMMARY_KEEP_RECENT = 8
CHAT_SUMMARY_BATCH_LIMIT = 20
CHAT_TRANSACTION_LIMIT = 40
_CATEGORY_HINTS: dict[str, list[str]] = {
    "Food": ["food", "eat", "eating", "restaurant", "coffee", "cafe", "ăn", "an", "uống", "uong"],
    "Transport": ["transport", "grab", "taxi", "fuel", "di chuyển", "di chuyen", "xe"],
    "Shopping": ["shopping", "shop", "mua sắm", "mua sam"],
    "Bills": ["bill", "bills", "electric", "water", "internet", "hóa đơn", "hoa don",
              "tiện ích", "tien ich", "subscription", "netflix", "spotify"],
    "Entertainment": ["entertainment", "game", "cinema", "giải trí", "giai tri"],
    "Health": ["health", "pharmacy", "hospital", "sức khỏe", "suc khoe"],
    "Education": ["education", "tuition", "course", "học phí", "hoc phi", "khóa học", "khoa hoc"],
    "Salary": ["salary", "income", "thu nhập", "thu nhap", "lương", "luong"],
    "Transfer": ["transfer", "chuyển khoản", "chuyen khoan"],
    "Other": ["other", "khác", "khac"],
}


def _normalize_chat_session_id(user_id: str, session_id: str | None) -> str | None:
    if not session_id:
        return None
    safe_session = re.sub(r"[^a-zA-Z0-9_.:-]", "-", session_id.strip())[:120]
    safe_user = re.sub(r"[^a-zA-Z0-9_.:-]", "-", user_id.strip())[:80]
    if not safe_session:
        return None
    return f"{safe_user}:{safe_session}"


def _select_chat_transactions(message: str, transactions: list, limit: int = CHAT_TRANSACTION_LIMIT) -> list:
    if len(transactions) <= limit:
        return transactions

    message_l = message.lower()
    hinted_categories = [
        category
        for category, hints in _CATEGORY_HINTS.items()
        if any(hint in message_l for hint in hints)
    ]
    if hinted_categories:
        filtered = [t for t in transactions if t.get("category") in hinted_categories]
        if filtered:
            return filtered[:limit]

    return transactions[:limit]


def _normalize_budget_category(category: str) -> str:
    from .categories import CATEGORY_SET, normalize_category
    raw = (category or "").strip()
    if raw in CATEGORY_SET:
        return raw
    return normalize_category(raw)


def _parse_csv(data: bytes, mapping: dict = None) -> list:
    """Expect CSV columns. Header row optional. If mapping is provided, use it."""
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    
    data_rows = rows
    if mapping:
        idx = {k: int(v) for k, v in mapping.items()}
    else:
        header = [c.lower().strip() for c in rows[0]]
        if "date" in header and "amount" in header:
            idx = {col: i for i, col in enumerate(header)}
            data_rows = rows[1:]
        else:
            idx = {"date": 0, "description": 1, "amount": 2}

    parsed = []
    for r in data_rows:
        if len(r) <= max(idx.values()) or not r[idx.get("date", 0)].strip():
            continue
        try:
            parsed.append({
                "date": r[idx.get("date", 0)].strip(),
                "description": r[idx.get("description", 1)].strip(),
                "amount": float(r[idx.get("amount", 2)].strip().replace(",", "")),
            })
        except (ValueError, IndexError):
            continue
    return parsed


def handle_enqueue(
    user_id: str,
    filename: str,
    data: bytes,
    storage,
    ai_client,
    userstore,
    sqs_queue_url: str = "",
    cost_tracker=None,
) -> dict:
    """Async upload path: store the file + create a job, then either hand it to
    SQS (production worker) or — when no queue is configured (local dev) —
    process it inline so ``/enqueue`` + ``/job-status`` work end-to-end either way.
    """
    job_id = str(uuid.uuid4())
    key = f"{user_id}/{job_id}/{filename}"
    storage.put(key, data)
    userstore.create_job(job_id=job_id, user_id=user_id, s3_key=key, filename=filename)
    put_metric("UploadJobCreated", 1, "Count", route="/enqueue", user_id=user_id)
    message = {"job_id": job_id, "user_id": user_id, "s3_key": key, "filename": filename}

    if sqs_queue_url:
        import boto3

        boto3.client("sqs").send_message(QueueUrl=sqs_queue_url, MessageBody=json.dumps(message))
        put_metric("SQSMessageSent", 1, "Count", route="/enqueue", user_id=user_id)
        return {"job_id": job_id, "status": "QUEUED",
                "message": "File đã được đưa vào hàng đợi xử lý."}

    try:
        result = process_job(message, storage, ai_client, userstore, cost_tracker)
    except Exception as exc:  # noqa: BLE001 — surface inline failure to the caller
        return {"job_id": job_id, "status": "FAILED", "error": str(exc)}
    return {
        "job_id": job_id,
        "status": result.get("status", "COMPLETED"),
        "rows_inserted": result.get("rows_inserted", 0),
    }


def handle_job_status(job_id: str, userstore, user_id: str) -> dict:
    """Trả về trạng thái của job theo job_id — chỉ cho chủ sở hữu.

    Scope theo user_id để tránh IDOR: job_id là UUID nhưng response chứa
    filename/s3_key/error của người khác. Trả NOT_FOUND (không phải 403) khi
    job thuộc user khác — không xác nhận sự tồn tại.
    """
    job = userstore.get_job(job_id)
    if not job or job.get("user_id") != user_id:
        return {"job_id": job_id, "status": "NOT_FOUND"}
    return job


def process_job(message: dict, storage, ai_client, userstore, cost_tracker=None) -> dict:
    """Process ONE async upload-job message → S3 get → ``services.process_csv`` →
    status. Routing through process_csv gives the async path **full dedup parity**
    with the sync /upload flow: file-hash check + per-row fingerprint dedup.

    Idempotent on two levels: a job already COMPLETED is skipped (SQS is
    at-least-once), and re-processing the same file content surfaces as a
    DuplicateFileError → no-op COMPLETED. Raises on real failure so the caller
    leaves the message for retry / DLQ.
    """
    from . import services
    from .cost_tracker import CostTracker
    from .dedup.service import DuplicateFileError

    job_id = message["job_id"]
    user_id = message["user_id"]
    s3_key = message["s3_key"]
    filename = message["filename"]

    existing = userstore.get_job(job_id)
    if existing and existing.get("status") == "COMPLETED":
        logger.info({"event": "sqs_job_skip_completed", "job_id": job_id})
        return {"job_id": job_id, "status": "COMPLETED", "skipped": True}

    tracker = cost_tracker or CostTracker(userstore)
    put_metric("SQSMessageReceived", 1, "Count", route="sqs_worker", user_id=user_id)
    logger.info({"event": "sqs_job_start", "job_id": job_id, "s3_key": s3_key})
    userstore.update_job_status(job_id, "PROCESSING")
    try:
        data = storage.get(s3_key)
        result = services.process_csv(
            user_id=user_id, filename=filename, content=data, store=userstore,
            ai_client=ai_client, cost_tracker=tracker, force=None,
        )
    except DuplicateFileError:
        logger.info({"event": "sqs_job_duplicate_file", "job_id": job_id})
        userstore.update_job_status(job_id, "COMPLETED", rows_inserted=0)
        return {"job_id": job_id, "status": "COMPLETED", "rows_inserted": 0, "duplicate_file": True}
    except Exception as exc:  # noqa: BLE001 — worker boundary: mark FAILED, re-raise for retry/DLQ
        put_metric("UploadJobFailed", 1, "Count", route="sqs_worker", user_id=user_id)
        logger.exception({"event": "sqs_job_failed", "job_id": job_id, "error": str(exc)})
        try:
            userstore.update_job_status(job_id, "FAILED", error=str(exc))
        except Exception:  # noqa: BLE001
            pass
        raise

    userstore.update_job_status(job_id, "COMPLETED", rows_inserted=result["rows_inserted"])
    put_metric("UploadJobSucceeded", 1, "Count", route="sqs_worker", user_id=user_id)
    logger.info({"event": "sqs_job_done", "job_id": job_id, "rows": result["rows_inserted"]})
    return {"job_id": job_id, "status": "COMPLETED", "rows_inserted": result["rows_inserted"]}


def handle_sqs_event(event: dict, storage, ai_client, userstore) -> dict:
    """Lambda SQS entrypoint — process each record; raise on failure so SQS retries."""
    results = [
        process_job(json.loads(record["body"]), storage, ai_client, userstore)
        for record in event.get("Records", [])
    ]
    return {"results": results}

    return {"processed": len(results)}



def handle_summary(user_id: str, month: str | None, userstore) -> dict:
    summary = userstore.summary(user_id, month=month)
    total = sum(v["total"] for v in summary.values())
    
    expenses = {k: v for k, v in summary.items() if v["total"] < 0}
    sorted_cats = sorted(expenses.items(), key=lambda kv: kv[1]["total"])
    
    from collections import defaultdict
    txns = userstore.list_transactions(user_id, month=month)
    daily_agg: dict = defaultdict(float)
    for t in txns:
        if float(t["amount"]) < 0:
            daily_agg[t["date"][:10]] += abs(float(t["amount"]))
    
    daily_trends = [{"date": k, "amount": v} for k, v in sorted(daily_agg.items())]

    return {
        "user_id": user_id,
        "month": month,
        "total_spend": total,
        "by_category": summary,
        "top_3_drivers": [
            {"category": cat, "total": v["total"], "count": v["count"]}
            for cat, v in sorted_cats[:3]
        ],
        "daily_trends": daily_trends,
    }


def handle_list_transactions(user_id: str, month: str | None, userstore) -> dict:
    return {"user_id": user_id, "month": month, "transactions": userstore.list_transactions(user_id, month=month)}


def handle_update_category(user_id: str, txn_id: int, new_category: str, userstore) -> dict:
    userstore.update_category(user_id, txn_id, new_category)
    return {"status": "success"}

def handle_clear_transactions(user_id: str, userstore) -> dict:
    userstore.clear_transactions(user_id)
    if hasattr(userstore, "clear_chat_memory"):
        userstore.clear_chat_memory(user_id)
    return {"status": "success"}


def handle_reset_chat(user_id: str, session_id: str | None, userstore) -> dict:
    if not hasattr(userstore, "clear_chat_session") and not hasattr(userstore, "clear_chat_memory"):
        return {"status": "unsupported"}

    server_session_id = _normalize_chat_session_id(user_id, session_id)
    if server_session_id and hasattr(userstore, "clear_chat_session"):
        userstore.clear_chat_session(user_id, server_session_id)
        return {"status": "success", "scope": "session"}

    userstore.clear_chat_memory(user_id)
    return {"status": "success", "scope": "all"}

def handle_delete_transaction(user_id: str, txn_id: int, userstore) -> dict:
    userstore.delete_transaction(user_id, txn_id)
    return {"status": "success"}

def handle_set_budget(user_id: str, category: str, amount: float, userstore) -> dict:
    from .categories import CATEGORY_SET
    normalized_category = _normalize_budget_category(category)
    amount = float(amount)
    if normalized_category not in CATEGORY_SET:
        raise ValueError(f"Unsupported budget category: {category}")
    if amount <= 0:
        raise ValueError("Budget amount must be greater than 0")
    userstore.set_budget(user_id, normalized_category, amount)
    return {"status": "success", "category": normalized_category, "amount": amount}

def handle_add_transaction(user_id: str, data: dict, userstore, ai_client) -> dict:
    txn = {
        "date": data.get("date"),
        "description": data.get("description"),
        "amount": data.get("amount"),
        "category": data.get("category", "Other"),
        "confidence": "high",
    }
    userstore.add_transaction(user_id, txn)
    return {"status": "success"}


def _chat_memory_available(userstore) -> bool:
    required = [
        "get_or_create_chat_session",
        "add_chat_message",
        "list_recent_chat_messages",
        "list_chat_messages_for_summary",
        "update_chat_summary",
    ]
    return all(hasattr(userstore, name) for name in required)


def handle_chat(user_id: str, message: str, session_id: str | None, month: str | None, userstore, chatbot_client, cost_tracker=None):
    all_transactions = userstore.list_transactions(user_id, month=month)
    has_transactions = bool(all_transactions)
    has_any_transactions = has_transactions or (bool(userstore.list_transactions(user_id)) if month else False)
    if not has_any_transactions and hasattr(userstore, "clear_chat_memory"):
        userstore.clear_chat_memory(user_id)

    transactions = _select_chat_transactions(message, all_transactions)
    budgets = userstore.get_budgets(user_id)
    from datetime import date

    from . import services
    eff_month = month or date.today().strftime("%Y-%m")
    _dash = services.build_summary(user_id=user_id, month=eff_month, store=userstore)
    summary = {
        c["category"]: {"total": -float(c["amount"]), "count": int(c["count"])}
        for c in _dash.get("by_category", [])
    }

    session: dict = {"id": session_id, "summary": "", "profile": {}, "message_count": 0}
    recent_messages = [{"role": "user", "text": message}]

    if _chat_memory_available(userstore):
        server_session_id = _normalize_chat_session_id(user_id, session_id)
        session = userstore.get_or_create_chat_session(user_id, server_session_id)
        userstore.add_chat_message(user_id, session["id"], "user", message)
        session = userstore.get_or_create_chat_session(user_id, session["id"])
        if has_transactions:
            recent_messages = userstore.list_recent_chat_messages(
                user_id,
                session["id"],
                limit=CHAT_RECENT_MESSAGE_LIMIT,
            )
    
    cost_sink: list[TokenUsage] = []
    stream_generator = chatbot_client.chat(
        user_id=user_id,
        messages_context=recent_messages,
        transactions=transactions,
        budgets=budgets,
        summary=summary,
        data_scope=f"Month {month}" if month else "All available transactions",
        memory_summary=session.get("summary", "") if has_transactions else "",
        profile=session.get("profile", {}) if has_transactions else {},
        userstore=userstore,
        cost_sink=cost_sink,
    )

    def sse_generator():
        assistant_chunks = []
        for chunk in stream_generator:
            assistant_chunks.append(chunk)
            yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"

        if cost_tracker is not None and cost_sink:
            turn_usage = TokenUsage.zero()
            for u in cost_sink:
                turn_usage = turn_usage.merge(u)
            cost_tracker.record(user_id, "chat", turn_usage)

        assistant_text = "".join(assistant_chunks).strip()
        if assistant_text and _chat_memory_available(userstore):
            userstore.add_chat_message(user_id, session["id"], "assistant", assistant_text)
            messages_to_compact = userstore.list_chat_messages_for_summary(
                user_id,
                session["id"],
                keep_recent=CHAT_SUMMARY_KEEP_RECENT,
                limit=CHAT_SUMMARY_BATCH_LIMIT,
            )
            if messages_to_compact:
                try:
                    updated_summary, summary_usage = chatbot_client.summarize_memory(
                        session.get("summary", ""), messages_to_compact
                    )
                    max_message_id = max(m["id"] for m in messages_to_compact)
                    userstore.update_chat_summary(user_id, session["id"], updated_summary, max_message_id)
                    if cost_tracker is not None:
                        cost_tracker.record(user_id, "chat_summary", summary_usage)
                except (BotoCoreError, ClientError, ValueError, KeyError):
                    logger.exception({"event": "chat_memory_summary_failed", "user_id": user_id, "session_id": session["id"]})

    return sse_generator()

def handle_get_budgets(user_id: str, month: str | None, userstore) -> dict:
    budgets = userstore.get_budgets(user_id)
    summary = userstore.summary(user_id, month=month)
    
    alerts = []
    budget_status = []
    for category, raw_limit in budgets.items():
        limit = float(raw_limit)
        category_total = float(summary.get(category, {}).get("total", 0))
        spent = abs(category_total) if category_total < 0 else 0
        remaining = max(limit - spent, 0)
        percent = round((spent / limit) * 100, 1) if limit > 0 else 0
        item = {
            "category": category,
            "limit": limit,
            "spent": spent,
            "remaining": remaining,
            "percent": percent,
            "exceeded": spent > limit,
        }
        budget_status.append(item)
        if item["exceeded"]:
            alerts.append(item)
            
    return {"budgets": budgets, "month": month, "status": budget_status, "alerts": alerts}
