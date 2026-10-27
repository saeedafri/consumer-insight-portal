# Complete CIP Share Bundle Manifest

## Purpose

This bundle is a reviewable, path-preserving export of the CIP remediation work. It contains full source files in addition to unified diffs and test/performance reports.

## Included

- The complete `etl/` tree, excluding caches and operating-system metadata.
- The complete `tests/` tree, including fixtures and all added or modified tests.
- Full current copies of every modified non-ETL source/config file: `.env.example`, `api/main.py`, and `api/mcp.py`.
- Added benchmark and review scripts.
- All CIP performance, re-audit, safety, benchmark, release-gate, and supporting evidence documents created during this work.
- A complete worktree patch against base HEAD `6f978b0595b2c71c064991ae10b832514637a0da`.
- Git state, name-status, diff-stat, changed-file, addition, modification, and deletion manifests.
- SHA-256 checksums for every bundled file.

## Change accounting

Tracked modifications are listed in `EVIDENCE/TRACKED_NAME_STATUS.txt`. Added remediation artifacts are listed in `EVIDENCE/ADDED_FILES.txt`. Tracked deletions are listed in `EVIDENCE/DELETED_FILES.txt`; the file states `NONE` when no tracked deletion exists.

## Excluded by design

- `.git/`, credentials, `.env`, tokens, local databases, raw respondent data, logs, caches, virtual environments, `node_modules/`, frontend build output, and operating-system metadata.
- Existing ZIP bundles are not nested inside this archive. Their source documents are included directly.
- No staging or production data export is included.

## Review order

1. `docs/performance/cip_final_remediation/00_EXECUTIVE_VERDICT.md`
2. `docs/performance/cip_final_remediation/01_FULL_TEST_CLOSURE.md`
3. `docs/performance/cip_final_remediation/02_CODE_CHANGES_WITH_EVIDENCE.md`
4. `docs/performance/cip_final_remediation/03_BENCHMARK_BEFORE_AFTER.md`
5. `EVIDENCE/CIP_COMPLETE_WORKTREE_PATCH.diff`
6. `EVIDENCE/SHA256SUMS.txt`
