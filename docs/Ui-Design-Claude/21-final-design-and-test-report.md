# 21 · Final design and test report: the portal, the system and how it was tested (21 Oct 2026)

This is the one document to read. It says what was built, what was tested and how, the results (users, speed, RAM), what came from the Lovable mock-up and the business team's Excel, and what is still open. Every number was measured against **STG (Azure `cip_stg`)** unless marked otherwise.

## 1. The answers first

| Question | Answer |
|---|---|
| **How many users at once on staging (1 core, 4 GB)?** | **16,000 simultaneous users tested: every standard screen at p95 1–3 ms, 0 errors.** Library, overview, question explorer, cross-tab banner, trends, what changed and survey preview are published files that nginx serves. At that load nginx used **7 % of the core and 60 MB**, and the API 30 % and 337 MB (§4). |
| **Speed** | Screens draw in **0.32–0.49 s** in the browser, fully drawn, including chart rendering. Data requests to the server take **p50 0.1–0.3 ms, p95 under 2 ms**. Search takes **1–5 ms**. |
| **Best speed** | **0.1 ms** p50 for a published file (survey list, wave, trend), at any of the tested loads. |
| **RAM on the 4 GB staging box** | **About 400 MB in use at 16,000 users** (API 337 MB + nginx 60 MB). Idle is 233 MB. The API cache is capped at 256 MB per worker, however big the archive grows. |
| **The one dependency** | Two-cut cross-tabs (e.g. Gen Z × female) still query MySQL. Over the VPN from the test Mac each query takes about 3 s, so under load they get "busy, retry" (§4.2). Inside Azure they take 5–20 ms. |
| **ETL per survey** | **2.3–2.5 minutes** per weekly wave and **180–184 MB RAM**, measured twice on STG. 98 % of that is waiting on Azure from the Mac (§7). |
| **Did every click work?** | **Yes.** 24 screen visits across 4 surveys (2 weekly trackers, 1 annual, 1 ad hoc) and 140 clicks or changes, each checked for data on screen. Result: **0 failures, 0 console errors, 0 failed requests.** Layout passes at 1440, 1024, 768 and 390 px, and the theme toggle passes (§5). |

## 2. What was built

### Screens (React 19 + Vite + TypeScript + ECharts)

Every survey and wave since 2018 is covered: 371 today, and more as the archive loads. Screenshots are in [`ui/portal/`](ui/portal/).

| Screen | What it does | Picture |
|---|---|---|
| **Survey library** | All waves, latest tracker first, archive by year. Filter by type, year, title or module. Waves with no results yet are greyed out | [01](ui/portal/01-library.png) |
| **Search** | Every question since 2018 by words, code, answer label or survey title. **Corrects typos and uses synonyms** and says what it did | [02](ui/portal/02-search-typo-corrected.png) |
| **Overview** | **The business team's Databank block** ("This week at a glance" tiles, vs LY, vs prior week, key takeaways) for module waves. The biggest significant moves (Benjamini–Hochberg corrected). One chart per section | [03](ui/portal/03-overview-databank-glance.png) |
| **Question explorer** | Bars, columns, stacked (scale colours from the style guide), donut and table, offering only the types valid for the question. Total, by gender, by generation or all columns. Download CSV or PNG; copy link | [04](ui/portal/04-explorer-bars.png)–[07](ui/portal/07-explorer-by-generation.png) |
| **Cross-tab matrix** | Base row; blue heat; significance letters or arrows against any column you click; small bases flagged. **Two cuts combined**, with 1 / 2 / 4-week pooling and a warning when bases changed | [08](ui/portal/08-crosstab-letters.png), [09](ui/portal/09-crosstab-two-cuts-pooled.png) |
| **Trends** | Real date axis with **gaps for missing weeks and seasons**, the latest value at each line's end, significant moves marked, ±margin band, 4-week average, 3m/6m/1y/all, any column | [10](ui/portal/10-trend-margin-band.png), [11](ui/portal/11-trend-year.png) |
| **What changed** | Every answer vs last week or last year. Significant only after the multiple-comparison correction; demographic shifts hidden by default | [12](ui/portal/12-what-changed.png) |
| **Survey preview** | The questionnaire as respondents saw it, with live results | [13](ui/portal/13-survey-preview.png) |
| **Archive and ad hoc surveys** | The same screens. Columns without respondents (no profile data) are not offered | [14](ui/portal/14-archive-annual-survey.png) |
| **Dark theme** | Toggle in the top bar; the system setting by default; no flash on load | [15](ui/portal/15-dark-overview.png)–[17](ui/portal/17-dark-trend.png) |
| **Phone** | Single column, no sideways scrolling | [18](ui/portal/18-phone-overview.png), [19](ui/portal/19-phone-explorer.png) |

