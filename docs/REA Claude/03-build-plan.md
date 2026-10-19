# 03 · Build plan

**Principle:** the data core is correct and verified, so keep it. Spend the next weeks on the four things that can hurt the business today:
- missing data,
- a leaked or over-broad credential,
- silent pipeline failures,
- a production job that only one laptop can run.

The front-end rewrite is a separate decision. It has a gate, and this plan says what has to be true before opening it.

Gap IDs refer to [02-identified-gaps.md](02-identified-gaps.md). Effort is in focused engineer-days (d) and assumes one engineer, who is the current owner.

## Phase 0: stop the exposure (day 1, about 0.5 d)

| # | Task | Closes | Exit check |
|---|---|---|---|
| 0.1 | Rotate the password for the `10.2.1.9` account, the value on `.env` line 70. Delete `.env` lines 68–70. Keep one `FORSTA_API_KEY`. | G-01, G-06 | `python -c "import app.core.config"` prints no dotenv warning |
| 0.2 | Redact the password in `docs/REA Gemini/05-…LEDGER.md` and `docs/LLM Council Gemini/advisors/01-the-contrarian.md` | G-01 | `grep -r` for the old value over the repo returns nothing |
| 0.3 | Make `saeedafri/consumer-insight-portal` private. Untrack `logs/`. | G-05 | `gh api repos/… --jq .private` → `true` |
| 0.4 | The owner reviews and commits the working tree, including `etl/integrity.py`, `scripts/backup_db.py` and its plist | G-04 | A fresh clone runs `scripts/weekly_forsta.py --help` (or the test suite) |

## Phase 1: recover the missing data (week 1, about 1 d engineering plus Forsta admin time)

| # | Task | Closes | Exit check |
|---|---|---|---|
| 1.1 | A Forsta admin reactivates or exports the 51 hibernated surveys, starting with the 43 tracker waves. Automation stays GET-only, per the standing rule. | G-02 | Register shows `hibernated` = 0 or only non-tracker studies; the next run loads them |
| 1.2 | Turn "closed survey hibernated before load" from a watch item into a failure (exit 5, alert). Add a coverage check: every Monday since the first Forsta wave has one verified tracker wave. | G-02 | `integrity --check` exits non-zero while any tracker week is missing |
| 1.3 | Correct the README and business docs to describe actual coverage | G-29 | README numbers come from a query script |

*Reason:* the data is the asset. Each week the hibernated surveys sit there, the risk grows that Forsta's retention policy removes them. [U] The real policy: surveys older than 460 days are still listed, so the documented "365 days" is not borne out.

## Phase 2: make failures loud (week 1–2, about 2 d)

| # | Task | Closes |
|---|---|---|
| 2.1 | In `conftest.py`, add an autouse fixture that stubs `notify.send` and `notify.teams` | G-09 |
| 2.2 | Save the throttle state only after a successful send, and put the problem count in the subject | G-07 |
| 2.3 | Wrap `run()` in one handler: log masked, write the jsonl record, call `notify.failure`, return 1 | G-08 |
| 2.4 | `GET_LOCK('cip_etl', 0)` run lock | G-16 |
| 2.5 | Narrow the `insert_answers` fallback to errors 1148 and 3948 | G-17 |
| 2.6 | Keep a good wave `verified` when a reload fails after the write | G-18 |
| 2.7 | Cap retries for failed surveys (3 attempts, then a daily retry) | G-19 |
| 2.8 | DB `read_timeout` and `write_timeout` | G-20 |
| 2.9 | Heartbeat: alert if there has been no successful run in 26 h. This catches the silent mid-retry deaths of 14 and 16 Oct. | G-14 |

Each of these is a few lines and comes with one test. **Exit check:** pytest passes with notify stubbed, and a forced exception in `discover()` produces one email and exit 1.

## Phase 3: least privilege and schema correctness (week 2, about 2 d)

