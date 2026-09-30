# What IT Needs To Provide — Forsta ↔ MySQL Integration

Hand this document to IT. It is split into what only they can supply and what is
already known, so nobody re-derives settled facts.

---

## Already confirmed — no need to ask

Re-checked directly on 29 September 2026:

| Item | Value | How it was confirmed |
|---|---|---|
| Platform | Forsta Surveys (formerly Decipher) | the `/apps/lumos/` portal URL; sign-in page is "Decipher: Sign in" |
| API host | `se1.decipherinc.com` | the survey link itself |
| API base | `https://se1.decipherinc.com/api/v1/` | live probe |
| Auth scheme | `x-apikey:` request header | error text: *"Missing API key. Supply the x-apikey header"* |
| Company directory / project | `58f` / `260908` | from the URL path |
| Existing key | a 64-character key is already on file (`Dwh/credentials.yml` → `FORSTA_API_KEY`) | sent to `rh/users/self` |
| **Why it fails** | **`401 — API user account is not valid: account disabled`** | same answer on `rh/users/self`, `…/datamap` and `…/data` |
| Our outbound IP (dev Mac on VPN) | `103.211.52.116` | `api.ipify.org`, 29 Sep 2026 |
| STG (DWH) MySQL | `csr-mysql8-flex-stg.mysql.database.azure.com:3306`, database `dwh_stg`, account `dwh_app_access`, TLS | connected; `GRANT ALL ON dwh_stg.*`; all 19 `csi_` tables and 8 `v_csi_` views are created |

**Not yet confirmed:** that `selfserve/58f/260908` is the right API path. An
unauthenticated call returns the same 401 for a made-up path
(`selfserve/58f/999999999`) and for `nonsense/path`, so the 401 proves the host
and auth scheme only — not the path. It is confirmed the moment a working key
returns a datamap.

**The single blocking fix:** the Forsta user that owns the existing key has been
disabled. Either re-enable that user, or issue a new key on an active service
account (1.1 below). Nothing else is needed to start pulling live data.

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

### 2.1 Connection details — resolved

| Setting | Env variable | Value |
|---|---|---|
| Host | `STG_DB_HOST` | `csr-mysql8-flex-stg.mysql.database.azure.com` |
| Port | `STG_DB_PORT` | 3306 |
| Database | `STG_DB_NAME` | `dwh_stg` |
| Account | `STG_DB_USER` / `STG_DB_PASSWORD` | `dwh_app_access` — the DWH account US-census-ETL uses (`DB_USER_DWH` / `DB_PASSWORD_DWH`, held in `Code-Base/Modular-Code/.env`) |
| TLS | `STG_DB_SSL_CA` | `DigiCertGlobalRootG2.crt.pem` |

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

> **Blocking (one item):**
> 1. The Forsta user that owns our API key is **disabled** — the API answers
>    `401 API user account is not valid: account disabled`. Please re-enable it,
>    or issue a new 64-character key on an active **service account** with view
>    and data-export rights on directory **`58f`** at `se1.decipherinc.com`.
>
> **Needed soon, not blocking:**
> 2. Is the key IP-restricted? If so, allowlist the ETL host (dev Mac today:
>    `103.211.52.116`; the Azure host's egress IP once it is scheduled there).
> 3. Confirm the API path for this project is `selfserve/58f/260908`, and whether
>    each weekly wave is re-fielded in the same project (09/21 and 09/28 both are,
>    judging by the exports) or gets a new project number.
> 4. The project paths of any historic waves we should backfill.
> 5. Whether a codes-format data layout exists for this project (and its ID).
> 6. A read-only `csi_app` account for the portal (`sql/004_grants.sql`); the
>    portal uses `dwh_app_access` until then.
> 7. Where secrets should live (Key Vault or server `.env`). Note:
>    `Dwh/credentials.yml` currently holds several live keys in plaintext.
> 8. Whether Forsta can push at field close (webhook/SFTP) rather than us polling.
>
> Already settled, no input needed: API host, base URL, auth header, the STG
> MySQL host, database (`dwh_stg`) and account.

---

## 4. How To verify once the key arrives

```bash
cd consumer-insight-portal
cp .env.example .env          # fill in the values above
python scripts/test_connection.py
```

The script reports each integration separately and names the missing credential
rather than dumping a stack trace.
