# CIP Stage 5 SQL approval manifest

Date: 2026-10-27  
State: **APPROVED AND EXECUTED — COMPLETE**

Execution evidence: [FINAL_STAGING_SANITIZED_RESULTS.json](evidence/FINAL_STAGING_SANITIZED_RESULTS.json).  
Consolidated outcome: [CIP_FINAL_CONSOLIDATED_RESULT.md](../CIP_FINAL_CONSOLIDATED_RESULT.md).

Use the identical Stage 4 TLS identity, one-connection, read-only, 5-second
SELECT, 3-second lock, 10-second socket, ETL-lock, thread-pressure, serial and
no-retry safeguards.

## SQL-046 — final compatibility predicate plan

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
 AND (c.cohort_id IS NULL OR c.cohort_id = 0)
 AND c.dim = 'total'
JOIN cip_stg.cip_survey AS s
  ON s.survey_id = m.survey_id
 AND s.load_status = 'verified'
WHERE co.concept_id = 1;
```

Purpose: verify `ref_or_null`, `ix_agg_map` selection and all four key parts for
the final code. Nonexecuting. Expected one plan row, under two seconds, zero
affected rows and negligible lock risk.

## SQL-047 — bounded legacy-zero existence check

```sql
SELECT cell_id, survey_id
FROM cip_stg.cip_agg_cell
WHERE survey_id = 262
  AND cohort_id = 0
LIMIT 1;
```

Purpose: determine whether one known wave contains a legacy zero row. The
`survey_id` prefix bounds the scan to the wave; Stage 3 estimated approximately
31,372 cube rows for its wave-wide total query. Expected zero or one returned
row, zero affected rows, under five seconds, no material row lock. Stop on the
existing timeout; do not retry.

A global `WHERE cohort_id=0` count is not proposed because no current index
leads with `cohort_id`; absence could require scanning all ~2.79 million cells.

No actual concept SELECT, index creation, data cleanup, CHECK/FK, statistics
refresh, ETL or deployment is requested.
