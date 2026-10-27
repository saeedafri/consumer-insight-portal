# CIP bounded-operation runbook and monitoring

Date: 2026-10-27

No alert or notification integration was invoked or configured by this work. The items below are operational requirements only.

## Before a diagnostic or job

1. Confirm exact staging host and `DATABASE()='cip_stg'`.
2. Confirm intended role and minimum permissions.
3. Record autocommit, transaction mode, SELECT/MDL/row-lock deadlines.
4. Check `IS_USED_LOCK('cip_etl')`; do not acquire or release it during inspection.
5. Record `Threads_running`, `Threads_connected`, cumulative slow/temp counters and uptime.
6. Use one worker first. Do not overlap a scheduler/manual writer.
7. State exact stop budget and own-session cancellation procedure.

## Operational thresholds

| Signal | Initial threshold/action |
|---|---|
| Query exceeds its operation budget | Stop the job; record fingerprint/phase; cancel only the CIP-owned session after verification. |
| Metadata lock wait | Application/inspection deadline 3–5 s; ETL 10 s; fail, do not wait indefinitely. |
| Row lock wait | Application 10 s; ETL 30 s; roll back whole transaction. |
| Pool checkout | 10 s; fail with controlled error instead of opening unbounded connections. |
| Threads running | Diagnostic stop threshold 8 until a DBA supplies a capacity-specific value. |
| CIP named lock held | Do not start a second writer. Report current job state. |
| Retry | Only 1205/1213, whole idempotent transaction, at most three attempts with bounded backoff/jitter. |
| Publication validation failure | Delete staged build; retain current version. |

## Failure behavior

| Failure | Persisted-data effect | Recovery/fallback | Signal |
|---|---|---|---|
| DB busy or pool exhausted | No new transaction | Fail request/job after checkout deadline; keep published data | Pool timeout counter/log |
| MDL wait | No statement execution | Fail after lock deadline; retry only via operator/job policy | MySQL error and fingerprint |
| Deadlock/row timeout | Transaction rolled back | Retry only bounded idempotent serving build; otherwise fail | Error code 1213/1205, retry count |
| Socket disconnect | Transaction outcome must be verified | Dispose connection; do not blindly replay non-idempotent work | Disconnect/error log |
| Process crash during ETL | Current transaction rolls back; named lock releases with session | Rerun idempotent wave under lock | Run ID lacks completion marker |
| Partial publication | Staged directory only | Remove staged build; serve last known good | Publication gate failure |
| Missing/stale artifact | Database fallback only within its query budget | Serve last known good or controlled unavailable response | Artifact completeness metric |

## Required metrics

- SQL fingerprint and call site, never parameter values.
- Wave ID, job/run ID, worker count and phase.
- Query duration, rows returned/affected, retry/error code.
- Pool checked-out/overflow/wait duration.
- Named-lock acquisition outcome.
- Publication completeness and hashes.
- MySQL threads, connections, slow-query and temporary-table counter deltas when safely attributable.

Without Azure metrics, CPU-credit and storage-I/O attribution remains unavailable. MySQL counters and application telemetry reduce blind spots but do not replace infrastructure monitoring.
