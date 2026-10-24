# 50 · Ops, security, stack and profile level: pre-launch audit

Date: 23 Oct 2026 · Repo HEAD `aa4bfdb` (= `origin/master`), one untracked file (`scripts/launchd/com.coresight.cip-api.plist`).
Tags: **[O]** observed (command or file:line), **[I]** inferred, **[U]** unknown. Secret values were never printed; only key names, lengths and whether a value matches tracked text.

## Summary verdict: NOT launch-ready for clients

The code quality is good. 290/290 tests pass, CI is green on GitHub, and the Docker/nginx target is thought through. The hosting, identity and secrets around that code are still a developer prototype. Four things block any client launch:

1. **Anyone with the link is signed in as anyone, with access to every product.** The live API runs with `APP_ENV=LOCAL`, so `/auth/dev-login?email=<any>` issues a valid 12 h session with products `*` through the public tunnel. [O] `curl` returned 303 + `Set-Cookie: cip_session`. No OIDC path exists for the React/FastAPI portal.
2. **A DB credential is in the public GitHub repo.** `gh repo view` → `"visibility":"PUBLIC"`. The bare credential on `.env:70` (20 chars, for `mohdsaeed@10.2.1.9`) is committed in two Gemini docs since `442cfb5` (20 Oct) and is pushed. It is still in `.env`. Whether it was rotated is [U].
3. **The internet-facing API uses a personal account with ALL PRIVILEGES on 4 schemas.** Both the `app` and `etl` engines are `mohdsaeedafri@%`, with ALL on `cip_stg`, `chainxydata_stg`, `coresight_market_data_stg` and `dwh_directus_stg`, plus SELECT on `dwh_stg`. [O] `SHOW GRANTS`.
4. **One Mac with no backups on disk.** The API, ETL, watchdog, backups and tunnel all run on one developer Mac behind a cloudflared *quick* tunnel (random URL, no SLA, new URL on every restart). `backups/` is empty, no off-machine copy is configured, and the last proven backup is from 19 Oct and is gone.

Entitlements, tenancy, audit logging and the respondent salt are also missing (see the PRF items). They matter before external clients, though not for an internal-only pilot.

## 1. Stack inventory

| Layer | What | Evidence |
|---|---|---|
| Python | 3.13.12 (venv and Docker `python:3.13-slim-trixie`) | [O] `.venv/bin/python --version`, `deploy/Dockerfile` |
| API | FastAPI 0.150.0, uvicorn 0.54, gunicorn 26.2 | `requirements.txt` |
| Live process | **one** `python -m uvicorn api.main:app --port 8000`, started by hand 10:50:53 (not gunicorn, not launchd) | [O] `ps` pid 7310 |
| Web | React + Vite (TS), echarts, tanstack-query; served from `web/dist` by FastAPI locally, by nginx in the target | `web/package.json`, `api/main.py:503-515` |
| Staff UI | Streamlit 1.55 `app/pages/*`. **Not running** today. It is still in `requirements.txt` and `app/core` is shared by the API. Two UIs coexist; only React is live. | [O] `ps` has no streamlit |
| DB | Azure MySQL Flexible `csr-mysql8-flex-stg…`, schema `cip_stg`, TLS with `DigiCertGlobalRootG2.crt.pem` | `logs/backup.log`, `app/core/database.py` |
| LLM | `anthropic==2.0.0` for Ask CIP. `ANTHROPIC_API_KEY` is not set in `.env`/`api.env`, so answers fall back to cited figures. | [O] key names; `api/assistant.py:5` |

**Pinning.** `requirements.txt` mixes `==` and `>=`, and there is no lock file. The Dockerfile installs its **own hand-listed pins** (`deploy/Dockerfile:13-16`), so the image and the venv can drift. [O]

**Outdated** (`pip list --outdated`): fastapi 0.150→0.161, streamlit 1.55→1.66, pandas 2.3→3.1, SQLAlchemy 2.1.1→2.1.6, pillow 12.3→13.0, anthropic 2.0→2.1, among others.

