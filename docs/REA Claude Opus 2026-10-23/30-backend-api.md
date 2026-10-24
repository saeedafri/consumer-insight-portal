# 30 · Backend API (FastAPI): reverse-engineering audit

Audited 23 Oct 2026 against commit `aa4bfdb` (live `/healthz` reports `build: aa4bfdb`; the working tree is clean except for the untracked `scripts/launchd/com.coresight.cip-api.plist`).

Markers:
- **[O] observed:** read in the code, the DB, a log or a live response.
- **[I] inferred:** follows from what was observed.
- **[U] unknown:** not established.

Method:
- Read every module under `api/` and every `app/` module the API imports.
- Ran SELECT and SHOW GRANTS through `app.core.database`.
- Sent 50 GET requests to the live link `https://cheque-bought-dust-successfully.trycloudflare.com`.
- Ran pytest.
- Nothing was started, stopped or edited apart from this file.

---

## 1. Summary verdict

**The engine is good. The front door is not ready for a launch.**

The serving design is fast and well thought through:
- prebuilt gzip files;
- a per-worker LRU response cache keyed on the data version;
- ETag/304;
- admission control;
- bound SQL everywhere;
- suppression of cells under 5 people on almost every path.

Server time for every published or cached read is 0.3–8 ms [O].

The blockers are about who can get in and where it runs:

1. **Anyone with the public link is signed in automatically, as anyone they choose.**
   - The live process runs with `APP_ENV=LOCAL` (`~/.config/cip/api.env`), so `/auth/dev-login` is enabled on the public tunnel (`api/main.py:466-474`).
   - The React app redirects every 401 to it (`web/src/api.ts:93,164`).
   - `?email=` accepts any address. A live probe got a valid cookie for `ceo@coresight.com` [O].
   - There is no OIDC, logout or revocation in the API at all.
2. **The API's "read-only" database role is the owner's personal account.** It has `ALL PRIVILEGES` on `cip_stg` and on three other databases [O].
3. **Small cells leak on two routes.** `/api/v1/trend` and `/api/v1/trends/...` return percentages for groups of 2–4 people: 1,418 such cells for one question, live [O]. Every other route masks them.
4. **It runs on one Mac behind a quick tunnel.** The 10:34 IST reboot took the portal down for about 17 minutes and changed the URL [O].
   - The new launchd agent restarts the API but not cloudflared.
   - `deploy/` (nginx, security headers, rate limit, gunicorn) is not what runs.

Tests: **290 passed** with `pytest -q tests` [O]. Bare `pytest -q` from the repo root **errors at collection**, because `scripts/e2e_perf_test.py` needs playwright and there is no `testpaths` setting [O]. No test exercises the API's sign-in route or a cookie over HTTP [O].

---

## 2. Architecture and request lifecycle

```
Browser (React SPA, web/dist)
   │  HTTPS
   ▼
Cloudflare edge (DEL) ── quick tunnel, random *.trycloudflare.com URL, no account, no Access policy
   │  QUIC
   ▼
cloudflared (pid 7387, started by hand 10:51 IST; not under launchd)
   │  http://127.0.0.1:8000
   ▼
uvicorn, 1 process, 1 worker (pid 7310, Homebrew Python 3.13, started by hand)
   │   [launchd com.coresight.cip-api (pid 17199) loops "while :8000 is taken, sleep 15", then would exec .venv uvicorn]
   ▼
FastAPI app  api/main.py
   middleware (outer → inner): cache_static (main.py:493)  →  performance_logging (main.py:477, Server-Timing + [PERF]/[PERF-SLOW] > 200 ms)
   │
   ├─ /healthz                       no auth
   ├─ /auth/dev-login                no auth; only when APP_ENV=local (main.py:58,469)  ← LIVE: enabled
   ├─ /auth/check                    HMAC cookie (nginx auth_request; unused on the Mac)
   ├─ /api/v1/openapi.json           no auth (main.py:216-217)
   ├─ /api/v1/* (Depends(user))      HMAC cookie "email|products|expires" (main.py:228-239, app/core/session.py)
   │     │
   │     ├─ in-memory STORE (dashboards, loaded from cip_dash_payload at start + every 60 s) ──── no DB per request
   │     ├─ _cached(): RESULTS LRU (CIP_CACHE_MB, default 256 MB/worker; key starts with the SERVING version)
   │     │      miss → BUILD_SLOTS semaphore (8; wait 3 s, then 503 + Retry-After) → thread:
   │     │          _published(): data/published/current/api/v1/<path>.json.gz      (static ETL output)
   │     │          else payloads.*(): SQL on srv_wave / srv_result / srv_answer (Azure MySQL, "app" engine)
   │     ├─ CATALOGUE: SQLite FTS5 in memory (api/search.py), rebuilt when srv_wave changes
   │     ├─ team router (api/team.py): direct SQL per request, no cache (~255–280 ms each = one Azure round trip)
   │     ├─ /ask → api/assistant.py → Anthropic Messages API (claude-opus-5-5) or figures-only fallback
   │     └─ /export → api/exports.py (openpyxl / python-pptx in a thread)
   │
   └─ Mount "/" SinglePageApp(web/dist): files, else index.html (main.py:503-515)

Background: _refresh_forever every 60 s (main.py:190-198):
  srv_wave version + dashboard stamp → reload STORE / CATALOGUE, drop RESULTS on change; rebuild the schedule
```

