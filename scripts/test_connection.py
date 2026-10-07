"""Pre-flight check: can we reach MySQL, and can we reach Forsta?

    python scripts/test_connection.py

Run this first when something breaks — it tells you which of the two
integrations is at fault, and exactly which credential is missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import config          # noqa: E402
from app.core.database import healthcheck   # noqa: E402

TICK, CROSS = "✓", "✗"


def check_database() -> bool:
    print("\n── STG (DWH) MySQL ─────────────────────────────────────────")
    db = config.database("etl")
    print(f"  host     {db.host or '(not set)'}:{db.port}")
    print(f"  database {db.database or '(not set)'}")
    print(f"  user     {db.user or '(not set)'}")
    print(f"  ssl      {'required' if db.ssl_enabled else 'off'}")
    ok, msg = healthcheck("etl")
    print(f"  {TICK if ok else CROSS} {msg}")
    return ok


def check_forsta() -> bool:
    print("\n── Forsta Surveys (Decipher) API ───────────────────────────")
    fc = config.forsta
    print(f"  host        {fc.host}")
    print(f"  api key     {'set (' + str(len(fc.api_key)) + ' chars)' if fc.api_key else '(not set)'}")
    if not fc.is_configured:
        print(f"  {CROSS} not configured — see docs/04-it-requirements-checklist.md")
        return False
    if len(fc.api_key) != 64:
        print(f"  ! key is {len(fc.api_key)} characters; Forsta keys are 64")
    try:
        from etl.forsta_client import ForstaClient

        client = ForstaClient(fc.host, fc.api_key, fc.timeout)
        who = client.whoami()
        print(f"  {TICK} authenticated as {who.get('login', '?')}")
        print(f"  {TICK} {len(client.surveys())} surveys visible")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  {CROSS} {exc}")
        return False


def main() -> int:
    print("Consumer Insight Portal — connection check")
    db_ok = check_database()
    forsta_ok = check_forsta()
    print("\n────────────────────────────────────────────────────────────")
    if db_ok and forsta_ok:
        print("All good. `python -m etl.forsta_etl --due`")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
