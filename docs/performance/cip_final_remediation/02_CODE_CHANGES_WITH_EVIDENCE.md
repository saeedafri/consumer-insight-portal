# CIP final remediation — code changes with evidence

Date: 2026-10-27  
Repository: `consumer-insight-portal`  
Base HEAD: `6f978b0595b2c71c064991ae10b832514637a0da`  
State: local uncommitted patch

## Change matrix

| Decision | Area | Before | After | Evidence / rollback |
|---|---|---|---|---|
| FIXED LOCALLY | Analysis fixtures | Test execution depended on an unrelated ignored DB marker; application engines used an empty DB. | Real schema plus deterministic two-wave synthetic seed. | 13/13 pass; clean/no-marker and dummy-marker runs. Revert `tests/analysis_fixture.py` and `tests/test_analysis.py`. |
| FIXED LOCALLY | Trend fixtures | Copied ignored `data/csi_local.db`. | Two synthetic waves in `csi_db`. | 2/2 pass without marker. Revert `tests/test_trends_multiwave.py`. |
| FIXED LOCALLY | Test isolation | Live `.env` values could be imported before fixtures; socket/message protection was incomplete. | Local SQLite and blank integrations before imports; TCP/UDP blocked; SMTP/Teams mocked. | `tests/test_test_isolation.py`; full suite green. Revert test-only files. |
| FIXED LOCALLY | Forsta labels | Every coded row stored a label, then a wave-wide cleanup UPDATE cleared derived labels. The first optimization cleared multi labels too. | Single/grid metadata labels remain NULL; multi item label is retained only when option metadata could override it. Forsta skips the cleanup UPDATE. | View output, case/accent/spacing, unknown code and multi Yes/No regression tests. Revert `_answer` and `drop_labels=False`. |
| FIXED LOCALLY | Reconciliation | Selected only code/number/text; label-only coded values were treated as equal. | Selects and compares `value_label`. | Changed synthetic label is detected. Revert tuple/query hunk in `reconcile_survey`. |
| FIXED LOCALLY | Forsta shrink/empty | Shrink performed a redundant survey-wide answer delete before the normal replacement; empty `people` executemany failed. | One answer delete remains inside one transaction; empty respondent batches are skipped; child and derived rebuilds tested. | FK, rollback, idempotency, full shrink and empty reload tests. Revert `_write` hunks. |
| FIXED LOCALLY | Qualtrics import | One transaction, respondent upsert, ID lookup and answer upsert per respondent; removed cells/respondents could persist. | `_replace_respondents` performs batched respondent upsert, one ID lookup, one answer replacement, ordered missing-child cleanup and one bulk answer load in one transaction. | Exact output hashes; shrink/empty/rollback tests; benchmark below. Revert `qualtrics_export.py` call and remove `_replace_respondents`. |
| FIXED LOCALLY | Publisher workers | Fixed default argument; no environment control/range guard. | CLI argument > `CIP_PUBLISH_JOBS` > default 4; range 1–4. `.env.example` documents it. | Precedence/invalid-value tests. Revert `worker_count` and config line. |
| FIXED LOCALLY | Serving workers | `build_all` accepted arbitrary thread counts. | 1–4 validator; default remains 1. | Unit coverage for bounds. Revert `serving_worker_count`. |
| FIXED LOCALLY | Publisher memory/telemetry | Grouped cuts and respondent bitsets coexisted; `query_count=2` looked measured; one whole-wave timer was attributed to a query fingerprint. | Writes/releases cuts before people; logs expected reads, configured/effective workers, group count, two read/build phases and wall time. | Canonical payload tests and log assertions. RSS reduction was not demonstrated; see benchmark. |
| FIXED LOCALLY | Publisher discovery | `SELECT DISTINCT w.survey_family, w.study_type, r.qcode FROM srv_result r JOIN srv_wave w ...`. | Enumerates complete, versioned `waves/<sid>/cuts/*.json.gz`; `cut_inventory` rule forces a safe first rebuild. | SQL spy: 1 discovery query to 0; exact artifact hashes; stale-question and invalidation tests. Revert inventory block/rule. |
| FIXED LOCALLY | MCP crosstab | MCP always called live `payloads.crosstab`, even when the same cuts were published. | HTTP and MCP share `_crosstab_payload` and serving-version cache; absent/incomplete files retain live fallback. | ASGI test fails on any DB access and still returns MCP result; fallback test passes. Revert `api/main.py`, `api/mcp.py`. |
| FIXED LOCALLY | Qualtrics writer overlap | CLI lacked the repository MySQL named lock. | CLI wraps ingest in `etl_lock`; direct function remains composable for tests. | Static caller trace and existing lock tests. Revert `main` hunk. |

## SQL and data contracts

### MySQL grouping is unchanged

`app/data/payloads.py::question_cuts` still executes:

```sql
SELECT survey_id, qcode, item_id, option_id, <six cuts>, COUNT(*)
FROM srv_answer
WHERE survey_id IN (...)
GROUP BY survey_id, qcode, item_id, option_id, <six cuts>
```

There is no Python tuple/dictionary grouping replacement. This preserves `utf8mb4_0900_ai_ci` behavior. SQLite tests prove payload structure and arithmetic, not MySQL collation equivalence.

### Forsta answer replacement

Before shrink path:

```sql
DELETE FROM cip_answer WHERE survey_id = :s; -- early
DELETE FROM child tables for removed respondents;
DELETE FROM cip_answer WHERE survey_id = :s; -- normal replacement
```

After:

```sql
DELETE FROM child tables for removed respondents;
DELETE FROM cip_answer WHERE survey_id = :s; -- exactly once
bulk insert replacement answers;
```

All statements remain inside one `engine.begin()` transaction. Checked-in FKs cascade `cip_answer`, `cip_profile`, `cip_weight` and `cip_respondent_cohort`; `cip_tracker_line` and `srv_answer` are rebuilt by the full load and explicitly tested.

### Qualtrics snapshot

Before: `O(respondents)` transactions and ID lookups, answer upserts, no full stale-row cleanup.

After: one transaction containing one respondent executemany, one respondent map SELECT, one survey answer DELETE, missing respondent cleanup and one bulk answer insert. Downstream profile/base/cube behavior is unchanged.

## Explicitly not changed

- No index, schema migration, DDL or MySQL setting change.
- No Python grouping for `srv_answer`.
- No change to publisher default four workers.
- No `cip_agg_cell` SQL rewrite without a MySQL plan.
- No `v_cip_answer_long` summary/index without a confirmed caller.
- No deployment, scheduler, cloud or shared DB change.

## Review files

- Source/test patch: [CIP_FINAL_REVIEW_PATCH.diff](CIP_FINAL_REVIEW_PATCH.diff)
- Measurements: [03_BENCHMARK_BEFORE_AFTER.md](03_BENCHMARK_BEFORE_AFTER.md)
- Release/rollback: [06_RELEASE_AND_ROLLBACK_GATE.md](06_RELEASE_AND_ROLLBACK_GATE.md)
