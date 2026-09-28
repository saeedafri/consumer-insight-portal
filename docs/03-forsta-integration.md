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

**Verified live on 28 September 2026.** An unauthenticated request to
`/api/v1/surveys/selfserve/58f/260908/datamap?format=json` returns:

```json
{"$error": "invalid key. Verify the spelling of your key by accessing the Research Hub",
 "$code": 401}
```

The route resolves and the survey path is correct — the API rejects only the
missing key. Nothing else about the connection is unknown.

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
   `MAX(completed_at)` from `cip_respondent` and passes it as `?start=`.
   `cip_datafeed_state` stores the watermark.

Either way every write is an upsert keyed on `(survey_id, forsta_record)` and
`(respondent_id, variable_id)`, so re-running a load is always safe. `--full`
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
| `403` | key valid, account lacks rights on directory `58f` | grant view/export on the directory |
| `401` only from the scheduled host | key is IP-restricted | add the ETL host's outbound IP |
| Connection timeout | our egress firewall blocks `se1.decipherinc.com:443` | open outbound HTTPS |
| `datamap_hash` changed | questionnaire edited between waves | expected — review the diff before loading |
| Row counts drop suddenly | `cond` filter or a quota change | check `cip_ingest_run`, compare to `summary/completions` |

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
