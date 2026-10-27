# CIP staging Stage 2 SQL execution approval manifest

Date: 2026-10-27  
State: **APPROVED AND EXECUTED ONCE — COMPLETE**  
Scope: one bounded wave-catalog read plus nonexecuting MySQL plans

The owner approved the exact manifest. All statements were executed once in the documented order on 2026-10-27. Results are in `11_STAGE2_EXECUTION_AND_PLAN_FINDINGS.md`; the SQL below is retained unchanged as the execution specification.

## Why survey 262 appears in plan SQL

Survey ID `262` is a real staging ID already present in the prior verified G02 plan evidence. It is used only as a literal for nonexecuting `EXPLAIN FORMAT=JSON`; this does not claim it is a modest benchmark wave. SQL-019 will return bounded candidate wave metadata for a later Class C proposal. No actual query for survey 262 is requested here.

## Exact proposed execution order

### SQL-030 — identity and fresh session state

```sql
SELECT VERSION() AS server_version,
       DATABASE() AS current_database,
       CURRENT_USER() AS authenticated_account,
       @@hostname AS server_hostname,
       @@port AS server_port,
       CONNECTION_ID() AS inspection_connection_id,
       @@session.autocommit AS session_autocommit,
       @@session.transaction_read_only AS transaction_read_only,
       @@session.max_execution_time AS max_execution_time_ms,
       @@session.lock_wait_timeout AS metadata_lock_wait_seconds,
       @@session.innodb_lock_wait_timeout AS row_lock_wait_seconds;
```

### SQL-031 — enforce read-only transactions

```sql
SET SESSION TRANSACTION READ ONLY;
```

### SQL-032 — five-second SELECT budget

```sql
SET SESSION max_execution_time = 5000;
```

### SQL-033 — three-second metadata-lock wait

```sql
SET SESSION lock_wait_timeout = 3;
```

### SQL-034 — three-second row-lock wait

```sql
SET SESSION innodb_lock_wait_timeout = 3;
```

### SQL-035 — verify guardrails

```sql
SELECT @@session.autocommit AS session_autocommit,
       @@session.transaction_read_only AS transaction_read_only,
       @@session.max_execution_time AS max_execution_time_ms,
       @@session.lock_wait_timeout AS metadata_lock_wait_seconds,
       @@session.innodb_lock_wait_timeout AS row_lock_wait_seconds;
```

Required result: `1, 1, 5000, 3, 3`. Otherwise stop.

### SQL-036 — observe CIP lock without acquiring it

```sql
SELECT IS_USED_LOCK('cip_etl') AS cip_etl_owner_connection_id;
```

Required result: `NULL`. Otherwise stop without inspecting/killing the owner.

### SQL-037 — pressure snapshot

```sql
SHOW GLOBAL STATUS
WHERE Variable_name IN (
    'Threads_connected', 'Threads_running', 'Connections',
    'Aborted_connects', 'Created_tmp_tables',
    'Created_tmp_disk_tables', 'Slow_queries', 'Questions', 'Uptime'
);
```

Stop if `Threads_running > 8`. Counters are cumulative and will not be attributed to a plan.

### SQL-019 — choose bounded candidate waves

```sql
SELECT survey_id, study_type, wave_date, qualified_n, rows_built,
       prior_survey_id, ly_survey_id
FROM cip_stg.srv_wave
ORDER BY rows_built ASC, survey_id ASC
LIMIT 10;
```

Target/cost: `srv_wave`, estimated 368 rows/48 KiB. No `rows_built` index, so expect a full catalog scan and filesort of roughly 368 rows. Returns at most 10 rows/<5 KiB. Expected under 100 ms; hard SELECT budget 5 seconds. Nonlocking read, zero rows affected. No index is proposed.

### SQL-023 — grouped-cut plan

```sql
EXPLAIN FORMAT=JSON
SELECT survey_id, qcode, item_id, option_id,
       gender, age_band, generation, income_band, census_region, urbanicity,
       COUNT(*)
FROM cip_stg.srv_answer
WHERE survey_id IN (262)
GROUP BY survey_id, qcode, item_id, option_id,
         gender, age_band, generation, income_band, census_region, urbanicity;
```

Target: `srv_answer`; source `app/data/payloads.py::question_cuts`. Purpose: selected PK range, estimated rows/cost and grouping/temp strategy. The SELECT is not executed. Expected optimizer work under 2 seconds, one JSON row/<512 KiB; client timeout 10 seconds, MDL wait 3 seconds, zero affected rows.

### SQL-024 — respondent extraction plan

```sql
EXPLAIN FORMAT=JSON
SELECT respondent_id, qcode, item_id, option_id,
       gender, age_band, generation, income_band, census_region, urbanicity
FROM cip_stg.srv_answer
WHERE survey_id = 262;
```

Target: `srv_answer`; source `app/data/payloads.py::people`. Purpose: selected access path, estimated rows and projected width. No respondent row is returned. Same 2-second expectation/10-second client timeout/3-second MDL wait; zero affected.

### SQL-025 — serving join plan

