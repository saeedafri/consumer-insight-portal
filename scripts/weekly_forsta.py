"""The unattended weekly Forsta run: fetch → load → verify → harmonise → cube
→ re-check every publication. One log line per step; the exit code says what
happened, so a scheduler (cron, Azure WebJob) can alert on anything but 0.

    python scripts/weekly_forsta.py            # the wave is detected from the fielding dates

Exit codes: 0 loaded and verified · 1 the load failed or does not match its
payload · 2 Forsta rejected the key · 3 loaded, but a published number moved.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import config  # noqa: E402
from etl import run_pipeline  # noqa: E402
from etl.forsta_client import ForstaAuthError, ForstaClient  # noqa: E402

log = logging.getLogger("cip.weekly")


def run(client=None) -> int:
    from app.data import publications

    if client is None:
        fc = config.forsta
        if not fc.is_configured:
            log.error("Forsta is not configured (FORSTA_HOST, FORSTA_API_KEY, FORSTA_SURVEY_PATH)")
            return 2
        client = ForstaClient(fc.host, fc.api_key, fc.survey_path, fc.timeout, fc.max_retries)
    try:
        client.whoami()
    except ForstaAuthError as exc:
        log.error("Forsta rejected the key: %s", exc)
        return 2
    try:
        survey_id = run_pipeline.ingest_api("auto", client=client)
    except Exception as exc:                         # the load log keeps the detail
        log.error("Load failed: %s", exc)
        return 1
    log.info("Loaded and verified survey_id=%s", survey_id)
    drift = publications.drift_summary()
    moved = drift[(drift[["moved", "missing", "new", "error"]].sum(axis=1)) > 0] if not drift.empty else drift
    for row in moved.itertuples():
        log.warning("Publication %s v%s no longer reproduces: moved %d, missing %d, new %d",
                    row.pub_code, row.version, row.moved, row.missing, row.new)
    return 3 if len(moved) else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    sys.exit(run())
