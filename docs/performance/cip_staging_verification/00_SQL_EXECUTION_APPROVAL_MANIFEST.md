# CIP staging SQL execution approval manifest

Date: 2026-10-27  
Repository: `/Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal`  
Branch/base: `master` / `6f978b0595b2c71c064991ae10b832514637a0da`  
Target schema: Azure MySQL staging `cip_stg` only  
State: **PROPOSED — NOT AUTHORIZED. No staging connection or SQL has been executed.**

## Stop gate

This document requests approval only for SQL-001 through SQL-022. They are identity checks, connection-local safety settings, metadata reads, one bounded non-PII wave-catalog read, named-lock observation, scheduler metadata, and global health counters. They execute serially on one dedicated connection.

No `EXPLAIN` is requested in this first batch because the owner has not yet approved a specific modest staging wave ID. SQL-019 will return ten bounded candidates. After the owner selects one ID, a second manifest will contain fully expanded `EXPLAIN FORMAT=JSON` statements with the literal approved ID and no placeholders. No plan or data query will be improvised from SQL-019's result.

## Current code findings

| Finding | Evidence | Status |
|---|---|---|
| The MySQL driver is PyMySQL through SQLAlchemy `QueuePool`. | `requirements.txt:21`; `app/core/config.py:54-64`; `app/core/database.py:71-114` | Proven from source. Live version unverified. |
| Current application defaults permit long waits: 20-second connect timeout, 600-second application read/socket timeout and 1,800-second ETL read/socket timeout. Only the read role installs `max_execution_time`; the writer has no server-side statement deadline. | `app/core/database.py:24-29,95-111` | Proven from source; unsafe as a long-term bounded-operation policy. |
| Pool defaults are 10 persistent plus 20 overflow connections per role and per process, with a 30-second checkout timeout. Total deployment process count is unknown. | `app/core/config.py:38-50,145-155` | Code proven; deployed aggregate capacity unknown. |
| ETL sessions request 16 MiB sort/join buffers and 512 MiB temporary/heap limits. These are limits, not preallocated memory, but concurrent ETL queries can make them material. | `app/core/database.py:27-29,99-100` | Code proven; live session values and pressure unknown. |
| Publisher jobs are constrained to 1–4 but default to four. Each fresh wave still performs one MySQL-collated grouped `srv_answer` query and one respondent extraction. | `etl/publish.py:70-78,135-161`; `app/data/payloads.py:365-415` | Proven from source. Correct SQL collation semantics preserved. |
| Serving builds default to one worker and allow at most four. Deadlock retry is limited to three attempts, but sleep lacks jitter and other transient errors are not classified. | `etl/serving.py:235-245,321-355` | Proven from source. Azure behavior unverified. |
| CIP's named writer lock uses `GET_LOCK('cip_etl', 0)`, so acquisition does not wait. Its connection receives a seven-day idle timeout and releases the lock in `finally`; external schedulers and manual paths remain unverified. | `etl/loaders.py:21-46` | Source behavior proven; deployed overlap unknown. |
| The expensive serving read is the filtered `cip_agg_cell` join in `cube_rows`. The checked-in schema has `uq_agg_cell`, `ix_agg_question`, and `ix_agg_map`, but the live join order/index choice is unknown. | `etl/serving.py:103-125`; `sql/001_schema.sql:562-594` | Plan mechanism unverified. No index proposed. |
| Forsta no longer performs the derived-label cleanup update; Qualtrics and legacy loads still do. | `etl/forsta_etl.py:348`; `etl/qualtrics_export.py:154`; `etl/legacy_dwh.py:384`; `etl/run_pipeline.py:344-400` | Proven from source. MySQL write behavior unverified. |
| No current non-test repository caller issues the historic full `COUNT(*)` on `v_cip_answer_long`. | Repository search; view at `sql/002_views.sql:216-235` | Current caller unverified outside this repository. Full count is rejected. |
| The working tree remains uncommitted and contains existing source/test/document changes. Nothing was reset, committed, pushed, deployed, or restarted while preparing this manifest. | `git status --porcelain=v1` captured locally | Proven locally. |

## Connection and execution envelope

