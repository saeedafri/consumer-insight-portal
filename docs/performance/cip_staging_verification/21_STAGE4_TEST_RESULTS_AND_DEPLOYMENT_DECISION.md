# CIP Stage 4 tests and deployment decision

Date: 2026-10-27  
Decision: **PASS FOR REVIEW; NO-GO FOR DEPLOYMENT**

## Commands and results

```text
.venv/bin/pytest -q
364 passed in 19.22s

.venv/bin/python scripts/cip_stage4_mysql_benchmark.py \
  --samples 3 --predicate-samples 30 \
  --output docs/performance/cip_staging_verification/evidence/STAGE4_MYSQL_HARDENING_RESULTS.json
PASS: 1,260,000 synthetic rows; all hashes, memory limits and cleanup assertions passed

.venv/bin/python scripts/cip_stage4_readonly.py
PASS: SQL-042 and SQL-045 only; all staging guards passed
```

The pytest process used SQLite and blank integration credentials with socket
creation blocked by `tests/test_test_isolation.py`. The MySQL harness connected
only to `127.0.0.1:33306`. No notification module or external integration was
invoked.

## Final local code edits

| File/function | Change | Proof | Rollback |
|---|---|---|---|
| `app/data/payloads.py::people` | Always close the streamed result in `finally` | Injected exception: result closed, connection reusable, pool zero | Revert the `try/finally` only |
| `app/data/repository.py::_concept_cells` | Sargable legacy-compatible `IS NULL OR = 0`; positive IDs use equality | Old/compat hashes equal; local `ref_or_null` uses all `ix_agg_map` parts | Restore Stage 3 `IS NULL` form |
| `app/data/cube.py::build_cube` | Reject nonpositive named-cohort IDs | New regression test passes | Remove the validation guard |
| `app/core/database.py::get_engine` | App/ETL pools capped 4+0; writer remains 2+2 | Unit tests plus real 4-connected/4-timeout MySQL test | Remove `POOL_CAPACITY` and restore configured pool values |
| Stage 4 scripts/tests | Fixed staging allowlist, MySQL scale/failure harness and regressions | Evidence JSON and 364-test suite | Delete Stage 4-only additions |

No Python grouping of `srv_answer` was introduced. MySQL retains grouping and
collation semantics.

## Evidence classification

### Fixed and tested locally

- Legacy zero/NULL compatibility and positive-cohort isolation.
- Prevention of newly written zero cohort IDs through the cube writer.
- Stream result closure on success and exceptions.
- Exact extraction payload parity through 900,000 rows.
- Bounded app, writer and ETL connection pools.

### Verified by staging plan

- SQL-042 is a low-cost question-index lookup: seven estimated cube rows.
- Pure `IS NULL` uses all four parts of `ix_agg_map` and reduces SQL-043's
  estimated cell work from 35 to 3 per mapping.

### Still needs controlled staging/canary evidence

- Plan and runtime behavior of the final `IS NULL OR = 0` predicate on Azure.
- Actual frequency of legacy zero rows.
- Runtime, memory and shared-I/O behavior of the patched publisher against a
  representative staging wave.
- End-to-end output hashes from an approved one-worker staging code canary.

### Requires DBA/infrastructure approval

- Any new index or schema CHECK/FK.
- Shared connection budget and deployment environment pool settings.
- Actual query benchmarks, ETL execution, deployment and rollback rehearsal.

## Decision rationale

Correctness and local resource behavior now have adequate evidence for review.
Deployment is not ready because the final compatibility predicate has not been
planned or timed on Azure, historical zero prevalence is unknown, and no
patched staging canary has compared survey-output hashes.

The live API/tunnel was not restarted, rebuilt or reconfigured. The disposable
MySQL container used synthetic tmpfs data only.

No real emails or outbound notifications were sent. No staging/production
database writes, schema changes, ETL jobs, deployments or cloud modifications
were performed.
