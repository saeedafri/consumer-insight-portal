# CIP re-audit test results

Date: 2026-10-27

## Safety gate

Before collection, `tests/conftest.py` forces temporary SQLite and publication paths, blanks known live DB/Forsta/AI/SMTP/Teams/OIDC/blob/nginx variables, blocks Python TCP and UDP socket routes, mocks SMTP and Teams transports and moves notification throttle state to a temporary path. Repository test search found no subprocess network invocation.

No ETL CLI, scheduler, queue, migration, shared database command, deployment command or service-control command was run. The API on port 8000 and cloudflared process were not started, stopped or restarted.

One limitation: the repository contains a pre-existing ignored `data/csi_local.db`. Legacy `tests/test_trends_multiwave.py` copied that local snapshot to a temporary database during comprehensive runs. It did not modify the source snapshot, contact staging, or print respondent data, but it is not a newly generated synthetic fixture. No further snapshot-backed testing was performed.

## Collection and focused suite

```text
.venv/bin/pytest --collect-only -q
340 tests collected in 0.74s

.venv/bin/pytest -q tests/test_publish.py tests/test_forsta_etl.py tests/test_test_isolation.py tests/test_etl_fixes.py tests/test_serving.py tests/test_weighting.py tests/test_team.py
96 passed in 7.70s
```

The focused suite covers SQL spies, canonical payload bytes, collation guard, worker precedence/errors, FK enforcement, all respondent child rows, rollback, idempotency, coded-label reconstruction, unknown codes and network blocking.

The new publisher regression test was run before the correction and failed because the patch emitted zero grouping statements. After restoring SQL aggregation it passed. Two initial FK test failures were fixture-construction errors (`scheme_name` was not a schema column and an empty cohort rule was invalid); both test fixtures were corrected before judging implementation behavior.

## Full suite

```text
/usr/bin/time -l .venv/bin/pytest -q
327 passed, 4 failed, 9 errors in 19.63s
maximum resident set size: 358,875,136 bytes
```

All 13 non-passing cases are in `tests/test_analysis.py`:

Errors:

- `test_single_punch_answers_keep_distinct_codes`
- `test_gate_question_cohorts_match_published_bases[BN1-133]`
- `test_gate_question_cohorts_match_published_bases[DP1-222]`
- `test_gate_question_cohorts_match_published_bases[GP1-71]`
- `test_criteria_intersect_rather_than_union`
- `test_unfiltered_analysis_matches_the_published_crosstab`
- `test_routed_question_keeps_its_own_base_after_filtering`
- `test_break_by_splits_without_losing_the_total`
- `test_excel_export_is_a_readable_workbook_with_provenance`

Failures:

- `test_demographic_cohorts_match_the_crosstab_summary`
- `test_multi_select_base_is_everyone_answering_the_question`
- `test_every_single_punch_answer_resolves_to_a_code`
- `test_grid_rows_are_separate_distributions`

Every traceback reaches `sqlite3.OperationalError: no such table: cip_question`. The module decides whether to run from the existence of repository `data/csi_local.db`, while the safety harness intentionally redirects application connections to a new empty temporary SQLite database. These cases were not skipped, xfailed or hidden.

## Baseline comparison

A clean `git archive` of base HEAD was extracted to a temporary directory. The current fail-closed test harness was copied into it; no implementation hunk was copied.

```text
# No snapshot marker in clean archive
pytest -q
319 passed, 15 skipped in 18.88s

# Comparable deterministic suite, excluding the two snapshot-dependent modules
BASE HEAD: pytest -q --ignore tests/test_analysis.py --ignore tests/test_trends_multiwave.py
319 passed in 21.47s

CURRENT: pytest -q --ignore tests/test_analysis.py --ignore tests/test_trends_multiwave.py
325 passed in 17.50s
```

Wall times vary with machine load and are not used as a performance comparison for this suite.

Creating an empty snapshot marker against base reproduced the analysis failures (`4 failed`, `9 errors`) and also caused the two trend tests to error because that temporary baseline snapshot was empty. This proves the analysis failure mechanism, but it is not a substitute for an approved populated fixture.

## Repeated publisher benchmark

Command:

```text
.venv/bin/python docs/performance/reaudit_publish_benchmark.py --source-root <base-or-current> --label <label>
```

Each size received one warmup and five recorded samples. Data is deterministic SQLite synthetic data. `result_bytes` is uncompressed canonical payload size, not MySQL wire bytes; MySQL transferred bytes/rows examined were unavailable. Both versions executed two `srv_answer` queries and four total SQL queries per wave. Error count was zero.

| Respondents × questions | Rows | Base median / p95 | Corrected median / p95 | Payload bytes | Output hash equal |
|---|---:|---:|---:|---:|---|
| 250 × 10 | 2,500 | 0.004892 / 0.004910 s | 0.004889 / 0.004955 s | 10,688 | Yes |
| 1,000 × 20 | 20,000 | 0.036220 / 0.036971 s | 0.036633 / 0.037107 s | 30,362 | Yes |
| 2,500 × 30 | 75,000 | 0.153278 / 0.153825 s | 0.153605 / 0.154548 s | 71,177 | Yes |

Four-wave concurrency workload, 20,000 rows per wave, one warmup and three recorded samples:

| Jobs | Base median | Corrected median | Hash equal | Errors |
|---:|---:|---:|---|---:|
| 1 | 0.175940 s | 0.182057 s | Yes | 0 |
| 2 | 0.219476 s | 0.218860 s | Yes | 0 |
| 4 | 0.452641 s | 0.447544 s | Yes | 0 |

Peak benchmark-process RSS was 112,001,024 bytes for base and 115,015,680 bytes for the corrected tree. The small difference is not evidence of a regression or improvement from one process run. Local SQLite favored one worker; default four was not changed because this does not establish shared MySQL capacity.

An intermediate re-audit build with a `NamedTuple` extraction wrapper was 17–20% slower locally; the wrapper was removed. The final benchmark is effectively equal to base and makes no performance-gain claim.

## Smoke and operational checks

No isolated patched API process was started because the final patch changes ETL/publisher code, not API request handling, and the focused integration tests exercise those paths directly. A read-only health call to the unchanged API/tunnel is only an availability check and is not evidence that this uncommitted patch ran.

Post-change continuity check: `http://127.0.0.1:8000/healthz` returned 200 and the existing public tunnel `/healthz` returned 200. Neither process was restarted.

Real messages sent: zero. Shared staging/production writes: zero. Schema/cloud/deployment/service changes: zero.
