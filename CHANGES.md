# CHANGES — Production hardening (in progress)

Taking the AI layer from demo to production per the engineering brief.
`make check` → ruff clean · mypy clean · **89 passed / 9 skipped** (SQLite),
coverage **78%**. With a Postgres test DB: **98 passed** (full app on RDS backend).

### Post-Phase — Concurrency + rate limiting
- **Postgres connection pool.** `PostgresUserStore` now uses a
  `ThreadedConnectionPool` + a `_cursor()` context manager (checkout → transaction →
  commit/rollback → return), so concurrent request threads each get their own
  connection (parallel, bounded vs RDS max_connections) and multi-statement methods
  are atomic. Verified with a concurrent-writes test on a live Postgres.
- **API rate limiting** (`src/ratelimit.py`, adapter pattern): in-memory for
  local/single-task, **Redis/Valkey** (`REDIS_URL`) shared across Fargate tasks.
  Per-user fixed window/min → `429` + `Retry-After` on `/upload`, `/enqueue`,
  `/transaction`, receipt uploads, `/chat`. Fails **open** if the limiter is down.
  Terraform provisions an **ElastiCache Valkey** node (SG-locked) and wires
  `REDIS_URL` + `RATE_LIMIT_ENABLED`. Verified against a live Valkey container.
