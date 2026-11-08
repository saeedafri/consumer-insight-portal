# Status: what is done, what is pending, where we are stuck

The one place every agent (Claude, Gemini, Codex, others) and every person reads **before starting** and updates
**while working** on CIP. The rule is in CLAUDE.md, AGENTS.md and GEMINI.md.

## The standard

- **Read this file first.** Take the next pending item, or the one the user names; do not redo a done one.
- **Update it as you go**, in the same change as the code: when you start an item, finish it, or get stuck. One line
  per item in the table below; newest change at the top of its section.
- **Status**, exactly one of:
  - `Done`: built, tested, the docs updated (What's new, docs/CHANGELOG.md, docs/API.md when an API changed).
  - `Waiting for deploy`: done here, not yet on staging (the user commits and pushes; agents never do).
  - `In progress`: an agent is on it now; say which and since when.
  - `Pending`: agreed, not started.
  - `Stuck`: cannot move without someone; say exactly who or what is needed.
- **Where**: the files or screens it touches, so the next agent finds it. **Note**: one line; the detail lives in the
  code, the tests and docs/CHANGELOG.md, not here.
- Dates are written out (7 Nov 2026), times in IST. When an item has been `Done` on staging for a week, move it to
  "Done earlier" at the bottom as one line.

## In progress

| Item | Status | Where | Note |
|---|---|---|---|
| (nothing in progress) | | | |

## Waiting for deploy (done here, not on staging yet)

| Item | Status | Where | Note |
|---|---|---|---|
| New look in light and dark (the 8 Nov mockups, then Designs 1 and 2 combined): grouped folding rail, wave tabs in the wave card, header breadcrumb, card hover, three report cards, rises green and falls red, Upload survey stages, Columns chart removed, outline icons, page labels, hairline controls, type scale, cards, tables, charts, Ask CIP and Boards panels, empty states, footer | Waiting for deploy (copied to cip-stg 8 Nov, user approved) | frontend/src/styles.css, theme.ts, components/Shell.tsx, bits.tsx, EChart.tsx, QuestionChart.tsx, screens/Ask.tsx, Boards.tsx, app/app/boot.css, app/(site)/site.css | Claude 8 Nov. Logo and fonts (Montserrat/Roboto) kept; the mockups' invented panels and Inter not taken. Controls use hairline borders as the mockups do (was a 3:1 outline): the user's choice. Preview: :8001 with data/published/preview |
| China Consumer Survey: Upload survey page (Baidu raw + topline, every count checked), codebook, load into the served tables | Waiting for deploy | etl/baidu_qss_export.py, config/china_codebook.yml, api/ingest.py, frontend/src/screens/Ingest.tsx, deploy/nginx.conf + cip_proxy.conf | Claude 8 Nov, replacing Gemini's draft; 3 weeks (19 Oct-2 Nov) reconcile 123/123. Before deploy: `pip install xlrd`, run `python scripts/init_db.py` (platform 'baidu'), check `nginx -t` in the image. SharePoint pull waits for IT (Sites.Selected) |
| Skills sweep (8 Nov): 349 skills applied to CIP, 49 findings survived a skeptic; the real ones fixed | Waiting for deploy | api/assistant.py, api/metrics.py, etl/notify.py, shared/core/session.py, api/signin.py, api/main.py, .github/workflows/ci.yml, .env.example, CLAUDE.md, frontend/app/app/layout.tsx, styles.css | Fixed: Ask CIP timeout 20 s and a figure check; Excel formula text; Teams webhook not logged; non-ASCII cookie/header 500; missing script 404 and no year-long cache of a 404; email retried 3 times; reduced motion; GitHub CI web job (now also runs the statistics check); report page asked early; Forsta/Logs downloads in Safari and Firefox. Gemini's sweep (docs/research/Gemini-skill-sweep.md) added the download bug (fixed) and a SIGTERM trap for deploy/start.sh (not applied: the gunicorn|tee pipeline's $! is tee, not gunicorn, and it cannot be tested without the Azure image). Decisions left: set CIP_BACKUP_COPY_DIR (backups only on this Mac), client-set IP headers (audit.py), API writes use the owner DB account (config.py:154), logo cache and brotli (nginx), graphify-out/ tracked in git (10 MB) |
| Faster from far away and on slow lines: data asked from the HTML, portal code announced at build (frontend/scripts/preload-portal.mjs), charts load when drawn, API file server sends the .gz copies | Waiting for deploy | frontend/app/app/layout.tsx, QuestionChart.tsx, theme.ts, Explorer.tsx, api/main.py SinglePageApp, package.json, .dockerignore | Measured 8 Nov, 232 ms per request: overview first visit 2,044 to 1,526 ms; 200 kbit/s 27.5 to 15.6 s; 100 kbit/s 53.8 to 31.0 s (servers without nginx, like this Mac's live link, were 64.9 and 129 s: they sent the files unzipped); repeat at 100 kbit/s 1.1 s. HTTP/2 (IT, 9 Nov) measured a further ~180 ms |
| HEAD /healthz answers 200 (was a 404 page); Python packages pinned | Waiting for deploy | api/main.py healthz, requirements.txt | From Gemini's 8 Nov performance proof, reviewed by Claude: its pool_recycle 180 (unproven, adds reconnects) and nginx /healthz log filter (`=` is not valid in a map, matched nothing) were not kept |
| Do idle MySQL connections drop on staging? | Pending | shared/core/config.py pool_recycle, database.py:151 | Look in staging's logs for error 2013 on the first request after 5+ quiet minutes; change pool_recycle only if they are there (from India each reconnect costs ~4 s) |
| Times: viewer's own zone on every page, India time on Logs (raw lines too), 12-hour with AM/PM; Logs first visit after a deploy and each refresh made cheaper | Waiting for deploy | bits.tsx clock/ist/local, Logs.tsx istLine, Schedule/Forsta/FieldworkSurvey, api/main.py lifespan, api/logs.py tail, api/metrics.py problems | The zone comes from the browser: no lookup, no server cost. 5.4 s first Logs request after the 21:03 IST deploy (log read) now done at start in the background |
| Logs page: any dates (hourly beyond a day), visitor details, Show with context, Excel download of everything, 12-hour IST, token box only when asked, refresh once a minute while in view | Waiting for deploy | api/metrics.py, api/logs.py context, deploy/cip_logs.conf (referer), Logs.tsx, bits.tsx ist | Hours kept in logs/traffic-hours.jsonl (/home, ~22 MB a year) from the deploy on; a refresh costs ~50 ms here, ~0.2 s on staging |
| Audiences clear stale figures; stacked legend on one line; HTML codes out of wordings; new waves listed before publish | Waiting for deploy | Audience.tsx, QuestionChart.tsx, etl/records.py clean_text, api/main.py all_waves | 106 staging wordings repaired in cip_stg 7 Nov 20:05 IST (originals kept by Claude); they show after staging's next publish. all_waves fallback was Gemini's, kept with a test |
| Wave switcher (Previous, Next, the list, [ and ]) | Waiting for deploy | frontend/src/components/Shell.tsx TopBar | Used the browser's path (/app/w/…) with the router's navigate, so every switch opened /app/app/w/… ("Page not found") since 29 Oct; found by Gemini's 7 Nov screen test, checked in a browser after the fix |

## Pending

| Item | Status | Where | Note |
|---|---|---|---|
| Schema changes are applied by hand | Pending (known limit) | scripts/init_db.py, docs/technical/08-operations-runbook.md | No deploy step runs it: after a deploy that changes sql/ or schema_upgrade.py, run `python scripts/init_db.py` (role column 255 done by hand 7 Nov 17:15 IST) |
| More MCP tools: weekly report, sector databank, expected vs actual | Pending | api/mcp.py | Same rules as the screens; needs the published files' shapes |
| Disk alerts before the Azure worker disk fills | Pending | api/metrics.py, Teams webhook | The disk is Azure's (old deploy images fill it); CIP's own files are about 0.2 GB |
| Menus when the database is down at a server start | Pending (known limit) | shared/core/access.py managed_features | Until the first read succeeds, everyone gets their package: a removed trial menu can show for that time. Fix: keep the last choice in a file on /home |
| Two API workers saving keys at the same moment | Pending (known limit) | shared/core/api_keys.py save | Staging runs one worker, so no race today; add a file lock before running two |
| Split etl/fieldwork.py (collect, check, publish) | Pending (code review, judgement call) | etl/fieldwork.py | ~600 lines doing three jobs; works and is tested |

## Stuck

| Item | Status | Where | Note |
|---|---|---|---|
| The live link (:8000) shows data published on 2 Nov | Stuck: the user decides | data/published/current on this Mac | Newest wave 530 (staging has 532); Weekly reports, Sector databank, Expected vs actual answer 404. This Mac runs no ETL loop: one `python -m etl.publish` refreshes it (reads cip_stg a few minutes) |
| Remove CIP_DEMO_LOGIN from the staging App Service settings | Stuck: IT (Monday), no longer urgent | Azure, csr-awa-cip-portal-stg | The code ignores it once the deploy above is out; removing it keeps the settings honest |
| `cip-stg.coresight.com` does not resolve on the office network | Stuck: IT | office DNS 10.2.21.4 | Public DNS points it to the Azure app; until IT adds it, use the azurewebsites address |
| PDF export of very wide team reports | Stuck: Forsta | e.g. "Full cross" (41 columns) | Forsta's own PDF layout error; the Excel and PowerPoint of the same report work |
| Old Azure images filling the worker disk | Stuck: IT / Azure | App Service plan csr-awa-cip-portal-stg | Azure clears old images itself; IT can confirm the clean-up or move the app to a plan with more local disk |

## Done earlier

| Item | Status | Where | Note |
|---|---|---|---|
| Gemini's new-skills shortlist (8 Nov) reviewed | Done (8 Nov) | docs/research/Gemini-new-skills-shortlist.md | 12 repos exist. Worth installing: microsoft/azure-skills + MicrosoftDocs MCP; cloudflare/skills only if Cloudflare goes in front. Trial findings wrong: signin.py:240 already runs in a thread (test-only logging); srv_answer queries filter on survey_id+qcode, the primary key's start; ECharts not on the first page (that review); /dev/shm cache unmeasured |
| Gemini's end-to-end audit (7 Nov, docs/research/Gemini-end-to-end-…) reviewed | Done (8 Nov) | requirements.txt | Python packages pinned to the tested versions (was >=); npm and PyPI 0 known vulnerabilities; every API route p95 under 36 ms in the logs, first page 184 KB gzipped. Still to check: staging logs for MySQL 2013 after quiet spells. Already done or wrong: session secret (check_settings), deck blocking (sync def runs in a thread), ECharts on first page (lazy + idle prefetch), prompt caching (prompt too short to cache). Not needed: orjson, DuckDB, LangGraph, virtual tables, React compiler, route aliases. docs/skills/ files it names do not exist |
| Demo sign-in off, cache warm-up, question codes in any case | Done (staging ad9a9d57, 7 Nov 19:10 IST) | api/signin.py, config/access.yml, api/main.py | /auth/dev-login 404; warmed 1,740 of 1,740 cross-tabs; crosstab?q=Q1 200 |
| Keys survive a redeploy | Done | /home/cip/api_keys.yml | The staging MCP key still worked after the 885d7fa6 deploy (7 Nov 18:15 IST) |
| Gemini's second screen test (7 Nov) reviewed | Done | this board | Right: audiences stale, stacked legend, HTML codes, live :8000 stale. Wrong: empty waves spin, two-cut errors, Compare overlap, OIDC fails outside the office (public DNS resolves) |
| Gemini's local screen test (7 Nov) reviewed | Done | this board | Right: wave switcher, key copy error. Its local data gaps are the live :8000's published files (2 Nov); its admin-token bypass and reports-as-empty fixes would be wrong |
| Gemini's staging investigation (7 Nov) reviewed | Done | this board | Right: case bug, HEAD /healthz, team LIMIT 500, logout URL join, demo sign-in. Wrong or not a bug: its case fix, analyst menus (your Access choice, 15:18 IST), admin token under demo (by design), 228 RPS "brick wall" (a model, not measured) |
| Second Gemini Forsta research reviewed | Done | docs/FORSTA_API_REVIEW.md section 5 | 7 endpoints do not exist, statuses unmeasured, all six proposed menus would be empty or not apply: none built |
| Checked on staging after the 7 Nov deploy (443c3ef0) | Done | staging | 17 API routes and 5 MCP tools with a key; a key cannot make keys; a trial ended at 17:23:53 IST was refused 10 s later in the same session; no errors since the deploy |
| Hibernated surveys (8) | Done: decided not to wake them | etl/fieldwork.py | The user's decision, 7 Nov 2026: only their summary is kept |
| Review fixes: role column 255 characters, dropped menus seen by every worker, key file only where writable, blank answers paired by code, Survey preview logic gated, Logs fully in IST | Done (staging, 7 Nov) | sql/010, api/main.py, etl/fieldwork.py | |
| API guide, What's new = docs/CHANGELOG.md, docs/API.md | Done (staging, 7 Nov) | /app/api-guide, tests/test_docs.py | |
| Own API keys; menus per client and person; trials end without refresh | Done (staging, 7 Nov) | Account and Access pages, api/signin.py, deploy/cip_auth.js | |
| Forsta screens, read-only POSTs enforced, Forsta vs CIP check, Excel/PDF/PowerPoint | Done (staging, 7 Nov) | /app/forsta/…, etl/forsta_client.py | 43,396 of 43,396 cells match in 77 surveys |
| Fieldwork per survey, why respondents dropped out; Logs in IST | Done (staging, 7 Nov) | /app/fieldwork/…, Logs page | |
| CIP MCP connected to the super admin in Claude Code | Done | `claude mcp list` → cip (local), cip-stg (staging, your key "Claude Code (staging)") | |
| Company sign-in (SSO) on staging | Done | api/signin.py, csr-idp | |
| Ponytail at ultra level on every change | Done | CLAUDE.md, AGENTS.md, GEMINI.md | |