Lifecycle details:
- **Startup** (`main.py:201-212`) [O]:
  - refuses to start without `CIP_SESSION_SECRET`;
  - loads 175 dashboard payloads (204 KB gzipped) per `logs/api-launchd.log`;
  - loads the 3,719-document catalogue (live `/healthz`) and the schedule.
- **Authentication** (`main.py:228-239`) [O]:
  - The cookie is base64(`email|products|expires`) plus `.` plus an HMAC-SHA256 signature.
  - It is checked with `compare_digest`, with no DB lookup.
  - A tampered cookie returns 401 (live).
  - The session lasts 12 h (`session.py:12`).
  - Products are always `*` (`session.py:20`, `issue()` default).
- **Response path** (`_send`, `main.py:242-248`) [O]:
  - sends the ETag and handles `If-None-Match` → 304 (live check passed);
  - sends pre-gzipped bytes when the client accepts gzip;
  - `Cache-Control: private, max-age=60`, `Vary: Accept-Encoding, Cookie`.
- **Version cache** (`_changed`, `main.py:118-128`) [O]: `RESULTS` is cleared when `(COUNT, MAX(built_at))` of `srv_wave` changes, or when the `data/published/current` symlink target changes.
- **Error handling** [O]:
  - `LookupError` → 404 with `{"detail": str(exc)}` (`main.py:220-222`);
  - FastAPI's default 422 elsewhere (pydantic list format);
  - no global 500 handler, so Starlette's plain `Internal Server Error` is returned.
- **Static files and SPA** [O]:
  - `/assets/*` → `public, max-age=31536000, immutable`;
  - HTML → `no-cache` (`main.py:493-500`);
  - an unknown path → `index.html`, which is why `/docs` returns 200 HTML;
  - `api/`, `auth/` and `assets/` 404s stay 404.
- **Logging** [O]:
  - `[PERF]` and `[PERF-SLOW]` lines for every `/api/` request;
  - uvicorn access lines that include the client IP and the full query string, including search text;
  - searches with no hits are logged at `main.py:368`.

---

## 3. Route table

Auth key:
- **C** = the HMAC session cookie (`Depends(user)`).
- **none** = public on the tunnel.

| # | Method | Path | Auth | Data source | Response shape | Caching |
|---|---|---|---|---|---|---|
| 1 | GET | `/api/v1/dashboards/{code}` | C, plus a product check (always passes: `*`) | in-memory STORE (from `cip_dash_payload`) | dashboard JSON (`api/dashboards.py:payload`) | STORE, ETag |
| 2 | GET | `/api/v1/dashboards/{code}/{survey_id}` | C, plus a product check | STORE | same | STORE, ETag |
| 3 | GET | `/api/v1/waves` | C | published `waves.json.gz`, else SQL `payloads.waves` | `[ {survey_id,title,wave_date,family,…,modules,events,dashboards} ]`, 371 waves, 21 KB gz | RESULTS + ETag |
| 4 | GET | `/api/v1/waves/{id}/book` | C | published `book.json.gz`, else SQL `payloads.book` | `{wave, columns, n, questions:[{id,text,groups:[{rows}]}]}`, 16–22 KB gz | RESULTS |
| 5 | GET | `/api/v1/waves/{id}/results?q=&dim=` | C | SQL `srv_result` (≤ 20 qcodes, ≤ 8 dims) | `{columns, rows}`, masked under 5 | RESULTS |
| 6 | GET | `/api/v1/waves/{id}/crosstab?q=&by=a,b&weeks=1-4` | C | published `cuts/<q>.json.gz` (raw counts), else SQL GROUP BY on `srv_answer` | `{by, weeks, waves, warnings, columns, rows}`, masked under 5 | RESULTS |
| 7 | GET | `/api/v1/questions/{family}/{study}/{qcode}` | C | published `questions/...json.gz`, else SQL | compact columns `w,c,a,n,b` (`n` null under 5) | RESULTS |
| 8 | GET | `/api/v1/trend?survey_id=&q=&dim=&value=` | C | SQL only (trends are no longer published) | `{waves, versions, series:[{pct[],base[]}]}`: **not masked** | RESULTS |
| 9 | GET | `/api/v1/trends/{family}/{study}/{qcode}/{dim}/{value}` | C | published trend (none exist now), else SQL | same: **not masked** | RESULTS |
| 10 | GET | `/api/v1/search?q=&limit≤200&offset≤5000` | C | in-memory SQLite FTS5 | `{results, total, understood}` | RESULTS |
| 11 | GET | `/api/v1/schedule` | C | SQL `cip_forsta_survey`/`event`, rebuilt every 60 s | launch plan weeks | global SCHEDULE |
| 12 | POST | `/api/v1/ask` | C | catalogue, books, Anthropic API | `{answer, sources, no_source, mode}` | none |
| 13 | POST | `/api/v1/export/{xlsx\|pptx}` | C | the client's request body (no server data) | file attachment | none |
| 14–16 | GET, POST / DELETE | `/api/v1/team/views`, `/team/views/{id}` | C | SQL `cip_team_view` (written with the "app" engine) | list (LIMIT 500) / `{view_id}` / 204 | none |
| 17–19 | GET, POST / DELETE | `/api/v1/alerts`, `/alerts/{id}` | C | SQL `cip_metric_alert` | list (unbounded) / `{alert_id}` | none |
| 20–22 | GET, POST / DELETE | `/api/v1/audiences`, `/audiences/{id}` | C | SQL `cip_audience` | list / `{audience_id}` | none |
| 23 | POST | `/api/v1/waves/{id}/audience` | C | `people.json.gz` respondent bitsets (`lru_cache` 16), else SQL `srv_answer` | `{columns, rows}`; under 5 hidden, plus complementary suppression | lru per wave |
| 24–26 | GET, POST / GET, DELETE | `/api/v1/boards`, `/boards/{id}` | C | SQL `cip_board*` (3 sequential queries to open one) | list (LIMIT 500) / board with items and comments | none |
| 27–28 | POST / DELETE | `/boards/{id}/items`, `/boards/items/{id}` | C (pin: **no owner check**) | SQL | `{item_id}` | none |
| 29–30 | POST / DELETE | `/boards/items/{id}/comments`, `/boards/comments/{id}` | C | SQL | `{comment_id}` | none |
| 31 | GET | `/api/v1/boards/{id}/deck` | C | SQL plus python-pptx | .pptx | none |
| 32 | GET | `/healthz` | **none** | process state | build, counts, pool status | none |
| 33 | GET | `/auth/check` | C | none | 204/401 | none |
| 34 | GET | `/auth/dev-login?email=&next=` | **none** | none | 303 plus `Set-Cookie` | none |
| 35 | GET | `/api/v1/openapi.json` | **none** | FastAPI | OpenAPI 3 (18.5 KB) | none |
| 36 | GET | `/*` | none | `web/dist` (SPA fallback) | HTML/JS/CSS | immutable assets |

