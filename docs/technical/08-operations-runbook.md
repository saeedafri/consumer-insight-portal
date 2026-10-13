# 8. Operations runbook

## 8.1 Schedule

| | |
|---|---|
| Scheduler | launchd user agent `com.coresight.cip-forsta-etl` (plist in `scripts/launchd/`, installed in `~/Library/LaunchAgents/`) |
| Command | `.venv/bin/python scripts/weekly_forsta.py` in the repository |
| Times (IST) | daily **09:00**; Tuesday and Wednesday **14:00** and **23:30** |
| Why these times | waves launch Monday 12–13 UTC and close Monday 20:00 – Wednesday 23:00 IST; a missed slot runs when the Mac wakes |
| Log | `logs/forsta-etl.log` (appended) |
| Server equivalent | cron `0 9 * * *`, `0 14 * * 2,3`, `30 23 * * 2,3` with `APP_ENV=staging` |

## 8.2 What one run does

1. Database health check — 4 tries, 5 minutes apart.
2. Forsta key check — `GET rh/users/self`.
3. Schema check — `cip_forsta_survey`, `cip_search`, `cip_tracker_line` must exist.
4. Discover → load every due wave → verify → derive (see sections 2–5).
5. Re-check every frozen publication for drift.

## 8.3 Exit codes

| Code | Meaning | Action |
|---|---|---|
| 0 | Everything due loaded and verified (or nothing due) | none |
| 1 | A wave failed to load or verify | read `cip_forsta_survey.last_error`; the next run retries |
| 2 | Forsta rejected the key, it is not configured, or the schema is behind the code | renew the key / run `python scripts/init_db.py` |
| 3 | Loaded, but a published number moved | review on the Publications page |
| 4 | Database unreachable after 4 tries | check VPN / Azure firewall; the next slot retries |

## 8.4 Commands

```bash
python scripts/test_connection.py                  # database + Forsta check (never prints the key)
python scripts/init_db.py                          # create / upgrade the schema (refuses while a load runs)
python scripts/weekly_forsta.py                    # the scheduled run, by hand
python -m etl.forsta_etl --discover                # refresh the register only
python -m etl.forsta_etl --due                     # discover + load everything due
python -m etl.forsta_etl --survey selfserve/58f/260908   # load or reload one wave
python -m etl.forsta_etl --reconcile               # every loaded Forsta wave vs Forsta
python -m etl.forsta_etl --reindex                 # rebuild search for every verified wave
python -m etl.tracker_line --rebuild               # rebuild line-by-line rows
python -m etl.tracker_line --compare "<team file>.xlsx"  # compare with the data team's file (reads only)
python -m etl.survey_calendar                      # calendar + next 12 lead sectors
python -m etl.legacy_dwh --all [--era surveymonkey]      # history from dwh_sm*
python scripts/reconcile.py                        # every wave vs its source
python scripts/perf_check.py                       # P95 timings
python scripts/data_dictionary.py > docs/technical/06-data-dictionary.md
```

## 8.5 Monitoring queries

```sql
-- what the pipeline knows about Forsta
SELECT load_state, COUNT(*) FROM cip_forsta_survey GROUP BY load_state;

-- anything waiting or failed
SELECT forsta_path, state, load_state, qualified_n, total_n, closed_at, last_error
  FROM cip_forsta_survey WHERE load_state IN ('due', 'failed');

-- last runs
SELECT load_id, survey_id, source_type, status, rows_read, rows_loaded, started_at, finished_at, error_text
  FROM cip_load_log ORDER BY load_id DESC LIMIT 20;

-- nothing should be stuck
SELECT survey_id, wave_label, load_status FROM cip_survey WHERE load_status <> 'verified';
```

## 8.6 Common situations

| Situation | Cause | Fix |
|---|---|---|
| Runs log "Loaded 0" for days | No survey has closed in Forsta | Expected; the wave loads at the first run after it is closed |
| Exit 4 / "Can't connect to MySQL … timed out" | VPN down or office IP not allowed by the Azure firewall | Reconnect; the next slot retries |
| A wave `failed` with "does not match its payload" | Forsta changed data mid-load, or a load step broke | `python -m etl.forsta_etl --survey <path>`; investigate `last_error` |
| Survey `hibernated` and history needed | Forsta hibernated it before it was loaded | A Forsta owner reactivates it; the next run loads it |
| Survey reopened and closed again | New respondents | Discovery marks it due; it is reloaded in place |
| Exit 2 "schema is behind the code" | New code deployed | `python scripts/init_db.py` |

## 8.7 Change management

* Code: Python 3.13, SQLAlchemy 2, PyMySQL, tenacity, pandas; tests `pytest` (227 passing, SQLite).
* Schema: `sql/001_schema.sql` is the single source (MySQL DDL, converted to SQLite for tests);
  `app/core/schema_upgrade.py` adds new columns and indexes to an existing database.
* Rules without code changes: `config/survey_map.yml` (topics, demographics, bands), `config/cohorts.yml`,
  `config/tracker_line.yml`, `config/survey_calendar.yml`.

## 8.8 Security

* Forsta: GET only; no write method exists in the client. Key in `.env`, git-ignored, never printed.
* Warehouse: TLS; the portal uses a read-only account; only the ETL writes.
* Personal data: never stored (browser string, link, session, fingerprint, IP); panel id only as sha256.
