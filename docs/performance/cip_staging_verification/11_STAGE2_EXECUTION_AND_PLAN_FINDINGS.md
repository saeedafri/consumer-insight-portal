# CIP staging Stage 2 execution and plan findings

Date: 2026-10-27  
Target: authorized Azure MySQL staging database `cip_stg`  
Result: **all 16 approved statements succeeded; connection closed**

Machine-readable evidence: [STAGE2_SANITIZED_RESULTS.json](evidence/STAGE2_SANITIZED_RESULTS.json)  
SHA-256: `b3c4fe84b3d439352cd962430ca4ebab3d3722933f321788c7b84dd196eb2384`

## Safety and execution ledger

- One direct TLS PyMySQL connection; no pool and no retry.
- Client budgets: connect 5 seconds, read/write 10 seconds.
- Autocommit was `1`.
- Server/database/account/port matched the pseudonymized Stage 1 identity, MySQL reported `8.0.46-azure`, and the database was exactly `cip_stg`.
- The guarded session was verified as `autocommit=1`, `transaction_read_only=1`, `max_execution_time=5000`, `lock_wait_timeout=3`, `innodb_lock_wait_timeout=3`.
- `IS_USED_LOCK('cip_etl')` was `NULL` before the plans and before every individual plan.
- `Threads_running` was 1 initially and 1-2 before the plans, below the stop threshold of 8. Connections observed were 34-36.
- SQL-019 was the only data SELECT. It returned ten bounded `srv_wave` catalogue rows.
- SQL-023 through SQL-029 were `EXPLAIN FORMAT=JSON`; none of their underlying SELECTs ran.
- No statement timed out or errored. No row was inserted, updated, deleted or locked for update.
- The connection was closed after SQL-029.

| Statement | Elapsed ms | Returned rows | Outcome |
|---|---:|---:|---|
| SQL-030 | 254.085 | 1 | Identity and initial session state matched. |
| SQL-031 | 248.839 | 0 | Session transactions made read-only. |
| SQL-032 | 250.728 | 0 | Five-second SELECT budget installed. |
| SQL-033 | 251.457 | 0 | Three-second metadata-lock budget installed. |
| SQL-034 | 231.643 | 0 | Three-second row-lock budget installed. |
| SQL-035 | 229.371 | 1 | All five guards verified. |
| SQL-036 | 228.872 | 1 | CIP ETL lock was free. |
| SQL-037 | 230.167 | 9 | Initial pressure snapshot accepted. |
| SQL-019 | 251.756 | 10 | Tiny wave catalogue read completed. |
| SQL-023 | 295.835 | 1 | Grouped-cut plan captured. |
| SQL-024 | 231.430 | 1 | Respondent-extraction plan captured. |
| SQL-025 | 435.773 | 1 | Serving-join plan captured. |
| SQL-026 | 331.458 | 1 | Label-cleanup predicate plan captured. |
| SQL-027 | 336.889 | 1 | Respondent-map plan captured. |
| SQL-028 | 250.716 | 1 | Answer replacement predicate plan captured. |
| SQL-029 | 305.294 | 1 | Grouped-cut label plan captured. |

The elapsed values above measure parsing/optimization plus network latency for `EXPLAIN`; they are not the runtime of the underlying statements.

## Catalogue result

SQL-019 confirmed the `srv_wave` scan is harmless at current scale. It returned ten rows after scanning the approximately 368-row catalogue. Five old tracker rows reported `rows_built=0`; the remaining candidates ranged from 1 to 115 serving rows. `rows_built` is not an `srv_answer` row count and cannot alone select a representative grouped-query benchmark.

No `rows_built` index is justified. The catalogue remains about 48 KiB.

## Seven-plan matrix

Optimizer row and cost values are estimates, not measured execution counters.

| SQL | Current purpose | Selected indexes | Estimated work | Finding |
|---|---|---|---:|---|
| SQL-023 | Ten-dimension `srv_answer` grouping for cut publication/live fallback | `srv_answer.PRIMARY`, using only `survey_id` | 639,576 rows; cost 65,033.58; about 1 GiB estimated data read | Genuinely expensive shape. Survey lookup is indexed, but grouping requires an internal temporary table. |
| SQL-024 | Publisher audience/respondent extraction | `srv_answer.PRIMARY`, using only `survey_id` | 639,576 rows; cost 65,033.45; about 1 GiB estimated data read | Access path is correct; the cost is required row volume, repeated demographic columns, transfer and Python memory. |
| SQL-025 | `serving.cube_rows` metadata join for one wave | `q.uq_question`; `c.ix_agg_question`; item/option PKs; `m.uq_concept_map` | cost 293.22; `c` estimate 222 rows per selected question, 3.03% surviving | Current one-wave join is well indexed and not proven to be the historic expensive family. |
| SQL-026 | Derived-label cleanup predicate | `a.ix_answer_cover`; field/item PKs; `o.uq_option` | 1,354,298 answer rows; cost 2,038,728.49; repeated joins for the whole wave | Highest-cost plan. Survey lookup is indexed, but every answer must be checked against metadata. |
| SQL-027 | Respondent record-number map | covering `cip_respondent.uq_respondent` | 2,261 rows; cost 231.49 | Efficient. |
| SQL-028 | Read equivalent of full-wave answer deletion | covering `cip_answer.ix_answer_cover` | 1,354,298 rows; cost 140,216.30 | Index selection is correct, but replacing a large wave is inherently broad. This plan did not execute the DELETE. |
| SQL-029 | Total-row labels for grouped cuts | `srv_result.PRIMARY` on `survey_id`; question PK | 35,880 rows scanned, 3,588 retained; cost 7,595.59 | Moderate avoidable filtering because `dim` follows `qcode` in the PK, but not enough evidence for another index. |

