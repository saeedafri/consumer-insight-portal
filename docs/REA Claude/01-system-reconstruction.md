# 01 · System reconstruction

Markers: [O] observed, [I] inferred, [U] unknown. `E-xx` refers to [05-evidence-ledger.md](05-evidence-ledger.md).

## 1. What the system is

CIP replaces the data team's manual workflow: download a weekly Forsta survey to Excel, clean it, then paste it into master workbooks. It is three parts.

| Part | Code | Runs where | State |
|---|---|---|---|
| **Ingestion** (Forsta → `cip_stg`) | `scripts/weekly_forsta.py`, `etl/` | launchd on the owner's MacBook | In production. Loaded wave 261001 at 00:31 on 20 Oct [O] E-15 |
| **Warehouse** | `sql/001_schema.sql`, `sql/002_views.sql` | Azure MySQL 8 Flexible Server, database `cip_stg` | 33 `cip_` tables, 7 `dwh_sm*` legacy tables, 12 views, 39 FKs [O] E-16 |
| **Portal** | `app/` (Streamlit 1.55.0) | Local only (`scripts/run_local.sh`, port 8611) | Prototype. Auth mode `local` shared passphrase, `APP_ENV=LOCAL`, `DEBUG=true` in `.env` [O] E-12 |

A React + FastAPI front end is **proposed only** (`docs/12:16`, `docs/13:9`), not built [O].

## 2. Live inventory (read-only queries, 20 Oct 2026) [O] E-16

| Measure | Value | Note |
|---|---|---|
| Verified survey waves | **320**: Forsta 33, Qualtrics 142, SurveyMonkey 145 | No `loading` or `failed` waves at the time of the query |
| Respondents | **179,612** | The README still says 71,474 |
| Answers (`cip_answer`) | **≈23.3 M** | InnoDB estimate. The README still says 10.4 M |
| Concepts | **1,789** | The README still says 828 |
| Concept-map rows | 64,656 confirmed, **2,625 proposed** | The README's "985 uncertain matches" is stale |
| Cube cells (`cip_agg_cell`) | 2,131,784 | |
| Forsta register | 33 loaded, **51 hibernated with `survey_id IS NULL`**, 7 testing | The 51 were never loaded |
| `cip_crosstab`, `cip_weight` | **0 rows each** | Imported crosstabs and weighting are schema only |
| Auth sessions | 2 | |
| View DEFINER / portal DB user | `mohdsaeedafri@%` for both | Personal account |

## 3. Ingestion flow (actual code path)

```
launchd (119 StartCalendarInterval slots, local time zone)
 └─ .venv/bin/python scripts/weekly_forsta.py                         weekly_forsta.py:142
     ├─ config check ───────────────────────────── missing → exit 2  :52-57
     ├─ healthcheck("etl") ×4, fixed 300 s pauses ─ fail → exit 4     :59-69
     ├─ client.whoami()  GET /rh/users/self ─────── 401/403 → exit 2  :70-75
     ├─ required tables present ─────────────────── missing → exit 2  :76-80
     ├─ forsta_etl.discover()   GET surveys → upsert cip_forsta_survey, rebuild calendar   forsta_etl.py:77-119
     ├─ forsta_etl.run_due()    each 'due' or 'failed' survey, oldest first               :423-440
     │    └─ load_survey()                                                               :203-276
     │        fetch datamap + data (GET) → upsert_survey → status 'loading'
     │        → load_definitions (txn) → _write (ONE txn: respondents, answers via
     │          LOAD DATA LOCAL INFILE, falling back to batched INSERT on warnings/OperationalError)
     │        → verify (counts: respondents, fields, per-field non-null)
     │        → profiles → question bases → harmonise → cube → search → tracker_line
     │        → status 'verified', register 'loaded'
     ├─ notify per wave (email via M365 SMTP, Teams webhook; 6 h throttle)
     ├─ integrity.run()   19 checks: 3 derived (healed), 5 orphan (deleted), 9 base, 2 watch   integrity.py:62-124
     ├─ any failed wave ──────────────────────────────────────────── exit 1  :93-95
     ├─ publications.drift_summary()
     └─ exit 3 if drift, else 5 if integrity broken, else 0                            :103
```

[O] Every line above is from the ETL audit (E-20) and was cross-checked against the logs (E-15).

**The schedule** is in local time, which is IST on this Mac [O]:
- Monday: 09:00, 13:00, 18:00, then every 30 min from 20:00
- Tuesday and Wednesday: every 30 min
- Thursday to Sunday: 09:00, 13:00, 18:00

The installed plist is byte-identical to the repo copy [O]. The docstring at `weekly_forsta.py:6` and `docs/pipeline-resilience.yml:51` describe an older schedule [O].

