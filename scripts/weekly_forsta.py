"""The unattended Forsta run: discover every survey → load each closed,
readable, unloaded one (verify → harmonise → cube → search) → re-check every
publication. One log line per step; the exit code says what happened, so a
scheduler (cron, Azure WebJob) can alert on anything but 0.

    python scripts/weekly_forsta.py            # daily 06:00 IST and Tuesday 06:00 IST

Exit codes: 0 everything due loaded and verified · 1 a wave failed to load or
verify · 2 Forsta rejected the key or the schema is behind the code · 3 loaded, but a published number moved.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect  # noqa: E402

from app.core.config import config  # noqa: E402
from app.core.database import get_engine  # noqa: E402
from etl import forsta_etl  # noqa: E402
from etl.forsta_client import ForstaAuthError, ForstaClient  # noqa: E402

log = logging.getLogger("cip.weekly")


def run(client=None) -> int:
    from app.data import publications

    if client is None:
        fc = config.forsta
        if not fc.is_configured:
            log.error("Forsta is not configured (FORSTA_HOST, FORSTA_API_KEY)")
            return 2
        client = ForstaClient(fc.host, fc.api_key, fc.timeout, fc.max_retries)
    try:
        client.whoami()
    except ForstaAuthError as exc:
        log.error("Forsta rejected the key: %s", exc)
        return 2
    missing = {"cip_forsta_survey", "cip_search", "cip_tracker_line"} - set(inspect(get_engine("etl")).get_table_names())
    if missing:                                        # never load into a schema older than the code
        log.error("Schema is behind the code (missing %s): run scripts/init_db.py first", sorted(missing))
        return 2
    log.info("Register: %s", forsta_etl.discover(client))
    result = forsta_etl.run_due(client)               # the register and the load log keep the detail
    log.info("Loaded %d: %s", len(result["loaded"]), result["loaded"])
    if result["failed"]:
        log.error("Failed %d: %s", len(result["failed"]), result["failed"])
        return 1
    drift = publications.drift_summary()
    moved = drift[(drift[["moved", "missing", "new", "error"]].sum(axis=1)) > 0] if not drift.empty else drift
    for row in moved.itertuples():
        log.warning("Publication %s v%s no longer reproduces: moved %d, missing %d, new %d",
                    row.pub_code, row.version, row.moved, row.missing, row.new)
    return 3 if len(moved) else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    sys.exit(run())