Notes on the table [O]:
- Routes 1–13 and 32–35 are in `api/main.py:251-474`. Routes 14–31 are in `api/team.py`, mounted at `main.py:400` with `Depends(user)`.
- `api/dashboards.py` is an offline builder CLI (`--build/--show/--check`) that writes with the **etl** engine. It defines no routes.
- The API does **not** import `app/data/repository.py`, `publications.py`, `cohorts.py`, `cube.py` or `app/core/auth.py`. Those serve the legacy Streamlit app (`app/pages`).
- The UI calls only routes 1–7, 10–31 and 34 (grep of `web/src`). Routes 8 and 9 are unused by the UI but live.
- The `/api/v1/waves/{id}/compare` route that logs show the UI calling on 21 Oct (404) no longer exists, and the UI no longer calls it.

---

## 4. Live probe results (23 Oct 2026, ≈ 11:08 IST, from this Mac through the Cloudflare DEL edge)

| Request | Status | Total time | Server time (`Server-Timing`) | Bytes (gz) |
|---|---|---|---|---|
| `/healthz` (no cookie) | 200 | 349 ms | none | 347 |
| `/api/v1/waves` (no cookie) | 401 | 345 ms | none | 29 |
| `/api/v1/openapi.json` (no cookie) | **200** | 337 ms | none | 18,558 |
| `/auth/dev-login?next=/` | **303 + cookie** | none | none | none |
| `/auth/dev-login?email=ceo@coresight.com` | **303 + cookie** | none | none | none |
| `/auth/dev-login?next=/%5Cevil.com` | 303 → `/%5Cevil.com` (path stays relative, so no open redirect) | none | none | none |
| `/api/v1/waves` | 200 | 113 ms | 0.30 ms | 21,077 |
| `/api/v1/waves/415/book` (cold, then warm) | 200 | 492 / 119 ms | 3.12 / 0.51 ms | 22,483 |
| `/api/v1/waves/5/book` | 200 | 334 ms | 1.87 ms | 16,283 |
| `/api/v1/questions/CSI-US/tracker/Q1` | 200 | 317 ms | 0.48 ms | 57,881 |
| `/api/v1/waves/415/crosstab?q=Q1&by=generation,gender` | 200 | 343 ms | 7.94 ms | 1,644 |
| `/api/v1/search?q=holiday` | 200 | 343 ms | 6.66 ms | 1,867 |
| `/api/v1/dashboards/holiday_tracker` | 200 | 354 ms | 0.77 ms | 1,526 |
| `/api/v1/schedule` | 200 | 349 ms | 0.87 ms | 3,963 |
| `/api/v1/waves/415/results?q=Q1&dim=total,gender` | 200 | 626 ms | **286 ms** | 1,162 |
| `/api/v1/trends/CSI-US/tracker/Q1/total/Total` | 200 | 2,254 ms | **1,937 ms** | 6,016 |
| `/api/v1/trend?survey_id=5&q=Q1&dim=gender&value=Non-binary / third gender` | 200 | 3,138 ms | not captured | none |
| `/api/v1/boards`, `/team/views`, `/alerts`, `/audiences` | 200 `[]` | 366–612 ms | **270–275 ms** | 2 |
| same trends URL with `If-None-Match` | **304** | none | none | none |
| `/api/v1/waves/999999/book` | 404 `{"detail":"No such wave"}` | none | none | none |
| `/api/v1/waves/abc/book` | 422 (pydantic list) | none | none | none |
| `crosstab?q=x/../../book` | 404 (traversal not reachable, see API-14) | none | none | none |
| a tampered cookie | 401 | none | none | none |
| `Origin: https://evil.example` | no `Access-Control-*` header (no CORS middleware) | none | none | none |

