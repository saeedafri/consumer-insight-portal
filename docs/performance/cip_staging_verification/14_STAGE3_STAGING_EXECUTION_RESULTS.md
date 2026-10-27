# CIP Stage 3 staging execution results

Date: 2026-10-27  
Target: authorized Azure MySQL staging `cip_stg`  
Result: **all approved statements succeeded; SQL-042 was not executed**

Evidence: [STAGE3_STAGING_SANITIZED_RESULTS.json](evidence/STAGE3_STAGING_SANITIZED_RESULTS.json)  
SHA-256: `2f42fa4124253d3758d7e6688c1ec0f8f9a44840df825e6172c9c7bcc3f8b7e0`

## Safety outcome

- One direct TLS connection; no pool and no retry.
- Target matched the pseudonymized Stage 1/2 server and account, MySQL `8.0.46-azure`, port 3306, database exactly `cip_stg`.
- Verified `autocommit=1`, `transaction_read_only=1`, `max_execution_time=5000`, metadata/row lock waits of 3 seconds.
- `cip_etl` remained unlocked before every plan.
- `Threads_running` was 1 before five plans and 2 before the final plan; threshold was 8.
- The connection closed after completion.
- No underlying workload SELECT, DML, DDL, ETL, deployment or restart ran.

## Statement ledger

| Statement | Elapsed ms | Result |
|---|---:|---|
| SQL-040 | 294.212 | Returned question `7778` (`TM1`) for literal expansion. |
| SQL-041 | 334.790 | Captured current wave-report cube plan. |
| SQL-043 | 312.195 | Captured current cross-wave concept plan. |
| SQL-044A | 279.469 | Grouped plan for survey 238. |
| SQL-044B | 234.985 | Extraction plan for survey 238. |
| SQL-044C | 320.867 | Grouped plan for survey 10. |
| SQL-044D | 232.875 | Extraction plan for survey 10. |

These times are plan/network time, not underlying-query runtime.

## Findings

### SQL-041 — historic `wave_report` candidate

- `cip_agg_cell`: `ix_agg_question`, but only its `survey_id` part is used.
- Estimated 31,372 cells examined, 313 retained after `dim='total'` and `cohort_id IS NULL`.
- Question/item/option joins are one-row PK probes.
- Estimated cost: 34,280.38.

This is a genuine inefficient current shape and a plausible member of the historic expensive `cip_agg_cell` family. The existing index orders `question_id` before `dim`, so a whole-wave total query cannot use the latter key parts.

### SQL-043 — cross-wave concept candidate

- Concept options: `uq_concept_option(concept_id,option_code)`, about 19 rows.
- Mappings: `ix_map_concept_option`, about five rows per option, filtered by confirmed status.
- Surveys: PK lookup.
- Cells: `ix_agg_map(survey_id,map_key,cohort_id,dim)`, but only `(survey_id,map_key)` is used because `COALESCE(c.cohort_id,0)=0` makes the cohort key non-sargable.
- Estimated 35 cells examined per mapping, 10% retained; cost 2,061.34.

This confirms an application-level predicate issue. Replacing the `COALESCE` predicate with `IS NULL` for the all-respondent case preserves semantics and makes all index parts eligible.

### SQL-044 — candidate wave sizes

| Wave | Estimated `srv_answer` rows | Estimated data | Grouping |
|---|---:|---:|---|
| 238 | 852 | 2 MiB | Internal temporary table; no filesort. |
| 10 | 33,674 | 99 MiB | Internal temporary table; no filesort. |

Both use the `srv_answer` primary-key `survey_id` prefix. Survey 238 is the only reasonable candidate for a separately approved aggregate-only staging benchmark. Neither underlying query was executed.

## SQL-042 exact expansion — not executed

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
  AND c.question_id = 7778
  AND c.dim = 'total'
  AND COALESCE(c.cohort_id, 0) = 0;
```

This statement remains pending explicit approval.

