"""The unattended Forsta run: discover every survey → load each closed,
readable, unloaded one (verify → harmonise → cube → search) → re-check every
publication. One log line per step; the exit code says what happened, so a
scheduler (cron, Azure WebJob) can alert on anything but 0.

    python scripts/weekly_forsta.py            # launchd: 17:30 IST on each planned Monday, plus Fri 09:00 IST

On a planned Monday (config/launch_schedule.yml, the data team's plan) the run posts a Teams heads-up, then
watches: a run every 30 minutes until the week's wave is loaded and Forsta has closed it, or WATCH_HOURS pass.
A wave loads once its quota is reached or FIELD_HOURS after launch (etl/forsta_etl.fielded), and reloads when
Forsta closes it. Any other day it is one run. A run that finds nothing new costs one Forsta call and two small
queries; integrity and publication drift run after a load and on Friday.

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
import signal
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text  # noqa: E402

from app.core.config import config  # noqa: E402
from app.core.database import get_engine, healthcheck  # noqa: E402
from api import dashboards, team  # noqa: E402
from etl import forsta_etl, integrity, launch_schedule, notify, open_ends, publish  # noqa: E402
from etl.forsta_client import ForstaAuthError, ForstaClient  # noqa: E402
from etl.loaders import Locked, etl_lock  # noqa: E402

log = logging.getLogger("cip.weekly")
ERRORS = Path(__file__).resolve().parents[1] / "logs" / "forsta-etl-errors.jsonl"
HEARTBEAT = ERRORS.with_name("etl-heartbeat.json")   # read by --watchdog, which runs hourly on its own
RUN = datetime.now().strftime("%Y%m%d-%H%M%S")
DB_ATTEMPTS, DB_PAUSE_SECONDS = 4, 300     # a VPN or network blip gets 15 minutes before the run gives up
WATCH_EVERY_SECONDS, WATCH_HOURS = 30 * 60, 54   # Mon 17:30 → Wed 23:30 IST; 64 of 68 waves closed within 54 h
FULL_CHECK_DAY = 4                          # Friday: the one idle run a week that still runs integrity and drift
RUN_HOURS = 3                               # longest a run may take before the watchdog calls it stuck
LATE_MINUTES = 60                           # slack past the promised next beat


def beat(state: str, next_in_hours: float, **extra) -> None:
    """Promise the watchdog the next sign of life. A killed run cannot warn, so its silence has to."""
    try:
        HEARTBEAT.write_text(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), "run": RUN, "pid": os.getpid(),
                                         "state": state, "next": datetime.fromtimestamp(time.time() + next_in_hours * 3600)
                                         .isoformat(timespec="seconds"), **extra}))
    except OSError:
        log.exception("Heartbeat not written")


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
    for path in result["failed"]:
        tell(notify.failure, f"survey {path} did not load", forsta_etl.last_error_of(path))
    if not result["loaded"] and not result["failed"]:
        tell(notify.idle_run)
        if datetime.now().weekday() != FULL_CHECK_DAY:   # nothing changed: the derived rows and published
            return 0                                     # numbers are as the last full check left them
    broken = integrity.run()                        # heals derived rows; reports the rest
    for path in result["loaded"]:                   # verify counted the answers; this compares their values (one GET)
        try:
            checked, problems = forsta_etl.reconcile_survey(forsta_etl.survey_id_of(path), client)
        except Exception as exc:
            checked, problems = 0, [f"{type(exc).__name__}: {str(exc)[:200]}"]
        if problems or checked == 0:
            broken.append(f"survey {path}: {len(problems)} of {checked} answers differ from Forsta {problems[:3]}"
                          if checked else f"survey {path}: no answer could be compared with Forsta")
    if result["loaded"]:                            # the topic dashboards (config/dashboards.yml) of the new waves
        try:
            dashboards.build_for([forsta_etl.survey_id_of(path) for path in result["loaded"]])
        except Exception as exc:                    # last week's dashboards stay live; say so
            tell(notify.failure, "building the topic dashboards", str(exc))
        try:                                        # the team's metric alerts (api/team.py), judged once per new wave
            for message, email in team.due_alerts([forsta_etl.survey_id_of(path) for path in result["loaded"]]):
                tell(notify.teams, message)
                if email:                           # and the person who set it, by email
                    tell(notify.send, f"CIP alert: {message[2:80]}", message, [email])
        except Exception as exc:
            tell(notify.failure, "checking the metric alerts", str(exc))
        for path in result["loaded"]:               # open-ended answers coded into themes, charted with the rest
            try:
                open_ends.code_wave(forsta_etl.survey_id_of(path))
            except Exception as exc:
                tell(notify.failure, f"coding the open-ended answers of {path}", str(exc))
    # the standard screens as prebuilt files; after a failed reload too, which took that wave's serving rows away
    if result["loaded"] or result["failed"] or not (publish.ROOT / "current").exists():
        try:
            publish.publish()
        except Exception as exc:                    # the previous version stays live; say so
            tell(notify.failure, "publishing the portal files", str(exc))
    for path in result["loaded"]:                   # the team's email last: its dashboards and screens are live by now
        tell(notify.survey_loaded, forsta_etl.survey_id_of(path))
    if broken:   # the count in the subject: a different problem is told at once, not after the 6-hour repeat window
        tell(notify.failure, f"integrity check: {len(broken)} problem{'s' if len(broken) > 1 else ''}", "\n".join(broken))
    if result["failed"]:
        log.error("Failed %d: %s", len(result["failed"]), result["failed"])
        return 1
    drift = publications.drift_summary()
    moved = drift[(drift[["moved", "missing", "new", "error"]].sum(axis=1)) > 0] if not drift.empty else drift
    for row in moved.itertuples():
        log.warning("Publication %s v%s no longer reproduces: moved %d, missing %d, new %d",
                    row.pub_code, row.version, row.moved, row.missing, row.new)
    if len(moved):
        tell(notify.failure, f"published numbers moved in {len(moved)} publication{'s' if len(moved) > 1 else ''}",
             moved.to_string(index=False))
    return 3 if len(moved) else 5 if broken else 0


def watch(week: dict, lock=None) -> int:
    """A planned Monday: say what launches, then run every WATCH_EVERY_SECONDS until the wave is in. A cycle that
    crashes (Forsta down past its retries, the database dropping mid-run) is logged and told, and the watch goes on:
    otherwise the week's wave would wait for Friday. Each cycle pings the run lock's connection to keep it."""
    topics = f" with {', '.join(week['topics'])}" if week["topics"] else ""
    name = " + ".join(week["names"])
    tell(notify.teams, f"🗓️ Forsta launches {name}{topics} today ~18:00 IST (cycle {week['cycle']}). CIP checks every "
                       f"30 min and loads it at {launch_schedule.QUOTA} qualified or 03:00 IST, then reloads it when "
                       "Forsta closes it. Progress: portal → Launch schedule.")
    deadline, code = time.time() + WATCH_HOURS * 3600, 0
    while True:
        beat("watching: running", RUN_HOURS)
        try:
            if lock is not None:
                lock.execute(text("SELECT 1"))
            code = run()
            now = next((w for w in launch_schedule.weeks()["weeks"] if w["date"] == str(week["date"])), {})
        except Exception:
            log.exception("This watch cycle crashed; the watch carries on")
            tell(notify.failure, "a watch cycle crashed", traceback.format_exc()[-1500:])
            code, now = 1, {}
        if now.get("status") == "loaded" and now.get("closed"):
            log.info("This week's wave is loaded and closed: watch over")
            return code
        if time.time() > deadline:
            tell(notify.teams, f"⚠️ {name}: not in after {WATCH_HOURS} h (status: {now.get('status', 'unknown')}). "
                               "The Friday run checks again.")
            return code
        beat("watching: waiting", WATCH_EVERY_SECONDS / 3600, last_exit=code)
        time.sleep(WATCH_EVERY_SECONDS)


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


def watchdog() -> int:
    """Hourly, apart from the run: tell the team when a run stopped without saying so, or a planned Monday never began."""
    try:
        last = json.loads(HEARTBEAT.read_text())
    except (OSError, ValueError):
        last = None
    now = datetime.now()
    if last and last["state"] != "finished" and now > datetime.fromisoformat(last["next"]) + timedelta(minutes=LATE_MINUTES):
        tell(notify.failure, "the ETL run stopped without finishing",
             f"Last sign of life {last['at']} ({last['state']}, run {last['run']}); it promised another by {last['next']}. "
             "It was killed or the Mac slept or restarted. The next scheduled run starts it again; to resume now run "
             "scripts/weekly_forsta.py.")
        return 1
    started = launch_schedule.planned_today() and now.hour * 60 + now.minute > 18 * 60
    if started and (not last or datetime.fromisoformat(last["at"]).date() < now.date()):
        tell(notify.failure, "this Monday's ETL run never started",
             "It was due at 17:30 IST. Check that the Mac is awake and the launchd job is loaded; run scripts/weekly_forsta.py.")
        return 1
    if last is None or now - datetime.fromisoformat(last["at"]) > timedelta(days=8):
        tell(notify.failure, "no ETL run for over a week", f"Last run: {last['at'] if last else 'never recorded'}.")
        return 1
    return 0


def main() -> int:
    planned = launch_schedule.planned_today()
    try:
        with etl_lock() as lock:   # one writer at a time: a hand-run --due and launchd would load a wave twice
            beat("running", RUN_HOURS)
            code = watch(planned, lock) if planned else run()
    except Locked:
        log.info("Another CIP run holds the lock; this one stops")
        return 0
    beat("finished", 0, last_exit=code)
    return code


def stopped(signum, frame):
    raise SystemExit(128 + signum)


if __name__ == "__main__":
    setup_logging()
    if sys.argv[1:] == ["--watchdog"]:
        sys.exit(watchdog())
    signal.signal(signal.SIGTERM, stopped)   # launchd, a shutdown or kill: say so before going
    signal.signal(signal.SIGHUP, stopped)
    try:
        sys.exit(main())
    except SystemExit as exc:
        if isinstance(exc.code, int) and exc.code > 128:
            log.error("Stopped by signal %d", exc.code - 128)
            tell(notify.failure, "the ETL run was stopped", f"Signal {exc.code - 128} at {datetime.now():%Y-%m-%d %H:%M}. "
                                                            "The next scheduled run starts it again.")
            beat("finished", 0, last_exit=exc.code)
        raise
    except BaseException:
        log.exception("The run crashed")
        tell(notify.failure, "the ETL run crashed", traceback.format_exc()[-1500:])
        beat("finished", 0, last_exit=1)
        sys.exit(1)