These controls are part of the approval request. If any cannot be established, execution stops before SQL-008.

- Dedicated inspection connection using the configured staging host allowlist and schema exactly `cip_stg`; production hostnames and schemas fail closed client-side.
- TLS enabled. Credentials and connection URLs are never printed.
- PyMySQL driver values: `connect_timeout=5`, `read_timeout=10`, `write_timeout=10`, `autocommit=True`.
- SQLAlchemy pool, if used: `pool_size=1`, `max_overflow=0`, `pool_timeout=5`, no application/ETL engine reuse.
- Exactly one session and one statement at a time. No worker, scheduler, API, publisher, ETL, notification, or external integration process starts.
- SQL-001 must report `DATABASE() = 'cip_stg'`; otherwise close the session immediately.
- SQL-002 must show the expected inspection identity. A read-only account is preferred. If the account has write privileges, the client statement allowlist and SQL-003 provide additional fail-closed controls.
- SQL-003 through SQL-006 are connection-local only. No global setting is changed.
- Maximum server-side SELECT budget: 5 seconds. Metadata statements not covered by `max_execution_time` remain bounded by 3-second metadata-lock wait and 10-second client read timeout.
- Stop the batch if any statement exceeds 5 seconds, waits on metadata locks, returns an unexpected schema, reports an active `cip_etl` owner, or Azure monitoring shows CPU above 60%, exhausted/rapidly falling CPU credits, more than two additional running threads, or sustained storage latency above 20 ms.
- Capture `CONNECTION_ID()` from SQL-001. Automatic `KILL` is not authorized. On a watchdog timeout, close the socket, stop the batch, and ask a DBA to verify and cancel only that recorded CIP inspection session. Never cancel an arbitrary shared session.
- Close the connection after the batch. With autocommit enabled, no long-lived reader transaction is intentionally retained.
- Results are sanitized: no credentials, raw answers, respondent IDs, respondent keys, email addresses, SQL parameters containing PII, or other tenants' SQL text.

## Exact proposed SQL

### SQL-001 — identity, target and initial session state

```sql
SELECT
    VERSION() AS server_version,
    DATABASE() AS current_database,
    CURRENT_USER() AS authenticated_account,
    @@hostname AS server_hostname,
    @@port AS server_port,
    CONNECTION_ID() AS inspection_connection_id,
    @@session.autocommit AS session_autocommit,
    @@session.transaction_read_only AS transaction_read_only,
    @@session.transaction_isolation AS transaction_isolation,
    @@session.max_execution_time AS max_execution_time_ms,
    @@session.lock_wait_timeout AS metadata_lock_wait_seconds,
    @@session.innodb_lock_wait_timeout AS row_lock_wait_seconds;
```

- Target: server/session metadata; no table.
- Purpose/output: prove MySQL version, `cip_stg` target, authenticated account, own connection ID, and initial guards. Result: one row, expected under 2 KiB.
- Cost/affected rows: constant metadata lookup; one result row; zero data rows affected; expected under 100 ms, hard client timeout 10 seconds.
- Locks/risk: no table locks; negligible. Stop if schema is not exactly `cip_stg` or identity/host is not the configured staging target.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-002 — effective grants

```sql
SHOW GRANTS FOR CURRENT_USER;
```

- Target: privilege metadata.
- Purpose/output: determine whether the inspection identity is truly read-only and record excess privilege risk without printing credentials. Expected 1–20 short rows.
- Cost/affected rows: privilege-cache lookup; zero rows affected; expected under 100 ms, 10-second client timeout.
- Locks/risk: no application-table locks. Grant text is sanitized before reporting account/host identifiers.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-003 — session-default read-only transactions

```sql
SET SESSION TRANSACTION READ ONLY;
```

- Target: current inspection session only.
- Purpose/output: make subsequent transactions read-only at the server in addition to the client allowlist.
- Cost/affected rows: constant session-state change; no database row affected; expected under 100 ms.
- Locks/risk: none on application tables. Setting disappears when this connection closes.
- Class/status: **A safety control — PROPOSED, NOT AUTHORIZED**.

### SQL-004 — eligible SELECT deadline

