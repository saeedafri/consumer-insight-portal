# 01 · Consolidated gap register (23 Oct 2026)

This register merges 141 raw findings from the six area reports into **38 gaps**, ranked by launch impact. Each gap cites the raw IDs behind it. Evidence, file:line references and SQL are in the area reports:

| Prefix | Report |
|---|---|
| ETL | [10](10-etl-pipeline.md) |
| DB | [20](20-database.md) |
| API | [30](30-backend-api.md) |
| UI | [40](40-frontend-ui.md) |
| OPS / SEC / PRF | [50](50-ops-security-stack-profile.md) |
| MKT | [60](60-competitors-and-market-gaps.md) |

Tiers:
- **L0, launch blocker:** must be closed before any external client sees the product.
- **L1, fix before launch:** wrong or misleading output, or fragile operation.
- **L2, first quarter after launch.**
- **L3, strategic:** what stops CIP being top of market.

The lead re-checked these findings personally on 23 Oct:
- ETL-02: survey 97 Q7 shows Facebook, Instagram, Pinterest, TikTok, Twitter and YouTube at 0.000 % in `srv_result`.
- ETL-03: `concept_option_id` is non-NULL in 0 of 27,064 `srv_result` rows for waves 415 and 412.
- ETL-01: `database.bulk_insert` raises on any `SHOW WARNINGS` row, and `forsta_etl._number` does not round to 4 decimals.
- UI-01: `moves.ts:16-22` feeds p = 1 for untestable rows into Benjamini–Hochberg.
- UI-03: `bits.tsx:96,102` hardcode "US adults 18+".
- Tests: `pytest -q tests` gives **290 passed** at 11:3x IST. The 2 failures in ETL-18 did not reproduce.

---

## L0: launch blockers

