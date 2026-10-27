# CIP Stage 3 fixes and deployment decision

Date: 2026-10-27  
Decision: **PASS FOR REVIEW ONLY; NO-GO FOR DEPLOYMENT**

## Implemented locally

### Bounded respondent extraction

- File: `app/data/payloads.py`, `people()`.
- Replaces `.all()` retention of every `srv_answer` row with a server-streamed result and respondent membership sets.
- Preserves one database read for the extraction and the exact canonical bit positions/JSON hash.
- MySQL result: 76.0% lower traced Python peak, 6.6% faster median/p95.
- Rollback: revert only the streaming/membership hunk in `people()`.

### Sargable concept/cohort joins

- File: `app/data/repository.py`, `_concept_cells()`, `concept_trend()`, `concept_pooled()`.
- Emits `c.cohort_id IS NULL` for everyone or `c.cohort_id=:coh` for a real cohort instead of `COALESCE(c.cohort_id,0)=:coh`.
- Preserves exact result hashes and specific-cohort behavior.
- MySQL result: about 88% lower median and p95 on the synthetic cross-wave query.
- Rollback: restore the `_CONCEPT_CELLS` constant and `COALESCE` predicate.

### Tests and evidence tooling

- `tests/test_phase4.py`: specific-cohort trend and pooled parity.
- `scripts/cip_stage3_readonly.py`: fixed approved staging allowlist; SQL-042 prohibited.
- `scripts/cip_stage3_mysql_benchmark.py`: local-only MySQL synthetic benchmark and failure tests.

## Intentionally not implemented

- Split `cip_answer` cleanup: slower in MySQL.
- Python cut grouping: incorrect for MySQL collation semantics.
- `wave_report` SQL rewrite: no material local improvement.
- Any index, `ANALYZE TABLE`, staging DML/DDL or ETL.
- Publisher worker-default change: local four-worker result is not shared-server capacity evidence.

## Remaining deployment gates

1. Approve and capture SQL-042 exactly as expanded in the Stage 3 report.
2. Approve a new plan-only SQL for the optimized `IS NULL` concept query.
3. DBA review of the proposed `(survey_id,dim,cohort_id,question_id)` index, including live size/write amplification and online-DDL risk; do not create it yet.
4. Optional aggregate-only survey-238 benchmark under a separate three-second approval. No respondent extraction.
5. Dedicated read-only application account and aggregate connection-capacity review.
6. Approved staging code canary with output hashes, one worker initially, retained previous publication and rollback.

No production/staging performance improvement is claimed until the optimized code is deployed and measured under an approved canary.

