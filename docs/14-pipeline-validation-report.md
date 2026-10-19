# CIP ETL pipeline: audit and validation report

**19 October 2026** · scope: the Forsta → `cip_stg` pipeline (`scripts/weekly_forsta.py`, `etl/`), the weekly
cross-tab workbooks and the dashboards' data. Every number below was measured on `cip_stg` today, on wave
2026-10-12 (`selfserve/58f/261000`, survey_id 412, 595 respondents, 404 qualified, 147,635 answers). The team's
10/12/26 Excel exports were used only as a reference to check against. The pipeline reads the Forsta API.

Companion files: [`pipeline-resilience.yml`](pipeline-resilience.yml) (the error capture and self-healing
design) and [`samples/Holiday Status Cross Tabs 10_12_26 - proposed layout.xlsx`](samples/) (the proposed
analyst layout).

---

## Verdict

| Question | Answer |
|---|---|
| Does it run daily? | **Yes, but the installed schedule is out of date.** launchd runs at 09:00 IST daily, plus 14:00 and 23:30 IST on Tue and Wed. The 30-minute polling schedule committed on 18 Oct is **not installed** (`~/Library/LaunchAgents` still has the 8 Oct version). On 15, 16 and 18 Oct the only run of the day hit a database timeout, so those days had no successful run. Fix below (§2.1). |
| Is the data right? | **Yes.** Every answer of wave 412 equals the Forsta API (147,635 checked, 0 differ). The team's three cross-tab files are reproduced exactly: 28,080 + 4,914 + 13,338 cells, 100 % equal. Their Raw Data file has the same 404 qualified respondents and record numbers. |
| Are the tables linked? | **Yes.** There are 26 foreign keys across the 33 tables. Five derived or index tables have no FK by design, and a new integrity check now guards them (§1.4). All 16 checks pass. |
| Deduplicated? | **Yes.** There are 0 duplicate respondents (uuid) and 0 panelists qualified twice in any wave. Unique keys enforce one answer per respondent × field. |
| Fast? | The load of one wave went from **142 s to 116 s** (answer write 39.1 s → 8.6 s). Dashboards read the pre-computed cube (P95 0.35 s, unchanged). The biggest remaining lever is network latency, not code (§2.2). |
| Matches the manager's workbooks? | **It does now.** Before today the ETL's Holiday Status and Inflation Sentiment workbooks had **no significance letters**, while the team's Forsta exports have them (95 / 90, z-test). They are now added and agree with Forsta on 99.9 % and 99.6 % of cells; the few that differ are almost all on bases under 30. |

---

## 1 · Audit of the current pipeline

### 1.1 Flow (unchanged)

`discover` (register of every Forsta survey) → `run_due` (each closed, readable, unloaded wave, oldest first) →
per wave: fetch datamap + data → definitions → answers (one transaction) → **verify** against the payload →
profiles → harmonise → cube → search → line-by-line → `integrity` (**new**) → publication drift → notify.
A wave is invisible (`load_status = loading`) until it is verified.

### 1.2 Schedule and run history (logs/forsta-etl.log)

| Day | 09:00 run |
|---|---|
| 9, 10, 12 Oct | OK, nothing due |
| 11, 13 Oct | DB timeout (public IP changed); on 13 Oct the 14:00 run failed too, and a manual run at 14:13 caught up |
| 14 Oct | OK: wave 412 loaded in 214 s and emailed |
| 15, 16, 18 Oct | DB timeout after 4 × 5 min; **no further run that day** |
| 17, 19 Oct | OK, nothing due |

### 1.3 Bottlenecks (measured, wave 412 reload, 263 ms network round trip to Azure)

