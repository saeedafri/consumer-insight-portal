# CIP final consolidated remediation result

Date: 2026-10-27  
Repository: `consumer-insight-portal`  
Branch/base: `master` / `6f978b0595b2c71c064991ae10b832514637a0da`  
Decision: **GO FOR A CONTROLLED STAGING DEPLOYMENT**

This report identifies the tested tree. Its immutable Git revision and rollback
revision are recorded by the staging-release artifact. “GO” is not production
approval.

## Final survey-238 canary

Evidence:
[FINAL_SURVEY_238_CANARY_RESULTS.json](cip_staging_verification/evidence/FINAL_SURVEY_238_CANARY_RESULTS.json)  
SHA-256: `5ae5a6836c84f60593245ec9cc1c9f2f5156a00e6f5d1611f1466e051cf2defe`

The base-HEAD and working-tree payload modules ran sequentially in one isolated
process through one TLS staging connection. The connection used autocommit,
read-only transactions, a five-second SELECT budget, three-second lock budgets,
ten-second socket budgets, one worker and no retries. The ETL lock was checked
before every application SELECT; `Threads_running` never exceeded 1. New network
sockets were blocked after the database connection opened.

| Check | Result |
|---|---:|
| Database state before/after | 852 answer rows; 35 respondents; 81 result rows; unchanged hash |
| Question-cut payloads | 12/12 exact; 82 count rows; 81 answer rows |
| Respondent bitsets | 82/82 exact; 35 represented respondents |
| Book payload | 16 questions; 26 groups; 92 rows; exact |
| Bases/unweighted values | 52 / 92; exact |
| Weighted values in survey 238 | 0; this wave has no non-unit weighting output |
| Canonical bundle hash | exact: `700e5df9d11277baf91e8c893b840ed644190a4f10d39308515ef458f6a8ae13` |
| Publisher-contract bytes | exact |
| Application SELECTs | 22; maximum 411.597 ms; zero errors/timeouts |
| Baseline/patched wall time | 7.764 s / 7.571 s |
| Baseline/patched traced peak | 0.456 MiB / 0.418 MiB |
| Connection/output cleanup | pool checkout 0; physical connection closed; temporary output removed |

Two harness-only setup errors were found before the successful run (a
non-callable engine adapter, then a temporary-module configuration path). Each
attempt stopped before comparison, closed its database connection and removed
its temporary output. Both harness defects were corrected. No staging timeout
was deliberately induced; timeout and bounded-retry behavior is covered by the
isolated reliability tests below.

Survey 238 has no populated demographic cut bitsets and no non-unit weighting,
so those branches are not claimed as staging-canary measurements. Their exact
calculation behavior is covered by the full regression suite; weighted logic was
not changed by this patch. The canary compared live base-HEAD code against the
patched code on the same database state, not against a stale publication.

The live API (PID 1461) and cloudflared process (PID 66081) were unchanged before
and after the canary. `/healthz` remained HTTP 200 on build `6f978b0`.

## Regression, failure and rollback proof

```text
.venv/bin/pytest -q
364 passed in 18.59s

.venv/bin/pytest -q \
  tests/test_publish.py::test_publish_writes_the_api_bytes_swaps_atomically_and_rolls_back \
  tests/test_publish.py::test_a_failed_gate_keeps_the_live_version \
  tests/test_publish.py::test_people_closes_the_stream_when_row_iteration_fails \
  tests/test_database_reliability.py
12 passed in 2.28s

.venv/bin/python -m compileall -q app api etl scripts tests
PASS

git diff --check
PASS
```

Tests ran with SQLite-only paths, blank live integration settings, blocked
TCP/UDP sockets and fake SMTP/Teams/webhook transports. No tests were skipped or
weakened. Rollback was exercised only against a temporary publication root.

The existing disposable-MySQL evidence remains valid:
[FINAL_MYSQL_HARDENING_RESULTS.json](cip_staging_verification/evidence/FINAL_MYSQL_HARDENING_RESULTS.json),
SHA-256 `2387e53175c2a2189b290f5ecfff3d7dbe7672f3d37153a9918d8ceaa9bd0ace`.
At 900,000 synthetic rows, streaming preserved exact output while reducing
process RSS from 1,241.8 MiB to 263.4 MiB and median wall time from 11.366 s to
10.207 s. Injected stream failure closed the result and returned pool checkout
to zero. This is local MySQL evidence, not a claim of staging speedup.

## Fixes retained

- MySQL still performs cut grouping, preserving deployed collation semantics;
  the incorrect Python grouping optimization remains absent.
- Respondent extraction streams rows, uses compact membership sets and closes
  the cursor on success or exception.
- Concept reads preserve legacy `cohort_id IS NULL OR cohort_id = 0` behavior
  with all four `ix_agg_map` key parts; positive cohorts use equality.
