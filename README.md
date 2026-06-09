# BudgetBot — AI Money Coach

Upload a bank statement (CSV / Excel / PDF) or a bank-transfer screenshot → every
transaction is **categorized by AI** → spending is summarized by category, with
budgets, alerts, and a streaming **AI money-coach chatbot**.

Designed to run **fully locally** (rule-based stub, SQLite, filesystem) and flip to
AWS (Bedrock, S3, Postgres/DynamoDB, Cognito) **via env vars alone — no code changes**.

---

## Quick start (local, ~2 minutes)

### Backend

```bash
make install                 # python venv + pip install -r requirements.txt
cp .env.example .env         # local defaults: AI=local, storage=local, db=sqlite
make run                     # uvicorn src.app:app --reload --port 8000
```

```bash
# health check
curl http://localhost:8000/health

# end-to-end: upload a sample statement, then read the summary
curl -X POST http://localhost:8000/upload \
  -H "X-User-Id: alice" \
  -F "file=@sample_data/bank_statement_q2_2026.csv"

curl "http://localhost:8000/summary?month=2026-04" -H "X-User-Id: alice"
```

With the local defaults there are **no AWS calls**: categorization uses keyword
rules, uploads go to `data/uploads/`, and transactions land in SQLite at
`./_data/transactions.db`.

### Frontend

```bash
cd frontend
pnpm install
pnpm dev                     # Vite dev server → http://localhost:5173
```

The dev server proxies `/api` → `http://localhost:8000`, so run the backend too.
React 19 + Vite + Tailwind v4 + Recharts + React Query. Bilingual (VN primary / EN),
light + dark, mobile-first.

### Tests

```bash
make test                                  # pytest -v tests/
pytest tests/test_smoke.py::test_health -v # single test
```

Tests force local backends at import time — they never touch AWS.

---

## Features

- **Four ways to add transactions**, all converging on one categorize-and-save core:
  - **CSV / Excel statements** (`.csv`, `.xlsx`, `.xls`) — auto-detects the Date /
    Description / Amount columns (or Debit/Credit) by header synonyms, no per-bank code.
  - **Receipt images & PDFs** (`.png`, `.jpg`, `.webp`, `.pdf`) — a single vision
    prompt reads bank-transfer screenshots from any bank (VCB, Techcombank, MB, MoMo…).
  - **Manual quick-add** — one transaction at a time; AI suggests the category.
- **AI categorization** into 10 canonical categories: `Food, Transport, Shopping,
  Bills, Entertainment, Health, Education, Salary, Transfer, Other`. Vietnamese input
  is mapped via aliases. (Source of truth: `src/categories.py`, mirrored in
  `frontend/src/lib/categories.ts`.)
- **Deduplication** — 4-level: same-file re-upload (skip / replace / append), and a
  fingerprint + date-tolerance check that warns on near-duplicate rows.
- **Summaries, budgets & alerts** — spend by category, top drivers, per-category
  budget limits with over-budget warnings.
- **AI money-coach chat** — streaming (SSE), domain-guardrailed, with a `set_budget`
  tool and rolling conversation memory.
- **Auth** — AWS Cognito (email sign-up / verify / login / forgot-password) with a
  **"continue as guest"** option. Runs guest-only when Cognito env vars are unset.
- **Cost instrumentation** — token usage and USD cost tracked per request
  (`GET /admin/cost-report`), CloudWatch custom metrics in `BudgetBot/W7`.

---

## Architecture

Strictly layered — **business logic stays out of `app.py`**:

```
app.py        routes, HTTP concerns, user_id resolution
  └─ handlers.py     parsing, the categorize-and-save pipeline, summaries, budgets, chat
       └─ adapters/  pluggable backends, chosen by factory.py from env vars
```

The same `src.app:app` runs under **uvicorn** locally, **ECS Fargate** (`Dockerfile.web`),
and **AWS Lambda** (Mangum `handler`, `Dockerfile`). The Lambda handler routes SQS
`Records` to the async worker and everything else to Mangum.

### Adapters — swap purely by env var