Headers on every response [O]:
- present: `server: cloudflare`, `x-robots-tag: none` (added by the quick tunnel), `server-timing`;
- **absent:** `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security` and `Referrer-Policy`;
- the cookie is `HttpOnly; SameSite=lax; Max-Age=43200`, **without `Secure`**.

Cloudflare adds about 100 ms over the server time even on a 0.3 ms answer. Compression works: the JSON is pre-gzipped.

Small-cell check:
- `/trend?...Non-binary...` returned 1,418 (pct, base) pairs with base 2–4 and a percentage shown, e.g. ("Yes", 75.0 %, n=4) [O].
- The same cells through `/results` come back with `pct: null` (0 of 13 shown) [O].

Database facts from the read-only checks [O]:
- `CURRENT_USER()` of the "app" engine is a personal account (`moh***`).
- That account has `ALL PRIVILEGES` on `cip_stg`, `chainxydata_stg`, `coresight_market_data_stg` and `dwh_directus_stg`, plus `SELECT, SHOW VIEW` on `dwh_stg`.
- All six team tables are **empty**: boards, items, comments, views, alerts, audiences. No one has used those features on live yet.

Log facts (`logs/api.log`, 1,771 lines) [O]:
- Status counts: 283 × 200, 146 × 304, 27 × 401, 29 × 404, 1 × 403.
- 0 × 5xx.
- 0 calls to `/api/v1/ask`.

---

## 5. Security findings

### 5.1 Authentication [O]
- **There is only one sign-in path in the API: dev-login.**
  - It is guarded by `APP_ENV == "local"` (`main.py:58,469`), and the live env file sets `APP_ENV=LOCAL`.
  - The SPA sends every 401 to it (`web/src/api.ts:93,164`), so a visitor never sees a login.
  - `email` is a free query parameter (`main.py:467`). That is identity by assertion: anyone can mint `ceo@coresight.com`.
  - `products` is always `*` (`session.py:20`).
- **There is no OIDC, logout, session revocation or key rotation in the API.**
  - Streamlit's `app/core/auth.py` (OIDC, allowlist, `cip_auth_session`) is not used by the API.
  - `docs/08-authentication.md` describes only that Streamlit flow. It says the portal "does not go on a shared host without a login", which the React portal does today.
- **The protection is weaker than it looks.**
  - The quick-tunnel URL is random, but it is shared in chats.
  - The HMAC secret is strong only if `CIP_SESSION_SECRET` is [U] (not read, by policy).
  - `config.py:103,110` still defaults an unset `APP_ENV` to LOCAL. The API's own check (`main.py:58`) needs an explicit `local`, so an unset value is safe for the API; for Streamlit it is not.

### 5.2 Authorization [O]
- **Entitlements:**
  - Only `/dashboards/*` checks `products` (`main.py:258`).
  - waves, book, results, crosstab, questions, trend, search and ask are not scoped by product or client.
  - In the Docker design, nginx serves dashboard files directly after checking only the cookie (`deploy/nginx.conf:57-61`), which bypasses even that one check.
  - There is no per-client or per-organisation concept anywhere, so client-commissioned studies are visible to every session [I].
- **Team data:**
  - Lists are global, which is by design.
  - Deletion is owner-checked (`team.py:41-48`), but a row without an owner is deletable by anyone.
  - **Pinning to a board and commenting have no owner or membership check** (`team.py:308-346`): any user can add to any board.
  - Because the default dev-login email is the same for everyone (`analyst@coresight.com`), every visitor is the "owner" of everything [I].
- **Write account:**
  - Team writes go through `get_engine("app")` (`team.py:68,101,181,277,320,342`). The docstring says that account "may write only these tables" per `sql/004_grants.sql`.
  - Live, it is the personal account with ALL PRIVILEGES [O]. A single SQL injection or a code bug would have full DDL and DML on four databases. No injection was found.

### 5.3 Disclosure control (small cells, HIDDEN_BASE = 5, `payloads.py:28`)

