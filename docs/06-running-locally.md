# Running the Portal

Two modes, one codebase.

| Mode | Database | When |
|---|---|---|
| **STG** | `dwh_stg` on the Coresight Azure MySQL server | the real thing |
| **Local** | a SQLite file in `data/` | no VPN, no credentials, a first look |

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