**pip-audit** (via `uvx`, venv freeze): **37 known vulns**. 35 are in **pillow 12.3.0** (fix 13.0.0; pulled in by python-pptx and used by pptx export). The other two are gitpython 3.1.62 (dev only) and certifi 2026.7.22. [O]

**npm audit --omit=dev**: 2 low. katex sits under `@mermaid-js/mermaid-cli`, which is a **runtime** dependency of `web/` but is a docs tool and belongs in devDependencies. [O]

## 2. Hosting and ops reality

```
             Internet (anyone with the link)
                        │  https://cheque-bought-dust-successfully.trycloudflare.com
                        ▼
        cloudflared quick tunnel (pid 7387, hand-started 10:51, no account, no launchd)
                        │  http://127.0.0.1:8000   (no nginx, no TLS hop, no headers, no rate limit)
                        ▼
 ┌──────────── Developer MacBook (sleep=1 min, only caffeinate keeps it up) ────────────┐
 │ uvicorn api.main:app  (1 process, APP_ENV=LOCAL → dev-login ON)                      │
 │ launchd: cip-api (NEW, untracked) – busy-waits `lsof :8000` every 15 s, then execs   │
 │          uvicorn with ~/.config/cip/api.env (APP_ENV, CIP_SESSION_SECRET only)       │
 │ launchd: cip-forsta-etl (12 calendar slots, weekly_forsta.py)                        │
 │ launchd: cip-etl-watchdog (hourly, same script)                                      │
 │ launchd: cip-backup (Sun 10:00, mysqldump → backups/, KEEP=4, no off-box copy set)   │
 │ logs/ (716 KB, no rotation)   data/ 176 MB   backups/ EMPTY                          │
 └──────────────────────────────────────────┬───────────────────────────────────────────┘
                                            │ personal account mohdsaeedafri@% (ALL on 4 schemas)
                                            ▼
                         Azure MySQL Flexible STG  (cip_stg)  ◄── Forsta API (GET)
```

| Topic | Finding | Tag |
|---|---|---|
| SPOF / bus factor | One Mac, one person's DB account, Forsta key, SMTP, Teams webhook and home paths in plists (`/Users/mohdsaeedafri/...` appears in 123 tracked files). If the owner is away or the laptop sleeps, travels or reboots, the portal is down and the link changes. | [O] |
| Uptime | The reboot at ~10:35 today changed the tunnel URL. cloudflared is not under launchd, so it does not come back by itself. The `cip-api` launchd job can relaunch the API but **not** the tunnel. | [O] `ps`, `launchctl list` |
| `cip-api` job | `KeepAlive` + `RunAtLoad`. While :8000 is held it loops `lsof` every 15 s. If the hand-started API dies, it takes over with `api.env`, which is fine. Its earlier attempt failed with `[Errno 48] address already in use` (`logs/api-launchd.log`). The job is untracked in git. | [O] |
| DR / backups | `backups/` is **empty** (dir mtime 21 Oct 05:59). Only one proven backup was ever logged (19 Oct, 321 MB). `CIP_BACKUP_COPY_DIR` is not set, so there is no off-machine copy. The next run is Sunday 25 Oct. With the Mac lost, DR relies only on Azure MySQL's PITR [U: retention not verified]. | [O] `ls`, `logs/backup.log`, `scripts/backup_db.py:35,136` |
| Monitoring | ETL heartbeat `logs/etl-heartbeat.json` (last 09:01, exit 0). Watchdog hourly. Email + Teams via `etl/notify.py`; recipients are the developer only (`config/notify.yml:5`). There is **no uptime check of the API or tunnel**, so nobody is told when the shared link dies. | [O] |
| Logs | Every launchd log line starts with `python-dotenv could not parse statement starting at line 67`, caused by the malformed `.env`. No rotation; `api.log` is 150 KB and grows. Logs record the path but not the user, so they give no audit trail. | [O] `logs/etl-watchdog.log`, `api/main.py:474-487` |
| Sleep | `pmset`: `sleep 1`, prevented only by running `caffeinate` processes. No `autorestart`. | [O] |

### Target deployment (deploy/)

