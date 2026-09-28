# What IT Needs To Provide — Forsta ↔ MySQL Integration

Hand this document to IT. It is split into what only they can supply and what is
already known, so nobody re-derives settled facts.

---

## Already confirmed — no need To ask

Checked directly against `se1.decipherinc.com` on 28 September 2026:

| Item | Value | How it was confirmed |
|---|---|---|
| Platform | Forsta Surveys (formerly Decipher/FocusVision) | the `/apps/lumos/` portal URL |
| API host | `se1.decipherinc.com` | the survey link itself |
| API base | `https://se1.decipherinc.com/api/v1/` | live probe |
| Auth scheme | `x-apikey:` request header | Forsta REST API docs |
| Company directory | `58f` | from the URL path |
| Project number | `260908` | from the URL path |
| Survey path | `selfserve/58f/260908` | derived from the two above |
| REST API status | **enabled and reachable on this host** | `GET /api/v1/surveys/selfserve/58f/260908/datamap` returned `{"$error": "invalid key…", "$code": 401}` — the route resolves, it only rejects the missing key |

That 401 is the useful result: the endpoint exists and the survey path is right.
**A valid API key is the only thing standing between us and live data.**

---

## 1. Forsta side — six things

### 1.1 A service-account API key ★ blocking

A 64-character key (32 public + 32 private), sent as the `x-apikey` header.

Created in the Forsta portal: **profile avatar → API Access → Create new API
key**, then choose the target user.

Ask for it **on a named service account** (e.g. `svc-coresight-cip@`), not on a
person's login. A key tied to an individual dies when they change role, and the
audit log then attributes every pull to them.

### 1.2 Directory permission for that service account ★ blocking

The key inherits the user's permissions. The service account needs at least
**view / data-export rights on directory `58f`**, covering every CSI project, not
just `260908`. Without it the API returns 403 even with a valid key.

### 1.3 Endpoint restrictions on the key

Forsta lets a key be limited to named endpoints. Request these five, and nothing
more — a key scoped to exactly what the pipeline calls is a key that can't do
damage if it leaks:

```
surveys/<path:survey>/datamap
surveys/<path:survey>/data
surveys/<path:survey>/layouts
surveys/<path:survey>/summary/completions
rh/users/self
```

The pipeline is **read-only by design**. It never calls `data/edit`. Please do
not grant write endpoints.

### 1.4 IP allowlist — both directions

- If the key is IP-restricted, Forsta needs the **outbound IP of the host that
  runs the ETL** (the Azure VM or container running `etl/run_pipeline.py`).
- Conversely, our egress firewall must permit HTTPS to `se1.decipherinc.com:443`.

Please confirm both, and tell us the ETL host's public IP so we can register it.

### 1.5 Export layout — codes or labels?

Today's Excel exports carry **labels**, with unselected multi-punch items written
as `NO TO: <label>`. The loader handles that, but a **codes layout** is cleaner
and smaller over the wire.

Ask the Forsta admin: *is there a data layout configured for this project that
exports codes rather than labels, and if so what is its layout ID?* If yes, put
the ID in `FORSTA_DATA_LAYOUT_ID`. If not, we stay on labels — nothing breaks.

### 1.6 The full list of survey paths

`selfserve/58f/260908` is one wave. Trending needs the whole set. Please ask for
the project path of every wave we should load, current and historic — or confirm
the service account may list the directory so we can enumerate them ourselves.

### Optional, worth asking about

- **Datafeed.** Forsta can expose a named incremental feed
  (`GET /api/v1/datafeed/<feed>`) that returns only records not yet acknowledged.
  Cleaner than date-window polling for surveys still in field. Ask whether a feed
  can be created and what it would be called.
- **Push instead of pull.** If Forsta can POST to a webhook or drop files on
  SFTP at field close, that removes our polling schedule entirely. Worth knowing
  whether the contract includes it.

---

## 2. Our side — STG (DWH) MySQL

### 2.1 Connection details

| Setting | Env variable | Notes |
|---|---|---|
| Host | `STG_DB_HOST` | the STG DWH server |
| Port | `STG_DB_PORT` | 3306 |
| Database | `STG_DB_NAME` | existing STG schema, or a new `cip` schema — IT's call |
| TLS | `STG_DB_SSL_CA` | required; `DigiCertGlobalRootG2.crt.pem`, as used by market-data-stg |

### 2.2 Two database accounts, not one

| Account | Used by | Grant |
|---|---|---|
| `csi_etl` | `etl/run_pipeline.py` | `SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES` on `csi_%` |
| `csi_app` | the Streamlit portal | `SELECT` only, on `csi_%` and `v_csi_%` |

`sql/004_grants.sql` has the statements ready. Splitting them means a bug in the
portal cannot write to the warehouse.

All CSI objects are prefixed `csi_` (views `v_csi_`) so they never collide with
anything already in STG.

### 2.3 Firewall

An inbound rule on the STG MySQL server for the ETL host's IP, and for the host
serving the Streamlit app if it differs.

### 2.4 Secret storage

Where should `FORSTA_API_KEY`, `STG_DB_PASSWORD` and `APP_DB_PASSWORD` live —
Azure Key Vault, or a `.env` with locked-down permissions on the server, as the
other portals do? We will follow whichever pattern IT already runs.

### 2.5 Schedule

The pipeline is a single command and is safe to re-run (every write is an
upsert, so a retried run corrects rather than duplicates). It needs a cron entry
or Azure Scheduled Job. Proposed: **daily at 02:00 IST**, plus an on-demand run
at field close.

---

## 3. The short version — copy this into the ticket

> **Blocking:**
> 1. A 64-character Forsta Surveys API key on a **service account**, with view
>    and data-export rights on **directory `58f`** at `se1.decipherinc.com`.
> 2. Whether that key is IP-restricted — if so, we will supply the ETL host's
>    outbound IP for the allowlist.
> 3. STG (DWH) MySQL: host, port, database name, and two accounts — `csi_etl`
>    (read/write on `csi_%`) and `csi_app` (read-only). SSL required.
> 4. A firewall rule from the ETL host to the STG MySQL server.
>
> **Needed soon, not blocking:**
> 5. The project paths of all CSI waves we should load, not just `260908`.
> 6. Whether a codes-format data layout exists for this project (and its ID).
> 7. Where secrets should live (Key Vault or server `.env`).
> 8. Whether Forsta can push at field close (webhook/SFTP) rather than us polling.
>
> Everything else — the API host, base URL, auth header and survey path — is
> already confirmed and needs no input.

---

## 4. How To verify once the key arrives

```bash
cd consumer-insight-portal
cp .env.example .env          # fill in the values above
python scripts/test_connection.py
```

The script reports each integration separately and names the missing credential
rather than dumping a stack trace.
