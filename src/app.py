"""FastAPI app for BudgetBot — runtime-agnostic (uvicorn locally, Lambda via Mangum).

Routes only. All business logic lives in services.py / handlers.py.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel, ValidationError

from . import handlers, services
from .adapters import factory
from .adapters.chatbot import ChatbotAI
from .auth import verify_cognito_token
from .categories import CATEGORIES
from .config import config
from .cost_tracker import CostTracker
from .dedup.service import DuplicateFileError
from .idempotency import IdempotencyService
from .models import TransactionCreate, TransactionUpdate
from .ratelimit import make_rate_limiter

try:
    from mangum import Mangum  # type: ignore
except ImportError:
    Mangum = None

CSV_MAX_BYTES = 10 * 1024 * 1024

app = FastAPI(title="BudgetBot API", version=config.app_version)


@app.middleware("http")
async def strip_api_prefix(request, call_next):
    path = request.scope.get("path", "")
    if path.startswith("/api"):
        request.scope["path"] = path[4:] or "/"
    return await call_next(request)


_allowed = (
    ["*"] if config.cors_origins == "*"
    else [o.strip() for o in config.cors_origins.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_credentials=config.cors_origins != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)

ai_client = factory.make_ai()
storage = factory.make_storage()
userstore = factory.make_userstore()
pdf_extractor = factory.make_pdf_extractor()
cost_tracker = CostTracker(userstore)
idempotency = IdempotencyService(userstore)
rate_limiter = make_rate_limiter()
chatbot_client = ChatbotAI(region=config.aws_region, model_id=config.ai_model_id)

if hasattr(userstore, "migrate"):
    try:
        userstore.migrate()
    except Exception as exc:  # noqa: BLE001 — boot-time best effort
        logger.warning("migrate skipped: {}", exc)

# Loud boot-time warnings for insecure configs — defaults stay dev-friendly, but
# a production deploy must not run with these off (Terraform sets them true).
if not config.require_auth:
    logger.warning(
        "SECURITY: REQUIRE_AUTH is OFF — the X-User-Id header is trusted without "
        "verification (any caller can impersonate any user). Set REQUIRE_AUTH=true in production."
    )
if not config.rate_limit_enabled:
    logger.warning(
        "SECURITY: RATE_LIMIT_ENABLED is OFF — expensive AI endpoints are unthrottled. "
        "Set RATE_LIMIT_ENABLED=true in production."
    )
if config.cognito_user_pool_id and not config.cognito_client_id:
    logger.warning(
        "SECURITY: COGNITO_USER_POOL_ID is set but COGNITO_CLIENT_ID is empty — JWT "
        "audience/client_id validation is skipped. Set COGNITO_CLIENT_ID to enforce it."
    )


def _resolve_user_id(request, x_user_id: str | None) -> str | None:
    """Identity precedence: verified Cognito Bearer → API-GW authorizer claim →
    X-User-Id (only when REQUIRE_AUTH is off — local/demo single-user MVP)."""
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        claims = verify_cognito_token(auth_header[7:].strip())
        if claims and claims.get("sub"):
            return claims["sub"]
        if config.require_auth:
            return None

    try:
        event = request.scope.get("aws.event", {})
        sub = (
            event.get("requestContext", {}).get("authorizer", {})
            .get("jwt", {}).get("claims", {}).get("sub")
        )
        if sub:
            return sub
    except Exception:  # noqa: BLE001 — best-effort claim extraction
        pass

    if config.require_auth:
        return None
    return x_user_id


def require_user(request, x_user_id: str | None) -> str:
    uid = _resolve_user_id(request, x_user_id)
    if not uid:
        detail = "Valid Cognito token required" if config.require_auth else "X-User-Id header is required"
        raise HTTPException(status_code=401, detail=detail)
    return uid


def enforce_rate_limit(user_id: str) -> None:
    """429 when a user exceeds RATE_LIMIT_PER_MINUTE on expensive endpoints."""
    if not config.rate_limit_enabled:
        return
    allowed, retry_after = rate_limiter.allow(user_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please slow down.",
            headers={"Retry-After": str(retry_after)},
        )


def _error(status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": code, "message": message}
    if details:
        body["details"] = details
    return JSONResponse(status_code=status, content=body)


def _safe_errors(errors: Sequence[Any]) -> list[dict]:
    """Pydantic errors() can embed exception objects (ctx) that aren't JSON
    serialisable — keep only the safe primitive fields."""
    return [
        {"loc": list(e.get("loc", [])), "msg": str(e.get("msg", "")), "type": e.get("type", "")}
        for e in errors
    ]


@app.exception_handler(HTTPException)
async def _http_exc(_request: Request, exc: HTTPException):
    code = {400: "bad_request", 401: "unauthorized", 404: "not_found",
            409: "conflict", 413: "payload_too_large", 415: "unsupported_media_type",
            429: "rate_limited", 503: "service_unavailable"}.get(exc.status_code, "error")
    headers = getattr(exc, "headers", None)
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=headers)
    body = {"error": code, "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)


@app.exception_handler(RequestValidationError)
async def _validation_exc(_request: Request, exc: RequestValidationError):
    return _error(400, "validation_error", "Invalid request.", {"errors": _safe_errors(exc.errors())})


@app.exception_handler(Exception)
async def _unhandled_exc(_request: Request, exc: Exception):
    return _error(500, "internal_error", "Something went wrong.", {"type": type(exc).__name__})


@app.get("/health")
def health() -> dict:
    # Public, unauthenticated — keep only what the SPA needs (status, version,
    # require_auth to toggle guest mode, categories). Internal backend names
    # (ai/db/pdf) are not disclosed to anonymous callers.
    return {
        "status": "ok",
        "version": config.app_version,
        "categories": CATEGORIES,
        "require_auth": config.require_auth,
    }


_STATEMENT_EXT = (".csv", ".xlsx", ".xls")
_STATEMENT_MIME = {
    "text/csv", "application/csv", "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@app.post("/upload")
async def upload_csv(
    request: Request,
    file: UploadFile = File(...),
    x_user_id: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
    force: str | None = Query(default=None, pattern="^(skip|replace|append)$"),
) -> dict:
    """Import a bank statement — CSV or Excel (.xlsx/.xls)."""
    user_id = require_user(request, x_user_id)
    enforce_rate_limit(user_id)
    cached = idempotency.get(user_id, "upload", idempotency_key)
    if cached is not None:
        return cached
    name = (file.filename or "").lower()
    ctype = (file.content_type or "").lower()
    if not (name.endswith(_STATEMENT_EXT) or ctype in _STATEMENT_MIME or ctype.startswith("text/")):
        raise HTTPException(415, "Only CSV or Excel (.xlsx/.xls) files are accepted")
    data = await file.read()
    if len(data) > CSV_MAX_BYTES:
        raise HTTPException(413, f"File too large (max {CSV_MAX_BYTES // 1024 // 1024} MB)")
    if not data.strip():
        raise HTTPException(400, "Empty file")
    try:
        result = services.process_csv(
            user_id=user_id, filename=file.filename or "statement.csv",
            content=data, store=userstore, ai_client=ai_client,
            cost_tracker=cost_tracker, force=force,
        )
    except DuplicateFileError as dup:
        raise HTTPException(409, detail={
            "error": "duplicate_file",
            "message": _dup_message(dup.existing),
            "existing_upload": dup.existing,
            "options": ["skip", "reprocess_replace", "reprocess_append"],
        }) from dup
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if result["rows_inserted"] == 0 and result["summary"]["duplicates_skipped"] == 0:
        raise HTTPException(400, "No valid rows found. Expected columns: date, description, amount (or Ghi nợ/Ghi có).")
    idempotency.put(user_id, "upload", idempotency_key, result)
    return result


@app.post("/enqueue")
async def enqueue(
    request: Request,
    file: UploadFile = File(...),
    x_user_id: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
) -> dict:
    """Async statement import: store + queue (or process inline with no queue).
    Poll GET /job-status/{job_id} for progress."""
    user_id = require_user(request, x_user_id)
    enforce_rate_limit(user_id)
    cached = idempotency.get(user_id, "enqueue", idempotency_key)
    if cached is not None:
        return cached
    name = (file.filename or "").lower()
    ctype = (file.content_type or "").lower()
    if not (name.endswith(_STATEMENT_EXT) or ctype in _STATEMENT_MIME or ctype.startswith("text/")):
        raise HTTPException(415, "Only CSV or Excel (.xlsx/.xls) files are accepted")
    data = await file.read()
    if len(data) > CSV_MAX_BYTES:
        raise HTTPException(413, f"File too large (max {CSV_MAX_BYTES // 1024 // 1024} MB)")
    if not data.strip():
        raise HTTPException(400, "Empty file")
    result = handlers.handle_enqueue(
        user_id, file.filename or "statement.csv", data, storage, ai_client, userstore,
        sqs_queue_url=config.sqs_queue_url, cost_tracker=cost_tracker,
    )
    idempotency.put(user_id, "enqueue", idempotency_key, result)
    return result


@app.get("/job-status/{job_id}")
def job_status(
    job_id: str,
    request: Request,
    x_user_id: str | None = Header(default=None),
) -> dict:
    """Async upload job status: QUEUED → PROCESSING → COMPLETED | FAILED."""
    user_id = require_user(request, x_user_id)
    return handlers.handle_job_status(job_id, userstore, user_id)


IMAGE_MAX_BYTES = 10 * 1024 * 1024
_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
_IMAGE_MIME = {"image/png", "image/jpeg", "image/jpg", "image/webp"}


async def _handle_receipt_upload(request: Request, file: UploadFile, x_user_id: str | None) -> dict:
    user_id = require_user(request, x_user_id)
    enforce_rate_limit(user_id)
    name = (file.filename or "").lower()
    ctype = (file.content_type or "").lower()

    is_pdf = name.endswith(".pdf") or ctype == "application/pdf"
    is_image = name.endswith(_IMAGE_EXT) or ctype in _IMAGE_MIME
    if not (is_pdf or is_image):
        raise HTTPException(415, "Only PDF or image files (PNG/JPG/WEBP) are accepted")

    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    limit = config.max_pdf_size if is_pdf else IMAGE_MAX_BYTES
    if len(data) > limit:
        raise HTTPException(413, f"File too large (max {limit // 1024 // 1024} MB)")

    media_type = "application/pdf" if is_pdf else (ctype if ctype in _IMAGE_MIME else "image/png")
    try:
        return services.process_pdf(
            user_id=user_id, filename=file.filename or ("receipt.pdf" if is_pdf else "receipt.png"),
            content=data, store=userstore, pdf_extractor=pdf_extractor,
            ai_client=ai_client, cost_tracker=cost_tracker, media_type=media_type,
        )
    except DuplicateFileError as dup:
        raise HTTPException(409, detail={
            "error": "duplicate_file",
            "message": _dup_message(dup.existing),
            "existing_upload": dup.existing,
            "options": ["skip"],
        }) from dup


@app.post("/upload-pdf")
@app.post("/upload-image")
@app.post("/upload-receipt")
async def upload_receipt(
    request: Request,
    file: UploadFile = File(...),
    x_user_id: str | None = Header(default=None),
) -> dict:
    """Accepts a receipt PDF or a bank/e-wallet transfer screenshot (PNG/JPG/WEBP).
    Three paths are aliases — `/upload-pdf` kept for the existing frontend."""
    return await _handle_receipt_upload(request, file, x_user_id)


def _dup_message(existing: dict) -> str:
    when = (existing.get("uploaded_at") or "")[:16].replace("T", " ")
    count = existing.get("transaction_count", 0)
    return f"File này đã upload {when} ({count} giao dịch)."


@app.post("/transaction")
async def create_transaction(
    request: Request,
    x_user_id: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
    confirm: bool = Query(default=False),
) -> dict:
    user_id = require_user(request, x_user_id)
    enforce_rate_limit(user_id)
    cached = idempotency.get(user_id, "transaction", idempotency_key)
    if cached is not None:
        return cached
    raw = await request.json()
    try:
        body = TransactionCreate(**raw)
    except ValidationError as exc:
        raise HTTPException(400, detail={"error": "validation_error", "message": "Invalid transaction", "details": _safe_errors(exc.errors())}) from exc
    result = services.create_transaction(
        user_id=user_id, body=body, confirm=confirm, store=userstore,
        ai_client=ai_client, cost_tracker=cost_tracker,
    )
    if result.get("saved"):
        idempotency.put(user_id, "transaction", idempotency_key, result)
    return result


@app.put("/transaction/{txn_id}")
async def update_transaction(
    txn_id: str,
    request: Request,
    x_user_id: str | None = Header(default=None),
) -> dict:
    user_id = require_user(request, x_user_id)
    raw = await request.json()
    try:
        body = TransactionUpdate(**raw)
    except ValidationError as exc:
        raise HTTPException(400, detail={"error": "validation_error", "message": "Invalid update", "details": _safe_errors(exc.errors())}) from exc
    updated = services.update_transaction(
        user_id=user_id, txn_id=txn_id, fields=body.changed_fields(), store=userstore
    )
    if not updated:
        raise HTTPException(404, "Transaction not found")
    return {"transaction": updated}


@app.delete("/transaction/{txn_id}", status_code=204)
def delete_transaction(
    txn_id: str,
    request: Request,
    x_user_id: str | None = Header(default=None),
):
    user_id = require_user(request, x_user_id)
    services.delete_transaction(user_id=user_id, txn_id=txn_id, store=userstore)
    return None


@app.delete("/transactions")
def clear_transactions(
    request: Request,
    x_user_id: str | None = Header(default=None),
) -> dict:
    user_id = require_user(request, x_user_id)
    userstore.clear_transactions(user_id)
    if hasattr(userstore, "clear_chat_memory"):
        userstore.clear_chat_memory(user_id)
    return {"status": "success"}


@app.get("/transactions")
def list_transactions(
    request: Request,
    x_user_id: str | None = Header(default=None),
    month: str | None = None,
    category: str | None = None,
    source: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> dict:
    user_id = require_user(request, x_user_id)
    return services.list_transactions(
        user_id=user_id, store=userstore, month=month, category=category,
        source=source, search=search, page=page, page_size=page_size,
    )


@app.get("/transaction/{txn_id}/audit")
def transaction_audit(
    txn_id: str,
    request: Request,
    x_user_id: str | None = Header(default=None),
) -> dict:
    """Classification audit trail: why this transaction got its category."""
    user_id = require_user(request, x_user_id)
    return services.classification_audit(user_id=user_id, txn_id=txn_id, store=userstore)


@app.get("/summary")
def summary(
    request: Request,
    x_user_id: str | None = Header(default=None),
    month: str | None = None,
) -> dict:
    user_id = require_user(request, x_user_id)
    from datetime import date
    return services.build_summary(
        user_id=user_id, month=month or date.today().strftime("%Y-%m"), store=userstore
    )


@app.get("/admin/cost-report")
def cost_report(
    request: Request,
    x_user_id: str | None = Header(default=None),
    month: str | None = None,
) -> dict:
    user_id = require_user(request, x_user_id)
    return services.cost_report(user_id=user_id, month=month, store=userstore)


@app.get("/admin/usage-stats")
def usage_stats(
    request: Request,
    x_user_id: str | None = Header(default=None),
    month: str | None = None,
) -> dict:
    """Ops dashboard data: cost by flow, classification sources, catalog-hit %,
    needs-review %, latency p50/p95."""
    user_id = require_user(request, x_user_id)
    return services.usage_stats(user_id=user_id, month=month, store=userstore)


@app.get("/budgets")
def get_budgets(
    request: Request,
    month: str | None = None,
    x_user_id: str | None = Header(default=None),
) -> dict:
    return handlers.handle_get_budgets(require_user(request, x_user_id), month, userstore)


class BudgetUpdate(BaseModel):
    category: str
    amount: float


@app.post("/budgets")
def set_budget(
    request: Request,
    body: BudgetUpdate,
    x_user_id: str | None = Header(default=None),
) -> dict:
    try:
        return handlers.handle_set_budget(
            require_user(request, x_user_id), body.category, body.amount, userstore
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


class ChatBody(BaseModel):
    message: str
    session_id: str | None = None
    month: str | None = None
    history: list[dict] | None = None


class ChatResetBody(BaseModel):
    session_id: str | None = None


@app.post("/chat")
def chat(
    request: Request,
    body: ChatBody,
    x_user_id: str | None = Header(default=None),
) -> StreamingResponse:
    user_id = require_user(request, x_user_id)
    enforce_rate_limit(user_id)
    generator = handlers.handle_chat(
        user_id, body.message, body.session_id,
        body.month, userstore, chatbot_client, cost_tracker,
    )
    return StreamingResponse(generator, media_type="text/event-stream")


@app.post("/chat/reset")
def reset_chat(
    request: Request,
    body: ChatResetBody,
    x_user_id: str | None = Header(default=None),
) -> dict:
    return handlers.handle_reset_chat(require_user(request, x_user_id), body.session_id, userstore)


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if config.serve_frontend:
    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")


if Mangum:
    _mangum_handler = Mangum(app, lifespan="off")

    def handler(event, context):
        records = event.get("Records", [])
        if records and records[0].get("eventSource") == "aws:sqs":
            return handlers.handle_sqs_event(
                event=event, storage=storage, ai_client=ai_client, userstore=userstore
            )
        if event.get("version") == "2.0":
            event.setdefault("requestContext", {})
            event["requestContext"].setdefault("http", {})
            event["requestContext"]["http"].setdefault("sourceIp", "0.0.0.0")
            event["requestContext"]["http"].setdefault("userAgent", "unknown")
        return _mangum_handler(event, context)
