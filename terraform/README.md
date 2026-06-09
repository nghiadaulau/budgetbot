# BudgetBot — Infrastructure (Terraform)

Provisions the full BudgetBot stack on AWS. The same container image runs the API
and the async worker; everything is private-by-default behind WAF + ALB / CloudFront.

```
        app (apex)                                   api.
  budgetbot.xbrain26hackathon269.software   api.budgetbot.xbrain26hackathon269.software
            │                                             │
       ┌─────▼──────┐  WAF                          ┌──────▼──────┐  WAF
       │ CloudFront │── OAC ──▶ S3 (React SPA)      │     ALB     │ (HTTPS, ACM)
       └────────────┘                               └──────┬──────┘
                                                           │  (private subnets)
                                              ┌────────────▼─────────────┐
                                              │   ECS Fargate — API       │──┐
                                              │   (FastAPI, autoscaled)   │  │
                                              └────────────┬─────────────┘  │  VPC endpoints
                                                           │                │  (PrivateLink):
   ┌────────────────┐   SQS   ┌──────────────────────┐    │                ├─▶ Bedrock (Haiku 4.5)
   │ ECS Fargate —   │◀────────│  SQS jobs (+ DLQ)    │◀───┘                ├─▶ Textract
   │ worker          │         └──────────────────────┘                     ├─▶ ECR / Secrets / Logs
   └───────┬─────────┘                                                      └─▶ SQS / STS / S3 (gw)
           │
   ┌───────▼────────┐   ┌───────────────────┐   ┌──────────────┐   ┌──────────────┐
   │ RDS PostgreSQL │   │ ElastiCache Valkey │   │ S3 (uploads) │   │ Cognito      │
   │ (transactions) │   │ (rate limiting)    │   │ raw files    │   │ (JWT auth)   │
   └────────────────┘   └───────────────────┘   └──────────────┘   └──────────────┘

   Observability: CloudWatch logs + custom metrics → 8 alarms → SNS (email).
```

See the rendered diagrams in [`../docs/diagrams/`](../docs/diagrams/)
(infra PNG/PDF + Mermaid sources).

## Components

- **Frontend** — React build on **S3 + CloudFront** (private bucket, OAC), fronted by
  a **WAFv2** web ACL. `index.html` is served `no-cache`; hashed assets are immutable.
- **API** — **ECS Fargate** service (FastAPI/uvicorn) behind an HTTPS **ALB** (+ its own
  WAFv2 ACL). Runs in **private subnets**; reaches AWS APIs through **VPC endpoints**
  (PrivateLink) — no NAT egress for AWS traffic.
- **Worker** — a second ECS Fargate service that polls **SQS** for async uploads
  (`/enqueue`), with a **dead-letter queue** for poison messages.
- **Database** — **RDS PostgreSQL**; credentials live in **Secrets Manager** and are
  injected into the task via `DB_SECRET_NAME` (no plaintext in env/state).
- **Rate limiting** — **ElastiCache (Valkey)** replication group; the app fails open
  if the cache is unreachable.
- **AI / OCR** — **Bedrock** (Claude Haiku 4.5) for categorization + chat, **Textract**
  for PDF/image receipts — both reached over interface endpoints.
- **Auth** — **Cognito User Pool**; the API verifies the JWT `sub` server-side
  (`REQUIRE_AUTH`).
- **Scaling** — **Application Auto Scaling** (CPU target tracking) on both ECS services,
  within `[backend_min, backend_max]`.
- **Observability** — CloudWatch logs + custom metrics, **8 metric alarms** → **SNS**
  (set `alarm_email` to subscribe).
- **TLS** — ACM: a regional cert for the ALB, a us-east-1 cert for CloudFront, both
  DNS-validated in Route53.
- **State** — S3 backend with **native lockfile** (`use_lockfile`, no DynamoDB).
- Everything uses your local **`default`** AWS profile.

## Prerequisites

- Terraform **≥ 1.10**, AWS CLI, Docker, pnpm.
- A Route53 public hosted zone **`budgetbot.xbrain26hackathon269.software`** already
  exists (the apex serves the app; `api.` serves the API). Override via
  `domain_root` / `app_subdomain` / `api_subdomain` in `terraform.tfvars`.
- **Bedrock model access** enabled for the configured `ai_model_id` in the target
  region (Console → Bedrock → Model access). To run without Bedrock, set
  `ai_backend = "local"` / `pdf_backend = "local"`.

## Deploy (first time)

```bash
cd terraform

# 1) Create the S3 state bucket (one-time; the backend can't self-bootstrap)
./bootstrap.sh

# 2) Provision all infrastructure
terraform init
terraform apply            # ~15-20 min (CloudFront + ACM validation, RDS)

# 3) Build & publish app code (backend image + worker + frontend build)
./deploy.sh all
```

Then open **https://budgetbot.xbrain26hackathon269.software**. The API is at
**https://api.budgetbot.xbrain26hackathon269.software** (e.g. `/health`).

> First `apply` provisions an empty ECR + S3, so the ECS tasks won't be healthy
> until `./deploy.sh` pushes the image and publishes the frontend. That's expected.

## Day-to-day

```bash
./deploy.sh backend     # rebuild image + roll the API and worker services
./deploy.sh frontend    # rebuild + publish the UI (+ CloudFront invalidation)
terraform apply         # infra changes only
```

## Notes & trade-offs

- **Postgres, not SQLite/EFS.** The store backend is RDS PostgreSQL, so the API can
  scale horizontally — autoscaling runs `desired_count` ≥ 1 tasks behind the ALB.
  The local/dev default is still SQLite (`USERSTORE_BACKEND=sqlite`); the backend is
  runtime-agnostic and flips by env var.
- **Private egress.** Interface endpoints (Bedrock, Textract, ECR, Secrets Manager,
  CloudWatch Logs, SQS, STS) + an S3 gateway endpoint keep AWS traffic off the public
  internet and avoid NAT costs.
- **Async pipeline.** Large uploads go `/enqueue → S3 + SQS → worker → /job-status`;
  the worker is idempotent so redeliveries are safe, and failures land in the DLQ.
- **Cost (rough, ap-southeast-1):** Fargate (API + worker), ALB, RDS `db.t3.micro`,
  one-node Valkey, CloudFront/S3/Route53, WAF, and VPC interface endpoints (hourly
  each) — on the order of **\$0.20–0.30/hour** at idle demo scale, plus Bedrock
  per-use. Run `python ../scripts/cost_estimate.py --transactions 1000` for AI cost.
- **Teardown:** `terraform destroy` removes the managed stack. The state bucket
  (created by `bootstrap.sh`) is **not** managed by Terraform — delete it manually if
  you want it gone. Empty the S3 buckets first if a bucket isn't force-destroyable.

```bash
terraform destroy
```