```sql
SET SESSION max_execution_time = 5000;
```

- Target: current inspection session only.
- Purpose/output: stop eligible read-only `SELECT` statements after 5,000 ms.
- Cost/affected rows: constant session-state change; no row affected; expected under 100 ms.
- Locks/risk: none. It does not protect DDL/DML and is not represented as a universal timeout.
- Class/status: **A safety control — PROPOSED, NOT AUTHORIZED**.

### SQL-005 — metadata-lock deadline

```sql
SET SESSION lock_wait_timeout = 3;
```

- Target: current inspection session only.
- Purpose/output: fail a metadata-lock wait after three seconds instead of joining a lock convoy.
- Cost/affected rows: constant session-state change; no row affected; expected under 100 ms.
- Locks/risk: none. It does not cap query execution time.
- Class/status: **A safety control — PROPOSED, NOT AUTHORIZED**.

### SQL-006 — InnoDB row-lock deadline

```sql
SET SESSION innodb_lock_wait_timeout = 3;
```

- Target: current inspection session only.
- Purpose/output: fail any unexpected InnoDB row-lock wait after three seconds.
- Cost/affected rows: constant session-state change; no row affected; expected under 100 ms.
- Locks/risk: none. Proposed reads should not request row locks.
- Class/status: **A safety control — PROPOSED, NOT AUTHORIZED**.

### SQL-007 — verify all session guards

```sql
SELECT
    @@session.autocommit AS session_autocommit,
    @@session.transaction_read_only AS transaction_read_only,
    @@session.max_execution_time AS max_execution_time_ms,
    @@session.lock_wait_timeout AS metadata_lock_wait_seconds,
    @@session.innodb_lock_wait_timeout AS row_lock_wait_seconds;
```

- Target: current session metadata.
- Purpose/output: require `1,1,5000,3,3` before table metadata is read.
- Cost/affected rows: constant lookup, one result row, zero affected; expected under 100 ms.
- Locks/risk: none. Any mismatch ends the batch.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-008 — exact live column types and collations

```sql
SELECT
    table_name,
    ordinal_position,
    column_name,
    column_type,
    is_nullable,
    column_default,
    collation_name,
    column_key,
    extra
FROM information_schema.columns
WHERE table_schema = 'cip_stg'
  AND table_name IN (
      'srv_answer', 'srv_result', 'srv_wave',
      'cip_agg_cell', 'cip_answer', 'cip_field', 'cip_question',
      'cip_item', 'cip_option', 'cip_concept_map',
      'cip_respondent', 'cip_profile', 'cip_weight',
      'cip_respondent_cohort', 'cip_tracker_line'
  )
ORDER BY table_name, ordinal_position;
```

- Target: `information_schema.columns`; metadata for the 15 named CIP tables.
- Purpose/output: verify live types, nullable behavior and collations, especially `srv_answer` grouping semantics and label/FK key compatibility. Expected roughly 150–250 rows, under 100 KiB.
- Cost/affected rows: metadata only; no table data scan; zero affected; expected under one second, stop at five seconds.
- Locks/risk: brief metadata access; no row locks. Three-second MDL wait and serial execution apply.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-009 — exact live indexes and cardinality estimates

```sql
SELECT
    table_name,
    index_name,
    non_unique,
    seq_in_index,
    column_name,
    collation,
    cardinality,
    sub_part,
    nullable,
    index_type,
    is_visible
FROM information_schema.statistics
WHERE table_schema = 'cip_stg'
  AND table_name IN (
      'srv_answer', 'srv_result', 'srv_wave',
      'cip_agg_cell', 'cip_answer', 'cip_field', 'cip_question',
      'cip_item', 'cip_option', 'cip_concept_map',
      'cip_respondent', 'cip_profile', 'cip_weight',
      'cip_respondent_cohort', 'cip_tracker_line'
  )
ORDER BY table_name, index_name, seq_in_index;
```

- Target: `information_schema.statistics`; same 15 tables.
- Purpose/output: verify existing PK/secondary indexes and reject redundant proposals. Cardinality is treated as an estimate. Expected under 150 rows/50 KiB.
- Cost/affected rows: metadata only; zero affected; expected under one second, stop at five seconds.
- Locks/risk: brief metadata access; no row locks. No `ANALYZE TABLE` is implied or authorized.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-010 — foreign keys and delete/update rules