| # | Level | Gap | Raw IDs | Smallest fix |
|---|---|---|---|---|
| 1 | Profile / backend | **Anyone with the public link is signed in, as any email they type.** The live API runs `APP_ENV=LOCAL` (`~/.config/cip/api.env`), so `/auth/dev-login?email=` issues a session with all products. The React app sends every 401 there (`web/src/api.ts:93`). There is no OIDC, logout or revocation. `APP_ENV` defaults to LOCAL when unset. | API-01, API-04, SEC-01, SEC-08, PRF-01, UI-10, UI-12, API-18 | Before clients: OIDC (Entra ID) for the React API, dev-login compiled out unless LOCAL is set explicitly, `APP_ENV` default PROD, `Secure` cookie, logout. Interim for an internal pilot: Cloudflare Access in front of the tunnel. |
| 2 | Security | **Public GitHub repo, with a DB password committed in it.** `saeedafri/consumer-insight-portal` is PUBLIC. The `.env:70` password is in two Gemini docs pushed in `442cfb5`. | SEC-02, SEC-03, (old G-01, G-05) | Rotate the password today. Make the repo private. Remove the files and rewrite history (needs your OK). |
| 3 | Database / security | **The portal and ETL use your personal account, with ALL PRIVILEGES on `cip_stg` and 3 other projects' databases (about 560 GB).** The 12 views have that DEFINER and SQL SECURITY DEFINER. `sql/004_grants.sql` is correct but was never applied. | DB-01, DB-04, API-02, SEC-04 | DBA creates `cip_app` (SELECT plus team-table writes) and `cip_etl` (ALL on `cip_stg` only). Recreate the views as SQL SECURITY INVOKER. `config.py` refuses to start outside LOCAL without `APP_DB_USER`. |
| 4 | Tech stack / ops | **Production is one MacBook plus a cloudflared quick tunnel.**<br>• Today's reboot (about 10:35 IST) took the link down for about 17 min and changed it to `cheque-bought-dust-successfully…`.<br>• The Mac sleeps after 1 min unless a hand-started caffeinate holds it.<br>• cloudflared is unsupervised.<br>• The new `cip-api` launchd plist is untracked and restarts the API only.<br>• `backups/` is empty and there is no off-machine copy of the DB dump or the published files.<br>• No uptime alert exists.<br>• The ETL has no server home.<br>• The DB was unreachable on 7 days between 11 and 20 Oct. | ETL-05, OPS-01–05, API-05 | Target: Azure VM or Container Apps in the DB region, using `deploy/compose.yml` (nginx + API), the ETL as a cron/Container Apps job, a named Cloudflare tunnel or real domain + TLS, Key Vault, and a Blob backup (`CIP_PUBLISH_BACKUP_URL`). Stop-gap: `pmset sleep 0 autorestart 1`, launchd for caffeinate + cloudflared, external uptime ping. |
| 5 | ETL / data | **Wrong numbers are published.** The serving build keys cells on item **label**, so duplicate labels overwrite each other. That loses 766 cells across 8 legacy waves; for example, survey 97 Q7 shows YouTube at 0 % where the answer data has 612/1,293 = 47 %. There is no check that cube cells equal serving rows. | ETL-02 | Key on `item_id`/`option_id`. Add an integrity check (cube cell count = `srv_result` count per wave). Rebuild those 8 waves and republish. Check whether survey 97's legacy import is itself malformed. |
| 6 | Frontend / stats | **The product contradicts itself on significance.**<br>• Overview says "No significant change" while the GLP-1 takeaway on the same page says "+17 pts significant".<br>• Explorer shows unflagged red chips.<br>• BH runs over 577 rows, including untestable rows at p = 1, which hides real moves (wave 415 CS3 −11.7 pts, p = 0.0004 → "0 significant").<br>• The "Largest increase" KPI is n = 62, p = 0.10.<br>• Trends and Compare marks are uncorrected. | UI-01, UI-02, UI-04, UI-09 | One significance module used by every surface. BH over testable rows only. KPIs only from significant moves. One written rule shown in a methodology note. |
| 7 | Data / product | **Methodology is undisclosed and provenance is hardcoded.**<br>• Every chart, PNG and export says "US Consumer Survey · US adults 18+" and shows "✓ Verified Sample", including B2B client studies whose Overview shows "Male 0 · Female 0".<br>• No page states panel source, quotas, fielding window, that data is unweighted, or the data-quality rules. | UI-03, MKT-01, MKT-19, MKT-20, ETL-24 | Provenance taken from wave metadata (population, study type, fielding dates, n, weighting = none). One public methodology page. The weighting decision is in L3 #33. |
| 8 | Profile / data | **No tenancy, roles or entitlements.**<br>• Every Forsta survey the key can see, including client-commissioned studies (T-Mobile, Board, Rokbot…), is loaded and shown to every user.<br>• Product entitlement is checked on 1 route only.<br>• Boards, audiences, alerts and saved views are global.<br>• There are no analyst/client/admin roles. | ETL-12, PRF-02, PRF-03, PRF-04, MKT-24, API-06 | An `owner_client` / `visibility` field per survey (allow-list config), enforced in the API **and** the published-file layer. Roles: admin, analyst, client. Team objects scoped by org. |
| 9 | Privacy | **Small groups can be exposed.**<br>• `/api/v1/trend` and `/api/v1/trends/...` return figures for groups of 2–4 (1,418 cells live for one question), while every other route hides cells below 5.<br>• Audience differencing (8 conditions plus cuts) can isolate people.<br>• The UI says "n<30" while the rule is 5. | API-03, API-09, PRF-07, UI-06 | Delete the two unused trend routes. Agree one client threshold. Make differencing safe (minimum audience size, and no subtraction across audiences). Match the UI wording to the rule. |
| 10 | Privacy / DB | **Respondent identifiers are weak.**<br>• `respondent_key` is a plain, unsalted SHA-256 of the panel ID (`CIP_RESPONDENT_SALT` is set nowhere).<br>• 79,626 plaintext respondent IPs sit in `cip_stg.dwh_smresponse`.<br>• Session IDs are stored in plaintext. | DB-02, DB-03, ETL-14, PRF-06, DB-13 | Set the salt and rehash once. Null the IP column, or drop the legacy copy once history is verified. Store the session hash only. |
| 11 | Security | **The `.env` file is a hazard.** It contains:<br>• a pasted `curl` command with a live Cloudflare API token (lines 83–85);<br>• a bare password line;<br>• `FORSTA_API_KEY` defined twice with different values;<br>• foreign R2 keys.<br>python-dotenv warns on every run. | ETL-25, SEC-05, DB-15 | Rotate the Cloudflare token. Delete the pasted lines. Keep one Forsta key. Move secrets to Key Vault for Azure. |

## L1: fix before launch

