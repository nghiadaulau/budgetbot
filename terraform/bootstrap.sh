#!/usr/bin/env bash
# One-time: create the S3 bucket that holds Terraform remote state.
# Must run BEFORE `terraform init` (the backend block references this bucket).
# State locking uses S3's native lockfile (use_lockfile) — no DynamoDB needed.
set -euo pipefail

PROFILE="${AWS_PROFILE:-default}"
REGION="${AWS_REGION:-ap-southeast-1}"
BUCKET="${TF_STATE_BUCKET:-budgetbot-tfstate-xbrain26hackathon269}"  # must match versions.tf

echo "Creating state bucket s3://$BUCKET ($REGION, profile=$PROFILE)…"

if aws s3api head-bucket --bucket "$BUCKET" --profile "$PROFILE" 2>/dev/null; then
  echo "Bucket already exists — nothing to do."
else
  aws s3api create-bucket \
    --bucket "$BUCKET" \
    --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION" \
    --profile "$PROFILE"
  aws s3api put-bucket-versioning \
    --bucket "$BUCKET" \
    --versioning-configuration Status=Enabled \
    --profile "$PROFILE"
  aws s3api put-public-access-block \
    --bucket "$BUCKET" \
    --public-access-block-configuration \
      BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true \
    --profile "$PROFILE"
  echo "Done. Now run: terraform init"
fi
