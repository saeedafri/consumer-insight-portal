# Consumer Insight Portal (CSI)

Coresight Research · survey analytics on the STG (DWH) database.

CSI pulls consumer-survey data from the **Forsta Surveys** platform
(`se1.decipherinc.com`, formerly Decipher) into MySQL and serves it through a
Streamlit portal, replacing the Excel round-trip that analysis runs on today.

---

## Status — 29 September 2026

| Piece | State |
|---|---|
| Source data | 4 exports analysed: 09/21/26 and 09/28/26, raw + cross-tab each ([05](docs/05-source-data-analysis.md)) |
| Database | **`dwh_stg`**, account `dwh_app_access` — schema v2: 29 `csi_` tables + 8 `v_csi_` views (Phase 1 of the [survey platform design](docs/superpowers/specs/2026-09-29-survey-platform-design.md)) |
| Data loaded | both waves: 404 + 403 respondents, every answer, every published cross-tab cell |
| Verified | `scripts/reconcile.py`: 667/667 and 788/788 published cells reproduced from raw answers ([09](docs/09-data-verification.md)) |
| Forsta API | client written; key on file is **rejected — "account disabled"**. Excel bridge loads the same tables meanwhile ([04](docs/04-it-requirements-checklist.md)) |
| Portal | Overview · Questions · Analysis Builder · Cross-tabs · Trends · Data Health; cohort filters, breaks, grids, Excel export on every table |
| Dynamic surveys | rotating weekly modules load without code changes; topics resolved from `config/survey_map.yml` |
| Harmonisation | every wave's questions linked to canonical concepts on load; uncertain matches settled on the **Mappings** page (`/mappings`) |

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

# load a wave from the Excel exports (works without the API key)
python -m etl.run_pipeline --source excel \
    --raw "Raw Data 09_21_26.xlsx" \
    --crosstab "Cross Tabs 09_21_26.xlsx" \
    --wave 2026-09-21 --family CSI-US
python scripts/reconcile.py        # prove the load against the published cross-tab

streamlit run app/main.py
```

Once the API key is in `.env`:

```bash
python -m etl.run_pipeline --source api --wave 2026-10-05 --family CSI-US
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
│   └── pages/              Overview · Questions · Analysis Builder · Cross-tabs · Trends · Mappings · Health
├── config/survey_map.yml   topic rules and demographic detection — edit here, not in code
├── etl/
│   ├── survey_map.py       resolves topics and cuts for a questionnaire it has never seen
│   ├── forsta_client.py    Forsta REST client (x-apikey, retries, paging)
│   ├── excel_parsers.py    parsers for both workbook formats
│   ├── loaders.py          idempotent upserts
│   └── run_pipeline.py     CLI — one command, two sources
├── sql/                    001 schema · 002 views · 003 seed · 004 grants
├── scripts/                init_db.py · test_connection.py · reconcile.py
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

All database objects are prefixed `csi_` (views `v_csi_`) so nothing collides
with existing STG tables. The portal connects as a read-only account; only the
ETL can write.
