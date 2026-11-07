# Coresight Consumer Insight Portal (CIP)

Coresight Research's US consumer-survey portal. Every survey comes from **Forsta** (read only). A scheduled pipeline loads
each wave when its fieldwork ends, checks it against Forsta, and publishes the portal's screens; analysts and clients read
them in the browser.

## Where things are

| Folder | What it is | Language |
|---|---|---|
| [`frontend/`](frontend/) | **The website**: public pages and the portal (at `/app`). Built once into plain files | Next.js (TypeScript) |
| [`api/`](api/) | **The backend**: answers the website's data requests, sign-in, search, exports, the admin logs page | Python, FastAPI |
| [`etl/`](etl/) | **The data pipeline**: Forsta → database → checks → serving tables → published files | Python |
| [`shared/`](shared/) | Shared code the backend and the pipeline both use: settings, database access, the answer payloads | Python |
| [`scripts/`](scripts/) | Jobs to run: the scheduled pipeline run, backups, schema setup, checks | Python |
| [`config/`](config/) | Settings in plain YAML: who may see what, survey rules, dashboards, the launch schedule, email lists | YAML |
| [`sql/`](sql/) | Database tables and views (all named `cip_…`) | SQL |
| [`deploy/`](deploy/) | How it runs on a server: the Docker image, nginx, the process starter, the ETL schedule | Docker, nginx |
| [`tests/`](tests/) | Automated checks, run before every build | pytest |
| [`docs/`](docs/) | Business and technical documentation, the design, and the deployment guide | Markdown |

## How it works

```
Forsta (surveys) ──▶ etl/ (load, verify, harmonise, build serving tables) ──▶ MySQL cip_stg
                                                                    │
                                                    etl/publish.py ─┴─▶ published files (one per screen)
Browser ──▶ nginx ──▶ published files (most requests: ~1 ms, no database)
                 └──▶ api/ (cross-tabs, search, sign-in, admin) ──▶ MySQL cip_stg
```

- **One server, one container** (`deploy/Dockerfile`, target `app`): nginx serves the site and the published files, the API
  answers the rest, and the ETL runs on its schedule beside them. Caching at three levels: the browser (ETag, 304),
  nginx (published files and an answer cache) and the API (an answer cache per worker).
- **The ETL runs by itself** (`deploy/etl-loop.sh`): every Monday 12:00 UTC it watches the new weekly wave and loads it
  when fieldwork ends; every day at 03:30 UTC it loads any other survey that closed. Failures are emailed.
- **Operational logs** for admins at `/app/logs`: nginx requests and errors, the API, ETL runs, container restarts,
  Azure App Service's own log and security events.

## Data

| | |
|---|---|
| Source | **Forsta only** for every new survey (API, GET). History before July 2025 was loaded once from the old warehouse (SurveyMonkey 2018–2022, Qualtrics 2022–2025); the scheduled pipeline never reads it |
| Database | MySQL `cip_stg` on Azure (`csr-mysql8-flex-stg`). The portal reads; only the ETL writes |
| Waves | 373 verified waves, 18 Jan 2018 – 2 Nov 2026 |

## Definitions

| Rule | Value |
|---|---|
| Weighting | none by default: every percentage is unweighted, of qualified respondents |
| Base | each question's own: respondents who were asked it and answered |
| Small base | under 50: shown, flagged and faded |
| Suppressed | under 30: two-cut cross-tab and Compare cells show no number |
| Significance | two-proportion z-test at 95 %; What changed also applies Benjamini–Hochberg |
| Comparable | the same question: identical wording or answers harmonised to one concept; a reused code is a new version |
| Fieldwork over | 9 h after launch, or no quota left, or 400 qualified for a weekly tracker wave |

## Run it

**On a server:** see [docs/deployment/azure-app-service.md](docs/deployment/azure-app-service.md).

**On a laptop** (database access needed):

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env                  # fill in the database and Forsta settings
python scripts/test_connection.py     # can we reach MySQL and Forsta?
python scripts/weekly_forsta.py       # one pipeline run: discover → load what closed → verify → publish
python -m etl.publish                 # rebuild the published files
APP_ENV=LOCAL CIP_SESSION_SECRET=<random> gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w 1 -b 127.0.0.1:8000
cd frontend && npm ci && npm run dev  # the website, in another terminal
pytest -q                             # the checks
```

## Documentation

| Document | For |
|---|---|
| [Status](status/README.md) | what is done, waiting for deploy, pending and stuck: read it before starting, update it while working |
| [What's new](docs/CHANGELOG.md) | every feature, enhancement and update, the same as the portal's What's new page |
| [API and MCP guide](docs/API.md) | using the portal from programs and AI assistants with your own key, the same as the portal's API guide page |
| [Business description](docs/business/Business-Description.md) | the business team: the surveys, what is collected, how the pipeline works, quality and privacy |
| [Portal features](docs/business/portal-features.md) | what each screen does |
| [Technical documentation](docs/technical/00-overview.md) | Forsta API, extract, transform, load, serving tables, data dictionary, survey patterns, operations runbook |
| [Pipeline error handling](docs/technical/pipeline-resilience.yml) | every failure the scheduled run can meet and what it does about it |
| [Diagrams](docs/diagrams/) | every flow as Mermaid source and SVG |
| [Deployment](docs/deployment/azure-app-service.md) | Azure App Service: build, settings, sign-in, logs, schedule |
