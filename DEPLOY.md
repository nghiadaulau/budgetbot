# Deploying BudgetBot

The same `src.app:app` runs locally (uvicorn) and on AWS — pick a compute option,
flip env vars to the AWS adapters. No code changes.

## Env flip (local → AWS)

```diff
- AI_BACKEND=local
+ AI_BACKEND=bedrock
+ AI_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0

- PDF_BACKEND=local
+ PDF_BACKEND=bedrock          # also: pip install pymupdf  (PDF→image rasterisation)

- STORAGE_BACKEND=local
+ STORAGE_BACKEND=s3
+ STORAGE_BUCKET=budgetbot-statements-<acct>

- DB_BACKEND=sqlite
+ DB_BACKEND=postgres
+ USERSTORE_POSTGRES_URL=postgresql://user:pw@<rds-endpoint>:5432/budgetbot
+ CORS_ORIGINS=https://<your-frontend-domain>
```

Run `python scripts/migrate_add_dedup.py` once after pointing at a fresh DB.

## Option A — AWS Lambda + API Gateway (Mangum)

`src/app.py` exposes `handler` (Mangum). The `Dockerfile` targets the Lambda
Python 3.12 base image.

```bash
docker build -t budgetbot .
# push to ECR, create a Lambda from the image, set the handler to src.app.handler
```

- Front it with **API Gateway (HTTP API)**; the `strip_api_prefix` middleware
  makes the app work whether or not it's mounted under an `/api` stage.
- **Cognito JWT authorizer** → the app reads `sub` from the authorizer claims
  (falls back to the `X-User-Id` header for local dev).
- **PDF vision**: bundle `pymupdf` in the image and bump Lambda memory (≥512 MB)
  and timeout (≥30 s) — rasterisation + a vision call is heavier than CSV.

### Lambda + Postgres → use RDS Proxy
Each Lambda container opens its own `psycopg2` connection. Put **RDS Proxy** in
front of RDS to pool connections and survive scale-out; point
`USERSTORE_POSTGRES_URL` at the proxy endpoint.

## Option B — ECS Fargate / App Runner

Run the container with uvicorn (`CMD ["uvicorn","src.app:app","--host","0.0.0.0","--port","8000"]`
in a non-Lambda image). Long-lived process → a normal DB connection pool works,
no RDS Proxy required. App Runner is the simplest (give it the image + env vars).

## Cost

- `RDS db.t3.micro` (~$13/mo, single-AZ) is the biggest fixed cost — skip Multi-AZ
  for a demo.
- AI is variable and tiny: keyword fast-path resolves ~65% of rows offline; only
  ambiguous rows hit Bedrock Haiku. Estimate with
  `python scripts/cost_estimate.py --transactions 1000`.
