# 02 · Identified gaps

There are 44 items, ranked by severity. Each one carries the evidence behind it and the smallest fix that closes it. Markers: [O] observed, [I] inferred, [U] unknown. Evidence IDs (`E-xx`) refer to [05-evidence-ledger.md](05-evidence-ledger.md).

Severity means what happens if nothing is done:
- **Critical:** data loss, a leaked credential, or a system nobody else can run.
- **High:** wrong numbers, missed alerts, or an exploitable weakness.
- **Medium:** fragile or misleading behaviour.
- **Low:** hygiene.

## Critical

| ID | Gap | Evidence | Smallest fix |
|---|---|---|---|
| **G-01** | **A live DB password is written into Gemini's docs.** The value on `.env` line 70 appears in `docs/REA Gemini/05-…LEDGER.md` and `docs/LLM Council Gemini/advisors/01-the-contrarian.md`. Both files are untracked, and the repo is **public**. | [O] E-01, E-02 | Rotate that password on `10.2.1.9` and redact both files before anything in `docs/` is committed. Make the repo private (see G-05). |
| **G-02** | **About 50 of the 75 tracker weeks since May 2025 are not in the warehouse.**<br>• 51 closed Forsta surveys are `hibernated` with `survey_id IS NULL`: 43 tracker waves (Jul 2025 – Jun 2026) plus annual and client studies.<br>• `integrity.py` reports them only as a "watch" item, so runs exit 0.<br>• The business docs still say "every wave". | [O] E-10, E-11; memory note of 20 Oct | A person must reactivate or export them in Forsta; automation stays GET-only. Then make the hibernated-and-never-loaded case a **fail** (exit 5) rather than a watch, so it shows up as red. |
| **G-03** | **The portal runs with the owner's personal, all-privileges account.**<br>• `APP_DB_USER` is empty, so `config.py:140-143` falls back to the writer credentials.<br>• Live `CURRENT_USER()` for the "app" engine returns `mohdsaeedafri@%`.<br>• All 12 views have DEFINER `mohdsaeedafri@%`.<br>• The portal also writes through `get_engine("etl")` (auth, saved views, cube, cohorts, publications). | [O] E-12, E-13, E-16 | Create two service accounts: `cip_app` with SELECT plus INSERT/UPDATE on 3 tables, and `cip_etl` for the ETL. Fix `004_grants.sql` (G-11), then recreate the views with `SQL SECURITY INVOKER` or a service DEFINER. Make `config.py` **refuse** to start without `APP_DB_USER` outside LOCAL. |
| **G-04** | **Production runs code that is not in git.**<br>• The scheduled `weekly_forsta.py` (modified) imports `etl/integrity.py` (untracked).<br>• `scripts/backup_db.py` and its plist are untracked.<br>• 11 tracked files are modified.<br>• A clone of `master` cannot run the job that runs every 30 minutes. | [O] E-14 | The owner reviews and commits the working tree (the standing rule says Claude does not commit). Then run the scheduled job from a clean checkout. |

## High