| Path | Suppressed under 5? | Evidence |
|---|---|---|
| results | yes | `payloads.py:53-60`; live 0/13 |
| book (and Ask CIP, which reads books) | yes | `payloads.py:125` |
| questions (Compare/Trends) | `n` hidden, base shown | `payloads.py:431` |
| crosstab (live and from published cuts) | yes | `payloads.py:366-367` |
| dashboards | yes, plus takeaways skip suppressed rows | `api/dashboards.py:136,207,251` |
| audiences | yes, plus complementary suppression of the rest | `team.py:248`; the differencing risk is acknowledged at `team.py:246-247` |
| **trend / trends** | **no**: `pct` is rounded and returned for any base | `payloads.py:186`; live 1,418 cells |
| exports (xlsx/pptx) | not applicable: renders whatever the client posts, so it can be used to forge a branded Coresight deck with any numbers | `exports.py:16-24` |
| published `cuts/*.json.gz`, `people.json.gz` | raw counts and respondent bitsets on disk; served by **no** route on the Mac. In Docker, nginx serves only `waves`, `book`, `dashboards` and `questions` from disk | `nginx.conf:47-67` |

### 5.4 Injection, traversal, SSRF, formula injection [O]
- **SQL:**
  - every value is bound;
  - expanding `IN` uses `bindparam`;
  - f-strings interpolate only constant column lists and `CUTS`;
  - search FTS5 `MATCH ?` is bound and built from `[a-z0-9'-]` tokens (`search.py:99-101`).
  - No injection was found.
- **Path traversal:**
  - Path parameters cannot contain `/`.
  - `_published()` rejects only parts that *start* with `.` (`main.py:134`).
  - The crosstab `q` query value (`main.py:385`) can carry `x/../../…`. It is harmless today only because `cuts/` contains no subdirectories, and only `*.json.gz` files that parse as JSON with `counts` would be used (live probe: 404).
  - The `int` survey ids in `team.py:205` are safe.
- **SSRF:**
  - The only outbound call is the Anthropic SDK to a fixed host.
  - No user-supplied URL is fetched.
  - Saved-view and board URLs must start with `/w/` (`team.py:66,318`).
- **Formula injection:**
  - API xlsx escapes `= + - @` (`exports.py:27-29`) but not a leading tab or CR. That is low risk in xlsx.
  - Browser CSV escapes all six characters (`web/src/csv.ts:5`).
  - The legacy Streamlit `app/components/export.py:85` still writes raw values.
- **Error leakage:** messages are friendly. `LookupError` text is echoed, and no stack traces were seen. A malformed JSON body or a non-object body on `/ask` and the team POSTs raises a 500 [I], because `request.json()` and `.get` are not guarded (`main.py:418`, `team.py:64,274,339`).
- **CSRF:** every state change is POST or DELETE with a `SameSite=lax` cookie, and there is no CORS middleware, so cross-site requests are blocked. Whether `trycloudflare.com` is on the Public Suffix List, which governs same-site between tunnels, is [U].
- **Information exposure:**
  - unauthenticated `/healthz` shows build, pool internals, cache size and wave counts;
  - unauthenticated `/api/v1/openapi.json` gives the full route map.

### 5.5 Ask CIP (`api/assistant.py`) [O]
- **Provider:** the Anthropic Messages API (beta), model `claude-opus-5-5`, structured JSON output, the `server-side-fallback` beta.
- **What leaves the company:** question wording, answer labels, Total percentages and bases from published books (already masked under 5). No respondent rows.
- **Prompt injection:**
  - the user's question is sent verbatim;
  - output is schema-constrained;
  - citations are validated against real source ids (`assistant.py:102-104`);
  - **the prose is not checked against the figures**, so a wrong number could be shown with a valid citation [I].
- **Credentials:** no `ANTHROPIC_API_KEY` is set in `.env` or `api.env`, so live would answer in `figures` mode [I]. The live process environment was not read.
- **Use:** never called live.
- **Missing:** no rate limit, no per-user quota, no cost cap, no audit log of questions.

### 5.6 Transport and deployment hardening [O]
- Live has none of the planned protections:
  - no security headers;
  - no rate limit;
  - no request-body limit;
  - no gunicorn timeout.
- `deploy/cip_headers.conf` has only nosniff, `X-Frame-Options` and `Referrer-Policy`. It has no CSP or HSTS even in the Docker design.
- The cookie has `secure=False` (`main.py:473`).
- `cip_auth.js:17` compares HMACs with `!==`, which is not constant time (low risk).

---

## 6. Performance findings

`[PERF-SLOW]` lines (> 200 ms server time) in `logs/api.log`: 96 of 1,771 lines [O].

| Route | Count | Mean ms | Max ms | Cause |
|---|---|---|---|---|
| GET `/api/v1/boards` | 49 | 315 | 2,814 | one uncached SELECT per request to Azure MySQL from the Mac in India |
| GET `/api/v1/team/views` | 16 | 841 | 3,257 | same; the multi-second spikes are new pooled connections (TLS handshake) [I] |
| GET `/api/v1/alerts` | 16 | 327 | 656 | same |
| GET `/api/v1/boards/{id}` | 4 | 801 | 840 | **3 sequential queries** (board, items, comments) ≈ 3 round trips (`team.py:282-293`) |
| GET `/api/v1/audiences` | 2 | 1,915 | 3,504 | same plus a cold connection |
| DELETE/POST boards, items, comments, deck | 1–2 each | 290–811 | none | 2 round trips: the owner check, then the write |
| GET `/waves/{id}/book` | 2 | 304 | none | a cold build from SQL before the publish existed |