| # | Task | Closes |
|---|---|---|
| 3.1 | Rewrite `sql/004_grants.sql` with real grants:<br>• `cip_etl`: ALL on `cip_stg.*`;<br>• `cip_app`: SELECT on `cip_stg.*`, plus INSERT/UPDATE/DELETE on `cip_auth_session`, `cip_saved_view` and `cip_concept_map`. | G-11 |
| 3.2 | Create both accounts and set `APP_DB_USER`. Change `config.py` to refuse to start without it outside LOCAL, and route portal writes through `cip_app` rather than `get_engine("etl")`. | G-03 |
| 3.3 | Recreate the 12 views with a service DEFINER or `SQL SECURITY INVOKER`, and add the `load_status='verified'` filter to the 8 views that lack it | G-03, G-13 |
| 3.4 | Escape the apostrophe at `001_schema.sql:759`. Add a CI step that applies `001`–`004` to a throwaway MySQL 8 container. | G-12 |
| 3.5 | Drop `ft_answer_text` and `ix_answer_respondent` through `schema_upgrade.DROP_INDEXES` | G-34, G-36 |
| 3.6 | Re-key `respondent_key` as an HMAC with a pepper (one migration) | G-26 |
| 3.7 | Make the human-work FKs (`cip_saved_view`, `cip_concept_map`) `ON DELETE RESTRICT` | G-32 |
| 3.8 | Fix `.env.example` (`cip_stg`). Delete `drop_cip_from_dwh_stg.py`. | G-30, G-31 |

## Phase 4: move ingestion off the laptop (weeks 3–4, about 3–4 d)

| # | Task | Closes |
|---|---|---|
| 4.1 | A container image for `scripts/weekly_forsta.py` (Python 3.13-slim plus `requirements.txt`) | G-14 |
| 4.2 | An Azure Container Apps **job** on a UTC cron that matches the launchd slots. It reads secrets from Key Vault and reaches MySQL over a private endpoint or VNet rule, which removes the public-IP firewall dependency. | G-14, G-43 |
| 4.3 | Move backups to Azure: the Flexible Server's own automated backups, plus a weekly `mysqldump` from the job to blob storage | G-28 |
| 4.4 | Run the cloud job and launchd in parallel for 2 weeks, then turn launchd off | — |

*Why not sooner:* Phases 0–3 are hours each and remove the immediate risks. This phase needs IT (VNet, Key Vault, subscription access); start that request on day 1.

## Phase 5: portal hardening while it stays internal (weeks 3–5, about 3 d)

| # | Task | Closes |
|---|---|---|
| 5.1 | `APP_ENV` defaults to PROD, so auth fails closed | G-10 |
| 5.2 | Escape Excel formulas in `export.py` | G-15 |
| 5.3 | Replace the shared passphrase with Streamlit's built-in `st.login` (OIDC against Coresight's IdP) and add a sign-out link. Until then, add an attempt counter. | G-21, G-24 |
| 5.4 | Session check fails closed; `secure=True` on the cookie | G-23 |
| 5.5 | `AUTH_ADMIN_EMAILS` for Mappings and Publications | G-22 |
| 5.6 | Small-cell suppression (n < 30) in Analysis and its exports | G-25 |
| 5.7 | `max_entries` on every cache; fix the label slips | G-35, G-39 |
| 5.8 | Auto-confirm `exact_text` concept matches above the threshold to shrink the 2,625-row queue | G-27 |

## Gate: the front-end rewrite (React + FastAPI, docs/13)

Open this only when **all** of these are true. Each one is a fact to establish, not an opinion:

1. **External users are confirmed:** a client, a contract, a launch date. docs/12 and docs/13 are both marked *proposed*.
2. **Concurrency is the real limit.**
   - CIP's own measurement on Streamlit is 0.56 / 1.16 / 1.99 / **4.36 s** median as load rises to 20 users (docs/12:194). The 6.3–61.8 s figures are MIP's, not CIP's.
   - docs/12 itself says "Streamlit written well" is acceptable for internal tools under about 10 concurrent users.
3. **Phases 0–4 are done.** A faster UI over a data set with gaps and a laptop scheduler only fails faster.
4. **The client legal question is answered:** panel licence terms for showing respondent-level data to external parties.

If the gate opens, docs/13 is a reasonable design: React 19 + Vite SPA, FastAPI, the cube as the read model. Start with the two screens external users need, Trends and Crosstab with export. Leave Mappings, Data Health and Publications on Streamlit for staff, as docs/13:93-96 already says.

## Summary timeline

| Week | Work | Engineer-days |
|---|---|---|
| Day 1 | Phase 0 | 0.5 |
| 1 | Phase 1 (recovery) and Phase 2 (alerting) | 3 |
| 2 | Phase 3 (privilege and schema) | 2 |
| 3–4 | Phase 4 (cloud job) and Phase 5 (portal) | 6–7 |
| Then | Gate review for the front end | — |

Total: about 12 engineer-days to a pipeline that nobody's laptop runs, alerts reliably, holds every wave, and uses least-privilege accounts.
