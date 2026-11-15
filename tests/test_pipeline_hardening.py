"""Pipeline hardening (19 Oct 2026): significance letters, bulk-load escaping, integrity healing, masked logs."""
from __future__ import annotations

import importlib
import json
import re
from datetime import date, datetime, timedelta
import logging

import sqlalchemy as sa

from shared.core import database
from etl import crosstab_export, forsta_etl, integrity
from tests.test_forsta_etl import SURVEYS, FakeForsta, record


def test_the_z_test_gives_forstas_letters_on_the_teams_holiday_banner():
    # q1 "Gone to a shopping mall", 10/12/26: Still shopping 41/117 beats Not yet started 47/222 at 95 % ('B');
    # Finished shopping 11/32 does not beat it even at 90 % (their file: 'E' only, no 'b').
    assert crosstab_export.ztest(41, 117, 47, 222) > crosstab_export.Z95
    assert crosstab_export.ztest(11, 32, 47, 222) < crosstab_export.Z90
    assert crosstab_export.ztest(5, 1, 3, 40) == 0.0                 # no test on a base under 2


def test_stat_groups_read_forstas_notation():
    assert crosstab_export.stat_groups("holiday_status") == [[1, 2, 3, 4], [5, 6]]
    assert crosstab_export.stat_groups("standard") == []


def test_marks_letter_each_column_against_its_group_only():
    block = lambda x, n: [(None, [("Yes", float(x)), ("Count", 1.0)], n)]
    per = [block(150, 300), block(90, 100), block(10, 100), block(50, 100)]   # Total, B, C, D
    letters = crosstab_export.marks(per, 0, [[1, 2]])
    assert letters == {0: ["", "C", "", ""]}                          # D is outside the group; Count gets none


def test_load_data_fields_escape_what_mysql_would_read_as_structure():
    assert database.tsv(None) == r"\N"
    assert database.tsv("a\tb\\c\nd\re") == "a\\tb\\\\c\\nd\\re"
    assert database.tsv(2.5) == "2.5"


def test_integrity_heals_derived_rows_and_reports_base_problems(csi_db, monkeypatch):
    monkeypatch.setattr(integrity, "planned_weeks_missing", lambda today=None: [])
    forsta_etl.discover(FakeForsta())
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    assert integrity.run() == ["closed Forsta survey still not loaded after 3 days: 1 rows"]   # Holiday, closed 16 Sep
    forsta_etl.load_survey(FakeForsta(data={"selfserve/58f/260905": [record(n) for n in range(6, 9)]}), "selfserve/58f/260905")
    assert integrity.run() == []
    with csi_db.begin() as conn:
        conn.execute(sa.text("DELETE FROM cip_agg_cell WHERE survey_id = :s"), {"s": sid})
        conn.execute(sa.text("DELETE FROM cip_search WHERE survey_id = :s AND kind = 'survey'"), {"s": sid})
        conn.execute(sa.text("INSERT INTO cip_wave_module (forsta_path, module_code, module_name, kind)"
                             " VALUES ('selfserve/58f/gone', 'x', 'x', 'topic')"))
    assert integrity.run() == []                                      # all three are derived: rebuilt or removed
    with csi_db.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM cip_agg_cell WHERE survey_id = :s"), {"s": sid}).scalar() > 0
        assert conn.execute(sa.text("SELECT COUNT(*) FROM cip_wave_module WHERE forsta_path = 'selfserve/58f/gone'")).scalar() == 0
    with csi_db.begin() as conn:
        conn.execute(sa.text("UPDATE cip_forsta_survey SET survey_id = 99999 WHERE forsta_path = 'selfserve/58f/260905'"))
    left = integrity.run()
    assert left == ["register row pointing at a missing wave: 1 rows",
                    "register says loaded, wave not verified: 1 rows"]       # loaded data is never changed by itself


def test_a_wave_hibernated_before_its_final_reload_is_warned_about(csi_db, monkeypatch, caplog):
    """15 Nov 2026 audit: a wave loaded early (still live) that Forsta hibernated before its final reload keeps its
    pre-close data; the integrity check warned only about hibernated waves that were never loaded."""
    monkeypatch.setattr(integrity, "planned_weeks_missing", lambda today=None: [])
    path = "selfserve/58f/260907"

    def forsta(changed: dict):
        surveys = [dict(s, **changed) if s["path"] == path else s for s in SURVEYS]
        return type("Forsta", (FakeForsta,), {"surveys": lambda self: surveys})()
    early = forsta({"state": "live", "closedDate": None})
    forsta_etl.discover(early)                                         # live, 9 hours past launch: due
    forsta_etl.load_survey(early, path)                                # the early load
    forsta_etl.discover(forsta({"hibernated": True}))                  # closed and hibernated before the reload
    with caplog.at_level(logging.WARNING, logger="cip.integrity"):
        integrity.run(heal=False)
    assert "before its final reload" in caplog.text


