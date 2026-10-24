# 81 · Backend fixes (23 Oct 2026)

Scope: `api/*`, `app/core/*`, `app/data/payloads.py`, `deploy/*`, `requirements.txt`, CI, new `config/access.yml`, `config/methodology.yml`, `sql/008_access.sql`.

What was **not** done:
- Nothing was committed.
- The live API on :8000 and cloudflared were not touched. The public `/healthz` returned 200 before and after this work.
- `sql/008` was **not** applied to `cip_stg`, and `~/.config/cip/api.env` was **not** edited. Both are in the runbook at the end.

Tests:
- `.venv/bin/python -m pytest -q` (bare, now limited to `tests/`): **301 passed**.
- The same suite with pillow 13.0.0 (a scratch venv layered on `.venv`): **301 passed**.
- The new HTTP-level tests are in `tests/test_access.py` (11 tests).

A smoke test ran on a separate instance on :8001 against `cip_stg`, then that instance was stopped:
- demo sign-in works;
- `/me`, `/methodology`, `/waves` (371 waves with the new fields), `/book` and `/team/summary` answer;
- `/trend` returns 404;
- CSP, XFO and Referrer-Policy are present;
- a bad JSON body on `/ask` returns 422.

## Gap → change → test

| Gap | Change | Test |
|---|---|---|
| **API-01/04, SEC-01/08, PRF-01, UI-10/12, API-18** sign-in | New `api/signin.py`:<br>• `/auth/login:120`: OIDC authorization code + PKCE (S256), `state` and `nonce` in a signed 10-min `cip_login` cookie. Settings come from `CIP_OIDC_ISSUER`, `CIP_OIDC_CLIENT_ID`, `CIP_OIDC_CLIENT_SECRET` and optional `CIP_OIDC_REDIRECT_URI`. Without a provider it falls back to demo login when `CIP_DEMO_LOGIN=1`; otherwise it shows a clear 503 page.<br>• `/auth/callback:150`: exchanges the code with the PKCE verifier and checks `iss`, `aud`, `exp` and `nonce`. The email is mapped to role, client and tier, and an unknown email is refused when config says so.<br>• `/auth/logout:237`: revokes the session and uses the IdP's `end_session_endpoint`.<br>• `/auth/dev-login:191` works **only** with `CIP_DEMO_LOGIN=1`; `APP_ENV=LOCAL` no longer enables it.<br>• Cookie: `Secure` on https, including behind the tunnel via `X-Forwarded-Proto` (`https():62`); `next` is same-site only.<br>• `app/core/config.py:103,110`: an unset or unknown `APP_ENV` now means **production**. | `test_demo_sign_in_needs_cip_demo_login…`, `test_no_session_is_401…` |
| Session revocation, **DB-13** | `app/core/session.py`:<br>• the cookie is now `email\|products\|expires\|session id\|scope`;<br>• `read()` refuses unsigned, expired, revoked and old 3-field cookies;<br>• `sql/008` stores only the SHA-256 of the session id (`cip_access_session`).<br>Revocation is in memory per worker. `load_revoked()` runs on the 60 s poll, so every worker refuses a revoked session within a minute. `share_revoked()` writes `CIP_REVOKED_FILE` for nginx. Admins can sign a person out everywhere with `POST /api/v1/admin/sessions/revoke {email}`. | `test_sign_out_revokes_the_session_and_is_audited` |
| `cip_auth.js` `!==` | `deploy/cip_auth.js`:<br>• constant-time compare (njs has no `timingSafeEqual`);<br>• the 5-field cookie;<br>• the revoked-file check;<br>• 204 for scope `*`, **403 for a filtered session**, which `nginx` hands to the API (`error_page 403 = @api`). | node check of `same()` |
| **Access model** (PRF-02/03/04, MKT-22/24, API-04/06) | `config/access.yml` holds tiers (demo, core, professional, enterprise → features + study types), roles (admin, analyst, client), staff domains and admins, clients (domains, tier), survey ownership and visibility (by family or survey id; `all`, `client` or `staff`), unknown emails, rate limits, `min_audience` and `max_body_kb`.<br>`app/core/access.py` provides `profile`, `sees`, `allows`, `scope` and `spend`.<br>Enforcement:<br>• every data route checks feature + wave visibility (`main.py visible():279`, `need():287`): waves, book, results, crosstab, questions (filtered to the visible waves by `only_waves():457`), search (a per-scope catalogue, `catalogue():409`), ask (sources only from visible waves) and dashboards;<br>• team objects are scoped to the owner's organisation (`team.py mine():80`), and admins see everything;<br>• pinning and commenting only work on your own team's boards;<br>• deletes: the owner or an admin; an ownerless row: admin only (`remove():112`);<br>• in nginx, filtered sessions never get a shared published file or cached answer.<br>**With the shipped config everything stays visible:** every study is `all`, and unknown emails get `enterprise`, so the demo is unchanged. | `test_a_client_sees_its_own_study…`, `test_team_boards_are_scoped…` |
| **API-19, PRF-05, MKT-25** audit log | `sql/008` `cip_access_log`. `app/core/audit.py`: `record()` only queues the row, and one daemon thread batches the INSERTs, so a request never waits on it.<br>Logged events: sign-in, sign-out, export (screen and board deck), ask (question, mode, cited links), and every board, audience, alert and view write or remove.<br>The IP is stored as a keyed hash; the user agent is cut to 120 characters.<br>`GET /api/v1/admin/audit` (admin only, `main.py:565`) filters by `email`/`action` and pages with `before`. | sign-out and team tests read the rows back |
| **API-03/11, API-09, PRF-07** small cells | `/api/v1/trend` and `/api/v1/trends/...` are deleted. `web/src` calls neither: a grep finds only the `/w/:id/trends` page links, which use `/questions`. `payloads._trend:210` also masks below `HIDDEN_BASE`, for the tests that still call it.<br>Audiences: an audience under `min_audience` (30) shows no figures and no base (`team.py audience()`), so near-identical audiences cannot be subtracted. Complementary suppression of the rest stays.<br>Search returns no figures. Exports render what the screen posts, which is already masked. | `test_the_unmasked_trend_routes_are_gone`, `test_an_audience_…hides_groups_under_30` |
| **API-07** limits | Per-person token buckets (`access.spend`):<br>• `/ask` 10/min;<br>• `/export` 30/min;<br>• audience views 60/min.<br>All are configurable and answer 429 with `Retry-After`.<br>The body cap is `max_body_kb` = 1 MB (`main.py body_limit():634`): 413, or 411 for a chunked body without length. nginx also has `client_max_body_size 1m`. Export size was already bounded (2,000 × 60 × 500 characters). | `test_bad_bodies_are_422_or_413…` |
| **API-13/15** errors | `team.json_body:44`: a malformed or non-object body returns 422.<br>One error shape, `{"detail": text, "status": code}`, for HTTP errors, validation (422, with a readable string), LookupError and unhandled exceptions (500, logged) (`main.py:237-262`). The UI's `.detail` keeps working. | same |
| **API-12, SEC-09** | `/healthz` now returns only `{ok, build}` (CI's build check still matches). The old detail is admin-only at `/api/v1/admin/health`. `/api/v1/openapi.json` needs a session. | `test_me_and_methodology…` |
| **API-14** | `_published():140` rejects any part containing `..`, `/` or `\`. | `test_published_paths_never_climb_out` |
| **API-08, SEC-06, UI-24** headers | `main.py security_headers():618`, on every response:<br>• CSP: `default-src 'self'`, `script-src 'self'` plus the sha256 of index.html's inline theme script (computed from `web/dist`, so a rebuild stays valid), `style-src 'self' 'unsafe-inline'` (ECharts), `img-src data: blob:`, `frame-ancestors 'none'`;<br>• XFO DENY, nosniff, Referrer-Policy;<br>• HSTS on https.<br>nginx sends the same headers (`cip_headers.conf`, hash filled in at image build) and hides the API's copies. | `test_every_answer_carries_the_security_headers` |
| **UI-02** one significance rule | `api/dashboards.py tested():131`: a takeaway calls a change significant only when the ETL's `srv_result` `sig_prior`/`sig_ly` flag is on that answer's Total row (BH-FDR, the Overview's rule).<br>• Multi-code tiles and segments are never "significant".<br>• A wave whose serving rows carry no `sig_*` flag yet (built before the ETL change) falls back to the old z-test and says **"single comparison"** (`single():225`). | `test_takeaways_mention_only_significant…` (updated + 2 new asserts) |
| **UI-03, MKT-19/20, ETL-24** provenance | `payloads.describe():47` adds to every wave (in `payloads.waves()`, `book()['wave']`, and at serve time for files published before):<br>• `population` (from `config/methodology.yml`: tracker → "US adults 18+", else "Survey respondents"; per family or id overrides);<br>• `weighting` "unweighted";<br>• `in_field` (from `srv_wave.in_field`, read through `w.*`, so it works before the column exists);<br>• `verified` (`load_status == 'verified'`);<br>• `client`;<br>• `visibility`.<br>`GET /api/v1/me` returns {email, name, role, tier, client, features[]}. `GET /api/v1/methodology` returns `config/methodology.yml`: panel, qualification, fielding, weighting=none, data quality, small cells, significance. Panel and quota text only claims what the DB shows (sample source 114; quota_json is empty, so no quota dimensions are claimed). | provenance and `/me` tests |
| **API-10, PRF #28** team performance | `team.py cached():100`: lists and boards are kept in memory per database. Every write touches `CIP_TEAM_STAMP`, which every worker on the host compares (one `stat`), so there is no cross-worker staleness.<br>• A board opens in **one** JOIN instead of 3 queries (`BOARD`, `board():410`).<br>• A delete is one round trip when the row is yours.<br>• New `GET /api/v1/team/summary` returns boards, views, alerts and audiences in one call (empty lists for features the tier lacks). | `test_team_boards_are_scoped…` (cache cleared on write) |
| **OPS-06, SEC-07** | `pillow>=13.0.0,<14` added to `requirements.txt`. The Dockerfile now installs `requirements.txt` itself (no second pin list). `pip-audit -r requirements.txt` was added to `.github/workflows/ci.yml` and `bitbucket-pipelines.yml`. | 301 pass on pillow 13 |
| **OPS-09, API-16** | `pytest.ini` sets `testpaths = tests`; bare `pytest` now gives 301 passed. HTTP auth and cookie tests are in `tests/test_access.py`. | — |
| **OPS-02/04/07, API-05** one VM | `deploy/compose.yml` runs these services:<br>• `api`: gunicorn with 2 uvicorn workers and a healthcheck;<br>• `nginx`: TLS on 8443 with IT's cert from `/etc/cip/tls`; 8080 redirects to https unless a TLS proxy already sent `X-Forwarded-Proto: https`; healthcheck;<br>• `etl`: `deploy/etl-loop.sh` runs `weekly_forsta.py` at `Mon@12:00`, `Fri@03:30` UTC (17:30 and 09:00 IST, the launchd slots; the script decides planned Mondays from `launch_schedule.yml` and takes the ETL lock), the watchdog hourly, and logs/*.log rotation at 20 MB;<br>• `backup`: `deploy/backup.sh` runs `scripts/backup_db.py` (proven dump) plus a copy of the published files to `CIP_BACKUP_DIR` (an IT mount), keeping 4, on Sundays.<br>All services use `restart: unless-stopped` and json-file logs capped at 20 MB × 5. One image serves api, etl and backup; it is bookworm-based so MySQL's own `mysqldump` is available (`backup_db.py` uses MySQL-only flags). | not built: the Docker daemon is not running on this Mac |
| PERF-SLOW sweep | Of the 242 `[PERF-SLOW]` lines in `logs/api.log`:<br>• 224 are team endpoints, boards and their writes (fixed above);<br>• 2 are the deleted trend routes;<br>• the rest are cold book/results builds from SQL before a publish existed. Those are cached after the first request, and nginx serves the published copies. | — |

### Before and after: team endpoints against `cip_stg` from this Mac

Function-level timings, median of 8 runs. "After, first" is a cold cache, i.e. the first request after any team write.

| Request | Before | After (cached) | After, first |
|---|---|---|---|
| GET /boards | 275 ms | 0.01 ms | 277 ms |
| GET /team/views | 265 ms | 0.01 ms | 255 ms |
| GET /alerts | 257 ms | 0.01 ms | 258 ms |
| GET /audiences | 256 ms | 0.01 ms | 257 ms |
| The 4 lists a page polls | 1,040 ms (4 requests) | 0.02 ms (`/team/summary`) | 1,108 ms |
| Board open, SQL | 774 ms (3 queries) | — | 256 ms (1 JOIN) |

Over HTTP on :8001:
- `/team/summary` took 1,086 ms cold and 0.9 ms warm;
- `/boards` took 0.65 ms after that;
- `/me` took 0.46 ms.

## Hand-offs and open points

- **ETL agent:** `sql/009_serving_flags.sql` and my `schema_upgrade` entries (WIDEN `srv_result.flags` + `sig_prior`, `sig_ly`; COLUMNS `srv_wave.in_field TINYINT(1) NOT NULL DEFAULT 0`) define the same thing in the same member order. Either path works. `scripts/init_db.py` is idempotent; 009's `ADD COLUMN` fails harmlessly on a re-run.
  - 009's `cip_forsta_survey.load_state` ENUM change is only in 009.
  - `schema_upgrade.install` now runs `plan()` again after the SQL files, so a fresh install also gets the COLUMNS additions.
- **Frontend:**
  - 401 → `/auth/login?next=` works;
  - `/me` and `/methodology` exist with the shapes above;
  - `/team/summary` is available to replace the 4 polls.
- **Test file edits outside my own:**
  - `tests/test_dashboards.py`: one row gained `"sig": {"prior"}`, plus two assertions, because the takeaway rule changed by design;
  - the team tests call the list functions without a request; `request=None` means a trusted Python caller.
- **Known ceilings** (marked `ponytail:` in code):
  - rate limits are per worker (2 workers allow 2×);
  - the OIDC ID token signature is not re-verified (it comes straight from the token endpoint over TLS, as OIDC Core 3.1.3.7 permits);
  - a board's spec repeats per comment row in the one JOIN;
  - audiences use a minimum size, not rounding.
- **Grants:** the DBA needs to add, for `cip_app`: `INSERT` on `cip_access_log` and `INSERT, UPDATE` on `cip_access_session` (the lines are in the `sql/008` header).
- **Before external clients**, in `config/access.yml`:
  - set `unknown: refuse`;
  - list each client's domains;
  - set client studies to `visibility: client`;
  - leave `CIP_DEMO_LOGIN` unset on the client-facing VM.
- **Not verified:**
  - the Docker images were not built (no daemon), so the MySQL APT key and package name in the Dockerfile and the nginx config (`nginx -t`) are untested;
  - OIDC was not run against a real issuer.

## Apply at restart (needs user approval)

The live process runs the code it started with. None of this is active until it restarts.

1. **Apply the schema.** `sql/008_access.sql` adds `cip_access_log` and `cip_access_session`. It is idempotent, and `init_db` also adds `srv_wave.in_field` and the `sig_*` flags if 009 is not applied yet. Run it while no ETL load is running:
   ```
   .venv/bin/python scripts/init_db.py --dry-run   # review
   .venv/bin/python scripts/init_db.py
   ```
   Without it, the portal still works: sessions are not recorded for admin revocation, and audit rows are dropped with a warning.
2. **Keep the demo sign-in working.** Append one line to `~/.config/cip/api.env`, without touching the other lines:
   ```
   echo 'CIP_DEMO_LOGIN=1' >> ~/.config/cip/api.env
   ```
   Without it, the link shows "Sign-in is not set up". For real sign-in, also add `CIP_OIDC_ISSUER`, `CIP_OIDC_CLIENT_ID`, `CIP_OIDC_CLIENT_SECRET`, and `CIP_OIDC_REDIRECT_URI=https://<link>/auth/callback`; when OIDC is set, `/auth/login` uses it.
3. **Install pillow 13** in the venv: `.venv/bin/python -m pip install -r requirements.txt`.
4. **Restart, per the repo rule.** Kill only the :8000 listener, never cloudflared, and start with the venv's Python and the env file:
   ```
   kill $(lsof -ti tcp:8000 -sTCP:LISTEN)
   set -a; . ~/.config/cip/api.env; set +a
   nohup .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 >> logs/api.log 2>&1 &
   ```
   The `cip-api` launchd job may take over the port instead. Either way, check:
   ```
   curl -s https://cheque-bought-dust-successfully.trycloudflare.com/healthz   # → {"ok":true,"build":…}
   ```
5. **Effect on users:**
   - everyone's old cookie is refused once, because the cookie format changed;
   - the SPA sends them to `/auth/login`, which goes on to demo sign-in, so the demo is seamless;
   - Overview takeaways switch to the ETL's flags once the ETL rebuilds serving and dashboards; until then they say "single comparison".
