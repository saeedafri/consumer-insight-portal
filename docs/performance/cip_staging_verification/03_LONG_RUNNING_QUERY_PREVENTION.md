# CIP long-running query prevention — local implementation

Date: 2026-10-27  
State: implemented locally; not deployed

## Implemented controls

### MySQL connection and statement budgets

`app/core/database.py` now establishes finite per-role settings:

| Role | Connect | Socket read/write | SELECT deadline | MDL wait | InnoDB row-lock wait | Pool behavior |
|---|---:|---:|---:|---:|---:|---|
| `app` | 10 s | 185 s | 180 s | 5 s | 10 s | Existing read pool; checkout capped at 10 s; AUTOCOMMIT reads. |
| `api_write` | 10 s | 185 s | 180 s | 5 s | 10 s | New transactional pool, 2 persistent + 2 overflow maximum, checkout 10 s. |
| `etl` | 10 s | 605 s | 600 s for eligible SELECTs | 10 s | 30 s | Transactional writer; local infile only here; existing ETL buffers retained. |

MySQL `max_execution_time` does not terminate DML. Write safety still depends on transactions, lock deadlines, bounded input, socket watchdogs and operator cancellation. Socket timeout alone is not claimed to stop server execution.

### Transaction correctness

Production API writes no longer use the latency-optimized AUTOCOMMIT read engine. Ten write sites in `api/team.py`, `api/signin.py` and `app/core/audit.py` now use `get_engine("api_write").begin()`. This restores actual transactional commit/rollback semantics while keeping read paths one-round-trip optimized.

### Connection limits

- `DB_POOL_SIZE` must be 1–10.
- `DB_MAX_OVERFLOW` must be 0–20.
- `DB_POOL_TIMEOUT` must be 1–30 seconds and defaults to 10.
- Invalid or oversized values fail startup instead of silently falling back.
- The API-write pool is independently capped at four total connections per process.

The application read and ETL pools can still total 30 connections each per process under maximum configuration. Deployment process counts must therefore be included in the capacity review before release. A dedicated SELECT-only `APP_DB_USER` remains required.

### Retry and recovery

`etl.serving.build_wave` still attempts at most three whole-wave transactions. It now retries only MySQL 1205 lock timeout and 1213 deadlock, with bounded exponential backoff plus 0–250 ms jitter. Nontransient errors fail immediately. Each failed `_build_wave` attempt exits its `engine.begin()` context and rolls back before retry.

### Existing controls retained

- Publisher and serving concurrency remain validated at 1–4 workers.
- Named writer lock acquisition remains nonblocking (`GET_LOCK(...,0)`).
- Forsta/Qualtrics replacements remain transaction-scoped and idempotency-tested locally.
- Publication builds remain staged and are deleted on failure before promotion.
- Notification/network tests remain fail-closed.

## Tests

New `tests/test_database_reliability.py` cases verify:

- Exact connection, SELECT, metadata-lock and row-lock deadlines for all roles.
- API writes use a small transactional pool rather than AUTOCOMMIT.
- Unsafe pool values fail closed.
- Lock timeout and deadlock are retried with bounded backoff.
- Nontransient MySQL errors are not retried.

Results:

- Reliability tests: `9 passed`.
- Focused ETL/API regression: `178 passed`.
- Complete isolated suite: `360 passed, 0 failed, 0 errors, 0 skipped` in 18.71 seconds.
- `python -m compileall` and `git diff --check` are release checks still recorded in the final changed-files report.

## Remaining reliability gates

- Nonexecuting plans from Stage 2.
- Disposable MySQL 8 transaction/deadlock/timeout/load tests.
- Owner-selected one-wave, one-worker staging benchmark only after plan review.
- Dedicated read-only database account for `app`.
- Aggregate connection budget across all API workers, ETL processes and schedulers.
- Deployment/canary/rollback approval.
