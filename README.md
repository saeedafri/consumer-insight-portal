# Consumer Insight Portal (CIP)

Coresight Research · survey analytics on the STG (DWH) database.

CIP pulls consumer-survey data from the **Forsta Surveys** platform
(`se1.decipherinc.com`, formerly Decipher) into MySQL and serves it through a
Streamlit portal, replacing the Excel round-trip that analysis runs on today.

---

## Status

| Piece | State |
|---|---|
| Source-data analysis | done — both 09/21/26 exports fully parsed |
| Database schema | drafted — 16 tables, 6 views, DDL ready to apply |
| Excel loader | working end to end |
| Forsta API client | written; **needs an API key** |
| Streamlit portal | 5 pages scaffolded |

**Blocking:** a Forsta service-account API key. See
[`docs/04-it-requirements-checklist.md`](docs/04-it-requirements-checklist.md).

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env            # fill in STG_DB_* and FORSTA_*
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
│   ├── core/               config + pooled SQLAlchemy access
│   ├── data/repository.py  every query the app makes, cached
│   ├── components/         validated palette, Plotly builders
│   └── pages/              Overview · Questions · Cross-tabs · Trends · Health
├── etl/
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
| [`02-schema-design.md`](docs/02-schema-design.md) | the 16 tables and why the fact table is long |
| [`03-forsta-integration.md`](docs/03-forsta-integration.md) | endpoints, auth, incremental loading, failure modes |
| [`04-it-requirements-checklist.md`](docs/04-it-requirements-checklist.md) | **what to send IT** |
| [`05-source-data-analysis.md`](docs/05-source-data-analysis.md) | what the two Excel files actually contain |

## Conventions

Matches `market-data-stg` and `SIP-Prod`: `APP_ENV` of `LOCAL`/`STAGING`/
`PRODUCTION`, `STG_DB_*` credentials, SSL via `DigiCertGlobalRootG2.crt.pem`,
SQLAlchemy + PyMySQL with a pooled engine, Streamlit pinned to 1.55.0, Coresight
red `#d62e2f`.

All database objects are prefixed `cip_` (views `v_cip_`) so nothing collides
with existing STG tables. The portal connects as a read-only account; only the
ETL can write.