```sql
SELECT
    k.table_name,
    k.constraint_name,
    k.column_name,
    k.ordinal_position,
    k.referenced_table_name,
    k.referenced_column_name,
    r.update_rule,
    r.delete_rule
FROM information_schema.key_column_usage AS k
JOIN information_schema.referential_constraints AS r
  ON r.constraint_schema = k.constraint_schema
 AND r.constraint_name = k.constraint_name
 AND r.table_name = k.table_name
WHERE k.constraint_schema = 'cip_stg'
  AND k.referenced_table_name IS NOT NULL
  AND k.table_name IN (
      'srv_answer', 'srv_result', 'srv_wave',
      'cip_agg_cell', 'cip_answer', 'cip_field', 'cip_question',
      'cip_item', 'cip_option', 'cip_concept_map',
      'cip_respondent', 'cip_profile', 'cip_weight',
      'cip_respondent_cohort', 'cip_tracker_line'
  )
ORDER BY k.table_name, k.constraint_name, k.ordinal_position;
```

- Target: `information_schema.key_column_usage` and `referential_constraints`.
- Purpose/output: validate shrinking reload, cascade/restrict behavior and serving replacement assumptions. Expected under 100 rows/30 KiB.
- Cost/affected rows: metadata joins only; zero affected; expected under one second, stop at five seconds.
- Locks/risk: brief metadata access only.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-011 — triggers on affected CIP tables

```sql
SELECT
    trigger_name,
    event_object_table,
    action_timing,
    event_manipulation,
    action_orientation
FROM information_schema.triggers
WHERE trigger_schema = 'cip_stg'
  AND event_object_table IN (
      'srv_answer', 'srv_result', 'srv_wave',
      'cip_agg_cell', 'cip_answer', 'cip_field', 'cip_question',
      'cip_item', 'cip_option', 'cip_concept_map',
      'cip_respondent', 'cip_profile', 'cip_weight',
      'cip_respondent_cohort', 'cip_tracker_line'
  )
ORDER BY event_object_table, trigger_name;
```

- Target: `information_schema.triggers`.
- Purpose/output: detect trigger side effects before designing MySQL reload/rollback tests. The trigger body is deliberately excluded from this first result. Expected zero to a few dozen rows.
- Cost/affected rows: metadata only; zero affected; expected under one second, stop at five seconds.
- Locks/risk: brief metadata access; no data or trigger execution.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-012 — table size and row-count estimates

```sql
SELECT
    table_name,
    engine,
    table_rows,
    avg_row_length,
    data_length,
    index_length,
    data_free,
    update_time
FROM information_schema.tables
WHERE table_schema = 'cip_stg'
  AND table_name IN (
      'srv_answer', 'srv_result', 'srv_wave',
      'cip_agg_cell', 'cip_answer', 'cip_field', 'cip_question',
      'cip_item', 'cip_option', 'cip_concept_map',
      'cip_respondent', 'cip_profile', 'cip_weight',
      'cip_respondent_cohort', 'cip_tracker_line'
  )
ORDER BY table_name;
```

- Target: `information_schema.tables`; 15 named tables.
- Purpose/output: bound later plan/benchmark proposals without exact counts. `table_rows` is explicitly treated as an InnoDB estimate. Expected 15 rows under 10 KiB.
- Cost/affected rows: metadata/statistics only; zero affected; expected under one second, stop at five seconds.
- Locks/risk: brief metadata access; no table scan or row lock.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-013 — deployed `srv_answer` definition

```sql
SHOW CREATE TABLE cip_stg.srv_answer;
```

- Target: `cip_stg.srv_answer` metadata.
- Purpose/output: verify PK left prefix, collation and FK exactly; reject a redundant `(survey_id,qcode)` index. One DDL text row, expected under 20 KiB.
- Cost/affected rows: metadata only; zero affected; expected under 250 ms, stop at five seconds.
- Locks/risk: brief metadata lock; three-second MDL timeout applies.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-014 — deployed `cip_agg_cell` definition