| Step | Before | After | What it is |
|---|---:|---:|---|
| fetch (Forsta API) | 3.7 s | 3.7 s | datamap and data, 3 GETs |
| definitions | ~12 s | 12.7 s | questions/items/options; `ensure_topic` does one round trip per topic (8 ×) |
| **write answers** | **57.3 s** | **27.1 s** | of which the INSERT of 147,635 answers took **39.1 s → 8.6 s** (`LOAD DATA LOCAL INFILE`); DELETE of the old answers 12.7 s (reloads only) |
| verify | 1.5 s | 1.5 s | |
| profiles + bases | 9.4 s | 9.4 s | |
| harmonise | 5.0 s | 6.9 s | 1,789 concepts read each time |
| **cube** | **31.2 s** | **33.9 s** | 28 `INSERT … SELECT` (7 cuts × single/multi × everyone + 1 cohort), ~0.7 s each server-side; the cells are deleted twice |
| search | 3.2 s | 3.6 s | |
| line-by-line | 12.2 s | 11.3 s | |
| **total** | **141.7 s** | **116.2 s** | 141 → 113 SQL statements; DB time 112.7 → 86.6 s |

The cross-tab workbooks are not a bottleneck. Reading the wave takes 8 s and the three builds take 2.3 s.

Other findings:

* **Log noise.** Every run wrote ~40 Streamlit "No runtime found" warnings, which buried real warnings. Fixed.
* **No structured error record.** Errors existed only as free text in the run log. Fixed: `logs/forsta-etl-errors.jsonl`.
* **`.env` lines 67–69** hold a shell command and a bare secret on its own line. python-dotenv warns on every run
  ("could not parse statement starting at line 67"). Move the value to a named variable, or delete it and rotate it.
* **Redundant index.** `ix_answer_respondent (respondent_id)` duplicates the leading column of `uq_answer`.
  Dropping it changed the insert time within noise (32 s vs 36 s), so it was left alone on the 23 M-row table.
* `scripts/weekly_forsta.py` said "daily 06:00 IST" in its docstring. Corrected.

### 1.4 Relational integrity

Foreign keys (live `cip_stg`): survey → question → item/option → field → answer, respondent → answer / profile /
cohort membership, concept → concept option → concept map, publication → cells, cube → survey/question
(26 FKs). These tables have no FK:

| Table | Why | Now guarded by |
|---|---|---|
| `cip_forsta_survey` | register; a survey exists before its wave | "register row pointing at a missing wave", "register says loaded, wave not verified" |
| `cip_load_log` | history; keeps 10 rows of the two deleted Excel-era waves on purpose | — (history) |
| `cip_tracker_line` | derived, rebuilt per wave | orphan delete + "unqualified or other wave's respondent" |
| `cip_search` | FULLTEXT index table | orphan delete for survey / question / concept |
| `cip_wave_module` | calendar, rebuilt from the register | orphan delete |

Recommended next DDL (needs a quiet window, not done here): `cip_tracker_line.respondent_id → cip_respondent ON
DELETE CASCADE` and `cip_forsta_survey.survey_id → cip_survey ON DELETE SET NULL`.

### 1.5 Validation results (19 Oct 2026)

| Check | Result |
|---|---|
| Wave 412 vs Forsta API, every answer (`reconcile_survey`) | 147,635 checked, **0 differ** |
| Raw Data 10_12_26.xlsx vs warehouse | 404 = 404 qualified uuids, record numbers equal, q1r1 = the same 219 people |
| Cross Tabs 10_12_26.xlsx | 28,080 of 28,080 cells equal (the other 5,560 are paradata: browser, OS, dropout) |
| Holiday Status Cross Tabs | 4,914 of 4,914 cells equal · letters 4,749 / 4,753 |
| Inflation_Sentiment Cross Tabs | 13,338 of 13,338 cells equal · letters 12,851 / 12,901 |
| `python -m etl.integrity --check` | whole (16 checks) |
| `scripts/weekly_forsta.py` end to end | exit 0 in 34 s; 0 noise lines |
| Tests | 238 pass (7 new) |

Two defects in the ETL's cross-tabs came to light and are fixed:

1. The **Inflation Sentiment** banner has two columns labelled "Very" (Higher Inflation, Higher Gas Prices).
   The comparison keyed columns by label, so it only ever checked one of them. It now keys by column letter.
2. A numeric question's **"Don't know"** box (e.g. BDR4, 16 people) was missing from our table. Forsta shows it
   as a row beside the base. It is now there.

---

## 2 · Recommended changes

### 2.1 Done in this change (ready to deploy)

