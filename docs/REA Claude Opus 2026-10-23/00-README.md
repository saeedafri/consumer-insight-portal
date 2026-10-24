# REA Claude Opus · CIP launch-readiness reverse engineering (23 Oct 2026)

This is a bottom-up reverse engineering of the Consumer Insight Portal. It covers the Forsta and legacy sources, the ETL, MySQL `cip_stg`, the FastAPI backend, the React + Vite UI, the live public link, and 35+ competitors. It was done independently of the earlier `REA Claude`, `REA Codex` and `REA Gemini` folders. Each area report re-checks every earlier gap and marks it fixed, open or wrong.

## Verdict

**Not ready for an external client launch. Close to ready for an internal pilot.**

The core data is right:
- 371 waves are verified, and bases match a recount.
- 3 waves reproduce cell for cell from raw answers.
- The 84 Forsta waves agree with Forsta.
- The schema has no drift.
- Reads take milliseconds.
- 290/290 tests pass.

What blocks a client launch is everything around the data:
- **Sign-in:** anyone with the link gets in, as anyone.
- **Repo and database account:** the repo is public and contains a DB password, and the app uses a personal all-privileges account.
- **Hosting:** production is a MacBook behind a quick tunnel.
- **Wrong cells:** 766 cells are wrong in 8 legacy waves.
- **Statistics and method:** significance rules contradict each other, and the methodology is undisclosed.
- **Access control:** there is no tenancy, so client-commissioned studies are visible to all users.

## Files

| File | What it is |
|---|---|
| [01-gap-register.md](01-gap-register.md) | **Start here.** 38 consolidated gaps in tiers L0 (blocker) to L3 (strategic), each mapped to raw IDs and the smallest fix |
| [10-etl-pipeline.md](10-etl-pipeline.md) | Extraction, transformation, load and publish, with a diagram; correctness hunt with SQL; ETL-01 to ETL-25 |
| [20-database.md](20-database.md) | Live `cip_stg` inventory, ER diagram, EXPLAIN of hot queries, optimisation, integrity and data-quality checks; DB-01 to DB-16 |
| [30-backend-api.md](30-backend-api.md) | 36-route table, request lifecycle, live probes, security and performance; API-01 to API-19 |
| [40-frontend-ui.md](40-frontend-ui.md) | REA bundle analysis, source-to-bundle match, screen-by-screen live walkthrough (32 screenshots in `screens/`), statistics maths, accessibility; UI-01 to UI-25 |
| [50-ops-security-stack-profile.md](50-ops-security-stack-profile.md) | Stack, hosting reality, secrets, CVEs, tests and CI, user-profile and entitlement privacy; SEC, OPS and PRF items |
| [60-competitors-and-market-gaps.md](60-competitors-and-market-gaps.md) | Teardowns of 35+ US, international and India vendors, feature matrix, where CIP wins, MKT-01 to MKT-27 |
| [60-competitor-sources.json](60-competitor-sources.json) | 57 sources with URL, retrieval date and claim |

## How the product works (one paragraph per layer)

1. **Extraction:**
   - Every 30 min on planned Mondays and once on Fridays, launchd on the Mac runs `scripts/weekly_forsta.py`.
   - It polls the Forsta API (GET only, no webhooks) and finds closed or fielded surveys.
   - It fetches the datamap and responses.
   - History from 2018 comes from the `dwh_sm*` Qualtrics/SurveyMonkey copies (`etl/legacy_dwh.py`).
2. **Transformation:**
   - Survey type and topics come from `config/survey_map.yml`.
   - Questions, items and options are normalised into `cip_question`/`cip_item`/`cip_option`, and answers into a tall `cip_answer` table, with `respondent_key` as a hashed panel ID.
   - Respondent profiles are derived.
   - Harmonisation proposes concept mappings across waves.
   - The cube pre-aggregates every question × demographic cut.
   - `tracker_line` reproduces the team's line-by-line workbook.