On every chart:
- a **hover card** with the answer, % ± margin of error, ≈n, base, the change vs last week with significance in words, and vs last year;
- a **source line** underneath: population, fieldwork week, base, unweighted, test;
- a spoken data summary for screen readers (ECharts ARIA);
- the view is kept in the URL, so links can be shared.

### System

```
Forsta (GET) ──► ETL (etl/) ──► cip_stg: raw · cube · serving tables (srv_wave, srv_result, srv_answer)
                       │
                       └──► etl/publish.py ──► published/<version>/  (survey list, 371 wave books,
                              (atomic swap,                            17 dashboards, 5,360 trends:
                               quality gates,                          .json + .json.gz, 79 MB)
                               rollback)                 │
Browser ──► nginx (1 worker) ──┬─ published file  ◄──────┘   no Python, no database on the request
                               ├─ /assets, index.html        (web app, cached 1 year / revalidated)
                               └─ /api/* ──► FastAPI (2 gunicorn workers): two-cut cross-tabs, search
                                             (FTS5 in memory), anything not published; LRU cache;
                                             admission control → fast 503 "busy, retry"
```

| Piece | Where | Why |
|---|---|---|
| Payload builders, shared by the API and the publisher | `app/data/payloads.py` | The published bytes equal the API's bytes (tested) |
| Atomic static publishing with gates and rollback | `etl/publish.py`, after each load in `scripts/weekly_forsta.py` | The council's #1: standard screens never compute at request time |
| nginx: `gzip_static`, `auth_request` cached per session, SPA fallback, 503 page | `deploy/nginx.conf` | 0.1 ms per file, sign-in still enforced |
| Admission control | `api/main.py` (`CIP_BUILD_SLOTS`, `CIP_BUILD_WAIT`) | Overload becomes a fast "busy, retry" the screen retries itself, never a pile-up |
| One deployment for the server | `deploy/compose.yml`, `deploy/Dockerfile` (api + nginx targets) | Debian, 1 core: nginx about 60 MB, API about 340 MB under load |
| Search | `api/search.py`, `config/search_synonyms.yml` | SQLite FTS5 (standard library), stemming, typo correction, synonyms, answer labels, trigram fallback |
| Module dashboards: the Excel metrics | `api/dashboards.py`, `config/dashboards.yml` (`ly_rule: same_wave_number`) | The business Databank, configurable per module |
| Theme and palette | `web/src/theme.ts`, `web/src/styles.css` | One token set, light and dark, Coresight 2026 rules |
| Statistics | `web/src/stats.ts` (`npm run check`) | z-test, margin of error, Benjamini–Hochberg; checked against known values |

## 3. Where the design came from

| Source | What we took |
|---|---|
| **Business team's Excel** (Holiday Survey Databank) | The "This week at a glance" tiles (not started, started, finished, bought in past 7 days, #1 retailer) with vs LY and vs prior week, and the 5 key-takeaway sentences. **Wave 412 matches the Excel on every number** (55.0 % ▲1.7 vs LY; Walmart 50.4 % vs 45.8 % LY). "Last year" uses their rule: the same wave number last season. |
| **Lovable mock-up** (REA: Vite + React + Recharts, all data compiled in, one survey only) | The dark rail and question list beside the chart; a chart-type switch; heat-map cross-tab with segment bases and low-base warnings; respondent-view preview; dark-mode toggle. Built for **every** survey, on the API |
| **Coresight 2026 style guide** | Every colour and chart rule (doc [16 §2](16-portal-and-staging-test.md)): red highlight, light-blue bars, blue ombre, greys / blue / reds for scales, horizontal bars for long labels, circular line markers, ≥ 3:1 contrast, dark table headers, the red bar before headings |
| **Competitors**: desk research ([15](15-competitor-patterns.md), 48 sources) and REA on 7 live sites ([18](18-rea-competitor-dashboards.md)) | Base and wording everywhere; small-base flags; significance letters; click-to-compare; gaps for missing waves; margin bands; "what changed"; search across waves; tooltip contents; source line, PNG and share link, ARIA, end labels, in-place explanations |
| **LLM Council** ([19](19-council-system-design.md)) | Publish static files; FTS5 search; tool-calling chatbot; YAML configuration; multiple-comparison correction; admission control; honest latency promise; security first |

## 4. Load test: staging shape, STG data

### How