def test_the_logs_never_show_a_secret(monkeypatch):
    weekly = importlib.import_module("scripts.weekly_forsta")
    monkeypatch.setattr(weekly.Masked, "secrets", ["s3cret-api-key-123"])
    record = logging.LogRecord("cip.forsta", logging.ERROR, __file__, 1, "401 for key %s", ("s3cret-api-key-123",), None)
    assert "s3cret" not in weekly.Masked("%(message)s").format(record)
    entry = json.loads(weekly.JsonLines("%(message)s").format(record))
    assert entry["message"] == "401 for key ***" and entry["step"] == "cip.forsta" and entry["level"] == "ERROR"


def test_the_scheduled_run_writes_warnings_to_the_json_error_log(tmp_path, monkeypatch):
    weekly = importlib.import_module("scripts.weekly_forsta")
    monkeypatch.setattr(weekly, "ERRORS", tmp_path / "errors.jsonl")
    root = logging.getLogger()
    kept = root.handlers[:], root.level
    try:
        weekly.setup_logging()
        logging.getLogger("cip.integrity").warning("Integrity: %s", "something")
        logging.getLogger("cip.weekly").info("not an error")
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers[:], root.level = kept
    lines = (tmp_path / "errors.jsonl").read_text().splitlines()
    assert [json.loads(line)["message"] for line in lines] == ["Integrity: something"]


def test_the_watchdog_tells_when_a_run_goes_silent(tmp_path, monkeypatch):
    weekly = importlib.import_module("scripts.weekly_forsta")
    told = []
    monkeypatch.setattr(weekly, "HEARTBEAT", tmp_path / "beat.json")
    monkeypatch.setattr(weekly, "tell", lambda action, *args: told.append(args[0]))
    monkeypatch.setattr(weekly.launch_schedule, "planned_today", lambda: None)
    weekly.beat("watching: waiting", 0.5)
    assert weekly.watchdog() == 0 and told == []                     # inside its promise
    weekly.beat("watching: waiting", -2)                              # promised a beat two hours ago, then went quiet
    assert weekly.watchdog() == 1 and told == ["the ETL run stopped without finishing"]
    weekly.beat("finished", 0, last_exit=0)
    told.clear()
    assert weekly.watchdog() == 0 and told == []                      # a finished run owes nothing for 2 hours
    beat = json.loads((tmp_path / "beat.json").read_text())
    beat["at"] = beat["next"] = (datetime.now() - timedelta(hours=3)).isoformat(timespec="seconds")   # as one 3 hours old
    (tmp_path / "beat.json").write_text(json.dumps(beat))
    assert weekly.watchdog() == 1 and told == ["no ETL check for over 2 hours"]   # the 30-minute checks stopped


def test_a_long_run_inside_its_promise_is_not_a_stopped_scheduler(tmp_path, monkeypatch):
    """15 Nov 2026 audit: a run promises its next sign of life within RUN_HOURS (3), but the quiet check alarmed at 2
    hours, so a long load was reported as a stopped scheduler. Silence now counts from the run's promise."""
    weekly = importlib.import_module("scripts.weekly_forsta")
    told = []
    monkeypatch.setattr(weekly, "HEARTBEAT", tmp_path / "beat.json")
    monkeypatch.setattr(weekly, "tell", lambda action, *args: told.append(args[0]))
    monkeypatch.setattr(weekly.launch_schedule, "planned_today", lambda: None)
    started = datetime.now() - timedelta(hours=2.5)                    # a big load, 2.5 hours in
    (tmp_path / "beat.json").write_text(json.dumps({"at": started.isoformat(timespec="seconds"), "run": "r", "pid": 1,
                                                    "state": "running", "next": (started + timedelta(hours=weekly.RUN_HOURS)).isoformat(timespec="seconds")}))
    assert weekly.watchdog() == 0 and told == []


