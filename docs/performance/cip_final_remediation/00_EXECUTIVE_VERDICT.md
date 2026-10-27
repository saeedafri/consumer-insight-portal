# CIP final remediation — executive verdict

Date: 2026-10-27  
Repository: `consumer-insight-portal`  
Branch/base: `master` / `6f978b0595b2c71c064991ae10b832514637a0da`  
State: uncommitted local patch; base HEAD is not a fix commit

## Decision

**PASS FOR LOCAL REVIEW. NOT READY FOR DEPLOYMENT.**

The clean patched worktree passes all 350 deterministic tests with no failures, errors, skips or xfails. The original 13 analysis failures are repaired with real-schema synthetic fixtures. Qualtrics snapshot ingestion has a measured SQLite improvement and exact output hashes. Publisher artifacts remain byte-identical in the synthetic comparison, and the redundant `srv_result`/`srv_wave` discovery query is removed.

Deployment remains blocked because no disposable MySQL 8 runtime was available, no approved staging test was run, actual MySQL collation/FK/query-plan behavior was not verified, and the shared-server four-worker capacity decision remains open.

## Implemented fixes (13)

1. Replaced the 13-test ignored-database gate with deterministic two-wave real-schema data.
2. Replaced the remaining trend tests' ignored-database copy with synthetic fixtures.
3. Enforced pre-import local SQLite, blank live integration settings, socket blocking and mocked notifications.
4. Preserved MySQL SQL aggregation; no Python grouping replacement exists.
5. Removed the redundant pre-shrink full `cip_answer` delete while preserving one transactional replacement.
6. Preserved multi-select item labels when 0/1 option metadata would otherwise display `Yes`/`No`.
7. Made Forsta reconciliation compare label-only coded answers.
8. Made empty existing-wave Forsta reloads valid and verified derived-row cleanup after shrink.
9. Replaced Qualtrics per-respondent transactions with one transactional snapshot/bulk answer load, including stale-row removal and rollback.
10. Added bounded, documented publisher and serving worker validation; publisher default remains four.
11. Separated publisher cut and respondent materialization, releasing cuts before respondent extraction; telemetry now distinguishes expected reads and phase/wall time.
12. Removed the publisher's redundant `SELECT DISTINCT ... srv_result JOIN srv_wave` discovery query by using versioned cut-file inventories.
13. Reused published cuts for MCP crosstabs, retaining the live SQL fallback for missing/incomplete artifacts.

## Material bottlenecks still not fixed (5)

1. `srv_answer` publishing still performs one MySQL `GROUP BY` read and one respondent extraction read per fresh wave. Historic caller attribution remains unknown.
2. `cip_agg_cell` serving joins have no approved MySQL `EXPLAIN FORMAT=JSON`; no SQL/index change was safe to make.
3. The historic `v_cip_answer_long` count has no confirmed current application caller; no speculative summary/index was added.
4. Forsta `LOAD DATA LOCAL INFILE`, live MySQL import throughput and exact runtime memory remain unvalidated outside SQLite.
5. Shared scheduler overlap and the default publisher capacity of four require owner/DBA review; repository locks are improved but shared runtime configuration was not changed.

## Evidence map

- [Full test closure](01_FULL_TEST_CLOSURE.md)
- [Code changes and rollback](02_CODE_CHANGES_WITH_EVIDENCE.md)
- [Before/after benchmarks](03_BENCHMARK_BEFORE_AFTER.md)
- [Approval requests](04_OPEN_DB_APPROVAL_ITEMS.md)
- [Safety attestation](05_SAFETY_AND_NO_MESSAGE_ATTESTATION.md)
- [Release gate](06_RELEASE_AND_ROLLBACK_GATE.md)
- [Review patch](CIP_FINAL_REVIEW_PATCH.diff)

GO for local code review. NO-GO for deployment until every gate in `06_RELEASE_AND_ROLLBACK_GATE.md` passes.
