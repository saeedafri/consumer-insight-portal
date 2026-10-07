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
.venv/bin/streamlit run app/main.py --server.port 8611   # local testing on dwh_stg, no sign-in
```

The MySQL DDL in `sql/001_schema.sql` is the single source of truth. Local mode
converts it on the fly (`app/core/sqlite_compat.py`) rather than keeping a
second schema that drifts — so what you develop against is the schema that
ships.

---

## Offline (SQLite)

```bash
bash scripts/run_local.sh                        # schema + portal on http://127.0.0.1:8611
bash scripts/run_local.sh selfserve/58f/260907   # also load that wave from the Forsta API (GET only)
```

Creates the venv, builds or upgrades the schema in `data/csi_local.db`, and
starts the portal on port 8611 (8501/8503 belong to the Market Data Portal).
The Excel route is retired: waves come from the Forsta API only.

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
python -m etl.legacy_dwh --all --era surveymonkey # the SurveyMonkey years, 2018 – 2022
python -m etl.qualtrics_export --wave 2025-05-12 \
    --file "Shopping and Spending - inc Beauty + Inflation + Tariffs_May 20, 2025_08.00 1.xlsx"
python scripts/reconcile.py                        # every Forsta wave vs the API, every legacy wave vs its source
```

SurveyMonkey waves bring two extras: matrix questions load as grids (each cell is the column id plus its "<row> | <column>" text), and SurveyMonkey Audience's panel demographics (age, gender, income, Census division) fill the profile wherever no question did. A wave that fails is logged and skipped; `--all` carries on and exits 1 with the list to rerun with `--id`.

Both are safe to re-run: a wave's answers are replaced, not duplicated, and
concept decisions are kept. Load the Qualtrics export **after** the legacy waves —
its answers take their order from the concepts those waves create (the export
itself records answers in the order respondents happened to give them).

## Cohorts and the cube (Phase 4)

A **cohort** is a named rule over questions (`config/cohorts.yml`), applied the
same way to every wave. The **cube** (`cip_agg_cell`) pre-counts every answer
by the standard cuts, for everyone and each cohort, so standard views are one
indexed read. Every load builds its wave's cube; after editing
`config/cohorts.yml`, or to rebuild everything:

```bash
python -m app.data.cohorts --sync      # define/version the cohorts, derive every wave
python -m app.data.cube --all          # rebuild every wave's cube (~35 s a wave over the VPN)
python scripts/perf_check.py           # P95 of the three speed targets
```

Confirming a mapping on `/mappings` re-derives that wave's cohorts and
rebuilds only the cohort cells whose membership changed.

## Publications (Phase 5)

A delivered table is published from the **Publications** page (or
`app.data.publications.publish`) and frozen with its definition. Re-check every
publication against today's data — run it after any load or mapping change:

```bash
python -m app.data.publications --drift    # exit 1 if any published number moved
```

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
