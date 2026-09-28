# Consumer Insight Portal (CSI)

Coresight Research · survey analytics on the STG (DWH) database.

CSI pulls consumer-survey data from the **Forsta Surveys** platform
(`se1.decipherinc.com`, formerly Decipher) into MySQL and serves it through a
Streamlit portal, replacing the Excel round-trip that analysis runs on today.

---

## Status

| Piece | State |
|---|---|
| Source-data analysis | done — both 09/21/26 exports fully parsed |
| Database schema | 17 `csi_` tables + 8 views, applied and exercised end to end |
| Excel loader | working end to end |
| Forsta API client | written; key found in `Dwh/credentials.yml` and wired into `.env` |
| Streamlit portal | 5 pages, **running against the real 09/21/26 data** |
| Dynamic surveys | topics and demographic cuts resolved per wave from `config/survey_map.yml` |

**To see it now, with no credentials:** `bash scripts/run_local.sh`
**To point it at `dwh_stg`:** `bash scripts/setup.sh` — needs a network route
to the Azure server, which this cloud session does not have.

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# .env is already populated from market-data-stg/.env and Dwh/credentials.yml
python scripts/test_connection.py
python scripts/init_db.py

# load a wave from the Excel exports (works without the API key)
python -m etl.run_pipeline --source excel \
    --raw "Raw Data 09_21_26.xlsx" \
    --crosstab "Cross Tabs 09_21_26.xlsx" \
    --wave 2026-09 --family CSI-US

streamlit run app/main.py
```

Once the API key is in `.env`:

```bash
python -m etl.run_pipeline --source api --wave 2026-10 --family CSI-US
```

---

## Layout

```
consumer-insight-portal/
├── app/                    Streamlit portal
│   ├── main.py             entry point and navigation
│   ├── core/               config, pooled SQLAlchemy access, SQLite fallback
│   ├── data/repository.py  every query the app makes, cached
│   ├── components/         validated palette, Plotly builders
│   └── pages/              Overview · Questions · Cross-tabs · Trends · Health
├── config/survey_map.yml   topic rules and demographic detection — edit here, not in code
├── etl/
│   ├── survey_map.py       resolves topics and cuts for a questionnaire it has never seen
│   ├── forsta_client.py    Forsta REST client (x-apikey, retries, paging)
│   ├── excel_parsers.py    parsers for both workbook formats
│   ├── loaders.py          idempotent upserts
│   └── run_pipeline.py     CLI — one command, two sources
├── sql/                    001 schema · 002 views · 003 seed · 004 grants
├── scripts/                init_db.py · test_connection.py
├── tests/
└── docs/                   plan · schema · integration · IT checklist · data analysis
```

## Documentation

| Document | Read it for |
|---|---|
| [`01-implementation-plan.md`](docs/01-implementation-plan.md) | phases, decisions, risks |
| [`02-schema-design.md`](docs/02-schema-design.md) | the 16 `csi_` tables, and why every percentage carries its own base |
| [`03-forsta-integration.md`](docs/03-forsta-integration.md) | endpoints, auth, incremental loading, failure modes |
| [`04-it-requirements-checklist.md`](docs/04-it-requirements-checklist.md) | **what to send IT** |
| [`05-source-data-analysis.md`](docs/05-source-data-analysis.md) | what the two Excel files actually contain |
| [`06-running-locally.md`](docs/06-running-locally.md) | the two run modes, and what local mode does not test |

## Conventions

Matches `market-data-stg` and `SIP-Prod`: `APP_ENV` of `LOCAL`/`STAGING`/
`PRODUCTION`, `STG_DB_*` credentials, SSL via `DigiCertGlobalRootG2.crt.pem`,
SQLAlchemy + PyMySQL with a pooled engine, Streamlit pinned to 1.55.0, Coresight
red `#d62e2f`.

All database objects are prefixed `csi_` (views `v_csi_`) so nothing collides
with existing STG tables. The portal connects as a read-only account; only the
ETL can write.