## Detailed conclusions

### 1. `srv_answer` grouping

MySQL chose the existing primary key and used the `survey_id` prefix. A new `(survey_id,qcode)` index would duplicate the primary-key prefix and would not order the six demographic dimensions required by the grouped query.

The plan explicitly reports:

```text
using_temporary_table = true
using_filesort = false
```

This confirms an internal temporary table. It does **not** show whether that temporary table stays in memory or spills to disk. `Created_tmp_disk_tables` did not increase during the Stage 2 observation window, but the grouped SELECT was not executed, so this is not spill evidence either way. The earlier G02 statement that `using_temporary_table=true` proved an on-disk table is therefore rejected.

MySQL must retain collation-aware aggregation because the grouping strings use `utf8mb4_0900_ai_ci`. Python tuple/dictionary grouping remains prohibited.

### 2. Respondent extraction

SQL-024 uses the best available survey-leading path. An additional lookup index cannot eliminate the estimated 639,576 result rows because the caller asks for every answer row. Current `payloads.people()` calls `.all()`, retains all rows, builds a second respondent-seat set and bitsets, while the six demographic strings are transferred repeatedly for each answer.

The issue is projection/representation and peak memory, not a missing filter index.

### 3. `cip_agg_cell` serving joins

For the exact current `serving.cube_rows` query, MySQL starts from wave questions using `uq_question(survey_id,qcode)`, then probes cells using `ix_agg_question(survey_id,question_id,dim)`. Item, option and concept-map lookups are one-row `eq_ref` probes. The concept map's unique `(survey_id,map_key)` key prevents fanout.

This plan has no temporary table, filesort or join buffer. It does not explain the historic 207 statements/167 million rows examined. Possible reasons still requiring fingerprint-specific evidence are:

- the historic SQL was a different `cip_agg_cell` query, such as cross-wave concept trends or an older join order;
- it included many waves rather than one wave;
- it ran under older source/schema/statistics;
- repeated rebuilds, not one bad plan, accumulated the cost.

The live index cardinalities remain implausible, but the optimizer nevertheless selected the intended indexes here. No `cip_agg_cell` index is justified by SQL-025.

### 4. Answer-label cleanup and replacement

SQL-026 is the clearest remaining database hotspot. `ix_answer_cover` narrows to the wave, but MySQL estimates 1.35 million answer rows and performs three metadata probes for each. Adding `value_label` to an index would not make the row-dependent `COALESCE(o.value_label,i.item_label)` comparison directly searchable.

Forsta already avoids this cleanup. Qualtrics and legacy paths still invoke it. Removing it from those paths is not approved without consumer-contract and storage tests; retaining raw labels is safer than clearing required labels, but consumes more storage.

SQL-028 confirms the full-wave answer predicate uses the covering survey index. A full replacement still has to delete the wave's rows and maintain foreign keys/indexes. No read index can make that write free.

### 5. Existing-index decision

No additional index is justified now:

- reject `srv_answer(survey_id,qcode)` as redundant;
- reject a wide demographic grouping index until an isolated MySQL benchmark proves benefit greater than its write/storage cost;
- reject a new `cip_agg_cell` index because the intended index is already selected;
- defer `srv_result(survey_id,dim,...)`: it could avoid roughly 90% of SQL-029's estimated scan, but the absolute one-wave estimate and call frequency do not yet justify another large serving-table index;
- do not run `ANALYZE TABLE` without separate approval because it changes shared optimizer statistics.

## Application work that can reduce database work

1. Preserve incremental publication: unchanged waves are hard-linked and perform no grouped/extraction query. Validate the deployed scheduler actually reuses this path.
2. Count and log the live-crosstab fallback without parameters or user data. A complete published cut file should serve requests without querying `srv_answer`; fallback frequency will identify whether the historic grouped statements are publisher or API work.
3. Keep `CIP_PUBLISH_JOBS` bounded at 1-4 and select the deployed value only after MySQL tests at 1/2/4. Four parallel 639k-row groupings are not assumed safe.
4. Prototype a bounded-memory `people()` representation on disposable MySQL. It may separate one-row-per-respondent cut data from answer rows or stream deterministic batches, but canonical bitsets/JSON and respondent privacy must match exactly.
5. Do not replace SQL grouping with Python grouping. Any grouped-query optimization must retain MySQL collation and NULL semantics.
6. Measure the remaining Qualtrics/legacy label cleanup. Prefer avoiding redundant label writes during ingestion if exact MySQL-collation and consumer parity can be proven; otherwise keep the current behavior.
7. Identify the exact historic `cip_agg_cell` fingerprint before changing its SQL or indexes. SQL-025 shows the current one-wave serving join is not the demonstrated problem.

## Limits

- Stage 2 produced optimizer estimates, not actual execution timing, rows examined, buffer reads or memory consumption.
- No grouped query, respondent extraction, serving join, cleanup, delete or view count was executed.
- No production/staging speedup is claimed.
- Historical caller attribution remains unproven without original normalized SQL fingerprints and deployed revision/scheduler evidence.