| File | Change |
|---|---|
| `etl/forsta_etl.py` | Answers bulk-loaded with `LOAD DATA LOCAL INFILE`. Any server warning undoes the bulk load and falls back to batched INSERTs, as does a server that refuses LOCAL INFILE. Per-step timings go in the load log line. |
| `app/core/database.py` | `local_infile` enabled for the **etl** engine only; the read-only portal engine is unchanged. |
| `etl/integrity.py` (new) | 16 checks: rebuild a wave's missing derived rows, delete orphan index rows, report base-data problems. `python -m etl.integrity [--check]`. |
| `scripts/weekly_forsta.py` | Integrity after every run (exit **5** if anything stays wrong, then a failure email). JSON error log. Secrets masked in both logs. Streamlit noise off. |
| `etl/crosstab_export.py`, `config/crosstab_banners.yml` | Significance letters (`stat_groups` per banner; Summary shows "95 / 90 (z-test)"). Numeric "Don't know" row. `--compare` checks counts, bases and letters by column letter. |
| `scripts/launchd/com.coresight.cip-forsta-etl.plist` | Catch-up runs at 13:00 and 18:00 IST on the five days without polling. |
| `tests/test_pipeline_hardening.py` | z-test vs the team's letters, stat-group parsing, LOAD DATA escaping, integrity healing, log masking. |
| `tests/conftest.py` | **Bug fixed:** the test suite wrote its fake failures into the real alert throttle (`logs/notify-state.json`), which silenced genuine failure emails for 6 hours after every test run. Tests now use their own file. |

