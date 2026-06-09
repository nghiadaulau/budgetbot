#!/usr/bin/env python3
"""Estimate monthly AWS cost for a given transaction volume.

Bedrock token cost comes from the same constants the app bills against
(config.bedrock_*). RDS/S3/Lambda are rough Singapore on-demand list prices —
adjust for your account. Illustrative, not a quote.

Usage:  python scripts/cost_estimate.py --transactions 1000 [--region ap-southeast-1]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import config

TOKENS_IN_PER_TXN = 90
TOKENS_OUT_PER_TXN = 20
BEDROCK_HIT_RATE = 0.35

RDS_T3_MICRO_MONTH = 13.0
S3_BASE_MONTH = 0.50
LAMBDA_FREE_TIER_NOTE = "within free tier at this volume"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--transactions", type=int, default=1000)
    p.add_argument("--region", default=config.aws_region)
    args = p.parse_args()

    n = args.transactions
    billed = n * BEDROCK_HIT_RATE
    in_tok = billed * TOKENS_IN_PER_TXN
    out_tok = billed * TOKENS_OUT_PER_TXN
    bedrock = (in_tok / 1e6 * config.bedrock_input_cost_per_1m
               + out_tok / 1e6 * config.bedrock_output_cost_per_1m)

    rows = [
        ("Bedrock (Haiku, classify)", f"${bedrock:.4f}"),
        ("  · billed calls", f"{billed:,.0f} of {n:,} (keyword hit-rate {1-BEDROCK_HIT_RATE:.0%})"),
        ("  · tokens in/out", f"{in_tok:,.0f} / {out_tok:,.0f}"),
        ("RDS db.t3.micro (Postgres)", f"${RDS_T3_MICRO_MONTH:.2f}/mo"),
        ("S3 (raw uploads)", f"${S3_BASE_MONTH:.2f}/mo"),
        ("Lambda", LAMBDA_FREE_TIER_NOTE),
    ]
    width = max(len(r[0]) for r in rows)
    print(f"\nBudgetBot cost estimate — {n:,} transactions/month · {args.region}\n")
    for label, val in rows:
        print(f"  {label.ljust(width)}  {val}")
    print(f"\n  Variable AI cost: ${bedrock:.4f}/mo  (~${bedrock / max(n,1) * 1000:.4f} per 1k txns)")
    print(f"  + fixed infra:    ${RDS_T3_MICRO_MONTH + S3_BASE_MONTH:.2f}/mo\n")


if __name__ == "__main__":
    main()