| # | Level | Gap | Raw IDs | Fix |
|---|---|---|---|---|
| 12 | ETL | **A numeric answer with more than 4 decimals fails the whole wave on every retry.** Since 22 Oct, `bulk_insert` aborts on any MySQL warning, and `qtime` is not rounded. This happened to 250701 on 20 Oct. | ETL-01 | Round to 4 decimals in `_number`. A test against MySQL rules, not SQLite. |
| 13 | ETL / data | **Harmonisation never reaches users.** `concept_option_id` is NULL in all cube and serving rows, so 8,928 confirmed mappings have no effect on prior-week, last-year or trends. 3,771 more are still `proposed`. | ETL-03, DB-08, ETL-20 | Fill `concept_option_id` at cube/serving build from confirmed mappings. Rebuild serving when a mapping is confirmed. Auto-confirm exact-wording matches. Name an owner for the queue. |
| 14 | ETL | **One exception ends the 54-hour Monday watch.** The wave then waits until Friday. | ETL-04 | `try/except` around `run()` inside the watch loop. |
| 15 | ETL | **Annual and ad hoc studies publish while still fielding.** They load 9 h after launch and are not reloaded until closed (Holiday 2025 fielded for 8 days). | ETL-06 | The 9 h / 400 rule applies to trackers only; other studies load at close, or carry a visible "in field" state. |
| 16 | ETL / data | **Annual studies don't trend year on year** (family taken from the title). A 2-respondent aborted launch is a verified wave. | ETL-10, ETL-11, DB-07 | Explicit `family:` map in `survey_map.yml`. A minimum-n gate (`too_small`). Remove waves 394 `TEST_TRAINING`, 382 and 261 from serving. |
| 17 | Data | **18,968 qualified respondents (41 waves) have no profile row**, so every demographic cut on those waves is one blank segment equal to Total. | DB-06 | Backfill the profiles, or hide demographic cuts for those waves and say why. |
| 18 | ETL | **Run lock is incomplete, and its connection times out after 8 h inside a 54 h watch.** The 20 Oct deadlocks show two writers ran at once. | ETL-08 | One `etl_lock()` for every write entry point, plus a keep-alive. |
| 19 | ETL / data | **"Verified" means counts only.** Value reconciliation never runs on a schedule, and `--reconcile` passes a hibernated wave with 0 checked. | ETL-09 | Run `reconcile_survey` on each new wave. Treat `checked == 0` as a fail. |
| 20 | ETL | **A failed reload leaves live and published screens disagreeing.** Published files also lag serving (12:47 vs 17:31 on 22 Oct). | ETL-07, API-17, ETL-16 | Keep `srv_*` on the same status as the wave, or swap via a staging copy. Clean up `.build-*` on failure. |
| 21 | Backend | **No rate or size limits** on Ask CIP (paid Claude Opus calls), on exports (up to 2,000 × 60 cells rendered on 1 core) or on audiences. | API-07 | Per-user token bucket. Cap body size and export size. |
| 22 | Backend / frontend | **No security headers on the live path:** no CSP, XFO, HSTS, nosniff or Referrer-Policy, and the cookie lacks `Secure`. The nginx config that has them is not in use. | API-08, SEC-06, UI-24 | Comes free with the L0 #4 deploy (nginx), or add a middleware now. |
| 23 | Profile | **No audit log** of who viewed, exported or asked what. | PRF-05, MKT-25, API-19 | One `cip_access_log` insert per export, ask and sign-in. |
| 24 | ETL / ops | **The schedule is a hard-coded list of Mondays ending 11 Jan 2027.** All alerts go to one developer, and fixed subjects throttle new problems for 6 h. | ETL-17, ETL-19, OPS-10 | Generate the schedule from a rule plus exceptions. Use a team distribution list. Put the problem count in alert subjects. |
| 25 | Frontend | **Ad hoc and annual studies are labelled "vs last week" / "this week".** `?range=foo` crashes Trends. An empty catalogue crashes Library. Times are shown in IST. | UI-07, UI-05, UI-21, UI-22 | Wording from study type. Validate URL params. Empty states. Show times in US ET. |
| 26 | Dependencies | **pillow 12.3 has 35 CVEs.** There is no dependency audit in CI. The Docker image pins diverge from `requirements.txt`. 4 npm dependencies are unused (823 MB `node_modules`). | SEC-07, OPS-06, UI-16 | Bump pillow to 13. One lockfile. pip-audit + npm audit in CI. Drop mermaid, reactflow and @xyflow. |

## L2: first quarter after launch