| ID | Gap | Evidence | Smallest fix |
|---|---|---|---|
| G-05 | **The repo is public.** It exposes:<br>• the Azure MySQL host and internal IP `10.2.1.9`;<br>• internal design docs and business numbers;<br>• personal paths in the plists, including a OneDrive path;<br>• a personal email in `config/notify.yml:5`.<br>`logs/notify-state.json` is tracked. | [O] E-03 | Make it private now, then untrack `logs/`. |
| G-06 | **`.env` hygiene problems.**<br>• Line 68 is a pasted shell command, `mysql -h 10.2.1.9 -u … -p`.<br>• Line 70 is a bare password with no `=`, which makes python-dotenv warn on every run (it reports the statement as starting at line 67).<br>• `FORSTA_API_KEY` is defined twice (lines 48 and 66) with **different** values; the later one wins silently. | [O] E-04 | Delete lines 68–70 and keep one `FORSTA_API_KEY`. Record whose Forsta account owns the working key. [U] Whether it is a service account. |
| G-07 | **The alert throttle marks an alert as "told" before trying to send it** (`notify.py:287-300`). A failed SMTP send silences that alert for 6 h. The fixed subjects "integrity check" and "published numbers moved" also hide a *new* problem for 6 h. | [O] E-21 | Record the state only after `send()` returns True. Put the problem count in the subject. |
| G-08 | **A crash after the healthcheck exits 1 with no alert.** Uncaught errors in `discover`, `client.surveys`, the `run_due` query, `integrity.found` and `drift_summary` produce a traceback only. It is unmasked, missing from `errors.jsonl`, and no email goes out. | [O] E-20 | Wrap the body of `run()` in one `try/except Exception` that logs, masks, calls `notify.failure` and returns 1. |
| G-09 | **Running pytest sends real email and Teams messages.**<br>• The `weekly.run()` tests don't stub `notify.send` or `notify.teams`.<br>• `conftest.py` only redirects the throttle file, and `.env` has live SMTP and webhook values.<br>• Test subjects appear in `logs/notify-state.json` (17 Oct 22:38). | [O] E-22 | Add an autouse fixture in `conftest.py` that monkeypatches `notify.send` and `notify.teams` to no-ops. |
| G-10 | **Auth fails open when `APP_ENV` is unset or misspelled.** It defaults to LOCAL (`config.py:103,110`). With `DEBUG=1` everyone becomes `local@test.com` (`auth.py:258`, `:371-379`). `docs/08:20-22` claims the opposite. | [O] app audit | Default to PROD. Accept LOCAL only when it is set explicitly. |
| G-11 | **`sql/004_grants.sql` cannot work.** In MySQL, `` `cip_stg`.`cip_%` `` means a literal table named `cip_%`; wildcards apply to database names only. It also omits CREATE VIEW, DROP, CREATE TEMPORARY TABLES and SELECT on `dwh_sm*`. | [O] schema audit | Grant on `cip_stg.*` for the ETL account, and per table for the app account. |
| G-12 | **A fresh MySQL install fails.**<br>• `sql/001_schema.sql:759` has an unescaped apostrophe in a table COMMENT (`'The data team's …'`).<br>• `init_db.py` stops there, so `cip_wave_module`, the views and the seeds are never created.<br>• The SQLite tests strip comments, so they pass. | [O] schema audit | Escape the apostrophe (`''`). Add a test that runs `001`–`003` through a MySQL parser, or a CI job with a MySQL container. |
| G-13 | **8 of 12 views don't filter to verified waves.** This includes `v_cip_trend`, which the Trends page reads (`5_Trends.py:101`). A wave left `failed` or mid-reload `loading` appears in trends, with its answers already committed. | [O] schema audit | Add `JOIN cip_survey … AND load_status='verified'` to each view. |
| G-14 | **Ingestion depends on one laptop and its public IP.**<br>• The DB timed out on 11, 13, 15, 16 and 18 Oct.<br>• Two runs died mid-retry with no closing line and no alert.<br>• The Mac must be awake and on the VPN or whitelisted. | [O] E-15 | Short term: `caffeinate`/power settings, plus a heartbeat alert if no successful run in 26 h. Long term: an Azure Container Apps job with a private endpoint (build plan Phase 4). |
| G-15 | **Excel formula injection.**<br>• Respondents' free-text answers are written to `.xlsx` as-is (`app/components/export.py:85`).<br>• openpyxl turns any string starting with `=` into a formula.<br>• A panel respondent could plant `=HYPERLINK(...)` in an analyst's export. | [O] app audit | Prefix values that start with `= + - @` with `'` before writing. |

## Medium

