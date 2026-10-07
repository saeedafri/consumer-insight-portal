#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════
# Run the portal locally on a SQLite copy of the schema (converted on the fly,
# see app/core/sqlite_compat.py) — off-VPN, or for a first look.
#
#   bash scripts/run_local.sh                          # schema + portal
#   bash scripts/run_local.sh selfserve/58f/260907     # also load that wave from Forsta (GET only)
# ══════════════════════════════════════════════════════════════════════════
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then python3 -m venv .venv; fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip && pip install -q -r requirements.txt

export APP_ENV=LOCAL
export LOCAL_SQLITE_PATH=data/csi_local.db
mkdir -p data

echo "── creating / upgrading the schema (MySQL DDL, converted to SQLite)"
python scripts/init_db.py

if [ -n "${1:-}" ]; then
  echo "── loading $1 from Forsta"
  python -m etl.forsta_etl --survey "$1"
fi

PORT="${PORT:-8611}"                 # 8501/8503 belong to the Market Data Portal
echo
echo "── starting the portal on http://127.0.0.1:$PORT"
streamlit run app/main.py --server.port "$PORT"