| # | Level | Gap | Raw IDs |
|---|---|---|---|
| 27 | Database | Storage is about 3× what it needs to be: multi-select zeros, non-qualified answers, and indexes larger than the data (3.35 GB vs 2.64 GB), with 2.6 GB in legacy copies, all on a 2 GB buffer pool shared with 656 GB. 8 views have no verified-wave filter, and `v_cip_trend` scans whole tables. There are no CHECK constraints, 7 empty tables, case-insensitive code keys and 87 texts containing HTML entities. | DB-05, DB-09, DB-10, DB-11, DB-12, DB-14, DB-16 |
| 28 | Backend | The team endpoints cost about 255 ms each (one India→Azure round trip, uncached) and are polled on every page. Opening a board takes 3 queries in sequence (≈800 ms). The trend routes take 1.9–3.1 s. | API-10, API-11, UI-15 |
| 29 | Backend | Malformed JSON returns 500. The error and pagination contract is inconsistent, with a silent `LIMIT 500`. `/healthz` and openapi are public. There are no HTTP-level auth tests. | API-12, API-13, API-14, API-15, API-16, SEC-09 |
| 30 | Frontend / a11y | Help and warnings are hover-only (`title`). Delete has no confirmation. The mobile drawer has no focus trap. 5 screens have no `<h1>`. The bar colour is below 3:1 contrast. Sort and audience state are not in the URL. | UI-08, UI-11, UI-13, UI-14, UI-17, UI-18, UI-19, UI-20, UI-23 |
| 31 | Ops | No log rotation. No release tags or deploy step. Bare `pytest` breaks on `scripts/e2e_perf_test.py`. | OPS-07, OPS-08, OPS-09, ETL-18 |
| 32 | ETL | Mixed naive time zones. Reloads keep removed definitions. Legacy loaders never set `loading`. Two tracker waves exist in one week (RIWI, Dec 2023). | ETL-13, ETL-15, ETL-21, ETL-22, ETL-23 |

## L3: strategic gaps to the top of the market

These come from the competitor teardown in [60](60-competitors-and-market-gaps.md).

| # | Level | Gap | Raw IDs | Who does it |
|---|---|---|---|---|
| 33 | Data | **Sample and weighting.** About 400 unweighted US respondents a week gives ±4.9 pt overall and thin subgroups. | MKT-01, MKT-02 | Morning Consult (30k+ a day), YouGov (30M panel), GWI (2M+ a year), Euromonitor (~1k a market, quota-matched) |
| 34 | Distribution / AI | **No public API, no MCP server, no BI connector.** Ask CIP answers from the latest wave only (5 sources) and cannot answer trend questions. | MKT-16, MKT-12, MKT-13, MKT-14, MKT-15 | Morning Consult, GWI, YouGov, Statista, Euromonitor and Attest ship API and/or MCP into Claude, ChatGPT or Copilot |
| 35 | Data | **Open-ended answers are discarded.** There is no receipt/POS linkage and no respondent-level delivery. | MKT-04, MKT-05, MKT-06 | Numerator, NIQ, Circana (behavioural); Qualtrics, Displayr (text coding) |
| 36 | Product | **Workflow gaps against Statista, the closest match:**<br>• no "is this audience big enough" check before analysis;<br>• no index/z-score "what makes this group different" view;<br>• exports are synchronous;<br>• no event annotations;<br>• no embeds. | MKT-07, MKT-08, MKT-09, MKT-11, MKT-17 | Statista, GWI |
| 37 | Commercial | **No packaging, tiers or trial.** CIP's own scale figures conflict: PRODUCT.md says 144 waves / 71k respondents, the business description 318 / 166k, live data 371 / 190k. | MKT-21, MKT-22, MKT-23 | All |
| 38 | Enterprise | **No enterprise readiness:** no per-client SSO/SAML, SCIM, MFA, SOC 2/ISO collateral or data-residency statement. Multi-country is a later choice. | MKT-26, MKT-27, MKT-03 | GWI, YouGov, Qualtrics |

## What is solid (verified, not gaps)

- **Data correctness, apart from #5:** all 371 waves are verified. The qualified base equals a recount on every wave. Waves 238, 204 and 415 reproduce cell for cell from raw answers (55,802 rows of %, prior and last-year arithmetic). There are no orphans, duplicate respondents, garbled characters or out-of-range dates. All 84 Forsta waves agree with Forsta. 19 integrity checks pass.
- **No schema drift:** every table, column and index in `sql/001`–`007` is live.
- **Speed:** served reads take 0.3–8 ms. All API SQL is a primary-key or index range read and fully parameterised. ETag/304, gzip and admission control work.
- **Frontend:** the deployed bundle equals the source build (40/40 hashes). `tsc` and `stats.check.ts` pass. No source maps are exposed, and no layout overflows at 390 px.
- **Tests:** 290/290 pass, and GitHub CI is green.
- **Product breadth matches the leaders:** cross-tabs with two cuts, trends, change detection, boards, audiences, alerts, a cited assistant, native PPTX and XLSX export.
- **Differentiators:**
  - weekly retail-sector rotation with harmonised history back to 2018;
  - uncertainty shown everywhere;
  - an assistant that drops any claim it cannot cite;
  - very low cost to serve.
