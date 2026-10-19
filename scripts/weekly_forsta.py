"""The unattended Forsta run: discover every survey → load each closed,
readable, unloaded one (verify → harmonise → cube → search) → re-check every
publication. One log line per step; the exit code says what happened, so a
scheduler (cron, Azure WebJob) can alert on anything but 0.

    python scripts/weekly_forsta.py            # launchd: daily 09:00 IST; every 30 min Mon 20:00 – Wed 23:30 IST

Exit codes: 0 everything due loaded and verified · 1 a wave failed to load or
verify · 2 Forsta rejected the key or the schema is behind the code · 3 loaded, but a published number moved ·
4 the database stayed unreachable (4 tries, 5 minutes apart) · 5 the integrity check found something it
could not heal (etl/integrity.py).

Every warning and error also goes to logs/forsta-etl-errors.jsonl, one JSON object per line (run, step,
error type, traceback); secrets from the environment are masked in both logs.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect  # noqa: E402

from app.core.config import config  # noqa: E402
from app.core.database import get_engine, healthcheck  # noqa: E402
from etl import forsta_etl, integrity, notify  # noqa: E402
from etl.forsta_client import ForstaAuthError, ForstaClient  # noqa: E402

log = logging.getLogger("cip.weekly")
ERRORS = Path(__file__).resolve().parents[1] / "logs" / "forsta-etl-errors.jsonl"
RUN = datetime.now().strftime("%Y%m%d-%H%M%S")
DB_ATTEMPTS, DB_PAUSE_SECONDS = 4, 300     # a VPN or network blip gets 15 minutes before the run gives up


def tell(action, *args) -> None:
    """Notifying never decides the exit code: a broken mail server must not fail a load."""
    try:
        action(*args)
    except Exception:
        log.exception("Notification failed")


def run(client=None) -> int:
    from app.data import publications

    if client is None:
        fc = config.forsta
        if not fc.is_configured:
            log.error("Forsta is not configured (FORSTA_HOST, FORSTA_API_KEY)")
            tell(notify.failure, "Forsta is not configured", "FORSTA_HOST or FORSTA_API_KEY is missing.")
            return 2
        client = ForstaClient(fc.host, fc.api_key, fc.timeout, fc.max_retries)
    for attempt in range(1, DB_ATTEMPTS + 1):
        ok, status = healthcheck("etl")
        if ok:
            break
        log.warning("Database not reachable (attempt %d of %d): %s", attempt, DB_ATTEMPTS, status)
        if attempt < DB_ATTEMPTS:
            time.sleep(DB_PAUSE_SECONDS)
    else:
        log.error("Database unreachable; nothing loaded — the next scheduled run tries again")
        tell(notify.failure, "database unreachable", f"{DB_ATTEMPTS} tries, {DB_PAUSE_SECONDS} s apart: {status}")
        return 4
    try:
        client.whoami()
    except ForstaAuthError as exc:
        log.error("Forsta rejected the key: %s", exc)
        tell(notify.failure, "Forsta rejected the API key", str(exc))
        return 2
    missing = {"cip_forsta_survey", "cip_search", "cip_tracker_line"} - set(inspect(get_engine("etl")).get_table_names())
    if missing:                                        # never load into a schema older than the code
        log.error("Schema is behind the code (missing %s): run scripts/init_db.py first", sorted(missing))
        tell(notify.failure, "schema is behind the code", f"Missing tables: {sorted(missing)}. Run scripts/init_db.py.")
        return 2
    log.info("Register: %s", forsta_etl.discover(client))
    result = forsta_etl.run_due(client)               # the register and the load log keep the detail
    log.info("Loaded %d: %s", len(result["loaded"]), result["loaded"])
    for path in result["loaded"]:
        tell(notify.survey_loaded, forsta_etl.survey_id_of(path))
    for path in result["failed"]:
        tell(notify.failure, f"survey {path} did not load", forsta_etl.last_error_of(path))
    if not result["loaded"] and not result["failed"]:
        tell(notify.idle_run)
    broken = integrity.run()                        # heals derived rows; reports the rest
    if broken:
        tell(notify.failure, "integrity check", "\n".join(broken))
    if result["failed"]:
        log.error("Failed %d: %s", len(result["failed"]), result["failed"])
        return 1
    drift = publications.drift_summary()
    moved = drift[(drift[["moved", "missing", "new", "error"]].sum(axis=1)) > 0] if not drift.empty else drift
    for row in moved.itertuples():
        log.warning("Publication %s v%s no longer reproduces: moved %d, missing %d, new %d",
                    row.pub_code, row.version, row.moved, row.missing, row.new)
    if len(moved):
        tell(notify.failure, "published numbers moved", moved.to_string(index=False))
    return 3 if len(moved) else 5 if broken else 0


class Masked(logging.Formatter):
    """Masks every secret-looking value from the environment (keys, passwords, tokens, webhooks)."""
    secrets = sorted((v for k, v in os.environ.items() if len(v) >= 8 and any(
        word in k for word in ("KEY", "PASSWORD", "SECRET", "TOKEN", "PASSPHRASE", "WEBHOOK"))), key=len, reverse=True)

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        for secret in self.secrets:
            line = line.replace(secret, "***")
        return line


class JsonLines(Masked):
    def format(self, record: logging.LogRecord) -> str:
        entry = {"at": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "run": RUN, "level": record.levelname,
                 "step": record.name, "message": record.getMessage()}
        if record.exc_info:
            entry["error"] = record.exc_info[0].__name__
            entry["trace"] = self.formatException(record.exc_info)
        record = logging.makeLogRecord({"msg": json.dumps(entry, ensure_ascii=False, default=str)})
        return super().format(record)


def setup_logging() -> None:
    screen = logging.StreamHandler()
    screen.setFormatter(Masked("%(asctime)s %(levelname)-7s %(name)s | %(message)s"))
    ERRORS.parent.mkdir(exist_ok=True)
    errors = logging.FileHandler(ERRORS, encoding="utf-8")
    errors.setLevel(logging.WARNING)
    errors.setFormatter(JsonLines("%(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[screen, errors], force=True)   # app.core sets one up on import
    # app.data's @st.cache_data warns once per function outside Streamlit: ~40 lines of noise per run
    from streamlit import logger as streamlit_logger
    streamlit_logger.set_log_level("ERROR")


if __name__ == "__main__":
    setup_logging()
    sys.exit(run())