- `deploy/compose.yml` defines nginx :8080 → api (gunicorn 2 workers, 768 MB, 1 CPU), with the publish dir read-only and the nginx cache on the host. nginx checks the HMAC cookie itself (`deploy/cip_auth.js`), uses `limit_req` at 300 r/s per IP (`nginx.conf:33,97`), and sets `X-Frame-Options` (`cip_headers.conf:4`). The design fits the 1-vCPU servers (staging 4.5 GB, prod 8–9 GB). [O]
- **The ETL is not containerised.** compose expects it on the host via cron/systemd, but no systemd unit or cron file exists; only Mac launchd plists do. [O]
- **No TLS** in nginx; it listens on plain 8080. No HSTS, no CSP. TLS is assumed to come from an upstream not defined here. [O]
- **CI.** `.github/workflows/ci.yml` and `bitbucket-pipelines.yml` are identical: pytest, `npm run check` + build, docker build of both images, and an API boot against SQLite. The last 4 GitHub runs are all `success`. Bitbucket is [U]: the repo remote is GitHub only. CI has **no deploy step, no image push, no dependency audit and no lint/type check for Python**. [O] `gh run list`
- **Missing for Azure launch:**
  - a host (VM or App Service/Container Apps) and a private endpoint/VNet to MySQL;
  - TLS cert plus a stable domain;
  - OIDC/SSO for the React API;
  - a secrets store (Key Vault) instead of `.env`;
  - the `cip_etl`/`cip_app` service accounts from `sql/004_grants.sql`, created and wired via `APP_DB_USER`/`APP_DB_PASSWORD` (empty today);
  - a Forsta service-account key (`docs/04` §1.1, "blocking");
  - ETL scheduling on the server;
  - backups off-box;
  - uptime monitoring;
  - a release process: there is no tag or image registry, and `build` is just `git describe`. [O]/[I]

## 3. Security findings

| # | Finding | Evidence |
|---|---|---|
| S1 | **Repo is PUBLIC** on GitHub `saeedafri/consumer-insight-portal`. It contains internal hostnames: `csr-mysql8-flex-stg…` in 2 files and `10.2.1.9` in 12 files. It also has business docs, `docs/samples/*.xlsx`, `docs/data/concept_dictionary.csv`, 321 `graphify-out` cache files, a personal email in `config/notify.yml`, and home paths. | [O] `gh repo view`, `git grep -l` counts |
| S2 | **Leaked credential still tracked and pushed.** The value on `.env:70` appears verbatim in `docs/REA Gemini/05-IDENTIFIED-GAPS-AND-DEFECT-LEDGER.md` and `docs/LLM Council Gemini/advisors/01-the-contrarian.md`. It was introduced in commit `442cfb5` and is on `origin/master`. Removing the files is not enough: history must be rewritten and the password rotated. The LLM Council roadmap marks "Rotate Passwords: done" (`LLM Council Gemini/action-plan/01-prioritized-roadmap.md:17`), but `.env:68-70` still hold the line, so rotation is [U]. | [O] `git grep -lF`, `git log -S` |
| S3 | Live secrets (`STG_DB_PASSWORD`, `FORSTA_API_KEY`, `AUTH_SHARED_PASSPHRASE`, `EMAIL_PASSWORD`, `TEAMS_WEBHOOK_URL`, Cloudflare R2 keys/token, live `CIP_SESSION_SECRET`) appear in **no** tracked file and in no history. | [O] value match = 0 for each |
| S4 | `.env` hygiene: `FORSTA_API_KEY` is defined **twice**; lines 68–70 hold a pasted `mysql` command and a bare credential; lines 83–85 hold a pasted `curl` example with a Cloudflare bearer header and account path. `APP_DB_USER`/`APP_DB_PASSWORD` are empty. Unrelated Cloudflare R2 credentials sit in the CIP `.env`. Every process warns at line 67. The file is mode 600. | [O] key-name scan |
| S5 | `.claude/launch.json` (tracked) contains a `CIP_SESSION_SECRET=` value. It is a "loca…" dev placeholder, **not** the live secret (match = 0). This is Low, but it shows the secret was once pasted into a tracked file. | [O] |
| S6 | **Auth: dev-login is live on the internet.** `api/main.py:466-474` gates only on `APP_ENV == local`, and `~/.config/cip/api.env` sets `APP_ENV=LOCAL`. Any email is accepted, products are `*` (`app/core/session.py:20`), and the cookie is `secure=False`. `web/src/api.ts:93,164` sends every 401 to dev-login. There is **no other sign-in** for the React portal: no OIDC, no logout. Self-asserted identity also means `owned()` checks in `api/team.py:41-48` can be bypassed by signing in as the owner's email. | [O] curl 303 |
| S7 | Streamlit auth (`app/core/auth.py`) has `local` (allowlist + shared passphrase) and `oidc` modes, but `sign_in_oidc` (`:329`) has no caller in app code; `0_Login.py:38` is only a link. `APP_ENV` defaults to LOCAL when unset (`app/core/config.py:103,110`), so it **fails open**. | [O] |
| S8 | **CSRF.** The cookie is `SameSite=Lax` and mutating routes are POST/DELETE with JSON bodies, which is a reasonable baseline. There is no CSRF token and no Origin check. [I] Low risk today because dev-login already gives everything away. | [O] `api/main.py:473` |
| S9 | **Rate limiting / headers.** These exist only in nginx (`deploy/nginx.conf`), which is not used live. The live tunnel serves no HSTS, CSP or X-Frame-Options (curl -I shows only `server: cloudflare`). `/healthz` and `/api/v1/openapi.json` are public; healthz exposes the build, pool stats and counts. | [O] |
| S10 | **DB least privilege.** See verdict item 3. `sql/004_grants.sql` defines `cip_etl`/`cip_app` correctly (SELECT plus per-table writes for team tables), but nothing uses them. The API has blast radius over 3 other products' schemas. | [O] `SHOW GRANTS` |
| S11 | Formula injection is handled: `api/exports.py:28` and `web/src/csv.ts:4`. | [O] |
| S12 | Dependency CVEs: pillow ×35 (fix 13.0.0), certifi, katex (low). | [O] |