| Concern | Env var | Options | Local default |
|---|---|---|---|
| AI categorization/chat | `AI_BACKEND` | `bedrock`, `local` | `local` |
| Receipt/PDF extraction | `PDF_BACKEND` | `bedrock`, `local` | `local` |
| Object storage (uploads) | `STORAGE_BACKEND` | `s3`, `local` | `local` |
| Transaction DB | `USERSTORE_BACKEND` | `sqlite`, `postgres`, `dynamodb`, `documentdb`, `mysql` | `sqlite` |

`adapters/factory.py` is the **only** place backends are chosen. Adding a backend =
implement the documented interface + add one branch there.

`BedrockAI` is hybrid: fast keyword matching first, Bedrock `converse` only for
ambiguous rows, and **falls back to `LocalAI` on any Bedrock error** — so a missing
model or throttle never breaks an upload.

### API surface

```
GET  /health
POST /upload                 multipart CSV / Excel
POST /upload-pdf | /upload-image | /upload-receipt
POST /transaction            PUT/DELETE /transaction/{id}
GET  /transactions           DELETE /transactions
GET  /summary?month=YYYY-MM
GET  /budgets                POST /budgets
POST /chat                   POST /chat/reset       (streaming money coach)
GET  /admin/cost-report
```

`user_id` resolves from the Cognito JWT `sub` (API Gateway authorizer claims) →
`X-User-Id` header → `DEFAULT_USER_ID`. The SPA sends the Cognito `sub` (or a
`guest-…` id) as `X-User-Id`, so data scopes per user with no backend change.

**Domain conventions:** negative amount = expense, positive = income; budget "spent"
uses `abs()` of negatives. Currency assumed VND in the local stub; Bedrock is
currency-agnostic.

---

## Diagrams

