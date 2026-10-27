# CIP re-audit deployment gate

## Decision

**PASS FOR REVIEW ONLY**

The corrected patch appears behaviorally correct on the available isolated evidence. It is not approved for deployment. Shared MySQL performance, historic caller attribution, external direct-table consumers and owner/DBA capacity remain unverified.

## What is genuinely better

- Forsta no longer writes metadata-derived labels and then clears them with a large update.
- A shrinking reload performs one survey-wide answer delete rather than two.
- FK-enabled tests prove child cleanup, rollback and idempotent rerun behavior against the checked-in schema.
- Publisher worker count is explicit, bounded, configurable and recorded in the manifest.
- Per-wave publisher timing/fingerprint logging excludes parameters, respondent identifiers and answers.
- Tests fail closed against known live integration configuration and Python socket routes.

There is no proven publisher query-count, latency or memory improvement. The unsafe Python grouping optimization and its 33.5% claim were retracted.

## Still slow or unchanged

- Publisher and live ad-hoc crosstabs still use the original `srv_answer` multidimensional `GROUP BY`.
- `cip_agg_cell` serving joins are unchanged.
- `srv_result`/`srv_wave` publisher discovery is unchanged.
- `v_cip_answer_long` count behavior is unchanged and has no identified current code caller.
- `LOAD DATA LOCAL INFILE`, imports and `cip_agg_cell INSERT ... SELECT` are unchanged.
- Default publisher concurrency remains four.

## What could get worse

- Four workers may still be too expensive for shared MySQL; local SQLite concurrency is not capacity evidence.
- An external consumer reading `cip_answer.value_label` directly while a survey is `loading` could observe `NULL` earlier than before. No tracked repository consumer has that contract; external ownership must be checked.
- Process-global socket guards may affect future pytest plugins that legitimately need local sockets; such tests need explicit isolated design, not removal of the guard.
- The 13 analysis tests remain non-passing without an approved populated fixture.

## Required approval/evidence before deployment

1. Owner/DBA approval for a read-only representative MySQL run, including actual column collation metadata, plans, worker concurrency, connection counts, server waits and peak application memory. No historic monster-query replay.
2. Privacy-safe runtime attribution of the historic 681 group statements to publisher, ad-hoc API, retries or another caller.
3. Confirmation from data consumers that no external tool depends on derived `cip_answer.value_label` during `load_status='loading'`.
4. An approved anonymized snapshot/fixture for the 13 analysis tests; run them without skip/xfail.
5. Review of `CIP_REAUDIT_REVIEW_PATCH.diff` and explicit deployment authorization. Deployment, scheduler or schema work must remain separate.

## Rollback

The patch is uncommitted. Reviewers can reverse only the selected hunks in `CIP_REAUDIT_REVIEW_PATCH.diff`; no database rollback is needed. If later deployed, rollback is the previous application revision and removal of `CIP_PUBLISH_JOBS` if introduced. No schema rollback exists because no schema change is proposed.

## Safety attestation

Execution logs and the fail-closed harness independently support zero real email, Teams/Slack, webhook, SMS, push or other notification sends and zero staging/production database writes. No service restart, cloud modification, deployment, commit, push or PR occurred.