## 4. Profile level: identity, entitlements, tenancy, privacy

| # | Finding | Evidence |
|---|---|---|
| P1 | **No roles.** The session is `email\|products\|expires` and nothing more: no analyst/client/admin distinction. Every signed-in user can create, delete and comment on the global team boards, views, alerts and audiences. | [O] `api/main.py:228-239`, `api/team.py` |
| P2 | **Product entitlement covers only dashboards.** Only `/api/v1/dashboards/{code}/{id}` checks `products` (`api/main.py:258`). `results`, `waves`, `book`, `questions`, `search`, `ask`, `export`, team routes and nginx-served published files all ignore it. A `products=X` user still sees every wave. (This is Codex G01 and it is still open.) | [O] grep `products` = 1 check |
| P3 | **No tenancy.** There is no org/client column on sessions, studies or team tables. Ad hoc client studies (`study_type=adhoc`) are served to everyone. Client A would see client B's ad hoc study. | [O]/[I] no tenant field anywhere in `api/` |
| P4 | **No access audit for the React portal.** `cip_auth_session` (`sql/001_schema.sql:658-672`) is written only by Streamlit. API logs carry the path and timing, not the user. Exports and Ask are not logged per user. There is no record of who viewed or exported what. | [O] |
| P5 | **Respondent key is unsalted.** `etl/records.py:24-25` uses HMAC with `CIP_RESPONDENT_SALT` only if it is set. It is **not set** in `.env`, `api.env` or the environment, so new loads store plain `sha256(RID)`, which can be brute-forced if RIDs are enumerable. `forsta_uuid` is stored in clear (`etl/forsta_etl.py:371`). Open-text answers (`value_text`) are stored and may contain PII; there is no redaction step. | [O] |
| P6 | **Small-cell thresholds are inconsistent.** There are three rules: (a) `HIDDEN_BASE=5`, where figures are hidden under 5 (`app/data/payloads.py:28`; lowered from 30, see `etl/publish.py:83`); (b) `SMALL_BASE=50`, a warning only (`etl/serving.py:31`, `web/src/stats.ts:42`); (c) Excel crosstab flags `**` under 30 and `*` under 100 (`etl/crosstab_export.py:115`), and the Streamlit Analysis page warns under 30 (`app/pages/3_Analysis.py:164`). The audience builder admits a **differencing** attack: two audiences differing by fewer than 5 people can be subtracted (`api/team.py:246-247`, an acknowledged ponytail note). n=5 is a privacy floor, not a reporting floor, and is too low for client-facing custom audiences. | [O] |
| P7 | **GDPR/CCPA.** No retention policy, purge job, erasure path, DPA/processing record or privacy notice exists in the repo. Ask CIP would send question text and figures to Anthropic once a key is set, with no DPA noted. | [O] grep `retention\|purge\|erasure` = 0 |

