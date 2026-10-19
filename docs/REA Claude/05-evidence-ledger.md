# 05 · Evidence ledger

Everything here was observed on **20 October 2026** from `/Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal`. Secret values are never shown: wherever a secret was involved, the commands printed only key names, lengths, line numbers or match counts.

## 1. Evidence records

| ID | Type | Source | Observation |
|---|---|---|---|
| E-01 | Command | `grep -rl <password> . --exclude-dir=.git` | Matches in exactly 2 files: `docs/LLM Council Gemini/advisors/01-the-contrarian.md` and `docs/REA Gemini/05-IDENTIFIED-GAPS-AND-DEFECT-LEDGER.md`. The same value is on `.env` line 70. `git log --all -S` finds nothing, so it was never committed. |
| E-02 | Command | `gh api repos/saeedafri/consumer-insight-portal` | `"private": false, "visibility": "public"`, last pushed 2026-10-18 |
| E-03 | Command | `git ls-files` with grep | Tracked files contain the Azure MySQL host or `10.2.1.9` (8 files: docs and `scripts/drop_cip_from_dwh_stg.py`). `logs/notify-state.json` is tracked. |
| E-04 | Command | masked `awk` over `.env` | 72 lines.<br>• Line 66 `FORSTA_API_KEY=…` duplicates line 48, and the two values differ.<br>• Line 68 is `mysql -h 10.2.1.9 -u mohdsaeed -p`.<br>• Line 70 is a bare token.<br>• `APP_DB_USER` and `APP_DB_PASSWORD` are empty.<br>• `AUTH_PROVIDER=local`, `APP_ENV=LOCAL`, `DEBUG=true`, `STG_DB_NAME=cip_stg`. |
| E-10 | Live SQL | `cip_forsta_survey` | `loaded=33, hibernated=51, testing=7`. 51 rows are `hibernated` with `survey_id IS NULL`. |
| E-11 | Log | `logs/forsta-etl-errors.jsonl` | 6 records, all `Integrity (watch): closed Forsta survey hibernated before it was loaded … 51 surveys`, from 19 Oct 23:58 to 20 Oct 02:00. The runs still exit 0 (launchctl last exit 0). |
| E-12 | Code | `app/core/config.py:140-143` | The app role falls back to the STG writer credentials when `APP_DB_USER` is unset (from the app and schema audits) |
| E-13 | Live SQL | `information_schema.VIEWS`; `SELECT CURRENT_USER()` on `get_engine("app")` | All 12 views have DEFINER `mohdsaeedafri@%`. The app engine connects as `mohdsaeedafri@%`. |
| E-14 | Command | `git status`, `git diff --stat` | Untracked: `etl/integrity.py` (190 lines), `scripts/backup_db.py` (147), `scripts/launchd/com.coresight.cip-backup.plist`, `scripts/move_legacy_source.py`, `tests/test_pipeline_hardening.py`, docs. 11 tracked files are modified (+442/−72), including `scripts/weekly_forsta.py`, `etl/forsta_etl.py` and the ETL plist. |
| E-15 | Log | `logs/forsta-etl.log` (921 lines) | 20 Oct 00:30 `Register: {'hibernated': 51, 'loaded': 32, 'testing': 7, 'due': 1}` → 00:31:50 `Loaded 1: ['selfserve/58f/261001']`.<br>DB unreachable: 15 Oct 09:15 and 18 Oct 10:24. Failure emails were sent.<br>Earlier timeouts on 11 and 13 Oct. Runs truncated mid-retry: 14 Oct 09:03 and 16 Oct 09:15. |
| E-16 | Live SQL | `information_schema` and `cip_*` counts | FKs 39; base tables 40, of which 33 `cip_`; 12 views.<br>`cip_answer` indexes: PRIMARY, uq_answer, ix_answer_respondent, ix_answer_cover, ft_answer_text, fk_answer_field.<br>Surveys: forsta 33, qualtrics 142, surveymonkey 145, all `verified`.<br>Respondents 179,612; answers about 23,345,651 (InnoDB estimate).<br>Concepts 1,789; concept_map: proposed 2,625, confirmed 64,656.<br>Agg cells 2,131,784; crosstab 0; weight 0; auth sessions 2. |
| E-17 | Log | `logs/backup.log` | `Backup proven: cip_stg-20261019-2356.sql.gz (321 MB, 40 tables, 31,608,801 rows)` at 00:38:31. There is no "Copied to" line. |
| E-18 | Command | `launchctl list`, `diff` | `com.coresight.cip-forsta-etl` and `com.coresight.cip-backup` are loaded (last exit 0). The installed ETL plist is identical to the repo copy. |
| E-19 | Test run | `.venv/bin/python -m pytest -q` | **238 passed, 502 warnings in 46.14 s**. Python 3.13.12, pytest 9.1.1. No `pyproject.toml`, `pytest.ini` or `setup.cfg`. |
| E-20 | Audit | ETL subagent (read-only) | Flow, exit codes, 19 integrity checks, unsalted RID hash, the fallback on any OperationalError, no lock, no read timeout, uncaught crash path, schedule of 119 slots. Every item is cited with file:line in [02](02-identified-gaps.md). |
| E-21 | Code | `etl/notify.py:287-300` | `already_told()` writes state before `send()` is called |
| E-22 | Code/log | `tests/test_forsta_etl.py:244-264`, `tests/conftest.py:23-28`, `logs/notify-state.json` | `weekly.run()` tests don't stub `send` or `teams`. Test subjects are in the state file (17 Oct 22:38:24 and 22:38:31) but absent from the run log. |
| E-23 | Audit | App subagent and schema subagent (read-only) | Findings G-10 to G-13, G-15, G-21 to G-26, G-30 to G-39, with file:line |