```sql
EXPLAIN FORMAT=JSON
SELECT c.survey_id, c.question_id, q.qcode, q.qtype,
       COALESCE(c.item_id, 0) AS item_id,
       COALESCE(c.option_id, 0) AS option_id,
       COALESCE(i.item_label, '') AS item_label,
       o.value_code AS option_code,
       o.value_label AS option_label,
       COALESCE(i.sort_order, 0) * 1000 + COALESCE(o.sort_order, 0) AS sort_order,
       COALESCE(c.concept_option_id, m.concept_option_id) AS concept_option_id,
       c.dim, c.dim_value, c.n, c.base_n
FROM cip_stg.cip_agg_cell AS c
JOIN cip_stg.cip_question AS q
  ON q.question_id = c.question_id
 AND q.survey_id = c.survey_id
 AND q.survey_id IN (262)
 AND q.is_technical = 0
 AND q.is_virtual = 0
LEFT JOIN cip_stg.cip_item AS i
  ON i.item_id = c.item_id
LEFT JOIN cip_stg.cip_option AS o
  ON o.option_id = c.option_id
LEFT JOIN cip_stg.cip_concept_map AS m
  ON m.survey_id = c.survey_id
 AND m.map_key = c.map_key
 AND m.status = 'confirmed'
 AND m.concept_option_id IS NOT NULL
WHERE c.survey_id IN (262)
  AND c.cohort_id IS NULL
  AND c.base_n > 0
  AND (c.dim = 'total' OR c.dim_value <> '');
```

Target: `cip_agg_cell`, `cip_question`, `cip_item`, `cip_option`, `cip_concept_map`; exact `etl/serving.py::cube_rows` shape for one wave. Purpose: join order, index selection, estimated fanout/cost. Nonexecuting. Expected optimizer work under 2 seconds, one JSON row/<1 MiB, client timeout 10 seconds, MDL wait 3 seconds, zero affected.

### SQL-026 — label-cleanup predicate plan

```sql
EXPLAIN FORMAT=JSON
SELECT a.answer_id
FROM cip_stg.cip_answer AS a
JOIN cip_stg.cip_field AS f
  ON f.field_id = a.field_id
LEFT JOIN cip_stg.cip_option AS o
  ON o.question_id = f.question_id
 AND o.value_code = a.value_code
LEFT JOIN cip_stg.cip_item AS i
  ON i.item_id = f.item_id
WHERE a.survey_id = 262
  AND a.value_label = COALESCE(o.value_label, i.item_label);
```

Target: `cip_answer`, `cip_field`, `cip_option`, `cip_item`; read-only equivalent of `drop_derived_labels` predicate. Purpose: assess access path without `EXPLAIN UPDATE` or any write privilege. Nonexecuting. Expected under 2 seconds, one JSON row/<512 KiB, zero affected.

### SQL-027 — Qualtrics respondent-map plan

```sql
EXPLAIN FORMAT=JSON
SELECT record_no, respondent_id
FROM cip_stg.cip_respondent
WHERE survey_id = 262;
```

Target: `cip_respondent`; source `etl/run_pipeline.py::_replace_respondents`. Purpose: verify survey-leading uniqueness index and estimated rows. Nonexecuting; expected under one second, one JSON row, zero affected.

### SQL-028 — Qualtrics answer-delete predicate plan

```sql
EXPLAIN FORMAT=JSON
SELECT answer_id
FROM cip_stg.cip_answer
WHERE survey_id = 262;
```

Target: `cip_answer`; read-only equivalent of the replacement delete predicate. Purpose: verify `ix_answer_cover` range access and estimate affected-wave rows without deleting anything. Nonexecuting; expected under one second, one JSON row, zero affected.

### SQL-029 — grouped-cut label lookup plan

```sql
EXPLAIN FORMAT=JSON
SELECT r.survey_id, r.qcode, r.item_id, r.option_id,
       r.item_label, r.option_code, r.option_label, r.sort_order,
       r.flags, r.concept_option_id, q.qtext
FROM cip_stg.srv_result AS r
JOIN cip_stg.cip_question AS q
  ON q.question_id = r.question_id
WHERE r.survey_id IN (262)
  AND r.dim = 'total';
```

Target: `srv_result`, `cip_question`; second query in `question_cuts`. Purpose: verify PK range/filter and question join. Nonexecuting; expected under one second, one JSON row, zero affected.

## Shared safeguards

- One dedicated TLS PyMySQL connection, no pool, autocommit on.
- `connect_timeout=5`, `read_timeout=10`, `write_timeout=10`.
- One statement at a time, no automatic retries.
- Execute only after SQL-035 verifies the session and SQL-036 confirms no CIP ETL lock.
- Close immediately on any error, timeout, unexpected identity, lock owner or pressure breach.
- Record elapsed time, exact plan JSON, chosen indexes and optimizer estimates. Redact account/host/definer values.
- Do not run any explained SELECT, `EXPLAIN ANALYZE`, DML, DDL, `ANALYZE TABLE`, ETL, publisher or scheduler.

## Still not authorized

- Actual grouped cuts, respondent extraction, serving join or label query.
- Any view count.
- Any new index/statistics refresh.
- Any write, reload, import, transaction test or deployment.
- Any SIP/MIP/ChainXY schema access.

## Executed approval scope

SQL-030 through SQL-037, SQL-019, and SQL-023 through SQL-029 were approved and executed once in the documented order and envelope. Execution remained plan-only except for the 368-row `srv_wave` catalog read in SQL-019.
