# 90 · Go-live order (needs your yes)

All fixes are in the working tree. They are tested but not live:
- `pytest` passes 318 of 318.
- `tsc` is clean, `stats.check` passes, and a scratch `vite build` succeeds.
- The live API on :8000, cloudflared and `web/dist` (22 Oct 21:00) are untouched. Nothing was committed.

Each step's full commands and rollback are in [80 §3](80-fixes-etl.md) (data) and [81](81-fixes-backend.md#apply-at-restart-needs-user-approval) (API).

| # | Step | Time | Live effect | Rollback |
|---|---|---|---|---|
| 1 | `scripts/init_db.py`: sql/008 (access log, sessions) plus 009 (the `sig_*` flags, `in_field`, `too_small`) and the fixed views | 2 min | none until the restart | 80 §3.1 |
| 2 | Annual-family remap (5 UPDATEs) | seconds | Holiday, Grocery, Apparel and Back to School compare year on year | the saved CSV |
| 3 | Auto-confirm same-wording mappings (1,322 units) | 10–20 min | more questions trend | 80 §3.3 |
| 4 | Reload surveys 97 and 201 (malformed legacy labels) | ~10 min | correct Facebook/YouTube and grocery figures | 80 §3.4 |
| 5 | `etl.serving --all --jobs 4` | 25–45 min | correct cells, mapped prior and last year, `sig_*` flags, no blank segments, test waves removed | old `serving.py` + rerun |
| 6 | `etl.integrity --check` plus the 4 check SELECTs | 5 min | read-only | — |
| 7 | `api.dashboards --build` for each code, then `etl.publish` | ~20 min | published screens carry steps 2–5 | `etl.publish --rollback` |
| 8 | Append `CIP_DEMO_LOGIN=1` to `~/.config/cip/api.env`; `pip install -r requirements.txt` (pillow 13) | 1 min | none until the restart | remove the line |
| 9 | **Restart :8000**: kill only the LISTEN pid, never cloudflared, and start with `.venv/bin/python` | ~10 s down | new API: sign-in, access, audit log, headers, limits, faster team endpoints | restart from `git stash` |
| 10 | `npm --prefix web run build`, **after step 9** (the new UI needs `/auth/login`, `/me` and `/methodology`) | 5 s | new UI: one significance rule, provenance, Methodology page, light and dark redesign | rebuild from `git stash` |
| 11 | Check that public `/healthz` returns 200 and walk 5 screens | 2 min | — | — |
| 12 | Optional, irreversible: salt rekey (80 §3.10) and nulling the legacy IPs (80 §3.11) | 1 min each | privacy | keep a dump first (rekey only) |

**If nothing is applied:** the next scheduled ETL run, **Mon 26 Oct 17:30 IST**, runs the new ETL code anyway, because launchd runs the repo. It is safe without 009. It heals up to 20 waves per run and stops annual studies loading while fielding.

**Still needed from you:**
- the team email list for alerts (`config/notify.yml`);
- client domains, tiers and study ownership in `config/access.yml` before external clients;
- set `unknown: refuse` in `config/access.yml` at the same time;
- OIDC issuer, client id and secret when IT has them.
