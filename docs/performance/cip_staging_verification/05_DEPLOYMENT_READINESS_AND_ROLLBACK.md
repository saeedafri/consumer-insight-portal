# CIP deployment readiness and rollback

Date: 2026-10-27  
Decision: **NO-GO FOR DEPLOYMENT; PASS FOR LOCAL CODE REVIEW**

## Ready for review

- Stage 1 metadata evidence is complete and sanitized.
- Stage 2 captured all seven approved nonexecuting plans without a timeout, lock conflict or write.
- Stage 3 captured the additional cube plans and completed disposable MySQL 8 correctness, concurrency and failure tests.
- Local session/pool/retry safeguards are implemented.
- Full isolated suite passes 360 tests.
- No survey calculation/grouping semantics changed.
- No Python replacement for MySQL grouping exists.

## Blocking deployment

- SQL-042 and the optimized concept-query plan remain pending approval.
- The proposed `cip_agg_cell(survey_id,dim,cohort_id,question_id)` index has local evidence only and requires DBA review.
- No underlying expensive staging SELECT has run; Stage 2 plan costs are estimates, not before/after timings.
- The exact historic `cip_agg_cell` fingerprint/caller is still unidentified; the current one-wave plan is efficient.
- No dedicated `APP_DB_USER` is configured in the current local environment; the fallback identity has broad privileges.
- Aggregate pool capacity across deployment processes is unknown.
- No MySQL canary validates the new 180/600-second SELECT budgets against legitimate workloads.
- No staging deployment or one-wave canary is approved.

## Rollback of local safeguards

No database rollback is needed because no schema/data change occurred.

Code rollback consists of reverting only these local hunks:

- Per-role timeout/session construction and `api_write` pool in `app/core/database.py`.
- Bounded pool validation in `app/core/config.py` and `.env.example`.
- `api_write` role selection in `app/core/audit.py`, `api/team.py`, and `api/signin.py`.
- 1205/1213 retry/backoff change in `etl/serving.py`.
- Associated test additions.

Do not reset or discard unrelated working-tree changes. No automatic Git operation is authorized.

## Future canary criteria

- Dedicated approved small wave, one worker, one job.
- Correct release revision and environment confirmed.
- Existing published version retained as last known good.
- Exact counts, denominators, labels, cuts, bitsets and output hashes match expected values.
- Abort on query budget, lock wait, pool exhaustion, numerical drift or incomplete artifacts.
- Promotion remains explicit; failed/partial build is removed and never becomes current.
