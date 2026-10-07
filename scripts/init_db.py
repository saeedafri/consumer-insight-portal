"""Create or upgrade the CSI schema in the STG (DWH) database.

    python scripts/init_db.py            # upgrade in place, then apply schema + views + seed
    python scripts/init_db.py --dry-run  # print what would run
    python scripts/init_db.py --force    # run even though cip_load_log shows a running load
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import schema_upgrade              # noqa: E402
from app.core.config import config               # noqa: E402
from app.core.database import get_engine, healthcheck  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="ignore a cip_load_log row stuck in 'running'")
    args = ap.parse_args()

    print(f"Environment: {config.environment.value}")
    ok, msg = healthcheck("etl")
    print(f"Database:    {msg}")
    if not ok:
        print("\nCannot connect. Fill in STG_DB_* in .env — see .env.example.")
        return 1

    try:
        ran = schema_upgrade.install(get_engine("etl"), dry_run=args.dry_run, force=args.force)
    except RuntimeError as exc:
        print(f"\nRefused: {exc}")
        return 2
    for statement in ran:
        print(("[dry-run] " if args.dry_run else "applied   ") + statement)
    print("\nDone. 004_grants.sql is intentionally NOT applied — hand it to the DBA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
