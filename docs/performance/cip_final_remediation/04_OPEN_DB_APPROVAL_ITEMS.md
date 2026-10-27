# CIP final remediation — open DB and approval items

Date: 2026-10-27  
Repository: `consumer-insight-portal`  
Base HEAD: `6f978b0595b2c71c064991ae10b832514637a0da`  
State: uncommitted local patch  
Cross-links: [verdict](00_EXECUTIVE_VERDICT.md), [benchmarks](03_BENCHMARK_BEFORE_AFTER.md), [release gate](06_RELEASE_AND_ROLLBACK_GATE.md)

No request below was executed. All shared-DB work requires explicit authorization and a read-only account unless separately stated.

## 1. Deployed schema contract — BLOCKED BY DBA APPROVAL

Purpose: confirm checked-in assumptions, not change schema.

Requested read-only metadata:

```sql
SHOW FULL COLUMNS FROM srv_answer;
SHOW INDEX FROM srv_answer;
SHOW INDEX FROM srv_result;
SHOW INDEX FROM cip_agg_cell;
SHOW INDEX FROM cip_answer;

SELECT table_name, constraint_name, column_name, referenced_table_name, referenced_column_name
FROM information_schema.key_column_usage
WHERE table_schema = DATABASE()
  AND table_name IN ('cip_answer','cip_profile','cip_weight','cip_respondent_cohort','srv_answer');

SELECT trigger_name, event_object_table, action_timing, event_manipulation
FROM information_schema.triggers
WHERE trigger_schema = DATABASE()
  AND event_object_table LIKE 'cip\_%';
```

Acceptance: `srv_answer` text columns use `utf8mb4_0900_ai_ci`; FK/delete behavior matches checked-in schema; no unreviewed triggers alter reload semantics; no redundant `(survey_id,qcode)` index is proposed because the primary key already has that left prefix.

## 2. Bounded `cip_agg_cell` plan — BLOCKED BY DBA APPROVAL

Run `EXPLAIN FORMAT=JSON`, never `EXPLAIN ANALYZE`, for `etl/serving.py::cube_rows` on one approved modest wave and its current/prior/LY IDs. Capture chosen indexes, estimated examined rows, join order and temporary-table flags. Also capture `SHOW INDEX` cardinalities.

Decision rule: propose a SQL/index change only if the deployed plan demonstrates a selective mismatch and a disposable MySQL 8 parity test proves exact row/cardinality output. No index is currently proposed.

## 3. `srv_answer` publisher validation — BLOCKED BY APPROVAL

On an approved isolated MySQL 8 clone or explicitly approved modest staging wave:

- Run publisher jobs 1, 2 and 4 one at a time.
- Capture two `srv_answer` reads per fresh wave, elapsed p50/p95, rows sent/examined, process RSS, server CPU/IOPS/temp-table counters and output hashes.
- Confirm case/accent/trailing-space grouping under `utf8mb4_0900_ai_ci`.
- Attribute whether the historic 681 grouped statements came from publisher, HTTP fallback, MCP before this patch, retries or another caller.

Do not replay the historic monster queries on shared staging.

## 4. Qualtrics MySQL gate — BLOCKED BY APPROVAL

Use a disposable MySQL 8 database or approved anonymized clone. Validate:

- Fresh, same-file, shrinking, removed-cell, empty and injected-failure snapshots.
- One transaction for the respondent/answer snapshot.
- `LOAD DATA LOCAL INFILE` warning behavior and fallback.
- Exact hashes/counts versus base semantics.
- FK/trigger behavior and transaction rollback.

SQLite evidence is strong but does not prove MySQL `LOAD DATA`, collation or isolation behavior.

## 5. External label consumers — OWNER CONFIRMATION REQUIRED

Repository consumers reconstruct coded single/grid labels with metadata; multi values retain item labels when needed. Confirm that no external direct-table consumer requires denormalized `cip_answer.value_label` for known single/grid codes. If one does, gate the optimization or provide that consumer a documented view contract.

## 6. `v_cip_answer_long` historic count — OWNER/DBA CONFIRMATION REQUIRED

No current application caller was found. Identify the owner, count semantics and required freshness before considering a summary table, narrower query or index. Until then: `NO SAFE FIX PROVEN`.

## 7. Scheduler and capacity — OWNER/DBA/IT APPROVAL REQUIRED

- Decide whether production sets `CIP_PUBLISH_JOBS`; default remains 4.
- Verify the weekly wrapper, ad-hoc CLIs and any external schedulers cannot overlap outside the `cip_etl` named lock.
- Add shared observability for lock contention and actual active DB connections before changing capacity.
- Review still-unlocked manual mutation paths separately; do not alter shared schedules in this patch.

## Rollback of proposed validation

All requests above are read-only except a future isolated benchmark. End read-only sessions after capture. An isolated clone/container must be disposable. No shared schema rollback is needed because this patch executes no DDL.
