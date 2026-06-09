# BudgetBot — Infrastructure (Terraform)

Deploys BudgetBot to AWS:

```
                 budgetbot.xbrain26hackathon269.software            api.budgetbot.xbrain26hackathon269.software
                          │                                       │
                    ┌─────▼──────┐                          ┌─────▼─────┐
   Route53  ───────▶│ CloudFront │── OAC ──▶ S3 (React)     │    ALB    │ (HTTPS, ACM)
                    └────────────┘                          └─────┬─────┘
                                                                  │
                                                         ┌────────▼────────┐
                                                         │  ECS Fargate    │── Bedrock (Haiku)
                                                         │  (FastAPI)      │
                                                         └────────┬────────┘
                                                                  │ SQLite
                                                              ┌───▼───┐
                                                              │  EFS  │ (persistent)
                                                              └───────┘
```

- **Backend**: 1 Fargate task (FastAPI/uvicorn) behind an HTTPS ALB. SQLite lives
  on **EFS** so data survives restarts/redeploys. AI via **Bedrock** (task role).
- **Frontend**: React build on **S3 + CloudFront** (private bucket, OAC).
- **TLS**: ACM — regional cert for the ALB, us-east-1 cert for CloudFront, both
  DNS-validated in Route53.
- **State**: S3 with **native lockfile** (`use_lockfile`, no DynamoDB).
- Everything uses your local **`default`** AWS profile.

## Prerequisites
- Terraform **≥ 1.10**, AWS CLI, Docker, pnpm.
- The Route53 public hosted zone **`budgetbot.xbrain26hackathon269.software`** already exists.
- **Bedrock model access** enabled for Claude 3.5 Haiku in `ap-southeast-1`
  (Console → Bedrock → Model access). If it's only available via the APAC
  inference profile, set `ai_model_id = "apac.anthropic.claude-3-5-haiku-20241022-v1:0"`
  in `terraform.tfvars`.

## Deploy (first time)

```bash
cd terraform

# 1) Create the state bucket (one-time; backend can't self-bootstrap)
./bootstrap.sh

# 2) Provision all infrastructure
terraform init
terraform apply            # ~10-15 min (CloudFront + ACM validation)

# 3) Build & publish app code (backend image + frontend build)
./deploy.sh all
```

Then open **https://budgetbot.xbrain26hackathon269.software**. The API is at
**https://api.budgetbot.xbrain26hackathon269.software** (e.g. `/health`).

> First `apply` provisions empty ECR/S3, so the ECS task won't be healthy until
> `./deploy.sh` pushes the image. That's expected.

## Day-to-day
```bash
./deploy.sh backend     # rebuild + roll the API
./deploy.sh frontend    # rebuild + publish the UI (+ CloudFront invalidation)
terraform apply         # infra changes only
```

## Notes & trade-offs
- **Why Fargate + EFS, not Lambda/RDS?** Only the SQLite store implements the full
  v0.2 interface (filtered list, partial update, dedup, cost log, migrations).
  Fargate + EFS runs the current code unchanged with persistent data. To move to
  Lambda+DynamoDB or RDS later, implement those store methods first.
- **Single task / `desired_count = 1`** — SQLite is single-writer; don't scale the
  service horizontally without switching the DB backend.
- **Cost (rough, ap-southeast-1):** Fargate 0.5vCPU/1GB ~\$18/mo, ALB ~\$18/mo,
  EFS pennies, CloudFront/S3/Route53 negligible at demo traffic, Bedrock per-use.
  Run `python ../scripts/cost_estimate.py --transactions 1000` for AI cost.
- **Set `ai_backend=local` / `pdf_backend=local`** in `terraform.tfvars` to run
  without Bedrock (rule-based categorization, stub receipt extraction).
- **Teardown:** `./deploy.sh` artifacts aside, `terraform destroy` removes
  everything. The state bucket (created by `bootstrap.sh`) is not managed by
  Terraform — delete it manually if you want it gone.
```
terraform destroy
```