## 5. Tests and CI

- `.venv/bin/python -m pytest -q` (bare) gives **1 collection error and 0 run**: it collects `scripts/e2e_perf_test.py`, which needs `playwright` (not installed). There is no `testpaths` in config. [O]
- `.venv/bin/python -m pytest -q tests` gives **290 passed, 0 failed, 0 skipped, 18.0 s**. conftest stubs `notify.requests.post` and the SMTP throttle file (`tests/conftest.py:29-44`). [O]
- Web: `npm run check` is a statistics self-check (`src/stats.check.ts`). There are no component/e2e tests in CI. [O]
- CI runs on GitHub: last 4 runs green. [O]
- Not covered:
  - auth negative paths for the API (dev-login disabled when not LOCAL is not asserted in `tests/test_auth.py`) [U: not read in full];
  - entitlement on non-dashboard routes;
  - a real MySQL fresh install (SQLite only);
  - backup/restore;
  - nginx `cip_auth.js` parity with `api.main.user`.
- Docs freshness: README "371 waves" matches the live `/healthz` `serving_waves: 371`. [O]

## 6. Gap table

| ID | Sev | Gap | Evidence | Consequence | Smallest fix |
|---|---|---|---|---|---|
| SEC-01 | **Critical** | Dev-login open to the internet: any email, all products | `api/main.py:466-474`; `api.env APP_ENV=LOCAL`; curl 303 | Anyone with the link reads all survey data and impersonates staff | Today: set `APP_ENV` to non-local and front the tunnel with Cloudflare Access (email OTP), or add the `local` allowlist + passphrase to the API. Launch: OIDC |
| SEC-02 | **Critical** | DB credential in public repo history | 2 Gemini docs, commit `442cfb5`, `origin/master` | Credential abuse on `10.2.1.9` | Rotate first, then make the repo private, redact the 2 files and purge history (`git filter-repo`) |
| SEC-03 | **Critical** | Repo is public | `gh repo view` | Internal hosts, docs, samples and business numbers exposed | `gh repo edit --visibility private` (owner decision) |
| SEC-04 | **High** | API and ETL run as a personal ALL-PRIVILEGES account over 4 schemas | `SHOW GRANTS` | One API bug or SQLi reaches other products' data; bus factor | Create `cip_app`/`cip_etl` from `sql/004_grants.sql`; set `APP_DB_USER/PASSWORD` |
| SEC-05 | High | `.env` malformed: duplicate Forsta key, pasted commands and a bare credential, foreign R2 keys | key-name scan | Wrong key wins silently; warning noise; secret sprawl | Delete lines 68–70 and 83–85, keep one Forsta key, move R2 keys out |
| SEC-06 | High | No TLS/HSTS/CSP/rate limit on the live path; nginx unused | curl -I; `deploy/` | Clickjacking, brute force, no header hardening | Launch behind nginx (as in compose) with TLS |
| SEC-07 | Medium | pillow 12.3 has 35 CVEs; no audit in CI | pip-audit | Exposure via pptx path | Pin `pillow>=13`; add `pip-audit` + `npm audit` steps to CI |
| SEC-08 | Medium | Streamlit auth fails open (APP_ENV defaults LOCAL); OIDC unwired | `config.py:103,110`; `auth.py:329` | Unsafe if Streamlit is ever deployed | Default to PROD, or retire Streamlit from the deploy |
| SEC-09 | Low | Public `/healthz` and openapi expose build and pool detail | curl | Recon | Trim healthz for anonymous callers |
| SEC-10 | Low | Dev session secret value in tracked `.claude/launch.json` | file:35,52,69 | Habit risk | Read it from env |
| OPS-01 | **Critical** | Production = developer Mac + quick tunnel; URL changes on restart; no SLA | `ps`, `pmset`, memory note | Team loses access on any reboot (it happened today) | Interim: a named Cloudflare tunnel (stable hostname) under launchd. Launch: Azure host |
| OPS-02 | **High** | No backups exist now; no off-box copy | `backups/` empty; `CIP_BACKUP_COPY_DIR` unset | Data loss beyond Azure PITR | Set `CIP_BACKUP_COPY_DIR`, run once now, confirm Azure PITR retention |
| OPS-03 | High | No uptime alert for the API or tunnel | no probe found | Silent outage | External 5-min check of `/healthz`, posting to the existing Teams webhook |
| OPS-04 | High | ETL has no server home (compose assumes host cron; only Mac plists exist) | `deploy/compose.yml:2` | Cannot launch on Azure as-is | systemd timer or Container Apps job running `weekly_forsta.py` |
| OPS-05 | Medium | `cip-api` launchd plist untracked; cloudflared not supervised | git status; `launchctl list` | Unreproducible host setup | Track the plist; add a cloudflared plist |
| OPS-06 | Medium | Dockerfile pins diverge from `requirements.txt`; no lockfile | `Dockerfile:13-16` | Image ≠ tested env | Install from one pinned/locked file |
| OPS-07 | Medium | No log rotation; dotenv warning on every line | `logs/` | Noise; disk growth | newsyslog or `RotatingFileHandler`; fix `.env` |
| OPS-08 | Medium | No release process: no tags, no image registry, no deploy step | CI files | Can't say what is live or roll back | Tag + push image in CI; deploy from tag |
| OPS-09 | Low | Bare `pytest` breaks on `scripts/e2e_perf_test.py` | run output | Confuses contributors | `testpaths = tests` in config |
| OPS-10 | Low | Alerts go to one developer only | `config/notify.yml:5` | Bus factor | Add analyst/ops recipients |
| PRF-01 | **High** (client launch) | No SSO/OIDC for the React API; identity is self-asserted | `web/src/api.ts:93` | No real users, no offboarding | OIDC code flow in the API issuing the same HMAC cookie |
| PRF-02 | High | Product entitlement enforced on 1 route only | `api/main.py:258` | Subscriptions not enforceable | One dependency that checks product/survey on every data route and in `cip_auth.js` |
| PRF-03 | High | No tenancy: ad hoc client studies are visible to all | no org field | Client data cross-exposure | Add `client_id`/visibility to surveys and the session; filter |
| PRF-04 | High | No roles (analyst/client/admin) | session format | Clients could edit team boards and alerts | Add `role` to the session; gate `/team/*` writes |
| PRF-05 | High | No access audit log (view/export/ask) | grep | Can't answer "who saw what" | One middleware line: `email, path, status` to an append-only table or file |
| PRF-06 | Medium | `CIP_RESPONDENT_SALT` unset, so `respondent_key` is plain sha256 | `etl/records.py:24-25` | Re-identification by RID enumeration | Set the salt in the secrets store; run `scripts/rekey_respondents.py` |
| PRF-07 | Medium | Three small-cell conventions (5 / 30 / 50 / 100); audience differencing | §4 P6 | Inconsistent disclosure; small-group leakage | One policy constant; raise the client-facing floor (for example 30) and round audience counts |
| PRF-08 | Medium | No retention/erasure/DPA; open-text may hold PII | grep | GDPR/CCPA exposure | Retention note + purge script; PII scrub of `value_text` |

