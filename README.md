# Consumer Insight Portal (CSI)

Coresight Research · survey analytics on the STG (DWH) database.

CIP pulls consumer-survey data from the **Forsta Surveys** API
(`se1.decipherinc.com`, formerly Decipher — read only, GET) into MySQL and
serves it through a Streamlit portal. Every weekly tracker wave is its own
Forsta survey; the pipeline discovers them and loads each one as it closes.

---

## Status — 29 September 2026

| Piece | State |
|---|---|
| Source data | 4 exports analysed: 09/21/26 and 09/28/26, raw + cross-tab each ([05](docs/05-source-data-analysis.md)) |
| Database | **`dwh_stg`**, account `dwh_app_access` — schema v2: 29 `csi_` tables + 8 `v_csi_` views (Phase 1 of the [survey platform design](docs/superpowers/specs/2026-09-29-survey-platform-design.md)) |
| Data loaded | Forsta: both 2026 waves (404 + 403). History: 141 Qualtrics waves Aug 2022 – Apr 2025 from `dwh_sm*` + the May 2025 Excel export — 144 waves, 71,474 qualified respondents, 10.4 M answer rows |
| Verified | `scripts/reconcile.py`: 667/667 and 788/788 published cells reproduced from raw answers ([09](docs/09-data-verification.md)); all 141 legacy waves match their source (41,124 answer counts, 0 differences); Beauty retailer check vs the analysts' workbook: Amazon.com 492 = 492 |
| Forsta API | adapter + unattended weekly run (`scripts/weekly_forsta.py`) built and proven equal to the Excel path; the key on file is **rejected (401)** — the first live run is one command once IT's key is in `.env` ([03](docs/03-forsta-integration.md), [04](docs/04-it-requirements-checklist.md)) |
| Portal | Overview · Questions · Analysis Builder · Cross-tabs · Trends · Data Health; cohort filters, breaks, grids, Excel export on every table |
| Dynamic surveys | rotating weekly modules load without code changes; topics resolved from `config/survey_map.yml` |
| Harmonisation | every wave's questions linked to canonical concepts on load (828 concepts, 251 span several waves); 985 uncertain matches wait on the **Mappings** page (`/mappings`, filter by wave, 25 per page) |
| Cohorts & cube | named cohorts over concepts (`config/cohorts.yml`: Beauty shoppers — reproduces the analysts' workbook exactly on its 1,614 respondents); pre-computed cube for all 144 waves; standard view P95 0.35 s, ad-hoc cohort 0.82 s, five-wave stack 0.26 s over the VPN (`scripts/perf_check.py`) |
| Publications | delivered tables frozen with their definition and footnote; the **Publications** page (`/publications`) re-checks every one against today's data cell by cell (replaces the manual Cross-Check tab); `python -m app.data.publications --drift` exits 1 when a published number moved |

**Run it against `dwh_stg`** (VPN on): `.venv/bin/streamlit run app/main.py` — sign-in is bypassed locally (`APP_ENV=LOCAL` + `DEBUG=true`); OIDC/SSO to follow, as in MDP/SIP
**Run it offline** on a SQLite copy: `bash scripts/run_local.sh`

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# .env: STG host from market-data-stg/.env, dwh_stg account from Code-Base/Modular-Code/.env
python scripts/test_connection.py
python scripts/init_db.py

python -m etl.forsta_etl --discover   # register every survey the key can see (cip_forsta_survey)
python -m etl.forsta_etl --due        # load every closed, readable, unloaded wave; verify; cube; search
python scripts/reconcile.py           # re-read each wave from Forsta and compare every answer
python scripts/weekly_forsta.py       # the scheduled run: discover → load due → drift (exit code = outcome)

streamlit run app/main.py --server.port 8611
```

---

## Layout

```
consumer-insight-portal/
├── app/                    Streamlit portal
│   ├── main.py             entry point and navigation
│   ├── core/               config, pooled SQLAlchemy access, SQLite fallback
│   ├── data/repository.py  every query the app makes, cached
│   ├── components/         header nav, validated palette, Plotly builders, Excel export
│   ├── data/harmonise.py   links each wave's questions to concepts (spec §5.2)
│   └── pages/              Overview · Survey report · Analysis Builder · Trends · Mappings · Publications · Health
├── config/survey_map.yml   topic rules and demographic detection — edit here, not in code
├── etl/
│   ├── survey_map.py       resolves topics and cuts for a questionnaire it has never seen
│   ├── forsta_client.py    Forsta REST client (x-apikey, retries; GET only)
│   ├── forsta_api.py       datamap → questions (labels, bipolar grids, other-specify, flags)
│   ├── forsta_etl.py       discover → load → verify → publish → harmonise / cube / search
│   ├── records.py          shared parsed-question shape and text helpers
│   ├── loaders.py          idempotent upserts, search index
│   ├── legacy_dwh.py       Qualtrics / SurveyMonkey history from dwh_sm*
│   └── run_pipeline.py     loader steps shared by every source
├── sql/                    001 schema · 002 views · 003 seed · 004 grants
├── scripts/                init_db.py · test_connection.py · reconcile.py · weekly_forsta.py · perf_check.py
├── tests/
└── docs/                   plan · schema · integration · IT checklist · data analysis
```

## Documentation

| Document | Read it for |
|---|---|
| [`01-implementation-plan.md`](docs/01-implementation-plan.md) | phases, decisions, risks |
| [`02-schema-design.md`](docs/02-schema-design.md) | the 19 `csi_` tables, and why every percentage carries its own base |
| [`03-forsta-integration.md`](docs/03-forsta-integration.md) | endpoints, auth, incremental loading, failure modes |
| [`04-it-requirements-checklist.md`](docs/04-it-requirements-checklist.md) | **what to send IT** |
| [`05-source-data-analysis.md`](docs/05-source-data-analysis.md) | what the two Excel files actually contain |
| [`06-running-locally.md`](docs/06-running-locally.md) | the two run modes, and what local mode does not test |
| [`07-analysis-builder.md`](docs/07-analysis-builder.md) | the cohort engine, how the base travels, and the label/code bug |
| [`08-authentication.md`](docs/08-authentication.md) | providers, what IT must register for SSO, and what is not tested |
| [**Survey platform design (schema v2)**](docs/superpowers/specs/2026-09-29-survey-platform-design.md) | the target design for every survey platform — approved; Phase 1 live |
| [`10-analyst-workbook-review-and-schema-v2.md`](docs/10-analyst-workbook-review-and-schema-v2.md) | tab-by-tab review of the analysts' workbook and the defects found |
| [`09-data-verification.md`](docs/09-data-verification.md) | the reconciliation, the defects it caught, and the Forsta region-banner gap |

## Conventions

Matches `market-data-stg` and `SIP-Prod`: `APP_ENV` of `LOCAL`/`STAGING`/
`PRODUCTION`, `STG_DB_*` credentials, SSL via `DigiCertGlobalRootG2.crt.pem`,
SQLAlchemy + PyMySQL with a pooled engine, Streamlit pinned to 1.55.0, Coresight
red `#d62e2f`.

All database objects are prefixed `cip_` (views `v_cip_`) so nothing collides
with existing STG tables. The portal connects as a read-only account; only the
ETL can write.
