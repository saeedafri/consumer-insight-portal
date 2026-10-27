# CIP staging Stage 1 metadata results

Date: 2026-10-27  
Target: Azure MySQL staging `cip_stg`  
Approval executed: SQL-001–018 and SQL-020–022  
Excluded: SQL-019 and every heavy/data query  
Outcome: **21/21 approved statements succeeded; connection closed**

Sanitized machine-readable evidence: [STAGE1_SANITIZED_RESULTS.json](evidence/STAGE1_SANITIZED_RESULTS.json)

## Execution safety and identity

- One direct PyMySQL connection; no SQLAlchemy pool and no retry.
- TLS CA validation enabled; `local_infile` disabled.
- Client budgets: connect 5 seconds, read/write 10 seconds.
- Server identity: MySQL `8.0.46-azure`, port 3306, database exactly `cip_stg`. Host, account and connection ID are SHA-256 pseudonyms in the evidence file.
- Initial session: autocommit `1`, transaction read-only `0`, `max_execution_time=0`, `lock_wait_timeout=31536000`, `innodb_lock_wait_timeout=50`.
- Verified guarded session before table access: autocommit `1`, transaction read-only `1`, `max_execution_time=5000`, `lock_wait_timeout=3`, `innodb_lock_wait_timeout=3`.
- `IS_USED_LOCK('cip_etl')` returned `NULL`; no CIP writer held the application lock.
- Connection was closed after SQL-022. No transaction remained open.
- SQL-019 was not executed.

The inspection identity has `ALL PRIVILEGES` on `cip_stg`, not a database-enforced read-only grant. Session read-only mode and an exact statement allowlist were therefore essential. It also has permissions on other shared schemas; those scopes are redacted from the evidence and were not accessed.

## Statement ledger

| SQL | Result rows | Elapsed ms | Result |
|---|---:|---:|---|
| SQL-001 | 1 | 252.637 | Identity and initial settings confirmed. |
| SQL-002 | 6 | 241.448 | Grants retrieved; broader than inspection needs. |
| SQL-003 | 0 | 229.773 | Session transaction read-only enabled. |
| SQL-004 | 0 | 249.463 | SELECT deadline set to 5,000 ms. |
| SQL-005 | 0 | 231.632 | Metadata-lock wait set to 3 seconds. |
| SQL-006 | 0 | 229.431 | InnoDB row-lock wait set to 3 seconds. |
| SQL-007 | 1 | 229.773 | All guard values verified. |
| SQL-020 | 1 | 237.060 | CIP ETL named lock was free. |
| SQL-021 | 9 | 231.711 | Status counters captured. |
| SQL-008 | 176 | 299.687 | Columns/collations captured. |
| SQL-009 | 96 | 1,723.479 | Indexes/cardinality captured; slowest metadata statement. |
| SQL-010 | 28 | 267.591 | FK rules captured. |
| SQL-011 | 0 | 236.881 | No affected-table triggers. |
| SQL-012 | 15 | 231.753 | InnoDB size/row estimates captured. |
| SQL-013 | 1 | 229.082 | `srv_answer` DDL captured. |
| SQL-014 | 1 | 234.581 | `cip_agg_cell` DDL captured. |
| SQL-015 | 1 | 230.252 | `cip_answer` DDL captured. |
| SQL-016 | 1 | 244.852 | `srv_result` DDL captured. |
| SQL-017 | 1 | 229.864 | `srv_wave` DDL captured. |
| SQL-018 | 1 | 282.043 | View DDL captured; definer redacted. |
| SQL-022 | 0 | 307.293 | No `cip_stg` MySQL events. |

All statements affected zero rows. There were no MySQL errors, timeouts or missing permissions. The local `.env` loader emitted four parse warnings for unrelated lines; database keys parsed and the guarded connection succeeded. The malformed lines should be corrected separately without printing their contents.

## Pressure snapshot

| Counter | Value | Interpretation |
|---|---:|---|
| Threads running | 5 | Below the declared stop threshold of 8. |
| Threads connected | 36 | Snapshot only; maximum connection capacity was not queried. |
| Connections | 1,257,884 | Cumulative since server start. |
| Aborted connects | 16,623 | Cumulative; not attributed to CIP. |
| Slow queries | 136,978 | Cumulative; not attributed to CIP. |
| Created temporary tables | 12,175,076 | Cumulative; `SHOW STATUS` itself increments this counter. |
| Created disk temporary tables | 90,117 | Cumulative; not proof any individual CIP query spilled. |
| Questions | 164,395,287 | Cumulative. |
| Uptime | 1,941,925 seconds | Context for cumulative counters. |

The snapshot was safe enough to continue metadata inspection. It is not a performance benchmark and does not replace Azure CPU/I/O telemetry.

