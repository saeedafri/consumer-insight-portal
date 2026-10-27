# CIP SQL root-cause and index decisions after Stage 1

Date: 2026-10-27  
Evidence level: live schema/index/collation metadata; no heavy SELECT or execution plan yet

## Decisions

| Family | What Stage 1 proves | What remains unknown | Decision now |
|---|---|---|---|
| `srv_answer` grouped cuts | 12.1M estimated rows; PK starts `(survey_id,qcode,item_id,option_id,respondent_id)`; all grouped strings are `utf8mb4_0900_ai_ci`; no secondary index. | Selected range and grouping strategy for a real wave; in-memory vs disk temporary-table behavior; historic caller split. | Preserve MySQL aggregation. Do not add `(survey_id,qcode)`. Capture nonexecuting plan next. |
| `srv_answer` extraction | Survey-keyed PK range exists. The query projects respondent ID plus answer/cut columns and can transfer every answer row for a wave. | Actual estimated rows/width for a representative wave and whether transfer, network or Python memory dominates. | Plan next. No index can remove required returned rows. Streaming/reuse requires output-parity and memory evidence. |
| `cip_agg_cell` serving join | 2.79M estimated rows; 763 MiB indexes; survey/question/map indexes and unique concept map key exist. Some cardinalities are implausible. | Actual join order, chosen index, row estimates and fanout for a wave. | No new index or SQL rewrite until `EXPLAIN FORMAT=JSON`. `ANALYZE TABLE` remains unapproved. |
| `cip_answer` label cleanup | 27.8M estimated rows; `(survey_id,field_id,value_code,respondent_id)` index exists; metadata labels use the same collation; no triggers. | Rows matched for one Qualtrics/legacy wave and MySQL update duration/locking. | Forsta cleanup remains removed. Plan the read-equivalent predicate; no staging update. |
| Qualtrics replacement | Survey-leading `cip_answer` and respondent indexes exist; delete cascades for answer/profile/weight/cohort are deployed; no triggers. | Actual transaction duration, `LOAD DATA`, rollback and lock behavior. | Test writes only on disposable MySQL 8. Plan survey-keyed reads next. |
| `srv_result` | 2.23M estimated rows; PK starts `(survey_id,qcode,dim,...)`; significance flags deployed. | Plan for the total-label lookup, though it is not the dominant historic family. | Plan as part of the grouped-cut call path. No index proposed. |
| `srv_wave` discovery | Only 368 estimated rows/48 KiB; no `rows_built` index. | Exact candidate wave IDs because SQL-019 was not approved. | SQL-019 full scan/filesort is safe; no index warranted. Request separate approval. |
| `v_cip_answer_long` count | Deployed view matches the checked-in multi-join definition. | External owner, required semantics/freshness and plan. | Actual count rejected. Defer even plan work until owner is identified. |

## Confirmed root causes or risks

1. **Unsafe default session waits are real.** The live initial connection had no SELECT deadline, a 365-day metadata-lock wait and a 50-second InnoDB lock wait. This can turn application mistakes into long visible stalls.
2. **Least privilege is absent for the available account.** It has all privileges on `cip_stg` and access to other shared schemas. Application configuration currently has no separate `APP_DB_USER`, so the read path can fall back to the writer account.
3. **The grouped-cut cost is not a missing filter index.** The existing primary key already serves survey/question ranges. The remaining likely cost is grouping many range rows by six collation-aware text cuts; the exact optimizer plan remains unverified.
4. **The respondent extraction is inherently transfer-heavy.** Its existing index can locate a wave, but the caller requests row-level answers and cuts. An added lookup index cannot eliminate output volume.
5. **Optimizer statistics require skepticism.** Reported leading-column cardinalities exceed the 368-wave catalog by orders of magnitude, while one concept cardinality is reported as 1. This does not authorize a statistics refresh; it increases the need for actual plans and bounded representative tests.
6. **The API read engine was also used for writes.** Its AUTOCOMMIT optimization meant `engine.begin()` did not provide the intended DBAPI transaction semantics. Local remediation moves those writes to a separate transactional engine.

## Index decisions

### Rejected now

- `srv_answer(survey_id,qcode)`: redundant PK prefix.
- `srv_wave(rows_built)`: 368 rows do not justify write/storage overhead.
- Any wide `srv_answer` grouping index: it would be large, duplicate PK columns, increase serving-build writes, and remains unproven.
- Any new `cip_agg_cell` index: the table already carries approximately 763 MiB of indexes; join plan evidence is required.
- `ANALYZE TABLE`: changes shared optimizer statistics and requires separate approval.

### Possible only after plan evidence

- A `cip_agg_cell` index beginning `(survey_id, cohort_id, ...)` if the plan proves current indexes examine substantial cohort rows and a disposable MySQL 8 benchmark proves lower writes/reads with exact output parity.
- A narrower publication data path if plans and MySQL benchmarks prove the second `srv_answer` read, transfer or memory is dominant and canonical output hashes remain identical.

## Historical attribution boundary

Current code proves the grouped query can originate from the publisher and live crosstab fallback. Stage 1 metadata does not prove which caller generated most of the 681 historical statements, how many were retries, or which deployed revision ran. No dominant-caller claim is made.
