# 30 · Backend FastAPI: verified route table and behaviour (corrected 23 Oct 2026, evening)

> **Correction notice.** The first version had a "36-endpoint table" with latencies, handler names and paths I had not read (for example `PUT /boards/{id}`, `/export/csv`, `/auth/logout` as POST) and said the assistant used `claude-3-opus-20240229`. Those were invented. This version is built from `grep` of the route decorators and from `api/assistant.py`.

## 1. Two code states exist: do not mix them

| State | What it is | Evidence |
|---|---|---|
| **Live** (:8000) | Commit `aa4bfdb`, started before today's edits | `/healthz` returns `build: aa4bfdb` and the old verbose body; `/openapi.json` falls through to the SPA; `/auth/dev-login` issues a session [O, probed] |
| **Working tree** | ~68 modified + 18 untracked files from the Claude agent (OIDC, access control, audit, rate limits, security headers, ETL fixes, UI fixes). **Not committed, not live.** | `git status`, `git diff --stat` [O] |

So every "fixed" item in the Claude docs 80–82 is **code in the tree, not behaviour on the public link**. The 318-test pass (my run, 19 s) and `tsc`/`stats.check.ts` pass apply to the working tree.

## 2. Route table (working tree, from decorators) [O]

`api/main.py`: GET `/api/v1/dashboards/{code}`, `…/{code}/{survey_id}`, `/waves`, `/waves/{id}/results`, `/waves/{id}/book`, `/waves/{id}/crosstab`, `/search`, `/schedule`, `/questions/{family}/{study_type}/{qcode}`, `/me`, `/methodology`, `/openapi.json`, `/admin/health`, `/admin/audit`; POST `/ask`, `/export/{kind}`; GET `/healthz`.
`api/team.py`: GET/POST/DELETE `/team/views`, `/alerts`, `/audiences`, `/boards` (+ `/boards/{id}`, `/items`, `/comments`, `/boards/{id}/deck`), POST `/waves/{id}/audience`, GET `/team/summary`.
`api/signin.py`: GET `/auth/login`, `/auth/callback`, `/auth/dev-login`, `/auth/logout`, `/auth/check`; POST `/api/v1/admin/sessions/revoke`.

Live (`aa4bfdb`) had these instead of the new ones, per `git show aa4bfdb:api/main.py`: also `/api/v1/trend` and `/api/v1/trends/{…}` (removed in the working tree), and no `/me`, `/methodology`, `/team/summary`.

## 3. How it serves [O, read from `api/main.py`]
- Startup: `_load()` reads published dashboard payloads into `STORE`; `_changed()` compares `srv_wave` count/max `built_at` and the `data/published/current` realpath; a 60 s loop refreshes.
- Wave list, book, question files are read from `data/published/current/api/v1/…json.gz` (`_published()`), else built from MySQL by `payloads.*`.
- `_cached()` is a per-worker LRU (`CIP_CACHE_MB`, default 256) with an `asyncio.Semaphore(CIP_BUILD_SLOTS=8)`; waiting more than 3 s returns 503 "Busy".
- Responses carry ETag, `Cache-Control: private, max-age=60`, gzip.
- Search is an in-memory index over `cip_question` (+ options/items, concept names) rebuilt when serving changes; the live `/healthz` reports `catalogue: 3719`.
- Ask CIP: `api/assistant.py`, model `CIP_ASSISTANT_MODEL`, default **`claude-opus-5-5`**, `max_tokens=2000`. Cited-claims behaviour per the Claude audit; I did not call it [U].
- Exports: `/export/{kind}` via `api/exports.py`.

## 4. Verified on the live link
- `/healthz` 200 locally and via `cheque-bought-dust-successfully.trycloudflare.com`; shows 371 serving waves, 175 dashboards, pool 10.
- `GET /auth/dev-login?email=<any>` → 303 and a `cip_session` cookie with `HttpOnly; Max-Age=43200; SameSite=lax`, **no `Secure`**. With that cookie `/api/v1/waves` returned all waves, locally and through the tunnel. **I used this once during the audit, with a throwaway address; it left a 12-hour cookie only in my shell.** This confirms the sign-in bypass.
- Response headers on `/healthz` show no CSP, X-Frame-Options, HSTS or nosniff [O].
- Latency: I only have `server-timing` values (0.26–1.25 ms server side) and one-off `curl` timings (~1–2 ms local). I did **not** benchmark the tunnel; ignore the earlier per-route latency columns.

## 5. Not verified
Rate limits, audit log, OIDC, tenancy, security headers on a running instance (they exist only in the tree; the previous Claude smoke test on :8001 reported them working), real timing under load, Ask CIP answers.
