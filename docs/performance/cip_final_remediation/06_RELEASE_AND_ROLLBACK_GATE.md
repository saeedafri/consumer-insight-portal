# CIP final remediation — release and rollback gate

Date: 2026-10-27  
Repository: `consumer-insight-portal`  
Base HEAD: `6f978b0595b2c71c064991ae10b832514637a0da`  
State: uncommitted local patch  
Current decision: **PASS FOR LOCAL REVIEW / NOT READY FOR DEPLOYMENT**

Cross-links: [verdict](00_EXECUTIVE_VERDICT.md), [tests](01_FULL_TEST_CLOSURE.md), [changes](02_CODE_CHANGES_WITH_EVIDENCE.md), [benchmarks](03_BENCHMARK_BEFORE_AFTER.md), [approvals](04_OPEN_DB_APPROVAL_ITEMS.md), [safety](05_SAFETY_AND_NO_MESSAGE_ATTESTATION.md)

## Gate status

| Gate | Status | Evidence / remaining action |
|---|---|---|
| 1. Deterministic tests: zero failures/errors | PASS | Clean detached worktree: 350 passed, 0 failed/errors/skipped. |
| 2. Business output parity | PARTIAL | Synthetic exact hashes/counts pass. MySQL collation/FK and approved representative wave parity remain. |
| 3. Regression coverage | PASS locally | Python grouping remains absent; labels, reconciliation, shrink, empty, rollback, Qualtrics snapshot, discovery and MCP reuse covered. |
| 4. No real notifications/remote writes | PASS for executed paths | Pre-import environment isolation, socket block, fake transports; no staging connection. |
| 5. Optimization evidence | PARTIAL | Qualtrics local gain proven. Publisher one-query removal proven; no wall/RSS gain and no MySQL gain claimed. |
| 6. Approval-only work separated | PASS | See `04_OPEN_DB_APPROVAL_ITEMS.md`; nothing shared was changed. |

## Required approvers before any deployment

1. CIP code owner: source diff, output contracts and external `value_label` consumers.
2. DBA: deployed collations/indexes/FKs/triggers, bounded plans and isolated MySQL validation.
3. ETL/scheduler owner: named-lock coverage, schedule overlap and `CIP_PUBLISH_JOBS` capacity.
4. Release owner: approved staging revision, canary scope, rollback authority and observation window.

## First approved rollout plan

1. Apply the review patch to a review branch; do not include unrelated untracked artifacts.
2. Run the 350-test suite and web checks in CI with notifications/credentials absent.
3. Run the MySQL gates in `04_OPEN_DB_APPROVAL_ITEMS.md` on a disposable MySQL 8 instance.
4. On one approved modest staging wave, publish to a separate output root at jobs 1, 2 and 4; never swap `current` during benchmarking.
5. Require exact book/cut/people/question hashes or documented volatile-field normalization.
6. Canary one authorized ETL run with query/connection/RSS/error telemetry and zero notification testing.
7. Deploy only if counts, denominators, labels, bitsets and visible API outputs match and p95/error/resource gates do not regress.

## Fail criteria

- Any test failure/error or unexpected skip.
- Any MySQL collation grouping difference.
- Any stale respondent/answer/profile/cohort/tracker/serving row after reload.
- Any output hash/count/base/label difference not explicitly approved.
- Unbounded worker/connection behavior, material p95/RSS regression or new lock overlap.
- Any real notification from a validation environment.

## Rollback

- Application: deploy the previous approved revision based on `6f978b0`; this patch has no schema migration.
- Configuration: remove `CIP_PUBLISH_JOBS` to return to default 4, or restore the prior approved value.
- Published artifacts: use the existing atomic publisher rollback to repoint `current` to the prior verified version.
- Data: do not attempt manual shared-DB repair. Stop the writer, preserve logs, and use the pre-approved snapshot/restore procedure if an authorized rollout changed data.
- Code-review rollback: reverse the focused hunks listed in `02_CODE_CHANGES_WITH_EVIDENCE.md`; the test fixture/isolation changes may remain independently.

Deployment readiness becomes `READY FOR APPROVED DEPLOYMENT` only after Gates 2 and 5 pass on MySQL and all named approvers sign off.
