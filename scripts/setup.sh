#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════
# Consumer Insight Portal — one-shot setup against dwh_stg.
#
# Run this on your Mac (it needs network access to the Azure STG server,
# which the cloud session does not have).
#
#   cd ~/All-Code-Base/consumer-insight-portal
#   bash scripts/setup.sh
# ══════════════════════════════════════════════════════════════════════════
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "No .env found. Copy .env.example and fill it in."; exit 1
fi

if [ ! -d .venv ]; then
  echo "── creating virtualenv"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
echo "── installing dependencies"
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo
echo "── checking connections"
python scripts/test_connection.py || true

echo
echo "── creating the csi_ schema in dwh_stg"
python scripts/init_db.py

echo
echo "── loading the 09/21/26 wave from the Excel exports"
RAW="${1:-data/Raw Data 09_21_26.xlsx}"
XTAB="${2:-data/Cross Tabs 09_21_26.xlsx}"
if [ -f "$RAW" ]; then
  python -m etl.run_pipeline --source excel --raw "$RAW" \
      ${XTAB:+--crosstab "$XTAB"} --wave 2026-09 --family CSI-US
else
  echo "   skipped — put the two workbooks in ./data/ (or pass paths:"
  echo "   bash scripts/setup.sh '/path/Raw Data 09_21_26.xlsx' '/path/Cross Tabs 09_21_26.xlsx')"
fi

echo
echo "── done. Start the portal with:  streamlit run app/main.py"