## 7. Status of prior-audit gaps (ops/security/profile only)

| Prior gap | Status now | Evidence |
|---|---|---|
| Claude G-01 (password in Gemini docs, "untracked") | **Worse**: now tracked and pushed to the public repo | `git log -S` → `442cfb5` |
| Claude G-03 (personal all-priv account) | **Open** | `SHOW GRANTS` |
| Claude G-04 (prod code not in git) | **Mostly fixed**: tree clean except the `cip-api` plist | git status |
| Claude G-05 (repo public, notify-state tracked) | Public: **open**. `logs/` untracked: **fixed** (`.gitignore`) | `gh`, `git ls-files logs` = 0 |
| Claude G-06 (.env hygiene) | **Open** (dup key, lines 68–70, plus a new curl block 83–85) | key scan |
| Claude G-09 (pytest sends real mail) | **Fixed** | `tests/conftest.py:37-44` |
| Claude G-10 / G-23 / G-24 (Streamlit auth fails open, cookie, OIDC) | **Open** but moot while Streamlit is not deployed; the React path has a worse equivalent (SEC-01) | §3 |
| Claude G-11 (grants file broken) | **Fixed in file, not applied** | `sql/004_grants.sql:10-22`; live grants |
| Claude G-14 (one laptop) | **Open** | §2 |
| Claude G-15 / Codex G25 (formula injection) | **Fixed** | `api/exports.py:28`, `web/src/csv.ts:4` |
| Claude G-16 (no run lock) | **Fixed** | `scripts/weekly_forsta.py:235` GET_LOCK |
| Claude G-21 / G-22 (self-asserted identity, no roles) | **Open** | §4 |
| Claude G-25 / Codex G05 (small cells) | **Partly fixed**: masking under 5 everywhere, but the floor is low and inconsistent; differencing open | §4 P6 |
| Claude G-26 (unsalted key) | **Code fixed, config not**: salt unset | §4 P5 |
| Claude G-28 (backup gaps) | **Open / worse**: zero backups on disk | `ls backups` |
| Claude G-29 (stale README numbers) | **Fixed** for headline waves (371 = live) | healthz |
| Claude G-31 (dwh_stg drop script) | **Fixed** (deleted) | `ls` |
| Codex G01 (product policy only on dashboards) | **Open** | `api/main.py:258` |
| Codex G02 (no production OIDC; 401 → dev-login) | **Open** | `web/src/api.ts:93` |
| Codex G11 (grant plan) | **File updated, not applied** | as above |
| Codex G12 (dirty tree, unknown release) | **Improved**: HEAD = origin, healthz shows build `aa4bfdb`; still no tags | healthz |
| Gemini GAP-01 (Forsta key 401) | **Wrong / fixed**: ETL loads (register 84 loaded today) | `logs/forsta-etl.log` |
| Gemini GAP-02 (.env secret) | **Open**, and Gemini's own docs re-leaked it | §3 S2 |
| Gemini GAP-04 (DB unreachable via dynamic IP) | **Open** in principle (Mac-hosted) | §2 |
| Gemini GAP-05 (Streamlit 5-user ceiling) | **Moot**: React/FastAPI replaced it | `ps` |
| LLM Council Gemini roadmap "Rotate Passwords: done" | **Unverified / contradicted**: the line is still in `.env` and in the public repo | §3 S2 |