**To deploy the schedule** (installs the repo plist; the job's label is unchanged):

```bash
cp scripts/launchd/com.coresight.cip-forsta-etl.plist ~/Library/LaunchAgents/ && launchctl bootout gui/$(id -u)/com.coresight.cip-forsta-etl; launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.coresight.cip-forsta-etl.plist
```

The workbook layout the manager uses (Summary · Percentages · Counts, the same columns and rows) is unchanged.
The flag column beside each value, which held only `*` / `**` before, now also carries the letters, exactly
where Forsta puts them.

### 2.2 Recommended next (not done)

| # | Change | Expected gain | Effort |
|---|---|---|---|
| 1 | **Run the ETL in Azure**, in the database's region (an Azure Function or WebJob, as `weekly_forsta.py` already allows). Each round trip falls from 263 ms to about 1 ms, the VPN dependency behind the 11, 13, 15, 16 and 18 Oct failures goes away, and the run no longer depends on a laptop being awake. | most of the remaining 87 s of DB time; daily runs no longer missed | medium |
| 2 | Cube: one `INSERT … SELECT … UNION ALL` per cohort instead of 14, and remove the second DELETE in `refresh_wave` → `build_cube`. | ~8–10 s per wave | small |
| 3 | `load_definitions`: read all topics once instead of `ensure_topic` per topic; batch the per-question writes. | ~5 s | small |
| 4 | Reloads: write only changed answers (diff on uuid × field) instead of DELETE + reload. | 12.7 s DELETE + 8.6 s load on reopened waves | medium |
| 5 | Cap retries of a deterministically failing wave (e.g. 6 attempts, then `failed` until a person resets it). With polling every 30 min, a bad payload is otherwise retried ~100 times a week. | quieter failure list | small |
| 6 | Add the two FKs in §1.4. | integrity enforced by MySQL | small, needs a window |

**Configurability.** Recipients (`config/notify.yml`), banners and stat groups (`config/crosstab_banners.yml`),
the line-by-line columns (`config/tracker_line.yml`), topics (`config/survey_map.yml`) and the calendar
(`config/survey_calendar.yml`) are all YAML. Adding a banner or a recipient needs no code. A new survey platform
plugs in at `etl/run_pipeline.py` (shared loader steps), as Qualtrics and SurveyMonkey already do.

---

## 3 · Logging and self-healing

Full design: [`pipeline-resilience.yml`](pipeline-resilience.yml). In short:

* **Record everything.** The run log is human-readable. `logs/forsta-etl-errors.jsonl` holds one JSON object per
  warning or error: run id, step, message, exception class, traceback. `cip_load_log` and
  `cip_forsta_survey.last_error` keep the durable per-wave history.
* **Expose nothing.** Every environment value whose name contains KEY / PASSWORD / SECRET / TOKEN /
  PASSPHRASE / WEBHOOK is replaced with `***` in both logs (tested). Panel IDs are stored only as sha256, and
  browser, URL and session are never stored.
* **Heal what is safe to heal:**

  | Failure | Remedy |
  |---|---|
  | Network blip to the DB | 4 tries, 5 min apart |
  | Forsta 429 / 5xx | exponential retry |
  | Failed wave | reloaded on the next run |
  | Bulk load refused or warned | fallback to INSERTs |
  | Missing cube, search or line-by-line rows | that wave's rows are rebuilt |
  | Orphan index rows | deleted |

* **Never "heal" the data itself.** Duplicate respondents, a register out of step with the waves, a stuck load,
  or a published number that moved are reported (exit 3 / 5, failure email once per 6 h), not changed.

---

## 4 · Excel deliverables: suggestions for the analysts

The sample [`samples/Holiday Status Cross Tabs 10_12_26 - proposed layout.xlsx`](samples/) is built from
wave 412. Its Summary, Percentages and Counts tabs are exactly what is emailed today. It adds:

1. **Index tab.** Every table (58 here) with a link to it and how many significant cells it has, so nobody
   scrolls 1,500 rows to find XM3.
2. **Highlights tab.** The 40 largest gaps significant at 95 %, segment vs segment, linked to their table. The
   questions that define the banner are left out (they differ by construction).
3. **Colour on significance.** Green fill on a cell that beats another column at 95 %, light green at 90 %,
   with a legend on the Summary tab. The letters stay as they are.
4. Also worth doing:
   * a **"vs previous wave" column** on the standard banner (the email already shows q1 / CS1 / CS2 changes)
   * **net rows** (Top-2 / Bottom-2 box) on the 5-point grids (HI4, D34)
   * the **base flag in words** in the header ("N=29 · low base")
   * one workbook per wave with the three banners as **tab groups**, instead of three files

None of this is switched on for the weekly email until the analysts agree. The tab order and layout are kept
unchanged on purpose (no macros or habits broken).

---

## 5 · Further data products

1. **Wave-over-wave trend file.** The cube already holds every wave since Aug 2022 (319 verified waves). A weekly
   "Trends" workbook of the core measures (q1, CS1, CS2, holiday status) × the standard cuts, with
   significance against last week and against the same week last year.
2. **Holiday season tracker.** Season 2026 against season 2025 by wave number (the calendar numbers the waves
   per season). This needs the 2025 holiday waves reactivated in Forsta (8 of 9 hibernated).
3. **Sector deep-dive packs.** Each 12-week rotation's lead sector (Beauty, Home improvement, …) compared with
   its previous run 12 weeks earlier.
4. **Data-quality digest.** Weekly: incidence, median interview time, mobile share, speeders/terminates
   (paradata already loaded), and the integrity result. One page for the manager.
5. **Self-serve.** The portal's Analysis Builder and saved views already cover ad hoc cuts. Publishing the
   Index/Highlights view there means analysts start from the findings, not from 1,500 rows.

---

## 6 · Distribution list: open

`config/notify.yml` sends everything to the ETL developer only (testing). The recipient list in the brief was
left as `[FILL: recipient list]`, so **no analyst or manager addresses were added**. When they are known, fill
`tracker:` (weekly waves), `annual:`, `adhoc:` and `failure:`. No code change is needed. The next tracker wave
(launched Mon 19 Oct) will email whoever is listed when it loads.

---

## 7 · Data location, capture guarantee and recovery (added 19 Oct 2026, late)

### 7.1 Nothing CIP needs is in `dwh_stg` any more

| What | Before today | Now |
|---|---|---|
| CIP tables and views (33 + 9) | moved to `cip_stg` on 14 Oct, dropped from `dwh_stg` on 15 Oct | unchanged |
| Qualtrics / SurveyMonkey **source** (`dwh_sm*`, 7 tables, 5.78 M rows) | still in `dwh_stg`; `cip_stg` read 6 of them through pass-through views | **real tables in `cip_stg`** (`scripts/move_legacy_source.py`): copied inside MySQL at READ COMMITTED, every table's `COUNT(*)` and `CHECKSUM TABLE` equal to the source, then swapped in place of the views |
| `cip_stg` objects reading `dwh_stg` | 6 views | **none** |

Proof the legacy path still works on the local copy: Qualtrics waves 2025-04-21 (316/316 answers) and 2025-04-14
(301/301), and SurveyMonkey 2022-07-25 (185/185), reconcile equal to the `cip_stg` source.

Still in `dwh_stg`, and not CIP's to remove: the original `dwh_sm*` tables, which another process owns (someone
wrote to `dwh_smquestion` at 00:49 today; our account is read-only there). Other projects' tables
(`circana_survey_*`, `dwh_survey*`) are there too. Dropping the `dwh_sm*` originals needs the DWH owner's
agreement and an account with DROP rights; CIP no longer needs them.

