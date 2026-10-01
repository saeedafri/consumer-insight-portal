# Forsta Integration — How the Connection Works

Technical reference for the Forsta Surveys (Decipher) side. The credentials
checklist for IT is a separate document: `04-it-requirements-checklist.md`.

---

## What the survey URL tells us

```
https://se1.decipherinc.com/apps/lumos/58f/260908:edit
        └──── host ─────┘ └─app─┘ └┬┘ └──┬──┘
                                   │     └── project number
                                   └──────── company directory
```

That decomposes into everything the API needs except the key:

| Setting | Value |
|---|---|
| API host | `se1.decipherinc.com` |
| API base | `https://se1.decipherinc.com/api/v1/` |
| Survey path | `selfserve/58f/260908` |
| Auth header | `x-apikey: <64-char key>` |

**Re-checked live on 29 September 2026.**

- Without a key, every path — the real one, `selfserve/58f/999999999` and
  `nonsense/path` — returns `401 Missing API key. Supply the x-apikey header`.
  That proves the host and the auth scheme, **not** the survey path.
- With the key on file (`Dwh/credentials.yml`), every endpoint returns
  `401 API user account is not valid: account disabled`. The key is well formed;
  the Forsta user that owns it has been disabled.

So the one thing standing between us and live data is an enabled API user.
The survey path is confirmed the first time a datamap comes back.

---

## Endpoints the pipeline uses

| Method | Endpoint | Used for |
|---|---|---|
| GET | `rh/users/self` | cheap auth check in `scripts/test_connection.py` |
| GET | `surveys/<path>/datamap?format=json` | questions, rows, codes, labels |
| GET | `surveys/<path>/data?format=json&cond=qualified` | respondent-level data |
| GET | `surveys/<path>/layouts` | discover a codes-format layout, if one exists |
| GET | `surveys/<path>/summary/completions` | field progress for the health page |
| GET | `datafeed/<feed>` | optional incremental feed |
| POST | `datafeed/<feed>/ack` | acknowledge a feed batch |

All read-only. `data/edit` is never called, and the key should be scoped to
exclude it.

### Useful parameters on `/data`

| Parameter | Effect |
|---|---|
| `cond` | Forsta filter expression — `qualified`, or `qualified and q3.r2` |
| `start` / `end` | bound completion datetime; this is how incremental pulls work |
| `layout` | custom data layout ID (codes vs labels) |
| `fields` | restrict to named variables |
| `format` | `json`, `csv`, `tab`, `spss`, `xlsx`, … |

Responses carry an `x-usage-today` header. Forsta documents no hard rate limit
today but reserves the right to add one, so the client logs it.

---

## Incremental loading

Two options, in order of preference:

1. **Datafeed** (if Forsta will create one). `GET /api/v1/datafeed/<feed>`
   returns only records not yet acknowledged; `POST .../ack` confirms receipt.
   No watermark bookkeeping, no risk of a boundary gap.
2. **Date window** (works today, no setup). The pipeline reads
   `MAX(completed_at)` from `csi_respondent` and passes it as `?start=`.
   `csi_load_state` stores the watermark.

Either way every write is an upsert keyed on `(survey_id, record_no)` and
`(respondent_id, field_id)`, so re-running a load is always safe. `--full`
ignores the watermark and reloads the wave from scratch.

---

## Why the loader is layout-agnostic

The exports we have today carry **labels**, with unselected multi-punch items
written `NO TO: <label>`. A codes layout would be cleaner. Rather than depend on
which one we get, `excel_parsers.normalise_label_cell()` recovers the code from
either form in one place, and the datamap supplies the code→label dictionary
regardless. If the layout changes, one function is affected.

---

## Failure modes and what they mean

| Symptom | Cause | Fix |
|---|---|---|
| `401 invalid key` | key missing, mistyped, or revoked | re-issue in Portal → API Access |
| `401 account disabled` | the key's owning user is disabled (the state on 29 Sep 2026) | re-enable the user, or issue a key on an active service account |
| `403` | key valid, account lacks rights on directory `58f` | grant view/export on the directory |
| `401` only from the scheduled host | key is IP-restricted | add the ETL host's outbound IP |
| Connection timeout | our egress firewall blocks `se1.decipherinc.com:443` | open outbound HTTPS |
| `datamap_hash` changed | questionnaire edited between waves | expected — review the diff before loading |
| Row counts drop suddenly | `cond` filter or a quota change | check `csi_load_log`, compare to `summary/completions` |

`scripts/test_connection.py` distinguishes the first four automatically.

---

## Security posture

- Read-only key, scoped to five endpoints.
- Service account, not a person's login, so the Forsta audit log stays meaningful.
- Key lives in the environment (Key Vault or a locked-down `.env`), never in the
  repo — `.gitignore` excludes `.env`.
- Two MySQL accounts: the portal physically cannot write to the warehouse.
- TLS required on both hops — HTTPS to Forsta, SSL to Azure MySQL.

## Sources

- [Forsta Surveys REST API](https://forstasurveys.zendesk.com/hc/en-us/articles/4409469957531-Forsta-Surveys-REST-API)
- [How To retrieve a survey datamap using the Forsta Surveys API](https://forstasurveys.zendesk.com/hc/en-us/articles/4409461412251-How-to-Retrieve-a-Survey-Datamap-Using-the-Forsta-Surveys-API)
- [Decipher API endpoint reference](https://release.decipherinc.com/s/local/api.html)
- [`decipher` Python package (official beacon client)](https://pypi.org/project/decipher/)


## The weekly API run (Phase 7) — ready, waiting on a working key

`etl/forsta_api.py` turns the API's JSON into exactly the records the Excel
path loads, so an API wave gives the same numbers as an Excel wave — proven on
the 09/21/26 export re-expressed as API JSON (every answer identical,
`tests/test_phase7.py`). Three defects in the first API path were fixed on the
way: the datamap was read per *variable* (every checkbox row a question), the
numeric status (3 = qualified) was not mapped (nobody would have counted as
qualified), and codes were resolved as labels (single choices would have
loaded empty).

**First live run** — once IT's key is in `.env` as `FORSTA_API_KEY=`:

```bash
python scripts/test_connection.py     # proves the key (never prints it)
python scripts/weekly_forsta.py       # fetch → load → verify → harmonise → cube → drift
```

The first call is also where the assumed Decipher JSON shapes (datamap
`questions[].variables[]/values[]`, data records keyed by variable with codes)
are confirmed; `etl/forsta_api.py` is the one place to adjust if they differ.

**Exit codes** (for the scheduler to alert on): 0 loaded and verified · 1 the
load failed or does not match its payload (the load log has the detail) ·
2 Forsta rejected the key or it is not configured · 3 loaded, but a published
number moved (see `/publications`).

**Scheduling** — not installed by the portal (a standing job is IT's call).
Weekly, after the wave closes, e.g. Monday 06:00 IST:

```cron
0 6 * * 1  cd /home/site/wwwroot && APP_ENV=staging python scripts/weekly_forsta.py >> /home/logs/forsta-weekly.log 2>&1
```

or an Azure App Service WebJob (triggered, `0 30 0 * * 1` UTC) running the same
command. The wave label is detected (Monday of the first fielding day).
