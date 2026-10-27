# CIP database and infrastructure approval requests

Date: 2026-10-26  
Nothing in this file was executed.

## 1. Read-only staging plan capture

Approval needed: DBA/security owner for an explicitly read-only account/session and a quiet window.

Purpose:

- verify current deployed schema/indexes and revision;
- obtain `EXPLAIN FORMAT=JSON` for the current `cip_agg_cell` serving join and publisher discovery query;
- verify whether the app-role account is read-only;
- observe temp-table counters without replaying historic multi-minute statements.

Proposed safeguards:

1. Verify `CURRENT_USER()` and `SHOW GRANTS`; stop if any planned connection identity is ambiguous.
2. Start a read-only transaction where supported.
3. Use `EXPLAIN FORMAT=JSON`, never `EXPLAIN ANALYZE`, for large-table queries.
4. Bind one approved modest survey ID; do not run all-history/full-size SQL.
5. Capture only plans/counters. Do not select respondent-level answers or log parameter values.
6. Stop if the plan estimate or metadata lock wait is abnormal.

No DDL, DML, session/global tuning, cache purge, scheduler action, or notification is part of this request.

## 2. Controlled publisher worker benchmark on approved data

Approval needed: CIP owner and DBA for shared staging load; deployment owner if the local patch must be staged.

Run the same approved wave/data revision at `CIP_PUBLISH_JOBS=1`, `2`, and `4`, one run at a time, using a separate local output directory. Capture:

- job wall time;
- per-wave fingerprint count and rows from the new privacy-safe logs;
- database statement count and cumulative elapsed time;
- connection count, temp-table counters, and resource telemetry;
- output digests/parity against the approved reference build.

Acceptance requires exact payload parity and lower/acceptable shared-resource impact. SQLite favored one worker, but no default change should be approved from that result alone.

Rollback: restore `CIP_PUBLISH_JOBS=4`; no schema change is involved.

## 3. `cip_agg_cell` index/query decision

Approval needed: DBA after plan capture.

Candidate only—not a ready DDL recommendation: an index beginning with `survey_id` and `cohort_id` may help the serving join exclude cohort rows, but the exact suffix/order must follow actual selectivity and plan evidence. Existing indexes are:

- `(survey_id, question_id, dim)`;
- `(survey_id, map_key, cohort_id, dim)`;
- `(concept_option_id, cohort_id, dim, survey_id)`;
- unique `(survey_id, cell_key)`.

Required before approval:

- read-only plan for modest and large approved waves;
- cardinality/selectivity by `survey_id`, `cohort_id`, and `dim`;
- isolated clone build-time and write-amplification measurement;
- exact DDL, online/locking behavior, disk estimate, rollback DDL, and post-change parity.

Do not add `(survey_id,qcode)` to `srv_answer`; it duplicates the primary-key prefix.

## 4. Publisher discovery query

Approval needed: read-only staging plan/benchmark.

Candidate application change: select distinct `(survey_id,qcode)` from `srv_result`, then map family/study from the publisher's already-loaded `waves` dictionary. This may remove the `srv_wave` join but could transfer more intermediate pairs. Adopt only if same-data measurements show lower cost and identical rebuilt-question selection, including dropped-question cases.

## 5. `v_cip_answer_long` count ownership

Approval/coordination needed: identify the analyst/job/report that issued the 529.817-second all-history count and its required semantics.

Questions:

- Is the requirement exact answer rows, qualified respondents, waves, or a freshness check?
- Can it be bounded by survey/date/concept as the view documentation requires?
- Is a validated existing summary table sufficient?

Do not create a materialized table/index or schedule a refresh before these are answered.

## 6. Deployment and scheduler

Approval needed before any deployment, service restart, scheduler edit, CI trigger, or shared run.

Proposed deployment sequence after review:

1. Review local diff and test/benchmark evidence.
2. Deploy to an isolated instance, not live `127.0.0.1:8000`.
3. Run a notification-disabled, read-only publication against approved data and a local output root.
4. Compare payload hashes and operational counters.
5. Schedule production rollout with explicit rollback to the prior application revision.

No shared service was restarted and no live scheduler was touched during this work.

