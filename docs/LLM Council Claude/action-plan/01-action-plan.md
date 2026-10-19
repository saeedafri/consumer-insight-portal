# Action plan: council-amended

This is the REA Claude build plan ([`docs/REA Claude/03-build-plan.md`](../../REA%20Claude/03-build-plan.md)), re-ordered and amended by the chairman verdict.

**Who does each item:**
- **H:** a human or admin action; it cannot be scripted, and Forsta stays GET-only for automation.
- **E:** engineering.

## Today, Tue 20 Oct 2026

| # | Who | Action | Gap |
|---|---|---|---|
| 1 | H | **Send a written request to the Forsta admin** to reactivate or export the 51 hibernated surveys (43 tracker waves first), with a reply-by date. Ask about cost and the real retention policy in the same request. | G-02, CG-01, CG-08 |
| 2 | H | Rotate the password for the `10.2.1.9` account (the value on `.env` line 70), then pull the access logs for that account | G-01, CG-03 |
| 3 | E | Redact the password in `docs/REA Gemini/05-…LEDGER.md` and `docs/LLM Council Gemini/advisors/01-the-contrarian.md`. Delete `.env` lines 68–70. Keep one `FORSTA_API_KEY`. | G-01, G-06, CG-09 |
| 4 | H | Make `saeedafri/consumer-insight-portal` private | G-05 |
| 5 | H | The owner reviews and commits the working tree, including `etl/integrity.py`, `scripts/backup_db.py` and its plist | G-04 |
| 6 | E | Copy `backups/cip_stg-20261019-2356.sql.gz` off the laptop | G-28, CG-10 |

## Week 1, to Fri 30 Oct (engineering, about 3 d)

- Make `integrity` **fail** (exit 5) on a hibernated-never-loaded survey, and add a check that every Monday has a verified tracker wave. (G-02)
- Stop pytest sending real alerts (autouse fixture). (G-09)
- Save throttle state only after a successful send. (G-07)
- One crash handler around `run()`. (G-08)
- Add a run lock (G-16), retry cap (G-19) and DB timeouts (G-20).
- 26-hour heartbeat alert. (G-14)
- Narrow the LOAD DATA fallback (G-17). Keep a good wave visible when a reload fails (G-18).

## Week 2, to Fri 6 Nov

- **E:** load the recovered waves. Reconcile each against Forsta. Recompute the cube and concepts. Re-run `etl.tracker_line --compare`. (CG-05)
- **E:** real grants (`004_grants.sql`), plus `cip_app` and `cip_etl` accounts. `APP_DB_USER` is required outside LOCAL. Views get a service DEFINER and the `verified` filter. (G-03, G-11, G-13)
- **E:** fix the `001_schema.sql:759` apostrophe and add a MySQL-in-CI schema apply (G-12). Fix `.env.example`. Delete `drop_cip_from_dwh_stg.py`. (G-30, G-31)
- **H:** name a second operator and walk them through the runbook. (CG-04)

## Weeks 3–4, to Fri 20 Nov (engineering)

- Container image plus an Azure Container Apps job on a UTC cron, using Key Vault secrets and a **private endpoint** to MySQL. (G-14)
- Run it in parallel with launchd for one week of clean runs, then retire launchd.
- Move backups to Flexible Server backups plus a weekly dump to blob storage. (G-28)

## Week 5, to Fri 27 Nov

- **E:** `APP_ENV` defaults to PROD (G-10). Excel formula escaping (G-15). Streamlit `st.login` OIDC and a sign-out link (G-24). Session check fails closed (G-23). Admin allowlist for Mappings and Publications (G-22).
- **H (legal):** a written answer on panel-licence terms for showing or reselling data externally. (CG-06)

## Gate review: Tue 1 Dec 2026 (owner plus sponsor)

Open the React/FastAPI rewrite (docs/13) only if **all** of these hold:

1. A named external client has signed or sent a letter of intent.
2. Licence rights are cleared.
3. The ETL has run 3+ weeks off the laptop with no silent failures.
4. Measured concurrency exceeds about 10 users.

If any condition fails, record why and set the next review no later than **2 Mar 2027**.

## Plain-language glossary (the Outsider's ask)

| Term | Meaning |
|---|---|
| **Hibernated survey** | Forsta puts a finished survey to sleep after a few months. Its data can't be read until someone wakes it up by hand. |
| **Integrity check** | The automatic end-of-run test that the warehouse is complete and consistent. Today it misses the sleeping surveys. |
| **Harmonised concept** | The same question asked in different waves or tools, linked together so it can be trended. |
| **Small-cell suppression** | Hiding numbers based on very few people, so nobody can be singled out. |
| **Panel-licence terms** | The contract that says what Coresight may do with answers from the panel company's respondents. |