| ID | Gap | Evidence | Smallest fix |
|---|---|---|---|
| G-16 | No run lock. A manual `--due` or a hand-run job can overlap a launchd run and load the same wave twice (status flip-flops, deadlocks, duplicate emails). | [O] E-20 | `SELECT GET_LOCK('cip_etl', 0)` at the start of `run()`. |
| G-17 | `insert_answers` treats **every** `OperationalError` as "local_infile is off" (`forsta_etl.py:334`). After a deadlock rollback, the fallback INSERTs commit without the preceding DELETE. | [O] E-20 | Fall back only on MySQL errors 1148 and 3948; re-raise everything else. |
| G-18 | A failed *reload* hides a good wave. Status goes to `loading` first; any later failure, even in the cube or search step, leaves it `failed`. | [O] E-20 | Flip to `loading` only inside the `_write` transaction. If a derived step fails, restore `verified` and alert. |
| G-19 | Failed surveys are retried every run with no limit. A permanent 403 means a full fetch every 30 min, exit 1, and an email every 6 h. | [O] E-20 | Add `attempts` to `cip_forsta_survey` and back off after 3 attempts. |
| G-20 | No database read timeout. A hung query blocks the run, and launchd skips the slots that follow. | [O] E-20 | Add `read_timeout` and `write_timeout` to `connect_args`. |
| G-21 | **Identity is self-asserted.** One shared passphrase lets the holder sign in as any allowlisted address, with no rate limit. Saved views are deletable by email alone. | [O] app audit | Per-user credentials or SSO (G-24). Add a basic attempt counter until then. |
| G-22 | No roles. Any signed-in user can confirm or reject mappings, which changes every trend, and can publish tables. | [O] app audit | Add an `AUTH_ADMIN_EMAILS` allowlist for Mappings and Publications. |
| G-23 | The session cookie is set by JavaScript, so it is neither HttpOnly nor Secure. The live-session check **fails open** when the DB is unreachable (`auth.py:183-186`). | [O] app audit | Fail closed. Pass `secure=True`. HttpOnly needs a server-set cookie, which Streamlit cannot do (see docs/12 §5.1). |
| G-24 | **SSO is advertised but not implemented.** `sign_in_oidc` is called only from tests, and the login link has no client_id, state or PKCE. There is no logout control. | [O] app audit | Use Streamlit's built-in `st.login` (OIDC) or remove the button. Add a sign-out link that calls `auth.logout()`. |
| G-25 | **Small groups exposed.** Analysis shows counts down to n=1 with only a warning. Combining state, income, ethnicity and generation can single out a respondent. Verbatim dumps are open to every user. | [O] app audit | Suppress cells with base < 30, as `publications.py:79-83` already does. |
| G-26 | `respondent_key` is an **unsalted** SHA-256 of the panel RID, so it can be reversed by brute force if the RID space is small. It is exposed in `v_cip_respondent`. | [O] E-20, schema audit | Use HMAC with a secret pepper. Rehash in one migration, because it is only a join key. |
| G-27 | 2,625 concept-map rows are `proposed`, so trends silently miss those questions until a person reviews them. | [O] E-16 | Auto-confirm the `exact_text` matches above a threshold and leave the rest for review. |
| G-28 | **Backup gaps.**<br>• The OneDrive copy did not happen on the 20 Oct run.<br>• A copy failure dies without an email.<br>• The proof step takes about 41 min (a Python byte loop).<br>• The script and its plist are untracked. | [O] E-17 | Alert on copy failure. Use `gzip -t` for the proof. |
| G-29 | **Stale headline docs mislead reviewers.**<br>• The README still says 10.4 M answers, 144 waves, 828 concepts, 985 matches and "key rejected (401)".<br>• `docs/14` says 26 FKs and 16 checks; live has 39 and 19.<br>• The schema header says 29 tables.<br>• The data dictionary lists 9 views.<br>Gemini copied several of these as facts. | [O] E-16 | Regenerate the README table from a query script, the way `scripts/data_dictionary.py` already does. |
| G-30 | `.env.example:17` still says `STG_DB_NAME=dwh_stg`. A new setup would write to the shared warehouse, which the standing rule forbids. | [O] schema audit | Change it to `cip_stg`. |
| G-31 | `scripts/drop_cip_from_dwh_stg.py` is the only remaining path that writes to dwh_stg. It drops objects with FK checks off, and its guard compares row counts only. | [O] schema audit | The move is done (15 Oct), so delete the script. |
| G-32 | `ON DELETE CASCADE` from `cip_survey` reaches saved views and confirmed mappings, including the reviewer's name. A manual survey delete wipes human work across about 12 tables. | [O] schema audit | Make human-work tables `ON DELETE RESTRICT`, or soft-delete with the `superseded` status (defined but unused). |
| G-33 | `v_cip_item_incidence` builds its `reached` CTE over all of `cip_answer` per query. | [O] code / [U] needs EXPLAIN | EXPLAIN it on live. Prefer the cube. |
| G-34 | An unused FULLTEXT index `ft_answer_text` sits on the 23 M-row `cip_answer` and is rebuilt on every reload (about 150k rows). | [O] E-16, schema audit | Drop it. Search uses `cip_search`. |
| G-35 | Unbounded Streamlit caches: `search` (free text), `analyse` and `cohort_size` (filter sets), and `wave_report` (all verbatims). This is the same pattern docs/12 blames for SIP's memory problems. | [O] app audit | Add `max_entries` to every `st.cache_data`. |

