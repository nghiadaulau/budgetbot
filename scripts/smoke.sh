#!/usr/bin/env bash
# cURL smoke test for all BudgetBot endpoints. Requires a running server:
#   make run   (or: uvicorn src.app:app --port 8000)
#
# Usage:  bash scripts/smoke.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://localhost:8000}"
U="smoke-user"
H="X-User-Id: $U"
CSV="sample_data/sample_statement.csv"
PDF="sample_data/sample_receipts/highlands.pdf"

say() { printf "\n\033[1m== %s ==\033[0m\n" "$1"; }

say "health";            curl -s "$BASE/health" | head -c 400; echo
say "clear (reset)";     curl -s -X DELETE "$BASE/transactions" -H "$H"; echo
say "upload CSV";        curl -s -X POST "$BASE/upload" -H "$H" -F "file=@$CSV" | head -c 400; echo
say "upload CSV again (expect 409)"; curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST "$BASE/upload" -H "$H" -F "file=@$CSV"
say "list (page 1)";     curl -s "$BASE/transactions?page=1&page_size=5" -H "$H" | head -c 300; echo
say "summary";           curl -s "$BASE/summary?month=2026-06" -H "$H" | head -c 400; echo
say "manual add";        curl -s -X POST "$BASE/transaction?confirm=true" -H "$H" -H "Content-Type: application/json" \
                           -d '{"date":"2026-06-15","description":"Pho Le","amount":-75000,"source":"manual"}' | head -c 300; echo
say "idempotent replay (same key → no double-write)";
IDEM="smoke-idem-$$"
BODY='{"date":"2026-06-16","description":"Idem Coffee","amount":-42000,"source":"manual"}'
curl -s -X POST "$BASE/transaction?confirm=true" -H "$H" -H "Idempotency-Key: $IDEM" -H "Content-Type: application/json" -d "$BODY" >/dev/null
curl -s -X POST "$BASE/transaction?confirm=true" -H "$H" -H "Idempotency-Key: $IDEM" -H "Content-Type: application/json" -d "$BODY" | head -c 200; echo
say "classification audit";
TXN=$(curl -s "$BASE/transactions?page=1&page_size=1" -H "$H" | sed -n 's/.*"id"[: ]*"\([0-9]*\)".*/\1/p' | head -1)
curl -s "$BASE/transaction/$TXN/audit" -H "$H" | head -c 300; echo
say "upload PDF";        curl -s -X POST "$BASE/upload-pdf" -H "$H" -F "file=@$PDF" | head -c 400; echo
say "cost report";       curl -s "$BASE/admin/cost-report?month=2026-06" -H "$H" | head -c 300; echo
say "missing header (expect 401)"; curl -s -o /dev/null -w "HTTP %{http_code}\n" "$BASE/transactions"

echo; echo "Smoke test complete."