- **SQLite store is now thread-safe.** FastAPI runs sync routes in a thread pool, so
  requests hit the store concurrently; sharing one connection raced ('database is
  locked' / recursive cursor). Each thread now gets its **own connection
  (thread-local) + WAL + `busy_timeout=5s`** — concurrent readers with a single
  writer, writers wait instead of erroring. New `tests/test_concurrency.py`: 8
  threads × 25 writes + mixed read/write, zero errors, no lost rows.

### Post-Phase — Frontend async upload (P1)
- **Large files now use the async pipeline.** Files > ~1 MB go through
  `POST /enqueue` + poll `GET /job-status/{id}` (avoids the ALB 60s timeout);
  smaller files keep the rich synchronous `/upload` flow. New client helpers
  `enqueueCsv` / `getJobStatus` / `shouldUseAsync` (+ mock); UploadCsv shows a
  background-processing state then an "imported N transactions" result.
- **Auth fix:** the multipart `/upload` (and new `/enqueue`) now send the Cognito
  `Authorization: Bearer` via a shared `authHeaders()` — previously raw-fetch
  uploads sent only `X-User-Id`, so they'd 401 under `REQUIRE_AUTH`.

### Post-Phase — Small hardening (P1/P2)
- **CORS:** `allow_credentials` now off when `CORS_ORIGINS="*"` (wildcard+credentials
  is invalid/unsafe); on only for explicit prod origins.
- **Guest hidden under enforced auth:** `/health` exposes `require_auth`; the auth
  screen hides "continue as guest" when the backend enforces auth (a guest has no
  token → would 401).
- **Coverage:** added LocalStorage round-trip/list/presign tests. Suite **106 passed
  / 9 skipped**, coverage **79%**.

### Post-Phase — Async dedup parity (tech-debt A)
- **`/enqueue` (async) now dedups like `/upload`.** The worker core `process_job`
  routes through `services.process_csv`, so the async path gets the **file-hash 409
  check + per-row fingerprint dedup** (and Excel support) it was missing — no more
  double-import on SQS redelivery or re-enqueue.
- **Two-level idempotency:** job-status guard (skip COMPLETED) + `DuplicateFileError`
  on identical content → no-op COMPLETED (rows_inserted=0). Inline `/enqueue` (no
  queue) reuses the same `process_job` core.
- Removed dead code: `_categorize_and_save`, `_parse_pdf` (async no longer has a
  bespoke save path). `ruff`/`mypy` clean; **103 passed / 9 skipped** (SQLite),
  **112 passed** on Postgres.

### Post-Phase — Real backend auth (tech-debt P0-1)
- **Closed the X-User-Id IDOR gap.** New `src/auth.py` verifies a Cognito JWT
  (`Authorization: Bearer`) against the pool JWKS (RS256 sig + issuer + expiry +
  token_use/client_id) and derives `user_id` from `sub`. Identity precedence:
  verified Bearer → API-GW authorizer claim → X-User-Id.
- **Opt-in via `REQUIRE_AUTH`** (default off) — local/demo + the whole test suite
  keep the single-user X-User-Id behaviour; prod (Terraform) sets
  `REQUIRE_AUTH=true` + the Cognito pool/client ids so the backend enforces auth
  and a spoofed X-User-Id is rejected with 401.
- **Frontend** now sends the Cognito id token as `Authorization: Bearer` (set on
  login/restore, cleared on logout/guest).
- Dep: `pyjwt[crypto]`. **Tests (+9)**: identity precedence, REQUIRE_AUTH 401s,
  verified-token 200, graceful no-config. `ruff`/`mypy` clean; **101 passed / 9 skipped**.

### Post-Phase — Async pipeline (tech-debt P1)
- **Proper async upload flow**: `POST /enqueue` stores the file to **S3**, creates a
  `QUEUED` job, and sends an SQS message; a **Fargate poller worker** (`src/worker.py`,
  `python -m src.worker`) long-polls SQS and runs `handlers.process_job` → S3 get →
  classify → RDS → `COMPLETED`. Poll `GET /job-status/{id}`.
- **Correctness**: `process_job` is **idempotent** (skips an already-COMPLETED job —
  SQS is at-least-once) and **raises on failure** so the message is left for retry;
  after `maxReceiveCount=3` it lands in a **DLQ**. Queue visibility timeout (300s) ≥
  worker processing window so long jobs aren't redelivered mid-flight.
- **Terraform** (`sqs.tf`): S3 uploads bucket (private, 7-day lifecycle), SQS queue +
  DLQ, a second ECS service for the worker (reuses the image, task role, SG, RDS),
  shared `local.app_env`. **EFS removed** (state is now RDS + S3); storage flipped to
  S3; `TEXTRACT_ENABLED=true`; IAM gains SQS + S3 access. `terraform validate` passes.
- **Tests (+3):** `process_job` completes / is idempotent / fails→raises.

### Post-Phase — Postgres/RDS parity (tech-debt P0)
- **`PostgresUserStore` brought to full feature parity with SQLite** — `needs_review`
  column, `merchant_catalog`, `classification_audit`, `idempotency`, `cost_log`
  (incl. cache tokens), `uploaded_files`/`receipt_extractions`, and every method the
  app calls (list_filtered, catalog, audit, usage_stats, idempotency w/ TTL,
  dedup queries). Schema self-upgrades via `ALTER TABLE … ADD COLUMN IF NOT EXISTS`.
- **Verified against a live Postgres 16** — new `tests/test_store_parity.py` runs one
  battery across *both* backends (Postgres params auto-skip when `TEST_POSTGRES_URL`
  is unset, so the offline suite stays green), and the **entire app suite passes on
  Postgres** (98/98 on a clean DB).
- **RDS provisioned in Terraform** (`terraform/rds.tf`) — Postgres 16 db.t3.micro,
  private (SG admits only the ECS task SG), credentials in Secrets Manager. ECS task
  flips to `USERSTORE_BACKEND=postgres` + `DB_SECRET_NAME`; IAM gains
  `secretsmanager:GetSecretValue` (+ `textract:AnalyzeExpense` for the P1 fallback).
  `Dockerfile.web` now installs `psycopg2-binary`. `terraform validate` passes.

### Phase 3 · Observability + DX (3.1–3.6)
- **`GET /admin/usage-stats`** — ops metrics: cost by flow, classification sources,
  catalog-hit %, needs-review %, latency p50/p95.
- **Async upload path wired** — `POST /enqueue` (store + SQS, or inline when no
  queue) + `GET /job-status/{id}` (QUEUED→PROCESSING→COMPLETED|FAILED). Removed the
  dead legacy handlers (`handle_upload`, `handle_process_from_s3`) and the unused
  `transactionstore` re-export.
- **Idempotency TTL** — replays are cached for `IDEMPOTENCY_TTL_DAYS` (default 2)
  with opportunistic cleanup of expired keys.
- **PII discipline** — removed all `print()`; CloudWatch-metric + boot failures now
  log via loguru with masked user ids; no raw amount/description in non-error logs.
- **Quality toolchain** — `ruff` + `mypy` + `pytest-cov` configured in pyproject;
  whole `src/` is **ruff-clean and mypy-clean**. Makefile gains
  `dev / lint / format / typecheck / cov / check / docker-*`.
- **Tests (+3):** async enqueue/job-status + usage-stats.

### Phase 2 · Reliability + audit (2.1–2.5)
- **Adaptive retry/backoff on Bedrock.** All AI adapters share one
  `bedrock_client.make_runtime` factory with `retries={"mode":"adaptive"}`, so a
  transient ThrottlingException is retried before degrading to LocalAI.
- **Idempotency keys.** `Idempotency-Key` header on POST /upload and
  /transaction caches the first successful response (`idempotency` table) and
  replays it verbatim — a retried upload never double-imports. Only committed
  writes are cached.
- **Classification audit trail.** Every categorization records how it was decided
  (`classification_audit` table: source = keyword/llm/cache/rule/fallback/manual,
  prompt_version, model_id — never the raw prompt). New `GET /transaction/{id}/audit`
  endpoint; the transaction detail drawer shows a **"Vì sao phân loại?"** panel.
- **Async SQS worker parity.** `handlers._categorize_and_save` now delegates to
  `services._classify_rows` + budget guard + cost tracking + audit — full parity
  with the synchronous upload flow (was a naïve per-row loop).
- **PDF Textract fallback chain.** Bedrock vision → (if `TEXTRACT_ENABLED`) AWS
  Textract AnalyzeExpense → flagged manual-entry preview. Any vision failure
  (Bedrock error, missing PyMuPDF, bad image) degrades gracefully, never 500s.
- **Smoke script** exercises the new audit + idempotency paths; verified live.
- Removed dead code (legacy `BedrockAI.categorize`, unused few-shot params).
- **Tests (+7):** SQS parity, idempotency replay (×3), Textract fallback chain (×3).

### Phase 1 · commit 2 — AI quality + cost (1.3–1.7)
- **LLM output validation + `needs_review`.** Every classification is coerced
  through a pydantic `ClassificationResult` (`models.py`): malformed JSON,
  non-dict, unknown enum, or a missing batch row all degrade to `Other` +
  `needs_review=true` instead of crashing. Below a 0.6 confidence threshold also
  flags review. Persisted on transactions (new `needs_review` column), returned by
  the API, surfaced in the UI with an amber **"Cần kiểm tra"** badge; a manual
  re-categorize clears it.
- **Merchant catalog cache** (`catalog.py` + `merchant_catalog` table). A
  normalized-description → category cache short-circuits the LLM once a merchant
  is seen ≥3× with ≥0.8 avg confidence; duplicate descriptions within one upload
  are classified once and fanned out. Weak guesses are never cached.
- **Budget guard** (`services._budget_guard`). Per-request cost estimate and a
  per-user-per-day cap (env-tunable) degrade an upload to LocalAI — with a
  user-facing warning in the upload result — rather than overspend silently.
- **Bedrock prompt caching.** The large static money-coach system prompt is sent
  as a `cachePoint`-separated block from the per-request context; `TokenUsage`
  now tracks cache-read/-write tokens and prices them (cost_log columns added).
- **Determinism + safety.** All classification at `temperature=0.0`; broad
  `except Exception` replaced with named Bedrock errors across the AI adapters.
- **Tests (+18):** AI failure modes (malformed/invalid-enum/partial-batch/
  throttle→fallback), catalog hit + in-upload dedup, budget guard (per-request /
  daily / force-local), prompt-cache block shape, needs_review e2e.

### Phase 1 · commit 1 — P0 AI fixes + test infra
- **Chat is now cost-tracked.** `ChatbotAI` reads the `converse_stream` `metadata`
  event and surfaces token usage via a `cost_sink`; `handle_chat` records both the
  turn (`flow=chat`) and memory compaction (`flow=chat_summary`) to the cost log.
  Previously the most token-heavy flow was invisible in `/admin/cost-report`.
- **Category enum drift fixed.** `chatbot.py` and `handlers.py` no longer redeclare
  the stale Utilities/Subscriptions/Income enum — both now use the canonical
  `categories.py` set. The `set_budget` tool offers only valid categories; chat
  transaction-routing hints match stored rows. Dead duplicate dicts removed.
- **Determinism.** Money-coach inference dropped to `temperature=0.0` (was 0.3/0.1).
- **Reusable AI test doubles** (`tests/fakes.py`: `FakeBedrockRuntime`,
  `converse_text`, `stream_text`, `throttling_error`) enable deterministic
  success/failure-mode testing with zero AWS. New tests: chat cost tracking +
  enum-drift guard.

---

# CHANGES — Backend v0.2 (API contract, PDF, cost, dedup)

Extends the BudgetBot backend to the full frontend API contract with
production-grade structure. Runs fully locally (LocalAI + SQLite + LocalStub PDF,
no AWS); flips to Bedrock/RDS/S3 by env. `pytest -v` → **40 passed**.

## New / changed

### Categories (breaking)
Canonical enum is now **Food, Transport, Shopping, Bills, Entertainment, Health,
Education, Salary, Transfer, Other** (`src/categories.py`) — replaces the old
Utilities/Subscriptions/Income. Frontend mirror updated to match.

### Endpoints (singular contract)
- `GET /health` → `{status, ai_backend, db_backend, pdf_backend, version, categories}`
- `POST /upload` (CSV) → classifies in batches, dedups, returns
  `{transactions, rows_inserted, cost_estimate_usd, tokens, duplicates_skipped, summary}`
- `POST /upload-pdf` → extracts a receipt (vision/stub) → **preview, not saved**
- `POST /transaction` (+`?confirm=true`) → validate → AI-classify if needed → save
- `PUT /transaction/{id}` → partial update
- `DELETE /transaction/{id}` → 204 · `DELETE /transactions` → clear all
- `GET /transactions?month&category&source&search&page&page_size` → paginated
- `GET /summary?month` → income / expense / net + by-category% + prev-month comparison
- `GET /admin/cost-report?month` → cost aggregated by flow / day / tokens
- `/budgets` and `/chat` (SSE) preserved for the Insights + money-coach widgets.

### Adapters
- `ai.py`: `TokenUsage` dataclass + cost calc; `classify_one` / `classify_batch`;
  hybrid keyword fast-path → Bedrock Converse → LocalAI fallback; VN merchant dict.
- `pdf_extractor.py` (new): `PDFExtractor` ABC + `BedrockPDFExtractor` + `LocalStubPDFExtractor`.
- `transactionstore.py` (new): clearer alias of `userstore.py`; SQLite store gains
  `get/update/list_filtered/log_cost/aggregate_costs/migrate` + dedup queries.
- `factory.py`: `make_pdf_extractor`, `DB_BACKEND` precedence, "why adapter pattern" docstring.

### Cost instrumentation (P3)
- `cost_tracker.py`: every AI call logged to `cost_log` + structured (loguru) line
  with **masked** user id. `scripts/cost_estimate.py` CLI for AWS projections.

### Dedup (P7) — 4 levels, tested on SQLite
1. **File hash** → identical re-upload returns **409** with `existing_upload` +
   `options` (skip / replace / append); override via `?force=`.
2. **Transaction fingerprint** (date-less: `sha256(user|amount|normalized_desc)`)
   → within-batch + cross-DB skip, with **± date tolerance** (date proximity is
   checked separately, so the literal "include date in fingerprint" from the spec
   is implemented as fingerprint + tolerance — otherwise tolerance is meaningless).
   Normalisation strips transaction IDs, dates, punctuation and sorts tokens.
3. **Manual-entry soft warning** (wider window) → returns `warning` + `saved:false`;
   `?confirm=true` saves anyway.
4. **PDF receipt** → file hash (409) **plus** extracted-field fingerprint warning
   for re-scans of the same receipt.
   Config: `DEDUP_ENABLED`, `DEDUP_DATE_TOLERANCE_DAYS`, `DEDUP_MANUAL_WARN_DAYS`.

### Validation & errors (P4)
Pydantic models (`models.py`); 413 (CSV>10MB / PDF>5MB), 415 (mime), 400
(malformed CSV / invalid body), 401 (missing user), 409 (dup), 503-ready Bedrock
fallback. Global handler → consistent `{error, message, details}` JSON
(pydantic error objects are sanitised to stay JSON-serialisable).

### DX (P6)
`sample_data/sample_statement.csv` (58 VN rows, 3 months) + 3 synthetic receipt
PDFs (`scripts/gen_receipts.py`, CC0 — see `SOURCES.md`). Scripts: `init_db.py`,
`seed_db.py`, `migrate_add_dedup.py`, `cost_estimate.py`, `smoke.sh`. New deps:
loguru, pypdf, Pillow, reportlab (+ optional pymupdf for Bedrock PDF).

## Image import — bank transfer screenshots (any bank)
- `/upload-pdf` now also accepts **images** (PNG/JPG/WEBP); aliases `/upload-image`
  and `/upload-receipt` added. Frontend "Add receipt" accepts screenshots too.
- **Covers all banks without per-bank code**: one generic vision prompt
  (`prompts.PDF_EXTRACT_SYSTEM`) reads any layout — MB, Vietcombank, VietinBank,
  Techcombank, BIDV, VIB, OCB, Timo, ACB, MoMo, ZaloPay… — into a normalised
  schema (amount, date, direction in/out, counterparty, bank, account, content,
  reference). Images go straight to Claude vision; PDFs are rasterised first.
  `direction` sets the sign; bank transfers default to category Transfer; the user
  reviews/edits the preview before saving.
- Offline (`PDF_BACKEND=local`): images can't be OCR'd, so the stub returns an
  empty editable preview flagged `offline_stub` (UI nudges: enable vision or fill
  manually). Real extraction = `PDF_BACKEND=bedrock`. Tests: `test_image_flow.py`.

## Excel statement import (.xlsx/.xls)
- `POST /upload` now accepts **Excel** as well as CSV (`src/statement_parser.py`).
- **Generic, no per-bank code**: header row is auto-detected (anywhere in the first
  20 rows) and columns mapped via an accent-insensitive **synonym dictionary**
  (Ngày/Date, Diễn giải/Nội dung/Description, Số tiền/Amount, and **Ghi nợ/Ghi có**
  = Debit/Credit). A debit/credit pair is collapsed to one signed amount
  (credit = income +, debit = expense −). Extend coverage by adding synonyms.
- Unrecognised layouts → **400** with a clear message (the `mapping` override /
  column-picker UI is the escape hatch). `.xls` (old binary) needs `pip install
  xlrd`; `.xlsx` works out of the box (openpyxl). Tests: `test_excel_flow.py`.
- Frontend "Upload statement" page accepts `.csv/.xlsx/.xls`; mock mode shows a
  small sample for Excel (binary can't be parsed in the browser).

## Trade-offs / notes
- **Bedrock & PDF-vision paths are coded but not run here** (no AWS credentials in
  this environment); verified via the LocalAI / LocalStub paths. Bedrock has no
  native PDF input, so the adapter rasterises page 1 to PNG (PyMuPDF) for vision.
- **Dedup is fully implemented + tested on SQLite** (default). Postgres/DynamoDB
  keep the existing endpoints working; their dedup query methods are not yet
  implemented (documented; add `migrate()` + the `find_*` methods to enable).
- `uv` is used for dependency management (the environment blocks `pip`); a
  `pyproject.toml`/`uv.lock` were added. `requirements.txt` remains the canonical list.
- Not a git repository, so changes are grouped logically rather than per-commit.
