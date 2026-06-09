#!/usr/bin/env bash
# Build & push the backend image, roll the ECS service, build & publish the
# frontend. Run AFTER `terraform apply` (it reads Terraform outputs).
#
# Usage:  ./deploy.sh [backend|frontend|all]   (default: all)
set -euo pipefail

cd "$(dirname "$0")"
TARGET="${1:-all}"
PROFILE="${AWS_PROFILE:-default}"
export AWS_PROFILE="$PROFILE"

ECR=$(terraform output -raw ecr_repository_url)
# ECR URL: <account>.dkr.ecr.<region>.amazonaws.com/<repo>
REGION=$(echo "$ECR" | sed -E 's#^[0-9]+\.dkr\.ecr\.([^.]+)\..*#\1#')
CLUSTER=$(terraform output -raw ecs_cluster)
SERVICE=$(terraform output -raw ecs_service)
WORKER_SERVICE=$(terraform output -raw ecs_worker_service)
API_URL=$(terraform output -raw api_url)
APP_URL=$(terraform output -raw app_url)
BUCKET=$(terraform output -raw frontend_bucket)
DIST=$(terraform output -raw cloudfront_distribution_id)
ACCOUNT=$(echo "$ECR" | cut -d. -f1)
COGNITO_POOL=$(terraform output -raw cognito_user_pool_id)
COGNITO_CLIENT=$(terraform output -raw cognito_client_id)
COGNITO_REGION=$(terraform output -raw cognito_region)
ROOT="$(cd .. && pwd)"

deploy_backend() {
  echo "▸ Backend → $ECR:latest ($REGION)"
  aws ecr get-login-password --region "$REGION" \
    | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
  docker build --platform linux/amd64 -f "$ROOT/Dockerfile.web" -t "$ECR:latest" "$ROOT"
  docker push "$ECR:latest"
  echo "▸ Rolling ECS services (api + worker)…"
  aws ecs update-service --cluster "$CLUSTER" --service "$SERVICE" \
    --force-new-deployment --region "$REGION" >/dev/null
  aws ecs update-service --cluster "$CLUSTER" --service "$WORKER_SERVICE" \
    --force-new-deployment --region "$REGION" >/dev/null
  echo "  ECS deployment triggered (api + worker)."
}

deploy_frontend() {
  echo "▸ Frontend → s3://$BUCKET  (API=$API_URL, Cognito=$COGNITO_POOL)"
  pushd "$ROOT/frontend" >/dev/null
  # Cognito ids are baked into the static build so the SPA can talk to Cognito directly.
  export VITE_API_URL="$API_URL" VITE_USE_MOCK="false" \
    VITE_COGNITO_USER_POOL_ID="$COGNITO_POOL" \
    VITE_COGNITO_CLIENT_ID="$COGNITO_CLIENT" \
    VITE_COGNITO_REGION="$COGNITO_REGION"
  pnpm install --frozen-lockfile
  pnpm build
  # Hashed assets (immutable) get a long cache; the SPA shell must NOT be cached
  # or browsers keep serving an old index.html that points at stale JS bundles.
  aws s3 sync dist "s3://$BUCKET" --delete --region "$REGION" \
    --exclude "index.html" --cache-control "public, max-age=31536000, immutable"
  aws s3 cp dist/index.html "s3://$BUCKET/index.html" --region "$REGION" \
    --cache-control "no-cache, must-revalidate" --content-type "text/html; charset=utf-8"
  aws cloudfront create-invalidation --distribution-id "$DIST" --paths "/*" >/dev/null
  popd >/dev/null
  echo "  Frontend published → $APP_URL"
}

case "$TARGET" in
  backend) deploy_backend ;;
  frontend) deploy_frontend ;;
  all) deploy_backend; deploy_frontend ;;
  *) echo "usage: ./deploy.sh [backend|frontend|all]"; exit 1 ;;
esac

echo "Done."
