#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════
# Run the portal locally with no database access at all.
#
# Builds a SQLite copy of the real MySQL schema (converted on the fly, see
# app/core/sqlite_compat.py), loads a wave from the Excel exports, and starts
# Streamlit. Useful off-VPN, on a plane, or for a first look before the STG
# credentials are sorted out.
#
#   bash scripts/run_local.sh
#   bash scripts/run_local.sh "/path/Raw Data.xlsx" "/path/Cross Tabs.xlsx"
# ══════════════════════════════════════════════════════════════════════════
set -euo pipefail
cd "$(dirname "$0")/.."

RAW="${1:-data/Raw Data 09_21_26.xlsx}"
XTAB="${2:-data/Cross Tabs 09_21_26.xlsx}"

if [ ! -d .venv ]; then python3 -m venv .venv; fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip && pip install -q -r requirements.txt

export APP_ENV=LOCAL
export LOCAL_SQLITE_PATH=data/csi_local.db
mkdir -p data
rm -f data/csi_local.db

echo "── creating the schema (MySQL DDL, converted to SQLite)"
python scripts/init_db.py

if [ -f "$RAW" ]; then
  echo "── loading $RAW"
  python -m etl.run_pipeline --source excel --raw "$RAW" \
      ${XTAB:+--crosstab "$XTAB"} --wave 2026-09 --family CSI-US
else
  echo "!! $RAW not found — put the two workbooks in ./data/ or pass their paths"
  exit 1
fi

echo
echo "── starting the portal on http://127.0.0.1:8501"
streamlit run app/main.py