## 8. Decisions and information needed from the user

1. **Rotate the leaked `10.2.1.9` credential now?** Is that account still live? (Only the DBA or owner can confirm.)
2. **Make the GitHub repo private, and approve a history rewrite** to purge the two Gemini files? (Needs force-push; CLAUDE.md forbids agents committing.)
3. **Internal-only pilot or client launch?** For the internal pilot today, the minimum is SEC-01 + OPS-01 + OPS-02. A client launch also needs PRF-01..05.
4. **Identity provider:** the Coresight OIDC used by SIP-Prod (client id/secret, redirect URI)? Who owns it?
5. **Service DB accounts** `cip_app`/`cip_etl`: will the DBA create them on STG and prod?
6. **Azure target:** VM with docker compose (matches `deploy/`) or Container Apps? Domain name, TLS cert source, Key Vault access.
7. **Disclosure policy:** the client-facing minimum base (5 today vs 30 in Excel/Streamlit); allow custom audiences for clients?
8. **Tenancy rules:** which ad hoc studies belong to which client, and should analysts see all of them?
9. **Retention/DPA:** how long respondent rows and open-ends are kept; is Anthropic approved as a sub-processor for Ask CIP?
10. **Backup copy destination** (`CIP_BACKUP_COPY_DIR`: OneDrive/Azure Blob) and Azure MySQL PITR retention.