```sql
SHOW CREATE TABLE cip_stg.cip_agg_cell;
```

- Target: `cip_stg.cip_agg_cell` metadata.
- Purpose/output: verify live unique and secondary indexes used by `etl.serving.cube_rows`. One DDL row under 25 KiB.
- Cost/affected rows: metadata only; zero affected; expected under 250 ms, stop at five seconds.
- Locks/risk: brief MDL only.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-015 — deployed `cip_answer` definition

```sql
SHOW CREATE TABLE cip_stg.cip_answer;
```

- Target: `cip_stg.cip_answer` metadata.
- Purpose/output: verify answer uniqueness, survey-leading covering index and FK behavior before MySQL reload tests. One DDL row under 25 KiB.
- Cost/affected rows: metadata only; zero affected; expected under 250 ms, stop at five seconds.
- Locks/risk: brief MDL only.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-016 — deployed `srv_result` definition

```sql
SHOW CREATE TABLE cip_stg.srv_result;
```

- Target: `cip_stg.srv_result` metadata.
- Purpose/output: verify publication labels, PK ordering and concept index. One DDL row under 25 KiB.
- Cost/affected rows: metadata only; zero affected; expected under 250 ms, stop at five seconds.
- Locks/risk: brief MDL only.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-017 — deployed `srv_wave` definition

```sql
SHOW CREATE TABLE cip_stg.srv_wave;
```

- Target: `cip_stg.srv_wave` metadata.
- Purpose/output: verify comparison-wave catalog, family/date index, FK and deployment of `in_field`. One DDL row under 20 KiB.
- Cost/affected rows: metadata only; zero affected; expected under 250 ms, stop at five seconds.
- Locks/risk: brief MDL only.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-018 — deployed long-answer view definition

```sql
SHOW CREATE VIEW cip_stg.v_cip_answer_long;
```

- Target: `cip_stg.v_cip_answer_long` metadata and its referenced CIP tables.
- Purpose/output: compare the deployed view to `sql/002_views.sql` without executing it. One DDL text row, expected under 50 KiB.
- Cost/affected rows: metadata expansion only; zero affected; expected under 500 ms, stop at five seconds.
- Locks/risk: brief metadata locks on the view and referenced tables; no view rows read.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-019 — bounded candidate wave catalog

```sql
SELECT
    survey_id,
    study_type,
    wave_date,
    qualified_n,
    rows_built,
    prior_survey_id,
    ly_survey_id
FROM cip_stg.srv_wave
ORDER BY rows_built ASC, survey_id ASC
LIMIT 10;
```

- Target: `cip_stg.srv_wave` only.
- Purpose/output: nominate ten smallest serving waves without reading respondent rows. The owner must approve one returned ID before any plan query. Output contains no survey title, respondent identifier or answer. Exactly ten rows or fewer, under 5 KiB.
- Cost/affected rows: expected full scan and small sort of the wave catalog because `rows_built` is not known to be indexed; checked-in deployments contain hundreds, not millions, of wave rows. Live size remains unknown until SQL-012. Zero affected; expected under 250 ms, hard five-second SELECT limit.
- Locks/risk: consistent nonlocking read plus brief MDL-S. `LIMIT` bounds output, not scan; the table-size gate from SQL-012 must remain small. Stop instead of running if estimated `srv_wave.table_rows` exceeds 100,000.
- Class/status: **A bounded read — PROPOSED, NOT AUTHORIZED**.

### SQL-020 — observe CIP named-lock ownership without acquiring it

```sql
SELECT IS_USED_LOCK('cip_etl') AS cip_etl_owner_connection_id;
```

- Target: MySQL named-lock registry.
- Purpose/output: determine whether a CIP writer currently owns the application lock. One row.
- Cost/affected rows: constant lookup; zero affected; expected under 100 ms.
- Locks/risk: does not acquire or release the lock. If non-NULL, stop the batch before later plan work; do not inspect or kill the owner.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-021 — bounded shared-server health counters

