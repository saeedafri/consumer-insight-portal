# CIP Stage 4 staging plan results

Date: 2026-10-27  
Target: Azure MySQL staging `cip_stg`  
Scope: SQL-042 and SQL-045 only, both `EXPLAIN FORMAT=JSON`

Evidence: [STAGE4_STAGING_SANITIZED_RESULTS.json](evidence/STAGE4_STAGING_SANITIZED_RESULTS.json)  
SHA-256: `d24c84af907fd19e07c5181fe8147d6dd7c6006eada2e96d629da733242f0150`

## Execution and safety ledger

An initial connection failed closed before any plan because Azure MySQL does not
support `@@session.in_transaction` (error 1193). That connection closed. The
unsupported inspection field was removed; no approved plan was retried because
none had executed.

The successful run used one TLS connection, autocommit, read-only transaction
mode, a 5-second SELECT limit, 3-second metadata/row lock limits and 10-second
read/write socket limits. There were no retries.

| Event | Elapsed | Result |
|---|---:|---|
| Identity | 500.702 ms | Same pseudonymized Stage 1-3 Azure server/account; `cip_stg` |
| Read-only setting | 410.563 ms | Applied |
| SELECT timeout | 304.789 ms | Applied |
| Metadata lock timeout | 275.642 ms | Applied |
| Row lock timeout | 269.110 ms | Applied |
| Guard verification | 291.443 ms | `1,1,5000,3,3` |
| SQL-042 | 469.954 ms | One plan row; zero affected rows |
| SQL-045 | 388.448 ms | One plan row; zero affected rows |
| Final guard | 274.206 ms | Still read-only; no client transaction open |

Before both plans, `IS_USED_LOCK('cip_etl')` was `NULL`, `Threads_running` was
1 and `Threads_connected` was 42. The connection closed after completion.
Plan-return latency is not underlying-query runtime.

## SQL-042: one-question cube read

Optimizer cost: **12.47**.

| Table | Access | Selected index | Key parts | Rows/scan | Filter |
|---|---|---|---|---:|---:|
| `cip_question q` | `const` | `PRIMARY` | `question_id` | 1 | 100% |
| `cip_agg_cell c` | `ref` | `ix_agg_question` | `survey_id, question_id, dim` | 7 | 100% |
| `cip_item i` | `eq_ref` | `PRIMARY` | `item_id` | 1 | 100% |
| `cip_option o` | `eq_ref` | `PRIMARY` | `option_id` | 1 | 100% |

`COALESCE(c.cohort_id,0)=0` remains a residual condition, but only seven cells
are estimated after the selective question index lookup. This is not a current
priority optimization and does not justify another index.

## SQL-043 versus SQL-045

Both are optimizer estimates over the same concept and current staging state.

| Measure | SQL-043 `COALESCE` | SQL-045 `IS NULL` | Change |
|---|---:|---:|---:|
| Total optimizer cost | 2,061.34 | 360.25 | 82.5% lower estimate |
| `cip_agg_cell` access | `ref` | `ref` | — |
| Selected index | `ix_agg_map` | `ix_agg_map` | unchanged |
| Used key parts | `survey_id,map_key` | `survey_id,map_key,cohort_id,dim` | all four used |
| Estimated cells per mapping | 35 | 3 | 91.4% fewer |
| Cell filter | 10% | 100% | predicate moved into index lookup |

Other join choices were unchanged: `uq_concept_option`,
`ix_map_concept_option`, and the `cip_survey` primary key. SQL-045 verifies that
the index-friendly predicate works on Azure MySQL 8.0.46. It does not establish
runtime speed or validate the final legacy-compatible `IS NULL OR = 0` form.

No underlying SELECT, DML, DDL, `EXPLAIN ANALYZE`, ETL, scheduler, deployment or
service restart was executed.