Fast paths (`[PERF]` means): waves 2.7 ms, book 3.4 ms, crosstab 5.9 ms, search 6.8 ms, dashboards ~1 ms, xlsx 13 ms, pptx 32 ms [O].

Analysis:
- **≈ 255–280 ms is one Azure round trip.**
  - The "app" engine is already tuned to one round trip per query: AUTOCOMMIT and no pre-ping (`database.py:88-111`).
  - The floor is the network: the Mac is in India and MySQL is on Azure.
  - The team endpoints are polled on every page load by the SPA, which is why they dominate the slow log.
  - The fix is location (run the API in the DB's region), or caching the four lists in memory and invalidating on write, which costs about 10 lines.
- **`/trend` and `/trends` are always live SQL (1.9–3.1 s).** `etl/publish.py` stopped writing trend files (it publishes `questions/` instead). The UI no longer calls these routes, so they are slow, unmasked dead weight.
- **`/results` (286 ms)** is never published and is always live SQL. The UI does not call it either (grep).
- **The background poll** runs every 60 s and costs 2 queries plus a schedule rebuild (2 more), about 0.5–1 s of DB time per minute per worker [I].
- **Published data lags the serving tables:**
  - `manifest.json` `serving_version` is "2026-10-22 12:47:00";
  - live `/healthz` `serving_built` is "2026-10-22 17:31:41";
  - so published books and questions predate the newest serving rows, while live-built routes (results, trend, crosstab fallback) use newer rows [O for the values; the time zones are U].

---

## 7. API design quality compared with professional data products

| Aspect | CIP today | Typical professional data API (e.g. Qualtrics/YouGov/Morning Consult-style data feeds) |
|---|---|---|
| Versioning | `/api/v1` prefix only; payload shapes change with the UI; no deprecation policy | versioned, documented contracts with deprecation windows |
| Contract | raw `Response` bytes: OpenAPI has paths but **no response schemas** [I from code] | typed schemas, published docs, SDKs |
| Errors | `{"detail": "text"}` or a pydantic list (422) or plain-text 500; no error codes; no request id | stable error codes, a correlation id |
| Pagination | search only (limit/offset/total); views/boards silently capped at `LIMIT 500`; alerts unbounded | cursor pagination everywhere |
| Auth | browser cookie only; no API keys or OAuth client credentials; no scopes | OAuth2/API keys, per-client scopes, audit |
| Rate limits | none in the running API | per-key quotas with `429` and `Retry-After` |
| Customer API / export feed | **none**: every route is UI-internal; exports only re-render what the browser sends | bulk export, scheduled feeds, connectors (Snowflake, BI) |
| Strengths | ETag/304, gzip, versioned cache keys, admission control with `Retry-After`, honest `understood` block on search, cited AI answers | comparable or better than many |

---

## 8. Gap table

| ID | Sev | Gap | Evidence | Consequence | Smallest fix |
|---|---|---|---|---|---|
| **API-01** | **Critical** | The public link auto-signs anyone in, as any email | `main.py:466-474`; `~/.config/cip/api.env` `APP_ENV=LOCAL`; `web/src/api.ts:93`; live 303 + cookie for `ceo@coresight.com` [O] | All survey data, including client-commissioned studies, is open to anyone who has or receives the link. Team records can be created or deleted under any name, so the audit trail is meaningless. | Before launch, put the tunnel behind Cloudflare Access (a named tunnel plus a Zero Trust policy for @coresight.com), or gate dev-login with `AUTH_ALLOWED_EMAILS` plus a passphrase and drop the `email` parameter. Then add real OIDC (`/auth/login`, `/auth/callback`, `/auth/logout`). |
| **API-02** | **Critical** | The API's DB role is the owner's personal account with ALL PRIVILEGES on 4 databases | `SHOW GRANTS` [O]; `config.py:140-143`; `team.py` writes via "app" | Any bug or injection gets DDL and DML on `cip_stg` and other teams' databases. The person is a single point of failure: if the account is disabled, the portal dies. | Create a `cip_app` user with SELECT on `cip_*`/`srv_*` plus INSERT/DELETE on the 6 team tables. Set `APP_DB_USER` to it. Make `config.py` refuse to start without it outside LOCAL. |
| **API-03** | **High** | Small cells leak through `/api/v1/trend` and `/api/v1/trends/...` | `payloads.py:186` (no HIDDEN_BASE check); live: 1,418 cells with n = 2–4 and percentages [O] | Breaks the "under 5, no figure" rule that every other screen enforces; re-identification risk for minority groups (e.g. non-binary respondents). | Delete both routes; the UI uses `/questions`. Or apply `shown()` in `_trend`. Add one parity test that walks every GET route for base < 5. |
| **API-04** | **High** | No production identity: no OIDC, logout or revocation; entitlements are decorative (products are always `*`); nginx bypasses the dashboard check | `session.py:20`; `main.py:258`; `nginx.conf:57-61` [O] | Selling per-product or per-client access is impossible as built. A leaked cookie stays valid for 12 h and cannot be killed short of rotating the secret, which logs everyone out. | Put one `allowed(who, survey_id)` policy in `user()` and the `_cached` keys. Add a server-side session id with a revocation table (reuse `cip_auth_session`). |
| **API-05** | **High** | The production runtime is one Mac plus a quick tunnel: a reboot means an outage and a new URL; `deploy/` is not what runs | `last reboot` 10:34 IST, tunnel back 10:51 IST (`logs/tunnel.log` 05:21Z) [O]; launchd covers the API only; it waits on `lsof` and would exec the `.venv` Python while live runs Homebrew Python [O]; `api-launchd.log` bind error 11:03 [O] | Every reboot, sleep or network change breaks the team's link; the next start may run a different interpreter or dependencies; no gunicorn timeout, so one hung request holds the single worker. | Short term: a **named** Cloudflare tunnel (a stable hostname) under launchd, plus `caffeinate`. Launch: `deploy/compose.yml` on an Azure VM in the DB's region. |
| API-06 | Medium | Team authorization is thin: anyone can pin to or comment on any board; rows without an owner can be deleted by anyone; with a shared default email, owner checks are void | `team.py:41-48,308-346`; `main.py:467` [O] | Vandalism or accidental deletion of others' work once the features are used (the tables are empty today). | Check board ownership or membership on pin; treat a NULL owner as admin-only; fix with API-01. |
| API-07 | Medium | No rate limits or body-size limits in the running API: `/ask` (paid Opus calls), `/export` (up to 2,000 × 60 × 500-char cells rendered on 1 core), audiences | `exports.py:11,16-24`; `main.py:415-437`; nginx `limit_req` exists only in Docker [O] | One script can burn the LLM budget or pin the CPU and stall every user. | Add per-session token buckets on `/ask` and `/export` (in-process dict), plus a `Content-Length` cap. |
| API-08 | Medium | Live responses lack CSP, X-Frame-Options, nosniff, HSTS and Referrer-Policy; the cookie lacks `Secure` | live headers [O]; `main.py:473` | Clickjacking and MIME-sniffing exposure; the cookie could be sent over plain HTTP on a misrouted request. | One middleware that sets the 5 headers, and `secure=True` when not on localhost. |
| API-09 | Medium | Differencing is possible with audiences of up to 8 answer conditions plus cuts, over respondent bitsets | `team.py:214-257`; acknowledged at `:246` [O] | Two audiences one condition apart can reveal an individual's answer once external users get Audiences. | Round counts to 5, or require a minimum audience base of 30 for display, before client exposure. |
| API-10 | Medium | The team endpoints cost one Azure round trip each (255–280 ms) and are polled on every page; opening a board takes 3 sequential queries | `[PERF-SLOW]` table above; `team.py:282-293` [O] | Every page feels about 0.3–0.8 s slower; the slow log fills with noise. | Cache the 4 lists in memory, cleared on any write in this process; fetch a board in one JOIN. Long term: co-locate with the DB. |
| API-11 | Low | Trend routes are always live SQL (1.9–3.1 s) and unused by the UI | live probes; `etl/publish.py` writes no trends [O] | Dead, slow, unmasked surface. | Delete them (fixes API-03 too). |
| API-12 | Low | `/healthz` and `/api/v1/openapi.json` are public | live 200 without a cookie [O] | Reconnaissance: route map, build id, pool internals. | Put openapi behind `user`; reduce `/healthz` to `{ok, build}` publicly. |
| API-13 | Low | A malformed or non-object JSON body raises a 500 on `/ask` and the team POSTs | `main.py:418`; `team.py:64,274,339` [I] | Noisy 500s; no data risk. | Wrap with `try: body = await request.json(); assert isinstance(body, dict)` and return 422. |
| API-14 | Low | `_published()` accepts `..` inside a multi-segment query value (crosstab `q`) | `main.py:134,385` [O]; not exploitable today [O] | Becomes a file-read primitive (`*.json.gz`) if a subdirectory ever appears under `cuts/`. | Reject parts containing `/` or `\`, or check `path.resolve().is_relative_to(PUBLISHED.resolve())`. |
| API-15 | Low | Error and pagination contract is inconsistent; no response schemas; silent `LIMIT 500` | §7 [O] | Hard to build a customer API or chatbot tools on it. | Standard error envelope plus `response_model` for the public subset. |
| API-16 | Low | `pytest -q` from the root fails collection; no API auth tests | run output [O] | CI or humans may report a red suite or skip auth regressions. | Add `testpaths = ["tests"]`; add tests for dev-login gating, a tampered cookie, owner checks and the trend mask. |
| API-17 | Low | Published files lag the serving tables (12:47 vs 17:31 on 22 Oct) | `manifest.json` vs `/healthz` [O, time zone U] | Two screens can show different numbers for the same wave until the next publish. | After `etl.serving` succeeds, always run `etl.publish` (or gate API fallbacks on manifest equality). |
| API-18 | Low | `config.py` defaults `APP_ENV` to LOCAL; `cip_auth.js` compares HMACs with `!==` | `config.py:103,110`; `cip_auth.js:17` [O] | Fail-open for Streamlit; a theoretical timing side channel in nginx. | Default to production; use `crypto.timingSafeEqual`. |
| API-19 | Info | Ask CIP prose is not verified against the cited figures; no question audit log | `assistant.py:99-107` [O] | A hallucinated number can appear next to a valid citation. | Check every `%` in the answer against its cited source's figures; log questions (without PII). |

---

## 9. Status of prior-audit gaps (backend and security only)

| Prior ID | Claim | Status now | Evidence |
|---|---|---|---|
| Claude G-03 | The portal runs on the owner's all-privileges account; `APP_DB_USER` empty | **Still open.** "Empty" is now **wrong**: the key is set, but it resolves to the same personal account. | `SHOW GRANTS` [O] |
| Claude G-10 | Auth fails open when `APP_ENV` is unset | **Open for Streamlit.** The API needs an explicit `local`, but live *sets* it, so it is open anyway (API-01). | `config.py:103,110`; `main.py:58` |
| Claude G-11 / Codex B11 | Grants script unusable / missing `srv_*` | **Still open** [I]: live uses a personal ALL grant, not the script. | `SHOW GRANTS` |
| Claude G-15 / Codex B13 / G25 | Excel formula injection | **Fixed in the API** (`exports.py:27-29`) and CSV (`csv.ts:5`); **open in the legacy Streamlit** `export.py:85`. | code [O] |
| Claude G-20 | No DB read timeout | **Fixed.** | `database.py:95-98` [O] |
| Claude G-21 | Identity is self-asserted | **Worse in the API:** no passphrase at all; `?email=` is free. | API-01 |
| Claude G-23 / Gemini GAP-09 | Cookie not HttpOnly or Secure | **Partly fixed:** the API cookie is HttpOnly and SameSite=lax, but **not Secure**. The Streamlit cookie is unchanged. | live `Set-Cookie` [O] |
| Claude G-24 / Codex B02 / G02 | SSO not implemented | **Still open:** no OIDC routes in the API. | route table [O] |
| Claude G-25 / Codex B05 / G05 | Small cells exposed or inconsistent | **Mostly fixed** (5-person rule on results, book, questions, crosstab, dashboards, audiences); **still open on trend/trends** (API-03). Codex's "crosstab hides below 30" is **outdated** (now 5). | `payloads.py:28,186`; live |
| Codex B01 / G01 | Entitlements bypassed by generic endpoints and nginx | **Still open,** and moot today only because every session is `*`. | `session.py:20`; `nginx.conf:57-61` |
| Codex G03 | Compare returned 404 | **Resolved by removal:** the route no longer exists and the UI no longer calls it (21 Oct 404s in the log only). | `logs/api.log:882`; `web/src` grep |
| Codex G22 | No customer API | **Still open.** | §7 |
| Codex G31 | Search caps results with no total | **Fixed:** limit ≤ 200, offset, and `total` are returned. | `main.py:361`; `search.py:91` |
| Gemini 01 §3 | The app role writes only `cip_auth_session` and `cip_saved_view` | **Wrong:** the live role has ALL PRIVILEGES. | `SHOW GRANTS` |
| Gemini GAP-05 | Streamlit concurrency ceiling | **Superseded:** clients use React plus FastAPI; reads cost 0.3–8 ms of server time. | `[PERF]` lines |
| Gemini GAP-10 | Local macOS launchd dependency | **Still open and wider:** the API and tunnel now also live on the Mac. | API-05 |
| docs/08-authentication.md | "Does not go on a shared host without a login" | **Wrong for the React portal.** | API-01 |
| Claude G-01 (password in Gemini docs) / G-05 (repo public) | none | **Not re-checked here** (outside the backend scope) [U]. | none |

---

## 10. Unknowns

- **[U]** The live process environment: whether `ANTHROPIC_API_KEY` is set and how strong `CIP_SESSION_SECRET` is. Reading the process environment was blocked by policy; `api.env` holds only the key names `APP_ENV` and `CIP_SESSION_SECRET`.
- **[U]** Whether `trycloudflare.com` is a public suffix. If not, tunnels share a "site", which weakens SameSite.
- **[U]** The time zone of `srv_wave.built_at` compared with the manifest's UTC stamp, which decides the true size of API-17.
- **[U]** The OpenAPI schema completeness. It was fetched but not inspected in depth; response schemas are inferred to be absent because handlers return a raw `Response`.
- **[U]** Behaviour of every POST route under live conditions. POST, PUT and DELETE were not sent, by rule; their behaviour is from code and the SQLite tests only.
- **[U]** Who the external IPs in the access log are (72.152.x/72.153.x). They are presumably the business team.
