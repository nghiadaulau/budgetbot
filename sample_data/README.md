# BudgetBot sample data

Synthetic Vietnamese transactions inspired by common bank statement
formats (Techcombank, Vietcombank, MB Bank). Merchant names are real
businesses; amounts and dates are randomized (seed=42 for reproducibility).

## Files

- `bank_statement_q2_2026.csv` — full quarter, ~80 transactions
- `smoke_test_5_rows.csv` — minimal for fast testing

## Schema

`date,description,amount`

Amounts are in VND. Negative = expense, positive = income/refund.

## Categories (matches LocalAI rule-based stub + Bedrock prompt)

Food, Transport, Shopping, Utilities, Entertainment, Health,
Subscriptions, Income, Transfer, Other.

## Why synthetic vs HuggingFace?

No high-quality public transaction-classification dataset exists on
HuggingFace in clean CSV form. We surveyed:

| Dataset | URL | Why not used |
|---------|-----|--------------|
| `tushar27/Indian-bank-statements` | huggingface.co/datasets/tushar27/Indian-bank-statements | Indian banks only — descriptions/merchants don't match Vietnamese patterns |
| `Iress/transactions-classification` | huggingface.co/datasets/Iress/transactions-classification | Tiny (~100 rows), English merchants only |
| `polinaeterna/aiq` | huggingface.co/datasets/polinaeterna/aiq | Wrong domain (general Q&A, not transactions) |
| LEDGAR / lex_glue | huggingface.co/datasets/coastalcph/lex_glue | Legal contracts, wrong domain |

→ We **synthesize** realistic Vietnamese transactions instead and document the provenance.

## Source / Citation

This is **synthetic data — NOT from HuggingFace**.

- **Merchant names:** Real Vietnamese businesses (Highlands Coffee, Grab, Shopee, Vincom, etc.) — public knowledge, no proprietary data
- **Bank statement format:** Inspired by common Vietnamese bank statement schemas (Techcombank, Vietcombank, MB Bank)
- **Amount + date generation:** Pseudo-random with seed=42 (deterministic — re-running `tooling/fetch_w7_datasets.py --app budgetbot` produces identical output)
- **License:** Public domain / CC0 — free to use, modify, redistribute. No attribution required (but appreciated).

## Attribution (optional)

If you redistribute these CSVs or derivative work:

> Synthetic Vietnamese transaction dataset for XBrain W7 Capstone Hackathon (TechX × AWS Accelerator Program, 2026). Generator: `tooling/fetch_w7_datasets.py`. CC0 / public domain.

## Re-generate

```bash
python3 tooling/fetch_w7_datasets.py --app budgetbot
```

To increase row count: `--n 200` (default 80). To change seed: edit `fetch_budgetbot()` in the fetcher script (currently `seed=42`).