**Per-file test counts** (from `pytest --collect-only`, for comparison with Gemini's transcript):

| Test file | Tests |
|---|---|
| test_forsta_etl | 41 |
| test_phase4 | 29 |
| test_phase3 | 25 |
| test_harmonise | 24 |
| test_phase5 | 20 |
| test_auth | 18 |
| test_phase6 | 16 |
| test_analysis | 13 |
| test_schema_v2 | 13 |
| test_survey_map | 10 |
| test_tracker_line | 8 |
| test_pipeline_hardening | 7 |
| test_survey_calendar | 6 |
| test_notify | 4 |
| test_phase7 | 2 |
| test_trends_multiwave | 2 |

## 2. Live query script

The script ran through `get_engine("app")` and issued only SELECTs against `information_schema` and `cip_*`. It is kept at `scratchpad/live_counts.py` in the session scratch folder and is not part of the repo. Re-run it with:

```bash
PYTHONPATH=. .venv/bin/python <path>/live_counts.py
```

## 3. Limits of this investigation

- **No REA binary or runtime tools were used.** The skill routes source-repo analysis to normal tools.
- **Reconciliation was not re-run** (it would call Forsta). The parity figures come from docs/14.
- **The portal was not started** and no browser test was run. App findings are static code reading. Whether the HTML injection paths execute is [U].
- **Not checked:** `EXPLAIN` plans for the views, collation collisions in real waves, Forsta's real retention policy, and whose account owns the working Forsta key. All [U].
- **The audit agents' line numbers were spot-checked, not all re-verified.** Checked: `.env` lines, `notify.py` throttle, test counts, live counts, plist identity.

## 4. Investigation checklist (REA §"Plan broader investigations")

| # | Question | Status |
|---|---|---|
| 1 | What runs, where, on what schedule? | Answered (01 §3, E-15, E-18) |
| 2 | What is in the warehouse right now, and what is missing? | Answered (E-10, E-16) |
| 3 | Is the load correct and atomic? | Answered: correct counts; atomic for answers only (01 §3) |
| 4 | How do failures surface? | Answered: three silent paths (G-07, G-08, G-14) |
| 5 | Who can read or write what? | Answered (G-03, G-11, G-21, G-22) |
| 6 | Is anything secret exposed? | Answered (G-01, G-05, G-06) |
| 7 | Do the tests prove what they claim, and are they safe to run? | Partly: they pass, but they send real alerts and cannot see MySQL-only errors |
| 8 | Is the UI fast enough, and is a rewrite needed? | Partly: CIP's own figures show 4.36 s at 20 users; external-user demand is [U] |
| 9 | How accurate is Gemini's dossier? | Answered (04) |
| 10 | What should be built next? | Answered (03) |