| Item | Value |
|---|---|
| Server | Production images (`deploy/Dockerfile`), Debian 13. **nginx and the API share one CPU core** (`--cpuset-cpus 0`), with **3 GB + 256 MB** of RAM |
| Data | **STG (Azure `cip_stg`)**: the API reads STG; the published files were built from STG by `etl/publish.py` (100 s, 371 books, 5,360 trends) |
| Users | [`user_mix.py`](../../scripts/ui_benchmark/user_mix.py), on 3 other CPUs. Each user opens the library, opens a wave (70 % one of the last 8 weeks, 30 % any archive wave), then 1–3 more clicks: a two-cut cross-tab, a trend or a search. Think time averages 10 s, every click hits the server, and gzip is accepted like a browser. Each step ramps for 20 s, then measures for 60 s |

### 4.1 Results

| Users at once | Requests/s | Survey list p95 | Wave p95 | Trend p95 | Search p95 | Errors on those | nginx CPU / RAM | API CPU / RAM |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1,000 | 93 | 1.8 ms | 3.0 ms | — | 7.2 ms | 0 | 2 % / 16 MB | 15 % / 265 MB |
| 4,000 | 373 | 1.1 ms | 1.5 ms | — | 4.4 ms | 0 | 4 % / 26 MB | 20 % / 286 MB |
| 8,000 | 745 | 0.8 ms | 1.1 ms | — | 4.7 ms | 0 | 5 % / 39 MB | 25 % / 308 MB |
| **16,000** | **1,495** | **1.5 ms** | **1.8 ms** | **p50 0.1 ms** | **3.8 ms** | **0** | **7 % / 60 MB** | **30 % / 337 MB** |

**About the trend column:** published trends answered in 0.1–0.2 ms p50. The remaining trend errors (about 4 %) were single-wave surveys, which the Trends screen no longer requests.

### 4.2 Two-cut cross-tabs: the one screen that still needs the database

**From the test Mac over the VPN** (274 ms per round trip), a cross-tab cache miss takes about 3 s against STG. At 1,000 or more users, more misses arrive than the 16 build slots can clear, so the extra requests get a **503 "busy, retry" after 3 s**. The screen retries them itself; it isn't a slow pile-up. This is the VPN's latency.

**Inside Azure** a miss takes about 5–20 ms. An earlier run against a copy of the serving tables, made before the "STG only" instruction, carried **8,000 users at p95 56–293 ms** (doc [16](16-portal-and-staging-test.md)).

Run `user_mix.py` on the staging VM itself to confirm this on STG, which needs IT's server.

### 4.3 What the tests changed

| Found | Fix |
|---|---|
| nginx's per-IP connection limit (64) rejected users behind one address, as in a client office behind one NAT | Removed; the API's admission control protects the core |
| Uncompressed responses: p95 3.5 s at 8,000 users | Pre-gzipped files: p95 56 ms, and 1–2 ms once static |
| One worker on one core: 3,324 errors at 6,000 users | 2 workers, and the open-file limit raised in the image |
| An old `index.html` stayed in browser caches after a release | `index.html` is served `no-cache`; assets are hashed and cached for a year |
| Trends computed per request | Published per family (5,360 files) |
| Search recomputed for every request | Cached; FTS5 index in memory |

## 5. End-to-end click test: everything clicked, data checked

[`clicktest.py`](../../scripts/ui_benchmark/clicktest.py) drives a real headless Chrome against the staging stack on STG data. For each wave and screen it:
1. opens the screen and waits until it's **fully drawn with data** (charts drawn, tables filled, numbers shown);
2. **clicks every control:** chart types, column cuts, sort, grid rows, letters/arrows, reference columns, the two-cut selectors, week pooling, time ranges, toggles, the first questions in the list, survey answers;
3. after each click, checks the data is there and no error shows;
4. goes back in browser history and checks the screen restores;
5. records every console error and failed request.

| Run | Screen visits | Clicks or changes | Passed | Console errors | Failed requests |
|---|--:|--:|--:|--:|--:|
| First run (found the bugs below) | 24 | 160 | 18 | 0 | 12 |
| **Final run** | **24** | **140** | **24** | **0** | **0** |

The **bugs it found, now fixed**:
- Trends showed an error, not "nobody in this group", for surveys without demographic profiles.
- Cuts with 0 respondents were offered on archive and ad hoc surveys.
- Waves with no results were offered in the library.
- Single-wave surveys requested a trend.
- (From the screenshots) "vs previous wave" compared across a season gap: Sep 2026 vs Dec 2025, +47.9 pts.

