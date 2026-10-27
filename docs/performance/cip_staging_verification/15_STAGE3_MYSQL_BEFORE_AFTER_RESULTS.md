# CIP Stage 3 disposable MySQL 8 results

Date: 2026-10-27  
Environment: MySQL `8.4.13`, local container, `utf8mb4_0900_ai_ci`, 2 CPU, 3 GiB container memory, 512 MiB InnoDB buffer pool, 40 connections, local infile disabled  
Data: deterministic synthetic only

Evidence:

- [STAGE3_MYSQL_BEFORE.json](evidence/STAGE3_MYSQL_BEFORE.json)
- [STAGE3_MYSQL_AFTER.json](evidence/STAGE3_MYSQL_AFTER.json)
- [STAGE3_MYSQL_INDEX_EXPERIMENT.json](evidence/STAGE3_MYSQL_INDEX_EXPERIMENT.json)

Final after-evidence SHA-256: `198fd480750d741dc344c24419cce9b634d5c0a20b5cd1b91527a6383785680c`

## Dataset and method

- Four waves.
- 160,000 `srv_answer` rows.
- 40,000 `cip_answer` rows.
- 59,400 `cip_agg_cell` rows.
- MySQL collation variants include case, accents and trailing spaces.
- Ten measured samples per SQL/code comparison after warmup.
- Exact output hashes, row counts and published artifact hashes compared.
- Full publisher tested at 1, 2 and 4 workers.
- Real InnoDB lock timeout, transaction rollback, pool exhaustion and injected publisher failure tested.

## Implemented: bounded-memory `people()`

| Metric | Before | After | Change |
|---|---:|---:|---:|
| Median | 0.457622 s | 0.427412 s | 6.6% faster |
| p95 | 0.464668 s | 0.433969 s | 6.6% faster |
| Median traced Python peak | 23,415,707 bytes | 5,614,635 bytes | 76.0% lower |
| Output hash | `54ee00e…` | `54ee00e…` | exact parity |
| `srv_answer` reads per publisher wave | 2 total | 2 total | unchanged |

The implementation streams the existing row query, keeps respondent membership sets rather than every returned row object, then builds the same stable respondent-ID bit positions. MySQL remains responsible for grouping cuts; this is not the rejected Python grouping optimization.

## Implemented: sargable concept cohort predicate

| Metric | Before `COALESCE` | After `IS NULL` | Change |
|---|---:|---:|---:|
| Median | 0.009065 s | 0.001060 s | 88.3% faster |
| p95 | 0.009182 s | 0.001095 s | 88.1% faster |
| Returned rows | 90 | 90 | exact |
| Output hash | equal | equal | exact parity |

Reverse-order validation with 20 samples gave 0.009005 s versus 0.001037 s median, excluding simple cache-order bias. The application emits `IS NULL` when no cohort is requested and equality when a real cohort is requested. New regression coverage verifies both trend and pooled cohort results.

## Rejected: split answer-label cleanup

| Metric | Existing single update | Split option/item updates |
|---|---:|---:|
| Median | 0.048424 s | 0.066899 s |
| p95 | 0.049072 s | 0.067780 s |
| Updated rows | 28,022 | 28,022 |
| Final hash | equal | equal |

The candidate is about 38% slower and is not implemented. Existing MySQL collation semantics, including accent/case/trailing-space equivalence, remain intact. Forsta still avoids this cleanup; Qualtrics/legacy retain it until a better ingestion strategy is proven.

## `wave_report` and local-only index experiment

A SQL rewrite alone provided no material gain: 0.001878 s versus 0.001874 s median. It is not implemented.

The following index was then created only in the disposable database and removed immediately:

```sql
CREATE INDEX ix_agg_wave_dim_cohort
    ON cip_agg_cell (survey_id, dim, cohort_id, question_id);
```

| Metric | Existing indexes | Local candidate index |
|---|---:|---:|
| Median, 20 samples | 0.001835 s | 0.000676 s |
| p95 | 0.001968 s | 0.000725 s |
| Estimated cells | 471 per question | 90 total |
| Optimizer cost | 1,594.09 | 69.30 |
| Output hash | equal | equal |

This is a 63.2% local median reduction, but it is only a DBA proposal. No staging index or schema change occurred. Live storage/build/write cost must be estimated before approval.

## Publisher concurrency

Four waves produced identical 700,020-byte artifacts with SHA-256 `da4f8118…` at every worker count.

| Workers | Full publisher wall time | Group/extract SQL wall time |
|---:|---:|---:|
| 1 | 0.834726 s | 0.949318 s |
| 2 | 0.733661 s | 0.884961 s |
| 4 | 0.684254 s | 0.854788 s |

Four workers won on this isolated 2-CPU container and small synthetic workload. This does not authorize four workers on shared staging; no default was changed.

## Reliability tests

- Pool size 2 plus overflow 2: exactly four connections succeeded and four timed out; no unbounded growth.
- InnoDB lock test: error 1205 after 1.028 seconds; waiter rolled back and both connections closed.
- Injected statement failure: transaction restored the prior value exactly.
- Injected publisher worker failure: exception propagated and zero partial `.build-*` directories remained.
- Publisher artifacts matched across concurrency levels.
- Full isolated suite after changes: `361 passed in 18.73s`.
- Compile and `git diff --check`: passed.

## Interpretation limits

- Synthetic local results are not staging runtime guarantees.
- No actual expensive staging workload was run.
- Container memory after testing was about 1.17 GiB; no production-capacity claim is made.
- The existing `.env` has four unrelated parse warnings; contents were not printed.