```sql
SHOW GLOBAL STATUS
WHERE Variable_name IN (
    'Threads_connected',
    'Threads_running',
    'Connections',
    'Aborted_connects',
    'Created_tmp_tables',
    'Created_tmp_disk_tables',
    'Slow_queries',
    'Questions',
    'Uptime'
);
```

- Target: global status counters; no application table.
- Purpose/output: precheck server concurrency and record baseline cumulative counters. These values are not attributed to CIP or to an individual query. Expected nine rows.
- Cost/affected rows: in-memory status lookup; zero affected; expected under 100 ms.
- Locks/risk: no application-table lock. Results are operational metadata only. MySQL documents that `SHOW STATUS` itself increments `Created_tmp_tables`, so this snapshot cannot be used as an exact per-query temporary-table delta.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

### SQL-022 — MySQL event scheduler inventory for `cip_stg`

```sql
SELECT
    event_schema,
    event_name,
    status,
    event_type,
    execute_at,
    interval_value,
    interval_field,
    starts,
    ends,
    last_executed
FROM information_schema.events
WHERE event_schema = 'cip_stg'
ORDER BY event_name;
```

- Target: `information_schema.events` for `cip_stg` only.
- Purpose/output: establish whether MySQL-native events can overlap CIP jobs. Event bodies are deliberately excluded. Expected zero to a small number of rows.
- Cost/affected rows: metadata only; zero affected; expected under 250 ms, stop at five seconds.
- Locks/risk: no application data locks. External launchd/CI/cloud schedulers cannot be proven by this query and remain a separate code/owner check.
- Class/status: **A — PROPOSED, NOT AUTHORIZED**.

## Initial execution order and stop criteria

1. Connect with the client controls above.
2. Run SQL-001. Stop unless target identity is staging `cip_stg`.
3. Run SQL-002. Record whether privileges exceed inspection needs.
4. Run SQL-003 through SQL-007. Stop unless the verified values are exactly `autocommit=1`, `transaction_read_only=1`, `max_execution_time=5000`, `lock_wait_timeout=3`, `innodb_lock_wait_timeout=3`.
5. Run SQL-021 and inspect Azure read-only metrics. Stop on the documented resource thresholds.
6. Run SQL-020. Stop if `cip_etl` is owned.
7. Run SQL-008 through SQL-018 serially.
8. Run SQL-022.
9. Run SQL-019 only if SQL-012 confirms `srv_wave` is a small catalog. Return the ten candidates; do not select one autonomously.
10. Close the session. Return sanitized results and a new exact Class B manifest.

## Next-stage query fingerprints — not executable and not authorized

The following source-controlled families require plan validation after the owner approves a literal modest wave ID. They are intentionally not presented with a placeholder masquerading as runnable SQL.

| Family | Exact source | Tables | Required next evidence |
|---|---|---|---|
| Ten-column grouped cuts | `app/data/payloads.py:398-415` | `srv_answer`, then `srv_result`, `cip_question` | Nonexecuting plan for one approved wave; chosen index, estimated rows, grouping/temp-table strategy. Preserve MySQL collation semantics. |
| Respondent extraction | `app/data/payloads.py:365-395` | `srv_answer`, `srv_result`, `cip_question` | Nonexecuting plan for the same wave; projected row width and expected rows sent. No respondent rows returned in staging diagnostics. |
| Serving join | `etl/serving.py:103-125` | `cip_agg_cell`, `cip_question`, `cip_item`, `cip_option`, `cip_concept_map` | Nonexecuting plan first for the approved wave, then a separately approved current/prior/LY literal list if needed. |
| Label-cleanup predicate | `etl/run_pipeline.py:385-400` | `cip_answer`, `cip_field`, `cip_option`, `cip_item` | Read-only, predicate-equivalent `EXPLAIN FORMAT=JSON SELECT a.answer_id ...`; do not issue `EXPLAIN UPDATE` with a write identity in the first plan stage. |
| Qualtrics replacement predicates | `etl/run_pipeline.py:141-225` | `cip_respondent`, `cip_answer`, child tables | Read-only plans for survey-keyed selects/deletes using the approved literal ID; actual delete/reload only on disposable MySQL 8. |
| Historic view count | `sql/002_views.sql:216-235`; no current caller | `v_cip_answer_long` and underlying tables | Owner/caller requirement first. A plan-only request may follow; the actual full count remains rejected. |