### 7.2 Every survey is captured, or flagged

| Risk | Guard |
|---|---|
| A survey closes while the Mac is off | launchd runs a missed slot on wake; polling every 30 min Mon 20:00 – Wed 23:30, and 3 times a day otherwise |
| The DB or VPN is down | 4 tries, 5 min apart, then the next slot (now at most ~5 h away) |
| A load fails | reloaded on every run until it loads; failure email |
| A closed survey is still not loaded after 3 days | integrity **base** check → exit 5, failure email |
| A survey was hibernated before it was loaded | integrity **watch** check, logged every run: **51 surveys today**. Reactivate one in Forsta and the next run loads, verifies and emails it with no code change (discovery marks it due) |
| Forsta stops listing a survey we never loaded | integrity **watch** check |
| The warehouse is damaged or lost | weekly proven backup (§7.4), plus Forsta still holds every survey it hasn't hibernated |

The pipeline cannot recover the 51 hibernated surveys by itself: reading them needs a reactivation in Forsta, and
the pipeline never writes to Forsta (standing rule). Ask Forsta about retention (email of 19 Oct), then reactivate
in small batches and let the scheduled run load them.

### 7.3 Analyst-ready views (`sql/002_views.sql`)

| View | Grain | Today |
|---|---|---|
| `v_cip_wave` | one row per verified wave: platform, study type, family, title, dates, lead module, qualified n, questions | 319 waves (32 Forsta, 142 Qualtrics, 145 SurveyMonkey) |
| `v_cip_respondent` | one row per qualified respondent: wave, demographics (gender, age, generation, ethnicity, income, region, urbanicity, politics, outlook), interview time, device | 166,959 |
| `v_cip_answer_long` | one row per answer: wave, respondent, main cuts, question, **harmonised concept** (`concept_code`, mapping status), row, answer code / label / number / verbatim | wave 412: 94,677 answers, all with a concept, 3.1 s |

Every platform has the same shape and plain column names. Only verified waves and qualified respondents are
included. Follow a question across years by `concept_code`. Filter `v_cip_answer_long` by `survey_id`,
`wave_date` or `concept_code`.

### 7.4 Backup and restore

`scripts/backup_db.py` makes one consistent `mysqldump --single-transaction`. The file counts only when it is
proven: gzip intact, the dump completed, every table and view present, and each table's row count equal to the
live count. It keeps the newest 4. If `CIP_BACKUP_COPY_DIR` is set (e.g. a OneDrive folder), it also copies the
proven file there. It runs weekly (Sunday 10:00 IST) via `scripts/launchd/com.coresight.cip-backup.plist`.
The first proven backup was taken on 19 Oct 2026 22:34: 33/33 tables, 25.8 M rows.

**Restore** (into a new database first, never over the live one):

```bash
gunzip -c backups/cip_stg-YYYYMMDD-HHMM.sql.gz | mysql --defaults-extra-file=<0600 file with host/user/password/ssl-ca> cip_stg_restore
```

Then check it, point `STG_DB_NAME` at it (or rename), run `python scripts/weekly_forsta.py` to load anything
newer from Forsta, and `python scripts/reconcile.py` to prove every wave against its source.