def test_the_watch_holds_the_lock_only_while_it_checks(tmp_path, monkeypatch):
    """15 Nov 2026 audit: the Monday watch kept the one ETL lock through its 30-minute sleeps for up to 54 hours, so the
    Upload survey page answered 409 and the SharePoint watcher stopped on it. It holds the lock only for a check now,
    and the 30-minute checks still leave the checking to a live watch (no second Forsta read every 30 minutes)."""
    from contextlib import contextmanager
    weekly = importlib.import_module("scripts.weekly_forsta")
    held, checks, slept = [], [], []

    @contextmanager
    def lock(wait=0):
        held.append(1)
        yield None
        held.pop()
    weeks = iter([{"weeks": []}, {"weeks": [{"date": "2026-11-16", "status": "loaded", "closed": "2026-11-17T01:00:00Z"}]}])
    monkeypatch.setattr(weekly, "etl_lock", lock)
    monkeypatch.setattr(weekly, "HEARTBEAT", tmp_path / "beat.json")
    monkeypatch.setattr(weekly, "tell", lambda *a: None)
    monkeypatch.setattr(weekly, "run", lambda: checks.append(bool(held)) or 0)
    monkeypatch.setattr(weekly.time, "sleep", lambda seconds: slept.append(bool(held)))
    monkeypatch.setattr(weekly.launch_schedule, "planned_today",
                        lambda: {"date": date(2026, 11, 16), "names": ["Apparel"], "topics": [], "cycle": 1})
    monkeypatch.setattr(weekly.launch_schedule, "weeks", lambda today=None: next(weeks))
    assert weekly.main() == 0 and checks == [True, True] and slept == [False]
    weekly.beat("watching: waiting", 0.5)                               # the watch between two checks
    assert weekly.main(once=True) == 0 and len(checks) == 2             # the 30-minute check leaves it to the watch
    beat = json.loads((tmp_path / "beat.json").read_text())
    (tmp_path / "beat.json").write_text(json.dumps({**beat, "pid": 2 ** 22 + 1}))   # no such process: a deploy killed it
    assert weekly.main(once=True) == 0 and len(checks) == 3
    told = []
    monkeypatch.setattr(weekly, "tell", lambda action, *args: told.append(args[0]))
    monkeypatch.setattr(weekly, "WATCH_HOURS", 0)
    monkeypatch.setattr(weekly, "etl_lock", lambda wait=0: (_ for _ in ()).throw(weekly.Locked("a watch is checking")))
    assert weekly.main() == 0 and told == []                            # a second launch run never starts a second watch


def test_only_the_launch_run_watches_on_a_monday():
    """15 Nov 2026: every Monday is planned, so Monday's 03:30 UTC slot run started the watch at 09:00 IST and its
    54 hours ended Wednesday 15:00 IST, not 23:30. That minute is the 30-minute check's now."""
    loop = open("deploy/etl-loop.sh").read()
    runs = re.search(r'RUNS=\$\{CIP_ETL_RUNS:-"([^"]+)"\}', loop)[1].split()
    assert [slot for slot in runs if slot.startswith("Mon@")] == ["Mon@12:00"]


def test_the_30_minute_check_never_starts_a_watch(tmp_path, monkeypatch):
    """A check (--once) on a launch Monday is one run: only the 17:30 IST run watches, so a check never holds the lock
    for 54 hours, and a killed watch is replaced by the next check (9 Nov 2026, wave 261100)."""
    weekly = importlib.import_module("scripts.weekly_forsta")
    called = []
    monkeypatch.setattr(weekly, "HEARTBEAT", tmp_path / "beat.json")
    monkeypatch.setattr(weekly.launch_schedule, "planned_today", lambda: {"names": ["wave"], "topics": [], "cycle": 1})
    monkeypatch.setattr(weekly, "watch", lambda week, lock=None: called.append("watch") or 0)
    monkeypatch.setattr(weekly, "run", lambda: called.append("run") or 0)
    monkeypatch.setattr(weekly, "beat", lambda *a, **k: None)
    assert weekly.main(once=True) == 0 and called == ["run"]
    assert weekly.main() == 0 and called == ["run", "watch"]


def test_a_new_server_starts_the_week_instead_of_alarming_every_hour(tmp_path, monkeypatch):
    weekly = importlib.import_module("scripts.weekly_forsta")
    told = []
    monkeypatch.setattr(weekly, "HEARTBEAT", tmp_path / "beat.json")
    monkeypatch.setattr(weekly, "tell", lambda action, *args: told.append(args[0]))
    monkeypatch.setattr(weekly.launch_schedule, "planned_today", lambda: None)
    assert weekly.watchdog() == 0 and weekly.watchdog() == 0 and told == []   # no heartbeat yet: the week starts now
    beat = json.loads((tmp_path / "beat.json").read_text())
    beat["at"] = beat["next"] = "2020-01-01T00:00:00"
    (tmp_path / "beat.json").write_text(json.dumps(beat))
    assert weekly.watchdog() == 1 and told == ["no ETL check for over 2 hours"]  # and still alarms when quiet


def test_a_salted_respondent_key_matches_a_rekeyed_old_one(monkeypatch):
    import hashlib
    import hmac
    from etl import records
    old = records.respondent_key(123)                                   # before the salt: plain sha256
    monkeypatch.setenv("CIP_RESPONDENT_SALT", "s" * 32)
    assert old == hashlib.sha256(b"123").hexdigest()
    assert records.respondent_key(123) == hmac.new(b"s" * 32, old.encode(), hashlib.sha256).hexdigest()   # = rekey_respondents