- Cube writes reject zero/negative named cohort IDs.
- Application, API-write and ETL pools and query/lock/socket budgets are finite.
- Publisher concurrency is validated and bounded to one through four workers.
- Forsta/Qualtrics replacement, cleanup, rollback and idempotency fixes remain
  covered by the regression suite.
- No redundant `(survey_id, qcode)` index, schema change, global MySQL change or
  Python-side cut grouping was introduced.

Historic `cip_agg_cell` fanout, broad discovery/view counts, imports and live
ad-hoc groupings remain workload risks; no unmeasured speedup is claimed for
them. The final plans support the code predicates, but no index is justified by
the approved evidence.

## Controlled staging deployment commands — not executed

Run only after the working tree is reviewed and recorded as an immutable
`APPROVED_REVISION`. This deploys the API first and does not publish data.

```bash
cd /srv/cip/consumer-insight-portal
git switch --detach "$APPROVED_REVISION"
export RELEASE_ID="cip-remediation-20261027-$(git rev-parse --short=12 HEAD)"
export CIP_ENV_FILE=/etc/cip/api.env

docker image inspect cip-portal:latest >/dev/null
docker tag cip-portal:latest "cip-portal:rollback-${RELEASE_ID}"
docker build -f deploy/Dockerfile --target api \
  --build-arg "CIP_BUILD=$(git rev-parse --short=12 HEAD)" \
  -t "cip-portal:${RELEASE_ID}" .
docker tag "cip-portal:${RELEASE_ID}" cip-portal:latest

docker compose -f deploy/compose.yml up -d --no-deps --force-recreate api
docker compose -f deploy/compose.yml exec -T api python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).read().decode())"
docker inspect --format '{{.State.Health.Status}}' \
  "$(docker compose -f deploy/compose.yml ps -q api)"
```

Activate the ETL image only in a maintenance window, outside `Mon@12:00`,
`Fri@03:30` and minute `05` UTC, with no ETL lock holder:

```bash
now="$(date -u +%a@%H:%M)"; minute="$(date -u +%M)"
if [ "$now" = "Mon@12:00" ] || [ "$now" = "Fri@03:30" ] || [ "$minute" = "05" ]; then
  echo "Refusing ETL restart in a scheduled run/watchdog minute" >&2
  exit 1
fi
docker compose -f deploy/compose.yml exec -T api python - <<'PY'
from sqlalchemy import text
from app.core.database import get_engine
with get_engine("app").connect() as conn:
    lock = conn.execute(text("SELECT IS_USED_LOCK('cip_etl')")).scalar_one()
    running = int(conn.execute(text("SHOW GLOBAL STATUS LIKE 'Threads_running'")).one()[1])
if lock is not None or running > 8:
    raise SystemExit(f"unsafe database state: etl_lock={lock is not None}, threads_running={running}")
PY
docker compose -f deploy/compose.yml up -d --no-deps --force-recreate etl
docker compose -f deploy/compose.yml ps api etl
```

Do not run `python -m etl.publish`, migrations or a normal ETL job as part of
deployment. Observe API health, pool pressure, query timeouts and ETL heartbeat
before production consideration.

## Code rollback commands — not executed

```bash
cd /srv/cip/consumer-insight-portal
export CIP_ENV_FILE=/etc/cip/api.env
docker tag "cip-portal:rollback-${RELEASE_ID}" cip-portal:latest
docker compose -f deploy/compose.yml up -d --no-deps --force-recreate api

now="$(date -u +%a@%H:%M)"; minute="$(date -u +%M)"
if [ "$now" = "Mon@12:00" ] || [ "$now" = "Fri@03:30" ] || [ "$minute" = "05" ]; then
  echo "Refusing ETL restart in a scheduled run/watchdog minute" >&2
  exit 1
fi
docker compose -f deploy/compose.yml exec -T api python - <<'PY'
from sqlalchemy import text
from app.core.database import get_engine
with get_engine("app").connect() as conn:
    lock = conn.execute(text("SELECT IS_USED_LOCK('cip_etl')")).scalar_one()
    running = int(conn.execute(text("SHOW GLOBAL STATUS LIKE 'Threads_running'")).one()[1])
if lock is not None or running > 8:
    raise SystemExit(f"unsafe database state: etl_lock={lock is not None}, threads_running={running}")
PY
docker compose -f deploy/compose.yml up -d --no-deps --force-recreate etl
docker compose -f deploy/compose.yml exec -T api python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).read().decode())"
```

No database rollback is required because this patch has no migration or shared
database write. The live publication symlink was not changed. If a later,
separately approved publish must be reverted, the tested command is
`python -m etl.publish --rollback`; do not run it merely for code rollback.

## Safety attestation

No real emails or outbound notifications were sent. No staging/production
database writes, schema changes, ETL jobs, publisher jobs, deployments, service
restarts, publication swaps, cache purges or cloud modifications were performed.