Source files live in [`docs/diagrams/`](docs/diagrams/). The Mermaid blocks below
render natively on GitHub; the infrastructure diagram is also exported as a
high-DPI PNG and a **[vector PDF](docs/diagrams/budgetbot_-_aws_infrastructure.pdf)**
for crisp printing. To re-render any Mermaid file, paste it into
[mermaid.live](https://mermaid.live) or run
`npx -p @mermaid-js/mermaid-cli mmdc -i docs/diagrams/<name>.mmd -o <name>.svg`.

### Infrastructure (AWS)

![BudgetBot AWS infrastructure](docs/diagrams/budgetbot_-_aws_infrastructure.png)

Route53 splits traffic to **CloudFront → S3** (static SPA) and **ALB → ECS Fargate**
(API), both fronted by **WAFv2**. The API runs in private subnets, reaches AWS
services over **VPC endpoints (PrivateLink)**, and uses **RDS PostgreSQL**,
**ElastiCache (Valkey)** for rate limiting, **Bedrock** + **Textract** for AI/OCR,
**SQS (+DLQ)** with a worker service for async uploads, and **Cognito** for auth.
CloudWatch alarms fan out to SNS; app-autoscaling tracks CPU.

### Application architecture (by layer & feature)

[`docs/diagrams/app_architecture.mmd`](docs/diagrams/app_architecture.mmd)

```mermaid
flowchart TB
  classDef fe fill:#EAF4FF,stroke:#3b82f6,color:#0b2545;
  classDef api fill:#E5F7EE,stroke:#10b981,color:#064e3b;
  classDef logic fill:#FDE9F0,stroke:#db2777,color:#831843;
  classDef adapt fill:#FFF8DB,stroke:#d97706,color:#7c2d12;
  classDef bk fill:#E0F7FA,stroke:#0891b2,color:#0c4a6e;
  classDef ext fill:#FCE4EC,stroke:#9333ea,color:#581c87;

  subgraph FE["🖥️ Frontend — React 19 + Vite + TS (CloudFront/S3)"]
    direction TB
    pages["Pages: Dashboard · Giao dịch · Phân tích (Budgets) · Cài đặt"]
    chatw["Chat widget (SSE streaming)"]
    rq["React Query — useAllTransactions / useSummary / useBudgets / useSetBudget"]
    apic["api client — authHeaders(X-User-Id + Bearer) · isMock()"]
    pages --> rq --> apic
    chatw --> apic
  end
  class FE,pages,chatw,rq,apic fe;

  cog["☁️ Cognito User Pool — idToken (JWT)"]:::ext
  apic -. "login / signup" .-> cog

  subgraph API["⚙️ FastAPI app.py — routes only"]
    direction TB
    mw["strip_api_prefix · CORS"]
    auth["_resolve_user_id → verify Cognito JWT (JWKS) → sub"]
    rl["enforce_rate_limit"]
    routes["/upload · /enqueue · /process · /transactions · /summary · /budgets · /chat · /job-status"]
    mw --> auth --> rl --> routes
  end
  class API,mw,auth,rl,routes api;
  apic == "HTTPS /api  (Bearer)" ==> mw

  subgraph LOGIC["🧠 Business logic (keep out of app.py)"]
    direction TB
    handlers["handlers.py — orchestration · chat · jobs"]
    services["services.py — process_csv/pdf · _classify_rows · build_summary · budgets · audit"]
  end
  class LOGIC,handlers,services logic;
  routes --> handlers
  routes --> services
  handlers --> services

  subgraph ADAPT["🔌 adapters/factory.py — backend chosen by env var"]
    direction TB
    ai["ai — BedrockAI ↔ LocalAI (hybrid keyword + fallback)"]
    bot["chatbot — money-coach · set_budget tool · rolling memory"]
    store["userstore — Postgres / SQLite / DynamoDB …"]
    stor["storage — S3 / local"]
    pdf["pdf_extractor — Textract"]
    dedup["dedup — per-user file hash + fingerprint"]
    idem["idempotency"]
    cost["cost_tracker · metrics"]
    rlm["ratelimit — Redis/Valkey · fail-open"]
  end
  class ADAPT,ai,bot,store,stor,pdf,dedup,idem,cost,rlm adapt;
  services --> ai
  services --> store
  services --> stor
  services --> pdf
  services --> dedup
  services --> idem
  services --> cost
  handlers --> bot
  rl --> rlm

  subgraph BK["🗄️ Backends / AWS services"]
    direction TB
    bedrock["Bedrock — Claude Haiku 4.5"]
    textract["Textract"]
    pg["PostgreSQL (RDS)"]
    valkey["Valkey (ElastiCache)"]
    s3["S3 uploads"]
    sqsq["SQS + DLQ"]
    worker["ECS worker — process_job (idempotent)"]
  end
  class BK,bedrock,textract,pg,valkey,s3,sqsq,worker bk;
  ai --> bedrock
  bot --> bedrock
  pdf --> textract
  store --> pg
  rlm --> valkey
  stor --> s3
  handlers == "/enqueue" ==> sqsq
  sqsq --> worker
  worker == "process_job" ==> services

  subgraph FEAT["📌 Feature flows"]
    direction TB
    f1["1) Upload sao kê (CSV/Excel/PDF/ảnh) → 3 đường: sync /upload · presigned /process · async /enqueue→SQS"]
    f2["2) Phân loại: keyword nhanh → Bedrock cho dòng mơ hồ → fallback LocalAI → lưu tuần tự"]
    f3["3) Dashboard: build_summary (server) — chi=Σ|âm|, thu=Σ dương"]
    f4["4) Ngân sách: set/get + cảnh báo vượt (UI form + chatbot set_budget)"]
    f5["5) Chat money-coach: streaming + guardrails + bộ nhớ hội thoại"]
  end
```

### Use case (actors ↔ use cases)

[`docs/diagrams/usecase.mmd`](docs/diagrams/usecase.mmd)

```mermaid
flowchart LR
  actorU["👤 Người dùng<br/>(đã đăng nhập)"]
  actorG["👥 Khách / Guest"]
  cog["🔐 Cognito"]
  bed["🤖 Bedrock (AI)"]
  tex["📄 Textract (OCR)"]

  subgraph SYS["💰 BudgetBot — System boundary"]
    direction TB
    uc1(["Đăng ký / Đăng nhập"])
    uc2(["Tải lên sao kê CSV / Excel"])
    uc3(["Tải hóa đơn / ảnh (OCR)"])
    uc4(["Thêm giao dịch thủ công"])
    uc5(["Tự động phân loại giao dịch"])
    uc6(["Xem Dashboard tổng quan"])
    uc7(["Xem & sửa giao dịch"])
    uc8(["Phân tích chi tiêu"])
    uc9(["Đặt ngân sách & cảnh báo"])
    uc10(["Chat trợ lý tài chính"])
  end

  actorU --- uc1
  actorU --- uc2
  actorU --- uc3
  actorU --- uc4
  actorU --- uc6
  actorU --- uc7
  actorU --- uc8
  actorU --- uc9
  actorU --- uc10
  actorG --- uc2
  actorG --- uc4
  actorG --- uc6
  actorG --- uc7
  actorG --- uc8

  uc1 -. include .- cog
  uc2 -. include .- uc5
  uc3 -. include .- uc5
  uc3 -. include .- tex
  uc5 -. include .- bed
  uc10 -. include .- bed
  uc9 -. extend .- uc10
  classDef uc fill:#EAF4FF,stroke:#3b82f6,color:#0b2545;
  classDef act fill:#FFF4E5,stroke:#d97706,color:#7c2d12;
  classDef ext fill:#FCE4EC,stroke:#9333ea,color:#581c87;
  class uc1,uc2,uc3,uc4,uc5,uc6,uc7,uc8,uc9,uc10 uc;
  class actorU,actorG act;
  class cog,bed,tex ext;
```

### Sequence — statement upload & categorization

[`docs/diagrams/seq_upload.mmd`](docs/diagrams/seq_upload.mmd)

```mermaid
sequenceDiagram
  autonumber
  actor U as Người dùng
  participant FE as Frontend (React)
  participant API as FastAPI (ALB)
  participant SVC as services.py
  participant AI as AI (Bedrock↔Local)
  participant DB as PostgreSQL
  participant S3 as S3 uploads
  participant Q as SQS
  participant W as ECS Worker

  U->>FE: Chọn file sao kê (CSV/Excel)
  FE->>API: POST /upload (X-User-Id + Bearer JWT)
  API->>API: verify Cognito JWT · enforce_rate_limit
  alt File nhỏ — đồng bộ
    API->>SVC: process_csv(user_id, file)
    SVC->>DB: dedup (file hash + fingerprint / user)
    SVC->>AI: phân loại từng dòng (keyword → Bedrock nếu mơ hồ → fallback Local)
    AI-->>SVC: category + confidence
    SVC->>DB: lưu giao dịch (tuần tự, thread-safe)
    SVC-->>API: kết quả + summary
    API-->>FE: 200 OK
  else File lớn (>1MB) — bất đồng bộ
    FE->>API: POST /enqueue
    API->>S3: PUT file gốc
    API->>Q: gửi job (QUEUED)
    API-->>FE: 202 + job_id
    Q->>W: deliver message
    W->>SVC: process_job (idempotent)
    SVC->>AI: phân loại
    SVC->>DB: lưu giao dịch
    W-->>Q: xong (COMPLETED)
    loop Poll trạng thái
      FE->>API: GET /job-status/{id}
      API-->>FE: PROCESSING → COMPLETED
    end
  end
  FE->>API: GET /summary (làm mới)
  API->>DB: build_summary (GROUP BY danh mục)
  API-->>FE: Dashboard cập nhật
```

### Sequence — chat money-coach & budget

[`docs/diagrams/seq_chat.mmd`](docs/diagrams/seq_chat.mmd)

```mermaid
sequenceDiagram
  autonumber
  actor U as Người dùng
  participant FE as Chat widget
  participant API as FastAPI /chat
  participant H as handlers.handle_chat
  participant SVC as services.build_summary
  participant DB as PostgreSQL
  participant BOT as ChatbotAI
  participant BR as Bedrock (Haiku 4.5)

  U->>FE: "Đặt ngân sách Ăn uống 30M, Mua sắm 40M"
  FE->>API: POST /chat (SSE, Bearer JWT)
  API->>API: verify JWT · enforce_rate_limit
  API->>H: handle_chat(user_id, message, session)
  H->>SVC: build_summary(month)
  SVC->>DB: tổng chi theo danh mục
  H->>DB: giao dịch gần đây + ngân sách + bộ nhớ hội thoại
  H->>BOT: chat(context, tools=[set_budget])
  BOT->>BR: converse_stream(system + context + tools)
  BR-->>BOT: tool_use × N (set_budget) — nhiều block
  loop Mỗi tool call
    BOT->>DB: set_budget(category, amount)
  end
  BOT->>BR: converse_stream(tool results)
  BR-->>FE: stream tokens trả lời (SSE)
  H->>DB: cost_tracker ghi chi phí + cập nhật memory
  FE-->>U: "Đã đặt: Ăn uống 30.000.000 ₫, Mua sắm 40.000.000 ₫"
```

---

## Switching to AWS (env flip, no code change)

```diff
- AI_BACKEND=local
+ AI_BACKEND=bedrock
+ AI_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0
+ PDF_BACKEND=bedrock

- STORAGE_BACKEND=local
+ STORAGE_BACKEND=s3
+ STORAGE_BUCKET=budgetbot-statements-<accountid>

- USERSTORE_BACKEND=sqlite
+ USERSTORE_BACKEND=postgres          # OR dynamodb
+ USERSTORE_POSTGRES_URL=postgresql://user:pw@your-rds-endpoint:5432/budgetbot
```

For DynamoDB, set `USERSTORE_TABLE=…` (single-table: `PK=user_id`,
`SK=TXN#… / BUDGET#…`). Aggregations there need Scan/GSI; SQL backends do
`GROUP BY` natively — this trade-off is intentional.

Optional DB drivers (DocumentDB / MySQL / `psycopg2`): `pip install -r requirements-optional.txt`.

---

## Deploy to AWS (Terraform)

A full IaC stack lives in `terraform/` — ECS Fargate + EFS (SQLite persistence),
ALB + ACM, CloudFront + S3 (frontend), Cognito User Pool, and Route 53. State is in
S3 with native locking.

```bash
cd terraform
./bootstrap.sh                 # one-time: create the S3 state bucket
terraform init
terraform apply                # provision the stack
../terraform/deploy.sh all     # build+push backend image, publish frontend
```

`deploy.sh` bakes the Cognito outputs into the static frontend build automatically.
See **`terraform/README.md`** and **`DEPLOY.md`** for details, and **`CHANGES.md`**
for the v0.1 → v0.2 changelog.

Tear everything down with `terraform destroy`.

---

## Project layout

```
src/
├── app.py              FastAPI routes + Lambda handler
├── handlers.py         all business logic (parse, categorize, summarize, chat)
├── config.py           frozen env-driven settings
├── categories.py       canonical category enum + VN aliases
├── statement_parser.py CSV / Excel parsing (header auto-detect)
├── dedup/              normalization + dedup service
├── cost_tracker.py     token → USD cost accounting
├── metrics.py          CloudWatch custom metrics
└── adapters/
    ├── ai.py           BedrockAI (hybrid) | LocalAI (keyword rules)
    ├── chatbot.py      ChatbotAI streaming money coach
    ├── pdf_extractor.py receipt/PDF vision extraction
    ├── storage.py      S3Storage | LocalStorage
    ├── userstore.py    sqlite/postgres/dynamodb/documentdb/mysql + jobs + chat memory
    └── factory.py      env → adapter selection
frontend/               React 19 + Vite + Tailwind v4 SPA
terraform/              ECS/ALB/CloudFront/Cognito/Route53 IaC
docs/diagrams/          architecture diagrams (Mermaid .mmd + infra PNG/PDF)
sample_data/            sample CSV / PDF / receipt images
scripts/                cost estimate, AI accuracy eval, seed/init DB, smoke
tests/                  pytest (local backends only)
```

---

## Sample data

```
sample_data/bank_statement_q2_2026.csv   full statement
sample_data/smoke_test_5_rows.csv        tiny smoke file
sample_data/bank_statement_sample.pdf    PDF statement
sample_data/sample_receipts/             transfer-screenshot images
```

CSV format — header row optional:

```
date,description,amount
2026-04-02,Highlands Coffee - Bui Vien,-65000
2026-04-04,Salary deposit credit,18500000
```

Negative = expense, positive = income.