def test_a_planned_tracker_week_missing_after_four_days_is_reported(monkeypatch):
    from datetime import date
    from etl import integrity, launch_schedule
    plan = {"weeks": [{"date": "2026-10-12", "status": "loaded"}, {"date": "2026-10-19", "status": "load_failed"},
                      {"date": "2026-10-26", "status": "planned"}, {"date": "2025-01-06", "status": "not_found"}]}
    monkeypatch.setattr(launch_schedule, "weeks", lambda today=None: plan)
    assert integrity.planned_weeks_missing(date(2026, 10, 22)) == []          # 19 Oct is only 3 days old
    assert integrity.planned_weeks_missing(date(2026, 10, 23)) == ["planned tracker week not in the portal 4 days after its Monday: 2026-10-19"]


def test_waves_loaded_from_elsewhere_are_published_by_the_next_30_minute_check(tmp_path, monkeypatch):
    """11 Nov 2026: the China history went straight into the database; an idle check (nothing new in Forsta) now
    publishes it, instead of the screens missing those weeks until a restart or the next Forsta load."""
    import pandas as pd
    weekly = importlib.import_module("scripts.weekly_forsta")
    published = []
    (tmp_path / "current").mkdir()
    client = type("Client", (), {"whoami": lambda self: {}})()
    monkeypatch.setattr(weekly, "healthcheck", lambda role: (True, "ok"))
    monkeypatch.setattr(weekly, "inspect", lambda engine: type("I", (), {"get_table_names": lambda self: ["cip_forsta_survey", "cip_search", "cip_tracker_line"]})())
    monkeypatch.setattr(weekly, "get_engine", lambda role: None)
    monkeypatch.setattr(weekly.forsta_etl, "discover", lambda c: {})
    monkeypatch.setattr(weekly.forsta_etl, "run_due", lambda c: {"loaded": [], "failed": []})
    monkeypatch.setattr(weekly.fieldwork, "collect", lambda c, loaded: [])
    monkeypatch.setattr(weekly, "tell", lambda *a: None)
    monkeypatch.setattr(weekly.integrity, "run", lambda: [])
    monkeypatch.setattr(weekly.publish, "ROOT", tmp_path)
    monkeypatch.setattr(weekly.publish, "publish", lambda: published.append(1))
    from etl import publications
    monkeypatch.setattr(publications, "drift_summary", lambda: pd.DataFrame())
    monkeypatch.setattr(weekly.publish, "behind", lambda version: False)
    weekly.run(client)
    assert published == []   # up to date: nothing published
    published.clear()
    monkeypatch.setattr(weekly.publish, "behind", lambda version: True)
    assert weekly.run(client) == 0 and published == [1]


def test_the_full_check_runs_once_a_friday_on_the_first_idle_check_that_gets_the_lock(tmp_path, monkeypatch):
    """Every idle check of a Friday ran the full integrity and drift check, ~48 times on the one CPU; one Friday slot
    alone could miss it for a week when another run held the lock (15 Nov 2026 audit, second review)."""
    weekly = importlib.import_module("scripts.weekly_forsta")
    checked = []
    client = type("Client", (), {"whoami": lambda self: {}})()
    monkeypatch.setattr(weekly, "healthcheck", lambda role: (True, "ok"))
    monkeypatch.setattr(weekly, "inspect", lambda engine: type("I", (), {"get_table_names": lambda self: ["cip_forsta_survey", "cip_search", "cip_tracker_line"]})())
    monkeypatch.setattr(weekly, "get_engine", lambda role: None)
    monkeypatch.setattr(weekly.forsta_etl, "discover", lambda c: {})
    monkeypatch.setattr(weekly.forsta_etl, "run_due", lambda c: {"loaded": [], "failed": []})
    monkeypatch.setattr(weekly.fieldwork, "collect", lambda c, loaded: [])
    monkeypatch.setattr(weekly, "tell", lambda *a: None)
    monkeypatch.setattr(weekly.integrity, "run", lambda: checked.append(1) or ["stop here"])
    monkeypatch.setattr(weekly.publish, "behind", lambda version: False)
    monkeypatch.setattr(weekly, "FULL_CHECKED", tmp_path / "etl-full-check.txt")
    friday = type("Friday", (weekly.datetime,), {"now": classmethod(lambda cls, tz=None: weekly.datetime(2026, 11, 20, 4, 0))})
    monkeypatch.setattr(weekly, "datetime", friday)
    try:
        weekly.run(client)                                         # the first idle check of the Friday
    except Exception:   # noqa: BLE001 — past the full check the stubs end; only whether it ran matters here
        pass
    assert checked == [1] and weekly.run(client) == 0 and checked == [1]   # the next one leaves it