3. **Load:**
   - LOAD DATA bulk insert runs inside a per-wave transaction.
   - A count gate (Forsta total and qualified = stored) sets `load_status='verified'`.
   - Then the cube, search, `srv_wave`/`srv_result`/`srv_answer` serving tables and topic dashboards are built.
   - `etl/publish.py` writes gzip JSON books, trends and cut tables to `data/published` as atomic, hard-linked versions.
4. **Database:**
   - The database is MySQL 8.0 on Azure with 11.9 GB in `cip_stg`.
   - Raw answers are the bulk.
   - The serving tables are primary-key-shaped for single-survey reads.
5. **Backend:**
   - `api/main.py` (FastAPI, uvicorn) serves `web/dist` and the published files with ETag/gzip.
   - It computes two-cut cross-tabs in memory from the cut files.
   - FTS5 search, boards, audiences, alerts and team views run against MySQL.
   - Ask CIP is a cited Claude call over the latest wave.
   - Exports are CSV, XLSX and PPTX.
6. **Frontend:**
   - React 19 + Vite + ECharts, as a lazy-loaded SPA.
   - Screens: Library, Search, Overview, Questions, Cross-tab, Trends, Compare, Changes, Audience, Boards, Ask, Schedule and What's new.
   - The statistics are computed client-side (`stats.ts`, `moves.ts`).
7. **Runtime today:**
   - uvicorn runs on `127.0.0.1:8000` on this Mac, behind a cloudflared quick tunnel, with `APP_ENV=LOCAL` dev-login.
   - The intended runtime is `deploy/compose.yml` (nginx + gunicorn) on Azure, but it is not deployed.

## Incident during this audit

- **What happened:** the Mac rebooted at about 10:35 IST on 23 Oct. That stopped the API and the tunnel, so the shared `survivors-static-kitty-departments` link died and cannot be recovered.
- **Recovery:** someone outside this session started a new API and tunnel by 11:04: **https://cheque-bought-dust-successfully.trycloudflare.com**, `/healthz` 200. They also added an untracked `scripts/launchd/com.coresight.cip-api.plist`.
- **This session:** it did not start or stop either; the permission policy blocked starts on :8000 and :8001.
- **Remaining gap:** the new plist restarts the API only, not cloudflared, so the link will change again on the next reboot (gap #4).

## Method and limits

- **Tools:** REA was used where it adds evidence:
  - `analyze_javascript_application` on `web/dist`;
  - a source-to-bundle hash comparison;
  - bundle and route recovery on competitor public pages.
- **Other evidence:** ordinary source reading (as the REA skill directs for a source repo), read-only SQL on `cip_stg`, and light GET probes of the live link.
- **What was not done:** no Forsta calls, no DB writes, no load tests, no WebSearch, and no vendor log-ins.
- **Markers:** every claim in the area reports is marked [O] observed, [I] inferred or [U] unknown.
- **Not tested:**
  - the content of the Excel, PowerPoint and deck exports;
  - Ask CIP live (never called on live);
  - screen readers;
  - full-table `srv_result` counts (these timed out at 20 s on the shared 1-vCPU server; the queries are listed in 20 §10);
  - eMarketer (behind a Cloudflare challenge).

## Decisions needed from you

1. **Password rotation:** rotate the DB password and the Cloudflare token today. Who owns the rotation?
2. **Repo:** make the repo private, and approve rewriting its history to purge the password.
3. **Launch shape:** an internal pilot first, or straight to clients? This decides how much of L0 is needed now.
4. **SSO:** who provides it (Entra ID?), and who is the IT contact?
5. **DB accounts:** the DBA needs to create `cip_app` and `cip_etl`.
6. **Hosting:** Azure VM or Container Apps, plus the domain, TLS and Key Vault.
7. **Client studies:** which client owns which ad hoc study (T-Mobile, Board, Rokbot…), and may analysts see all of them?
8. **Disclosure and method:** the minimum base shown to clients (5, 30 or 50), and the weighting decision (weight, or label everything unweighted).
9. **Data policy:**
   - the retention period;
   - is Anthropic approved to process Ask CIP questions?
   - where the off-machine backup goes.
10. **Survey 97 Q7:** is the duplicated item set real or a legacy import defect? This decides whether gap #5 is a serving fix only or also a reload.