## Rejected or deferred SQL/actions

| Statement/action | Decision and reason |
|---|---|
| Actual `srv_answer` grouped SELECT | **Deferred Class C.** It can scan/group the wave and historically ran for minutes. First obtain metadata, a literal approved wave, nonexecuting plan, Azure headroom and a separate budget. |
| Actual respondent extraction from `srv_answer` | **Deferred Class C.** It returns respondent-level rows and is unnecessary for plan validation. A staging benchmark needs separate privacy and byte/row approval. |
| Actual `cip_agg_cell` serving SELECT | **Deferred Class C.** Obtain a nonexecuting plan first; never use an unbounded multi-wave list. |
| `SELECT COUNT(*) FROM cip_stg.v_cip_answer_long` | **Rejected.** Historic execution was about 530 seconds and examined roughly 36 million rows; no current owner/caller is proven. |
| `EXPLAIN ANALYZE ...` | **Rejected on shared staging.** It executes the query. |
| `ANALYZE TABLE`, `OPTIMIZE TABLE`, histogram changes | **Rejected in this stage.** They change shared metadata/statistics or can take consequential locks. |
| Any `CREATE INDEX`, including `(survey_id,qcode)` on `srv_answer` | **Rejected.** DDL is unapproved and that pair is already the checked-in PK left prefix. Live structure must be verified first. |
| Any `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `ALTER`, `DROP`, migration, `LOAD DATA`, cube/serving rebuild, reload or publisher invocation | **Rejected in this stage.** Class D work requires a separate manifest and normally a disposable MySQL 8 clone. |
| `SELECT GET_LOCK('cip_etl', ...)` or `DO RELEASE_LOCK('cip_etl')` | **Rejected.** Inspection must not acquire or release the application writer lock. SQL-020 observes only. |
| `SHOW FULL PROCESSLIST` or unrestricted `performance_schema` statement history | **Rejected.** It can expose unrelated tenants' SQL and parameter values. |
| `KILL`, `KILL QUERY`, or Azure session termination | **Not pre-authorized.** Escalate only for the recorded inspection connection and obtain DBA confirmation; never target another session automatically. |
| Global `SET`, server parameter changes, Azure configuration changes | **Rejected.** Only SQL-003 through SQL-006 alter the current disposable session. |
| Replaying the 681 historic grouped statements or all-wave ETL/publication | **Rejected.** It is unnecessary and risks repeating shared-server harm. |
| SIP, MIP, ChainXY or other-product queries | **Out of scope and rejected.** Only the listed `cip_stg` metadata and catalog query are proposed. |

## Exact approval request

Approve only SQL-001 through SQL-022, executed once each in the documented order and envelope. Approval does not include any plan query, data benchmark, respondent extraction, DML, DDL, `EXPLAIN ANALYZE`, ETL/publisher/scheduler invocation, deployment, service restart, notification, cancellation of another session, or access to another schema.

Suggested approval text:

> I approve only SQL-001 through SQL-022 from `00_SQL_EXECUTION_APPROVAL_MANIFEST.md`, once each, serially, against Azure MySQL staging schema `cip_stg`, within the documented connection, timeout, monitoring and stop limits. I do not approve any other SQL, plan query, DML, DDL, ETL, publisher, scheduler, deployment, notification or cross-product action. Stop and report if any identity, guardrail, lock, cost or resource check fails.

## Syntax references

- MySQL 8.0 server variables and `transaction_read_only` / `max_execution_time`: https://dev.mysql.com/doc/refman/8.0/en/server-system-variables.html
- MySQL `SET TRANSACTION` session scope and read-only restrictions: https://dev.mysql.com/doc/refman/8.0/en/set-transaction.html
- MySQL `innodb_lock_wait_timeout`: https://dev.mysql.com/doc/refman/8.0/en/innodb-parameters.html
- MySQL `SHOW STATUS` syntax and counter scope: https://dev.mysql.com/doc/refman/8.0/en/show-status.html