**Transactions** [O]:
- Only `_write` (respondents and answers) is a single transaction.
- Definitions, each derived step and the status flips are separate transactions.
- A crash mid-load leaves the wave `loading`, which hides it, and the next run reloads it.
- A failed *reload* of a good wave leaves it `failed`, so it disappears from the portal even when only a derived step (e.g. the cube) failed.

**Visibility** [O]:
- The portal's repository functions and the 3 analyst views filter on `load_status='verified'`.
- The other 8 views, including `v_cip_trend` (which the Trends page uses), and `v_cip_mapping_queue` do **not** filter.

## 4. Data model (grain of each table)

- **Definition:**
  - `cip_survey`: one row per wave, unique on (platform, source_ref, wave_label)
  - `cip_question`, holding `base_n` and the routing description
  - `cip_item` and `cip_option`
  - `cip_field`: one row per export column
- **Facts:**
  - `cip_respondent`: one per interview, unique on (survey, record_no)
  - `cip_profile`: one per respondent, with demographics flattened
  - `cip_answer`: one per respondent × field, in long format
- **Harmonisation:** `cip_concept` and `cip_concept_option` → `cip_concept_map` (survey × question:item:option), with status proposed, confirmed or rejected.
- **Speed layer:** `cip_agg_cell`, one per survey × question:item:option:cohort:scheme:dim:value. The portal reads totals from here, not from `cip_answer`.
- **Other:**
  - cohorts: `cip_cohort_def`, `cip_respondent_cohort`
  - publications: `cip_publication`, `cip_publication_cell`, a frozen copy with no FK to surveys
  - load audit: `cip_load_log`, `cip_load_error`, `cip_load_state`
  - Forsta register and calendar: `cip_forsta_survey`, `cip_wave_module`
  - derived: `cip_search`, `cip_tracker_line`
  - support: `cip_profile_map`, `cip_auth_session`, `cip_saved_view`
- **Schema only (0 rows):** `cip_banner`, `cip_segment`, `cip_crosstab_run`, `cip_crosstab`, `cip_weight_scheme`, `cip_weight`.

**Two bases** are kept for routed questions [O] (`sql/001_schema.sql`, the `v_cip_crosstab` view):
- segment size, i.e. the column base;
- the answering base for the question.

This is the most important analytical design choice in the repo, and it is implemented correctly in the cube and in the views that use it [I].

## 5. Privacy and security perimeter [O]

**Privacy**
- Personal Forsta variables are dropped on load: `userAgent`, `url`, `session`, `dcua`, `ipAddress`, `RID` (`forsta_api.py:25`).
- `respondent_key` is an **unsalted** SHA-256 of the RID (`forsta_etl.py:200`, `legacy_dwh.py:317`).
- `forsta_uuid` is stored and links straight back to the Forsta record.

**Forsta access**
- The client uses GET only (`forsta_client.py:72`).
- The key works today: the 20 Oct load succeeded.
- `.env` defines `FORSTA_API_KEY` twice, with **different** values. The later one, line 66, wins.

**Logging**
- The log mask replaces the values of secret-named env vars; it is not a regex.
- It covers only the stream handler and the jsonl handler. Uncaught tracebacks are not masked.

**Portal auth**
- Auth is a shared passphrase. It is compared in constant time but not hashed, with no rate limit.
- The cookie is set from JavaScript, so it is neither HttpOnly nor Secure.
- Streamlit's XSRF protection is on, since its defaults apply.
- The OIDC sign-in path is not implemented.
- There is no logout in the UI.

**Database accounts**
- The portal and the ETL both use the personal `mohdsaeedafri@%` account, which has ALL privileges.

**Repo exposure**
- The repo is **public** and includes DB host names, internal design docs, personal paths in the plists, and a personal email in `config/notify.yml`.
- `logs/notify-state.json` is tracked.

## 6. Operations [O]

**Backups**
- `scripts/backup_db.py`, launchd `com.coresight.cip-backup`, Sundays 10:00. It takes a `mysqldump --single-transaction`, then proves the gzip, table and row counts.
- The last dump is 321 MB, 40 tables, 31.6 M rows.
- The OneDrive copy did **not** happen on that run.
- The proof step takes about 41 minutes, because it loops over every byte in Python.
- Both the script and its plist are **untracked**.

**Uptime**
- On 11, 13, 15, 16 and 18 Oct the database timed out from the laptop (public-IP firewall).
- Two runs, 14 Oct 09:03 and 16 Oct 09:15, stopped mid-retry with no final line and no alert. The cause is unknown: the Mac sleeping, a kill, or a hang [U].

**Errors**
- `logs/forsta-etl-errors.jsonl` holds the integrity "watch" line (51 hibernated) on every run since 19 Oct 23:58.

**Tests**
- 238 tests, all passing in 46 s. They run on SQLite, so MySQL-only syntax errors are invisible to them (see G-12).
