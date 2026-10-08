# Forsta Integration — How the Connection Works

Technical reference for the Forsta Surveys (Decipher) side. The credentials
checklist for IT is a separate document: `04-it-requirements-checklist.md`.
Design and investigation: `superpowers/specs/2026-10-07-cip-forsta-etl-and-ui-design.md`.

---

## The connection

| Setting | Value |
|---|---|
| API host | `se1.decipherinc.com` |
| API base | `https://se1.decipherinc.com/api/v1/` |
| Auth header | `x-apikey: <64-char key>` (`FORSTA_API_KEY` in `.env`, never printed) |
| Surveys | discovered — every survey the key can see; no survey path is configured |

Working since 7 October 2026 (user 879, company 86, directory "Coresight Research").

**Read only.** Every call is a `GET`. The pipeline never reactivates, edits or
deletes a survey, and never changes its status.

---

## How Forsta publishes the tracker

- **One survey per wave**: `selfserve/58f/YYMMNN` (e.g. 260907 = wave 2026-09-28).
- Launched Monday 12–13 UTC, closed the same night (median 12.8 h), ~400
  qualified / ~500 total, sample source 114.
- Tags: `Weekly consumer tracker`, `annual tracker` (Holiday, Amazon Apparel,
  Online Grocery, Back-to-school), untagged client studies.
- **Hibernation**: after ~3–4 months a survey answers `428` until someone
  reactivates it in Forsta. Hibernated waves are left alone.
- **Deletion**: Forsta deletes a survey 365 days after creation — the warehouse
  is the record, so every wave is loaded as soon as it closes.

---

## Endpoints the pipeline uses

| Method | Endpoint | Used for |
|---|---|---|
| GET | `rh/users/self` | auth check (`scripts/test_connection.py`, weekly run) |
| GET | `rh/companies/all/surveys` | discovery: path, title, state, hibernated, tags, dates, counts |
| GET | `surveys/<path>/datamap?format=json` | questions, variables, codes, labels, flags |
| GET | `surveys/<path>/data?format=json` | every respondent, **all statuses** (no `cond`) |

---

## The pipeline (`etl/forsta_etl.py`)

```
discover ─► load (one survey = one wave) ─► verify ─► publish ─► harmonise ─► cohorts/cube ─► search
```

```bash
python -m etl.forsta_etl --discover          # refresh the register (cip_forsta_survey)
python -m etl.forsta_etl --due               # discover, then load every closed, readable, unloaded wave
python -m etl.forsta_etl --survey selfserve/58f/260907
python -m etl.forsta_etl --reconcile         # every loaded Forsta wave vs the API
python -m etl.forsta_etl --reindex           # rebuild the search index of every verified wave
```

- **Register** `cip_forsta_survey`: one row per Forsta survey with its
  `load_state` — `due` (closed, readable, not loaded), `loaded`, `failed`,
  `hibernated`, `testing`.
- **Load**: the wave is `loading` (invisible) until it verifies. Codes are
  written as codes; labels come from the question *or* its variables; bipolar
  grids keep their left/right statements on `cip_item`; other-specify text is
  its own text question; flags `t`/`v` mark technical and virtual questions.
- **Personal data**: `userAgent`, `url`, `session`, `dcua`, `ipAddress` are
  never stored; the panel id (`RID`) only as a sha256 `respondent_key`.
- **Verify**: every record a respondent, every datamap variable a field, every
  field exactly as many answers as the payload. A mismatch → `failed`, recorded
  in the register and `cip_load_log`; the run carries on with the next wave.
- **Idempotent**: a reload replaces the wave's answers; nothing duplicates.

---

## Failure modes and what they mean

| Symptom | Cause | Fix |
|---|---|---|
| `401` | key missing, mistyped, revoked or its user disabled | re-issue in Portal → API Access |
| `403` | key valid, account lacks rights on the survey | grant view/export on directory `58f` |
| `428` | survey hibernated | reactivate in Forsta (a change in Forsta — not done by the pipeline) |
| connection timeout | egress firewall blocks `se1.decipherinc.com:443` | open outbound HTTPS |
| register row `failed` | the load did not match its payload, or the API errored | `last_error` in `cip_forsta_survey`; rerun `--due` |

