"""Create the CSI schema in the STG (DWH) database.

    python scripts/init_db.py            # apply schema + views + seed
    python scripts/init_db.py --dry-run  # print what would run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import config          # noqa: E402
from app.core.database import healthcheck, run_sql_file  # noqa: E402

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
ORDER = ["001_schema.sql", "002_views.sql", "003_seed_topics.sql"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(f"Environment: {config.environment.value}")
    ok, msg = healthcheck("etl")
    print(f"Database:    {msg}")
    if not ok:
        print("\nCannot connect. Fill in STG_DB_* in .env — see .env.example.")
        return 1

    for name in ORDER:
        path = SQL_DIR / name
        if args.dry_run:
            print(f"[dry-run] would apply {name} ({path.stat().st_size} bytes)")
            continue
        print(f"Applying {name} ...")
        run_sql_file(str(path), role="etl")
    print("\nDone. 004_grants.sql is intentionally NOT applied — hand it to the DBA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
