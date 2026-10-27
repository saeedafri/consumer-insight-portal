# CIP Stage 3 before/after testing proposal

Date: 2026-10-27  
State: **PROPOSED — NOT AUTHORIZED**

Stage 2 does not authorize executing any statement below. This proposal separates further nonexecuting plans, isolated MySQL correctness/performance tests and an optional tiny staging aggregate.

## Gate A — additional nonexecuting staging plans

Use the same identity, TLS, read-only, timeout, lock and pressure checks as Stage 2. Execute one statement at a time with no retries. Stop on the existing thresholds.

### SQL-040 — select a question ID for plan literals

```sql
SELECT question_id, qcode
FROM cip_stg.cip_question
WHERE survey_id = 262
  AND is_technical = 0
  AND is_virtual = 0
ORDER BY question_id
LIMIT 1;
```

Purpose: obtain one non-sensitive question key for SQL-042. Expected scan at most the approximately 81 questions selected by `uq_question`; output one row; expected under 100 ms; five-second server timeout.

### SQL-041 — current wave-report cube read

```sql
EXPLAIN FORMAT=JSON
SELECT c.question_id, c.n, c.base_n, i.item_label, i.left_label, i.right_label,
       COALESCE(i.sort_order, 0) AS item_order, o.value_label,
       COALESCE(o.sort_order, 0) AS option_order
FROM cip_stg.cip_agg_cell AS c
JOIN cip_stg.cip_question AS q
  ON q.question_id = c.question_id
 AND q.is_virtual = 0
LEFT JOIN cip_stg.cip_item AS i ON i.item_id = c.item_id
LEFT JOIN cip_stg.cip_option AS o ON o.option_id = c.option_id
WHERE c.survey_id = 262
  AND c.dim = 'total'
  AND c.cohort_id IS NULL;
```

Purpose: determine whether an interactive `cip_agg_cell` shape behind `app/data/repository.py::wave_report` matches the historic expensive family. Nonexecuting; expected optimizer time under two seconds; zero rows affected.

### SQL-042 — current single-question analysis read

Replace `:approved_question_id` with the literal returned by approved SQL-040 before execution and return the expanded statement for review.

```sql
EXPLAIN FORMAT=JSON
SELECT c.dim_value AS segment, c.n, c.base_n, i.item_label,
       COALESCE(i.sort_order, 0) AS item_order, o.value_label,
       o.sort_order AS option_order, q.qtype, q.is_multi
FROM cip_stg.cip_agg_cell AS c
JOIN cip_stg.cip_question AS q ON q.question_id = c.question_id
LEFT JOIN cip_stg.cip_item AS i ON i.item_id = c.item_id
LEFT JOIN cip_stg.cip_option AS o ON o.option_id = c.option_id
WHERE c.survey_id = 262
  AND c.question_id = :approved_question_id
  AND c.dim = 'total'
  AND COALESCE(c.cohort_id, 0) = 0;
```

Purpose: verify the index used by `analyse_cube`. Nonexecuting and expected under one second. The `COALESCE` predicate may limit index filtering; actual impact must be established from the plan.

### SQL-043 — cross-wave concept trend plan

```sql
EXPLAIN FORMAT=JSON
SELECT s.survey_id, s.wave_label, s.wave_date, s.platform,
       co.option_label AS answer, co.sort_order AS answer_order,
       c.n, c.base_n
FROM cip_stg.cip_concept_option AS co
JOIN cip_stg.cip_concept_map AS m
  ON m.concept_option_id = co.concept_option_id
 AND m.status = 'confirmed'
JOIN cip_stg.cip_agg_cell AS c
  ON c.survey_id = m.survey_id
 AND c.map_key = m.map_key
 AND c.dim = 'total'
 AND COALESCE(c.cohort_id, 0) = 0
JOIN cip_stg.cip_survey AS s
  ON s.survey_id = m.survey_id
 AND s.load_status = 'verified'
WHERE co.concept_id = 1;
```

Purpose: test the cross-wave `cip_agg_cell` candidate omitted by SQL-025. `concept_id=1` is a plan literal, not a claim that the concept is representative. Nonexecuting; expected under two seconds.

### SQL-044 — plans for small-wave candidates

Repeat SQL-023 and SQL-024 as `EXPLAIN FORMAT=JSON` for survey IDs 238 and 10, one statement at a time. Do not execute the SELECTs. Purpose: compare estimated `srv_answer` range sizes before proposing an actual aggregate. Expected optimizer time below one second per plan.

## Gate B — disposable MySQL 8 correctness/performance suite

This is the preferred before/after environment because it permits DML, controlled concurrency and instrumentation without touching shared data.

Dataset:

- deterministic synthetic waves producing approximately 10k, 100k and 500k `srv_answer` rows;
- actual `utf8mb4_0900_ai_ci` definitions;
- case/accent variants, trailing spaces, empty strings and NULLs;
- single, multi-select, grid, unknown/free-text and missing-demographic cases;
- weighted and unweighted outputs;
- repeated publication and shrinking reloads.

For each size and candidate change:

- warmup 2, measured samples 10;
- publisher jobs 1, 2 and 4;
- p50/p95/worst wall time and SQL time;
- query count, rows returned and bytes transferred;
- `Created_tmp_tables`/`Created_tmp_disk_tables` session deltas;
- per-process peak RSS and connection high-water mark;
- exact canonical JSON, cut-count, bitset and published-file SHA-256 equality;
- rollback, injected deadlock/timeout and partial-failure behavior;
- zero real network or notification calls.

Candidate application changes must be tested independently:

1. privacy-safe live-fallback instrumentation;
2. bounded-memory/less-duplicated respondent extraction;
3. ingestion that avoids redundant derived-label writes;
4. deployment-specific publisher concurrency.

The original SQL grouped result is the correctness oracle. Python aggregation is excluded.

## Gate C — optional tiny staging aggregate

Only after SQL-044 proves a candidate estimate is small and after separate approval, execute one aggregate-only query for the smallest valid wave. Do not run respondent extraction on staging.

Safety envelope:

- one read-only connection, one worker, no retry;
- ETL lock free and `Threads_running <= 8` immediately before execution;
- `MAX_EXECUTION_TIME(3000)` optimizer hint plus the existing 10-second client watchdog;
- return only aggregate cells, never respondent identifiers;
- abort progression if estimated range exceeds 25,000 `srv_answer` rows;
- one warmup and three measured runs maximum;
- record elapsed time, returned rows/bytes and temporary-table counter deltas;
- no survey 262 execution until a smaller wave succeeds and separate approval names it.

This would measure current SQL only. An after measurement would require an approved code/SQL candidate and the identical wave/session envelope.

## Acceptance criteria

- Exact output hashes and numerical parity; no tolerance for count/base/percentage drift.
- No MySQL-collation, NULL, missing-cut or ordering change.
- No unbounded connection growth; all sessions close after failure.
- At least 20% median improvement or a material peak-memory/connection reduction without worse p95.
- No new index unless disposable MySQL demonstrates lower total read cost and acceptable write/storage cost, followed by a separate DBA proposal.
- Shared staging results remain evidence only; deployment still requires owner approval, a canary and rollback plan.

