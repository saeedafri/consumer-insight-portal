# Running the Portal

Three modes, one codebase.

| Mode | Settings | Database | Sign-in |
|---|---|---|---|
| **Local testing** (default in `.env`) | `APP_ENV=LOCAL`, `DEBUG=true`, `LOCAL_TEST_USER_EMAIL` | `dwh_stg` (VPN on) | **bypassed** — you act as `LOCAL_TEST_USER_EMAIL` |
| **STG** | `APP_ENV=STAGING` | `dwh_stg` | required |
| **Offline** | `APP_ENV=LOCAL`, `LOCAL_SQLITE_PATH=data/csi_local.db` | a SQLite file in `data/` | bypassed if `DEBUG=true` |

Local testing is the Market Data Portal's pattern: the same gate
(`APP_ENV=LOCAL` + `DEBUG=true`), the same live database. The header shows
"sign-in bypassed (local)" in amber so it can't be mistaken for a real session.
The bypass cannot switch on anywhere `APP_ENV` is not `LOCAL` — STG and PROD set
`APP_ENV` in their App Settings.

```bash
.venv/bin/streamlit run app/main.py          # local testing on dwh_stg, no sign-in
```

The MySQL DDL in `sql/001_schema.sql` is the single source of truth. Local mode
converts it on the fly (`app/core/sqlite_compat.py`) rather than keeping a
second schema that drifts — so what you develop against is the schema that
ships.

---

## Local (works right now, no credentials)

```bash
bash scripts/run_local.sh
```

Creates the venv, builds the schema, loads the 09/21/26 wave from
`data/*.xlsx`, and opens the portal on <http://127.0.0.1:8501>.

Verified run, 28 September 2026:

```
Parsed 93 question blocks from the datamap
Loaded 375 variables
Loaded 404/404 respondents
Profile mapping for survey_id=1: age<-D2, ethnicity<-D4, gender<-D1,
  income_band<-D5, outlook_economy<-CS2, outlook_income<-CS1, political<-D7,
  relationship<-D3, state_name<-D8, urbanicity<-D6
Rebuilt 404 profiles
Rebuilt question bases
Loaded 31800/33240 cross-tab cells
Skipped 1440 cells with no matching question: voqtable1(160) … vterm(160)
```

Those 1,440 are the quota and terminate tables. Forsta prints them in the
cross-tab but never puts them in the datamap, so they have no question to
attach to. They are counted in `csi_load_log.rows_bad`, not silently dropped.

## STG

```bash
bash scripts/setup.sh
```

Same steps against `dwh_stg`. Needs `.env` filled in (it already is) and a
network route to the Azure server.

---

## Harmonisation

Every load now links the wave's questions to canonical concepts automatically
(`app/data/harmonise.py`). Exact matches confirm themselves; the rest wait on
the **Mappings** page. To (re)link waves loaded before Phase 2:

```bash
python -m app.data.harmonise --all            # every wave, oldest first
python -m app.data.harmonise --wave 2026-09-28
```

Safe to re-run: a question that already has a decision is left alone.

## Survey history (Qualtrics 2022 – 2025)

The legacy tables (`dwh_sm*`, read-only) sit on the same server as `csi_*`,
so answers are copied inside MySQL; only the question definitions travel.
Over the VPN a wave takes 20–60 s; all 141 take about an hour.

```bash
python -m etl.legacy_dwh --all                     # every Qualtrics-era wave, oldest first
python -m etl.legacy_dwh --id SV_0IHGTy1GPAlUsGa   # one wave (Feb 2025 Beauty)
python -m etl.qualtrics_export --wave 2025-05-12 \
    --file "Shopping and Spending - inc Beauty + Inflation + Tariffs_May 20, 2025_08.00 1.xlsx"
python scripts/reconcile.py                        # Forsta cells + every legacy wave vs its source
```

Both are safe to re-run: a wave's answers are replaced, not duplicated, and
concept decisions are kept. Load the Excel export **after** the legacy waves —
its answers take their order from the concepts those waves create (the export
itself records answers in the order respondents happened to give them).

## What local mode does not test

- MySQL-specific behaviour: real `ENUM` enforcement, `utf8mb4` collation,
  connection pooling under load, the SSL handshake.
- `LAST_INSERT_ID()` semantics. The loaders no longer use it — ids are read
  back explicitly, which is portable and survives a proxy — but if you add a
  loader, do the same.
- Performance. SQLite on 404 respondents says nothing about MySQL on a year of
  waves.

Treat a green local run as "the logic is right", not "it will work on STG".
The first STG run still needs watching.
