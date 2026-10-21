# Consumer Insight Portal (CIP)

Coresight Research · consumer-survey analytics on the STG database (`cip_stg`).

CIP pulls consumer-survey data from the **Forsta Surveys** API (`se1.decipherinc.com`, read only, GET) into
MySQL, builds screen-agnostic serving tables, and serves them to analysts and clients through:

- **the portal** (`web/` React + Vite, `api/` FastAPI): every survey and wave since 2018. Library, search,
  overview with the business Databank tiles, question explorer, cross-tabs (incl. two cuts), trends, what changed,
  survey preview. Coresight palette, light and dark;
- **Streamlit staff pages** (`app/pages/`): data health, mappings, publications, analysis builder.

Every weekly tracker wave is its own Forsta survey; the pipeline discovers each one as it closes, loads it,
verifies it, builds the cube and serving tables, and publishes the portal's standard screens as static files.

**Design and test results:** [`docs/Ui-Design-Claude/00-README.md`](docs/Ui-Design-Claude/00-README.md). That covers
the stack decision, the serving design, the staging tests at 1 core / 4 GB, the ETL time and RAM, the council
verdict and the chatbot readiness.

---

## Status: data platform (September–October 2026)

| Piece | State |
|---|---|
| Source data | 4 exports analysed: 09/21/26 and 09/28/26, raw + cross-tab each ([05](docs/05-source-data-analysis.md)) |
| Database | **`cip_stg`** (moved from `dwh_stg` on 14 Oct 2026), account `mohdsaeedafri` — 33 `cip_` tables, 12 `v_cip_` views, and the 7 `dwh_sm*` Qualtrics/SurveyMonkey source tables (copied from `dwh_stg` on 19 Oct 2026, row counts and checksums equal; `scripts/move_legacy_source.py`). Nothing in `cip_stg` reads `dwh_stg` any more. Analysts start from `v_cip_wave`, `v_cip_respondent`, `v_cip_answer_long` |
| Data loaded | Forsta: both 2026 waves (404 + 403). History: 141 Qualtrics waves Aug 2022 – Apr 2025 from `dwh_sm*` + the May 2025 Excel export — 144 waves, 71,474 qualified respondents, 10.4 M answer rows |
| Verified | `scripts/reconcile.py`: 667/667 and 788/788 published cells reproduced from raw answers ([09](docs/09-data-verification.md)); all 141 legacy waves match their source (41,124 answer counts, 0 differences); Beauty retailer check vs the analysts' workbook: Amazon.com 492 = 492 |
| Forsta API | adapter + unattended weekly run (`scripts/weekly_forsta.py`) built and proven equal to the Excel path; the key on file is **rejected (401)** — the first live run is one command once IT's key is in `.env` ([03](docs/03-forsta-integration.md), [04](docs/04-it-requirements-checklist.md)) |
| Portal | Overview · Questions · Analysis Builder · Cross-tabs · Trends · Data Health; cohort filters, breaks, grids, Excel export on every table |
| Dynamic surveys | rotating weekly modules load without code changes; topics resolved from `config/survey_map.yml` |
| Harmonisation | every wave's questions linked to canonical concepts on load (828 concepts, 251 span several waves); 985 uncertain matches wait on the **Mappings** page (`/mappings`, filter by wave, 25 per page) |
| Cohorts & cube | named cohorts over concepts (`config/cohorts.yml`: Beauty shoppers — reproduces the analysts' workbook exactly on its 1,614 respondents); pre-computed cube for all 144 waves; standard view P95 0.35 s, ad-hoc cohort 0.82 s, five-wave stack 0.26 s over the VPN (`scripts/perf_check.py`) |
| Publications | delivered tables frozen with their definition and footnote; the **Publications** page (`/publications`) re-checks every one against today's data cell by cell (replaces the manual Cross-Check tab); `python -m app.data.publications --drift` exits 1 when a published number moved |

**Run the portal** (VPN on, against `cip_stg`): `npm --prefix web run build`, then
`APP_ENV=LOCAL CIP_SESSION_SECRET=<random> .venv/bin/gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 127.0.0.1:8000`
and open http://127.0.0.1:8000/auth/dev-login. **Deploy:** `deploy/compose.yml` (nginx + API on one server), and
`python -m etl.publish` after each load.

**Run the Streamlit staff pages against `cip_stg`** (VPN on): `.venv/bin/streamlit run app/main.py` — sign-in is bypassed locally (`APP_ENV=LOCAL` + `DEBUG=true`); OIDC/SSO to follow, as in MDP/SIP
**Run it offline** on a SQLite copy: `bash scripts/run_local.sh`

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# .env: STG host from market-data-stg/.env, STG_DB_NAME=cip_stg, account DB_USER_DWH from Code-Base/Modular-Code/.env
python scripts/test_connection.py
python scripts/init_db.py

python -m etl.forsta_etl --discover   # register every survey the key can see (cip_forsta_survey)
python -m etl.forsta_etl --due        # load every closed, readable, unloaded wave; verify; cube; search
python scripts/reconcile.py           # re-read each wave from Forsta and compare every answer
python scripts/weekly_forsta.py       # the scheduled run: discover → load due → integrity → drift (exit code = outcome)
python -m etl.integrity --check       # is the warehouse whole? (without --check it also heals derived rows)
python scripts/backup_db.py           # proven dump of cip_stg to backups/ (weekly via launchd com.coresight.cip-backup)
python -m etl.tracker_line --compare "Weekly Line-By-Line Survey Data.xlsx"   # ETL vs the team's file

streamlit run app/main.py --server.port 8611
```

---

## Layout

```
consumer-insight-portal/
├── api/                    FastAPI for the portal: main.py (endpoints, cache, admission control), search.py (FTS5),
│                           dashboards.py (module Databank tiles and takeaways from config/dashboards.yml)
├── web/                    React 19 + Vite + TypeScript portal (src/pages, src/components, Coresight theme)
├── app/                    Streamlit staff pages, plus the shared library every part imports:
│   ├── core/               config, pooled SQLAlchemy access, SQLite fallback, schema upgrades
│   └── data/               repository, cube, harmonise, cohorts, publications, payloads (the portal's responses)
├── etl/                    Forsta and legacy loaders, verification, serving tables (serving.py),
│                           static publishing for nginx (publish.py), notifications, integrity
├── config/                 survey map, cohorts, banners, calendar, dashboards, search synonyms (all YAML)
├── sql/                    001 schema · 002 views · 003 seed · 004 grants · 005 serving · 006 dashboards
├── deploy/                 Dockerfile (api + nginx targets), compose.yml, nginx.conf
├── scripts/                weekly run, backup, init, reconcile, checks, doc build; launchd jobs;
│   └── ui_benchmark/       reproducible load, browser and click tests behind the docs' numbers
├── tests/                  pytest suite (web: `npm --prefix web run check` for the statistics)
└── docs/                   decision log 01–14, business and technical specs, diagrams, UI and serving design
```

## Documentation

| Document | Read it for |
|---|---|
| [**CIP — Business Description**](docs/CIP-Business-Description.pdf) ([md](docs/CIP-Business-Description.md), [Word](docs/CIP-Business-Description.docx)) | for the business team: how the surveys run, the patterns, what is collected, how the pipeline works, quality and privacy |
| [**CIP — Technical Specification**](docs/CIP-Technical-Specification.pdf) ([md](docs/CIP-Technical-Specification.md), [Word](docs/CIP-Technical-Specification.docx)) | API, extract, transform, load, derived data, data dictionary, survey patterns, runbook — sections in `docs/technical/` |
| [**Portal design, tests and system design**](docs/Ui-Design-Claude/00-README.md) | stack decision, serving tables, staging tests at 1 core / 4 GB, ETL time and RAM, council verdict, chatbot readiness |
| [`docs/diagrams/`](docs/diagrams/) | editable Excalidraw (`.excalidraw`), Mermaid source (`.mmd`), SVG and PNG of every flow; interactive Archify pages in `.archify/` |
| [`01-implementation-plan.md`](docs/01-implementation-plan.md) | phases, decisions, risks |
| [`02-schema-design.md`](docs/02-schema-design.md) | the first schema (now `cip_` tables, see the Technical Specification), and why every percentage carries its own base |
| [`03-forsta-integration.md`](docs/03-forsta-integration.md) | endpoints, auth, incremental loading, failure modes |
| [`04-it-requirements-checklist.md`](docs/04-it-requirements-checklist.md) | **what to send IT** |
| [`05-source-data-analysis.md`](docs/05-source-data-analysis.md) | what the two Excel files actually contain |
| [`06-running-locally.md`](docs/06-running-locally.md) | the two run modes, and what local mode does not test |
| [`07-analysis-builder.md`](docs/07-analysis-builder.md) | the cohort engine, how the base travels, and the label/code bug |
| [`08-authentication.md`](docs/08-authentication.md) | providers, what IT must register for SSO, and what is not tested |
| [**Survey platform design (schema v2)**](docs/superpowers/specs/2026-09-29-survey-platform-design.md) | the target design for every survey platform — approved; Phase 1 live |
| [`10-analyst-workbook-review-and-schema-v2.md`](docs/10-analyst-workbook-review-and-schema-v2.md) | tab-by-tab review of the analysts' workbook and the defects found |
| [`14-pipeline-validation-report.md`](docs/14-pipeline-validation-report.md) | audit of 19 Oct 2026: bottlenecks, integrity, the cross-tab check vs the team's files, self-healing ([design](docs/pipeline-resilience.yml)) |
| [`09-data-verification.md`](docs/09-data-verification.md) | the reconciliation, the defects it caught, and the Forsta region-banner gap |

## Conventions

Matches `market-data-stg` and `SIP-Prod`: `APP_ENV` of `LOCAL`/`STAGING`/
`PRODUCTION`, `STG_DB_*` credentials, SSL via `DigiCertGlobalRootG2.crt.pem`,
SQLAlchemy + PyMySQL with a pooled engine, Streamlit pinned to 1.55.0, Coresight
red `#d62e2f`.

All database objects are prefixed `cip_` (views `v_cip_`) so nothing collides
with existing STG tables. The portal connects as a read-only account; only the
ETL can write.