## Live table sizes

InnoDB `TABLE_ROWS` values are estimates, not correctness counts.

| Table | Estimated rows | Data | Indexes | Main finding |
|---|---:|---:|---:|---|
| `cip_answer` | 27,796,732 | 2.58 GiB | 3.27 GiB | Largest CIP fact table; survey-leading covering index exists. |
| `srv_answer` | 12,061,859 | 1.19 GiB | clustered PK | Only the five-column PK exists. |
| `cip_agg_cell` | 2,789,342 | 687 MiB | 763 MiB | Multiple overlapping indexes; plan required before adding another. |
| `srv_result` | 2,225,030 | 485 MiB | 308 MiB | PK starts with survey/question/dimension. |
| `cip_respondent` | 194,818 | 33.6 MiB | 50.2 MiB | Survey-qualified and uniqueness indexes exist. |
| `cip_profile` | 188,337 | 30.6 MiB | 25.1 MiB | Survey/cut indexes exist. |
| `cip_concept_map` | 98,139 | 8.5 MiB | 31.1 MiB | Unique `(survey_id,map_key)` prevents ordinary serving fanout. |
| `srv_wave` | 368 | 48 KiB | 16 KiB | Tiny catalog; no `rows_built` index. |

## Actual structures and indexes

### `srv_answer`

- PK: `(survey_id, qcode, item_id, option_id, respondent_id)`.
- No secondary index.
- Seven text dimensions, including `qcode`, use `utf8mb4_0900_ai_ci`.
- FK: `survey_id -> srv_wave.survey_id ON DELETE CASCADE`.
- Decision: do not add redundant `(survey_id,qcode)`. The existing PK already provides that left prefix.

### `cip_agg_cell`

- PK: `cell_id`.
- Unique: `(survey_id, cell_key)`.
- `ix_agg_question (survey_id, question_id, dim)`.
- `ix_agg_map (survey_id, map_key, cohort_id, dim)`.
- `ix_agg_concept (concept_option_id, cohort_id, dim, survey_id)`.
- MySQL-created FK support index: `fk_agg_question (question_id)`.
- Cascades to survey and question.
- Several reported cardinalities are implausible (`concept_option_id` cardinality 1; survey cardinalities much higher than the 368-wave catalog). Treat optimizer estimates as suspect until the plans are captured. Do not run `ANALYZE TABLE` without separate approval.

### `cip_answer`

- PK: `answer_id`.
- Unique: `(respondent_id, field_id)`.
- Covering survey index: `(survey_id, field_id, value_code, respondent_id)`.
- FK support index: `field_id`.
- Answer rows cascade when respondent or field is deleted.
- All label/text columns use `utf8mb4_0900_ai_ci`.

### `srv_result`

- PK: `(survey_id, qcode, dim, dim_value, item_id, option_id)`.
- Secondary: `(concept_option_id, dim, dim_value, survey_id)`.
- FK: `survey_id -> srv_wave.survey_id ON DELETE CASCADE`.
- Live `flags` contains both `sig_prior` and `sig_ly`; checked-in serving upgrade is present.

### `srv_wave`

- PK: `survey_id`.
- Secondary: `(survey_family, wave_date)`.
- No index on `rows_built`.
- `in_field` is deployed.
- FK: `survey_id -> cip_survey.survey_id ON DELETE CASCADE`.

## Collation and FK conclusions

- Every inspected CIP textual grouping/join column uses `utf8mb4_0900_ai_ci`.
- MySQL therefore groups case/accent variants according to that collation. The SQL aggregation path must remain authoritative; naive Python tuple grouping remains prohibited.
- `srv_answer`, `srv_result`, answer/profile/weight/cohort rows and aggregate rows have the cascade behavior assumed by current reload/rebuild code.
- No triggers exist on the 15 affected tables. No hidden trigger writes alter reload behavior.
- No MySQL-native `cip_stg` events exist. External schedulers remain an operational inventory item.

## SQL-019 safety decision

`srv_wave` has approximately 368 rows and 48 KiB of data. Its only indexes are the PK and `(survey_family,wave_date)`; therefore:

```sql
SELECT survey_id, study_type, wave_date, qualified_n, rows_built,
       prior_survey_id, ly_survey_id
FROM cip_stg.srv_wave
ORDER BY rows_built ASC, survey_id ASC
LIMIT 10;
```

will scan the tiny catalog and perform a filesort because no index starts with `rows_built`. `LIMIT 10` bounds output, not the scan. At 368 rows this is low risk: expected scan under 400 rows, output at most 10 rows/<5 KiB, and expected execution under 100 ms with a 5-second server deadline.

No `rows_built` index is justified for a 368-row table. SQL-019 is safe to propose unchanged, but it remains unexecuted pending separate approval.
