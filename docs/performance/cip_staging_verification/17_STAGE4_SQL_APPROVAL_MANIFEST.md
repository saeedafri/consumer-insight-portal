# CIP Stage 4 SQL approval manifest

Date: 2026-10-27  
State: **PROPOSED — NOT AUTHORIZED**

Use the identical Stage 2/3 TLS identity, read-only session, five-second SELECT budget, three-second lock budgets, lock/pressure checks, serial execution and no-retry policy.

## SQL-042 — exact expanded single-question plan

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

Nonexecuting plan only. Expected one JSON row, optimizer work under one second, zero affected rows.

## SQL-045 — optimized cross-wave concept plan

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
 AND c.cohort_id IS NULL
 AND c.dim = 'total'
JOIN cip_stg.cip_survey AS s
  ON s.survey_id = m.survey_id
 AND s.load_status = 'verified'
WHERE co.concept_id = 1;
```

Purpose: verify whether the current `ix_agg_map(survey_id,map_key,cohort_id,dim)` uses all four key parts after removing `COALESCE`. Nonexecuting; expected under two seconds; zero affected rows.

## Not requested

- No actual SELECT, respondent extraction, aggregate execution, DML or DDL.
- No index creation or statistics refresh.
- No SQL-046 or improvised statement.