## Low

| ID | Gap | Evidence | Smallest fix |
|---|---|---|---|
| G-36 | `ix_answer_respondent` duplicates the leading column of `uq_answer`. docs/14 measured no material gain from dropping it (32 s vs 36 s), so it was kept. | [O] E-16 | Drop it in the same window as G-34, through `schema_upgrade.DROP_INDEXES`. |
| G-37 | Case- and accent-insensitive collation on code keys, combined with `INSERT IGNORE` into `cip_field`. Two column labels differing only by case would be silently merged. | [O] code / [U] whether any wave has such labels | Use a binary collation on the code columns. |
| G-38 | The saved-view unique key lacks `survey_id`, so saving the same name on another wave overwrites the first. | [O] app/schema audit | Add `survey_id` to the key. |
| G-39 | **Label and denominator slips.**<br>• "Median interview" shows the mean.<br>• "Six largest segments" are actually the alphabetically first six.<br>• The multi-select donut shows share of mentions, not of people.<br>• A null break value drops people from the base. | [O] app audit | Fix each label or calculation. |
| G-40 | `FORSTA_MAX_RETRIES` is ignored; the client hardcodes 4 attempts. | [O] E-20 | Read the setting. |
| G-41 | `scripts/reconcile.py` counts a hibernated survey as "0/0 match" and exits 0. | [O] E-20 | Return non-zero on `ForstaError`. |
| G-42 | The crosstab and weight tables are empty. `docs/02:157` claims the views apply weights; none do. | [O] E-16 | Fix the doc. Keep the tables until imported crosstabs or weighting are needed. |
| G-43 | launchd runs in local time, not pinned to IST. The docstrings describe an old schedule. | [O] E-20 | Document it. Moving to the cloud (G-14) replaces this with a UTC cron. |
| G-44 | `local_infile=True` is set on the whole ETL engine. | [O] E-20 | Acceptable with TLS and CA verification. Scope it to a separate engine if one is ever added. |

## What is solid (not gaps) [O]

- **Verification:** per-wave count verification before the wave becomes visible, plus answer-level reconciliation. docs/14 reports 147,635/147,635 for wave 412; not re-run here.
- **Tests:** 238 passing.
- **SQL injection:** none found anywhere. Every f-string interpolates allowlisted identifiers only.
- **XSRF:** Streamlit's XSRF protection is on.
- **Forsta access:** GET-only Forsta client.
- **Two bases:** routed questions keep both the segment size and the answering base.
- **Bulk load:** `LOAD DATA LOCAL INFILE` with a warning check and a batched-INSERT fallback.
- **Backups:** dump, prove, rotate.
