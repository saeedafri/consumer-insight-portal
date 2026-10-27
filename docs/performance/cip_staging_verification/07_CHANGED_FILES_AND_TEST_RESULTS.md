# CIP Stage 1 changed files and test results

Date: 2026-10-27  
Base HEAD: `6f978b0595b2c71c064991ae10b832514637a0da`  
State: uncommitted local worktree; no push/PR/deployment

## Stage 1 reliability changes

| File | Change |
|---|---|
| `.env.example` | Documents bounded pool checkout setting. |
| `app/core/config.py` | Validates pool size, overflow and checkout ranges; invalid configuration fails closed. |
| `app/core/database.py` | Adds finite per-role connection/socket/SELECT/MDL/row-lock budgets; adds bounded transactional `api_write` role. |
| `app/core/audit.py` | Audit inserts use transactional API-write engine. |
| `api/team.py` | Team mutations use transactional API-write engine. |
| `api/signin.py` | Session writes/revocations use transactional API-write engine. |
| `etl/serving.py` | Retries only MySQL 1205/1213, maximum three attempts, exponential backoff plus jitter. |
| `tests/conftest.py` | Maps `api_write` to the isolated SQLite fixture. |
| `tests/test_database_reliability.py` | Nine deadline/pool/retry tests. |
| `tests/test_pipeline_hardening.py` | Isolates integrity healing from its separately tested real-date launch-calendar check. |

Existing remediation and notification edits were preserved. No unrelated file was reset.

## Commands and outcomes

```text
.venv/bin/pytest -q tests/test_database_reliability.py
9 passed in 0.72s

.venv/bin/pytest -q [focused API/ETL/publish/serving/isolation files]
178 passed in 10.77s

.venv/bin/pytest -q
360 passed in 18.71s

# Stage 2 post-evidence regression rerun
.venv/bin/pytest -q
360 passed in 18.99s

# Stage 3 final regression rerun
.venv/bin/pytest -q
361 passed in 18.73s

python3 -m compileall -q app api etl tests
passed

git diff --check
passed
```

No test used the staging database. Test networking, SMTP and webhook routes remained fail-closed.

## Staging execution

- One connection, 21 approved statements, no retries.
- 21 succeeded; zero SQL errors/timeouts.
- SQL-019 and all heavy queries excluded.
- Connection closed.
- Raw sensitive identity fields were not persisted; evidence is sanitized and hashed.
