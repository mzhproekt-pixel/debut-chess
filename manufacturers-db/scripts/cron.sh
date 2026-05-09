#!/usr/bin/env bash
# Daily ingestion cron template.
# Place under crontab(5):  0 3 * * *  /path/to/manufacturers-db/scripts/cron.sh
set -euo pipefail

cd "$(dirname "$0")/.."
source .venv/bin/activate

LOG_DIR=./logs
mkdir -p "$LOG_DIR"
STAMP=$(date +%Y-%m-%d)

{
  echo "=== $(date -Is) — daily ingestion start ==="
  python -m src ingest gleif
  python -m src normalize gleif
  python -m src ingest sec
  python -m src normalize sec
  YEAR=$(date +%Y)
  python -m src trade --years $((YEAR - 2)) --years $((YEAR - 1)) --years "$YEAR"
  python -m src export manufacturers_basic
  python -m src export manufacturers_with_contacts
  python -m src export manufacturers_with_financials
  python -m src export trade_flows_by_hs
  echo "=== $(date -Is) — done ==="
} 2>&1 | tee -a "$LOG_DIR/cron-$STAMP.log"