---

## The scheduled run

```bash
python scripts/weekly_forsta.py       # auth check → schema check → discover → load due → drift
```

Exit codes: 0 everything due loaded and verified · 1 a wave failed · 2 Forsta
rejected the key, it is not configured, or the schema is behind the code (run
`scripts/init_db.py`) · 3 loaded, but a published number moved (see `/publications`).

**When it runs** — set from the 66 tracker waves' own timestamps: launched Monday
12–13 UTC, closed between Monday 20:00 and Wednesday 23:00 IST (median 13 h,
90th percentile 49 h). Installed on this Mac as the launchd agent
`com.coresight.cip-forsta-etl` (`scripts/launchd/`, same pattern as the other
Coresight ETLs; launchd runs a missed slot after the laptop wakes):

| When (IST) | Why |
|---|---|
| daily 09:00 | discover, load anything due, retry failures, reload reopened surveys |
| Tue + Wed 14:00 and 23:30 | each wave within hours of closing |

Log: `logs/forsta-etl.log`. On a server the same slots in cron:

```cron
0 9 * * *          cd /home/site/wwwroot && APP_ENV=staging python scripts/weekly_forsta.py >> /home/logs/forsta-etl.log 2>&1
0 14 * * 2,3       cd /home/site/wwwroot && APP_ENV=staging python scripts/weekly_forsta.py >> /home/logs/forsta-etl.log 2>&1
30 23 * * 2,3      cd /home/site/wwwroot && APP_ENV=staging python scripts/weekly_forsta.py >> /home/logs/forsta-etl.log 2>&1
```

---

## The data team's line-by-line table

The team built "Weekly Line-By-Line Survey Data.xlsx" by hand: each week's raw
export pasted under one header row (36 waves, Feb–Sep 2026, qualified only,
q1–q5 + CS1–CS2 + D1–D8 as labelled columns, plus Month, Age Range, Generation).
The ETL now builds the same rows for every tracker wave (`cip_tracker_line`,
`etl/tracker_line.py`, columns in `config/tracker_line.yml`) — the panel
`session` id excepted, which is personal data and never stored.

```bash
python -m etl.tracker_line --compare "Weekly Line-By-Line Survey Data.xlsx"   # reads only
python -m etl.tracker_line --rebuild                                          # every verified tracker wave
```

Checked on 8 Oct 2026 against the 16 waves both hold (≈6,400 respondents,
≈90 columns): same respondents per wave and the same count of every value in
every column, except three defects in the team's file:

| Defect in the file | Evidence |
|---|---|
| July's `Month` is typed 2026-07-26 | 1,608 rows (4 waves) |
| "Under 18" respondents banded `over 60` / `Boomer` | 1 per wave in 8 waves; the ETL leaves them unbanded |
| "Gone to a movie theater/cinema" and "Gone to a live performance" have no column | 10 waves, so those answers were dropped |

Cosmetic only: the file stores `&amp;` for `&` in retailer names and a header
spells "baby Toiletries".

---

## Security posture

- Read-only use: GET only, five endpoints.
- Key lives in the environment (Key Vault or a locked-down `.env`), never in the
  repo — `.gitignore` excludes `.env`.
- Two MySQL accounts: the portal physically cannot write to the warehouse.
- TLS required on both hops — HTTPS to Forsta, SSL to Azure MySQL.

## Sources

- [Forsta Surveys REST API](https://forstasurveys.zendesk.com/hc/en-us/articles/4409469957531-Forsta-Surveys-REST-API)
- [Decipher OpenAPI specification](https://docs.developer.focusvision.com/static/media/decipher-api.yaml)
- [Decipher API endpoint reference](https://release.decipherinc.com/s/local/api.html)