**Layout:** no sideways scrolling at 1440, 1024, 768 or 390 px (library, overview, cross-tab). **Theme:** dark ⇄ light round trip passes.

## 6. Search

Measured on all 3,719 question wordings from STG: **0.1–7 ms per query**, and the index builds in about 5 s at start-up.

| Typed | Found | How |
|---|---|---|
| `holidy shoping` | holiday shopping questions | spelling corrected, and the page says so |
| `klarna`, `bnpl` | buy-now-pay-later questions | synonym list (business-editable YAML) |
| `ozempic`, `glp1` | weight-loss medication questions | synonyms |
| `walmart` | Walmart+ membership, retailer questions | answer labels are indexed |
| `where do people buy groceries` | online grocery questions | trigram fallback on word fragments |
| `xm3`, `q6` | that question code | code field weighted highest |

Searches with no results are logged, so the synonym list can grow monthly. Tests are in `tests/test_search.py`.

## 7. ETL: time and RAM per survey and per day (STG)

From doc [17](17-etl-time-and-ram.md) and its measured addendum:

| | Value |
|---|---|
| Weekly wave, measured twice on STG | **150 s and 137 s**, peak RAM **179–184 MB**, CPU only **2.4 s** |
| Slowest stages | tracker_line 34–36 s (missing index), cube 28 s, write 15–24 s, definitions 13 s, serving 12–14 s |
| Large annual survey | 3.5–9 min |
| Per day | about 2.4 min × N weekly surveys (10 a day ≈ 25 min), RAM flat at about 180 MB, plus about 100 s to publish |
| Faster | Run the ETL inside Azure (98 % of the time is waiting on the network), add the tracker_line index, and three more fixes in doc 17. Expect about 1 min per weekly survey |

## 8. Chatbot readiness

The design is in [20](20-chatbot-ready-design.md). The bot will use **tool-calling over the typed API**:
- tools: list surveys, find questions, get a wave, get a trend, get a cross-tab, get a module dashboard;
- schemas come from the API's OpenAPI document (`/api/v1/openapi.json`, switched on);
- numbers always come with their base, flags and wave, and suppressed cells are never shown;
- it is never text-to-SQL;
- **still to add before the bot:** a metric catalogue, canonical question IDs, a request log and a gold-question evaluation set.

## 9. Repository clean-up (approved, done)

**Removed** (the previous versions are in git history):
- the 24 duplicate root diagrams;
- Archify QA output and an unfinished project (`.archify` 6.8 → 3.7 MB);
- 2 byte-identical ChatGPT copies;
- caches and one-off logs.

**Untracked:** `web/tsconfig.tsbuildinfo` and `logs/notify-state.json`, now in `.gitignore`.

**Untouched:** the Gemini files, `.env` and the zip.

**README:** rewritten for the current structure.

## 10. Still open

| Item | Owner | Why it matters |
|---|---|---|
| **Rotate the leaked DB password and the Forsta key in `.env.example`, make the repo private** | You | The only live risk (council's "do first") |
| Run `user_mix.py` on the real staging VM | IT server | Confirms the cross-tab numbers on an Azure core (§4.2) |
| SSO in front of nginx | IT and us | The dev login stands in today |
| Decide **weighting** | Research | The figures are unweighted; changing that later rebuilds the serving tables |
| 5 legacy waves have no cube data (ids 14, 16–19) | ETL | Shown as "no results loaded" |
| ETL fixes from doc 17; run the ETL inside Azure | Us | Brings 2.4 min down to about 1 min per survey |
| Metric catalogue, canonical IDs, request log, gold set | Us | Before the chatbot |
| PPTX export, saved views, Top-2 box, event markers on trends | Us | Next competitor gaps ([18](18-rea-competitor-dashboards.md)) |

## 11. Re-run everything

```bash
# images and publish (STG)
docker build -f deploy/Dockerfile --target api -t cip-portal .
docker build -f deploy/Dockerfile --target nginx -t cip-web .
CIP_PUBLISH_DIR=/srv/cip/published python -m etl.publish
# staging stack: nginx + API on one core
CIP_PUBLISH_DIR=/srv/cip/published docker compose -f deploy/compose.yml up -d
# load, click and screenshot tests (headless Chrome on :9333 for the last two)
python scripts/ui_benchmark/user_mix.py http://<server>:8080 --users 1000,4000,8000,16000
python scripts/ui_benchmark/clicktest.py http://<server>:8080 --waves 412,415,261,259
python scripts/ui_benchmark/shots.py http://<server>:8080 out/ / /w/412 --theme dark
# code checks
.venv/bin/python -m pytest -q && npm --prefix web run check
```
