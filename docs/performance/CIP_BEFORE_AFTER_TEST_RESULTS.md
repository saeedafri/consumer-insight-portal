# CIP before/after test and benchmark results

> **Re-audit correction, 2026-10-27:** the one-query publisher benchmark and 33.5% improvement below describe an unsafe intermediate patch that has been removed. They are retained only as historical evidence and are not results for the final working tree. See `CIP_REAUDIT_TEST_RESULTS.md`.

Date: 2026-10-26  
Machine/runtime: same local macOS workspace; Python 3.13.12; pytest 9.1.1; SQLite fixtures.  
Scope: synthetic/anonymized local data only. No staging/production benchmark or speedup claim.

## Safety gate

The repository `.env` contains live-capable DB and outbound integration settings. Tests were not run until pytest bootstrap was changed to:

- select a temporary SQLite database before CIP imports;
- blank all live integration credentials before dotenv loading;
- redirect published files and notification state to temporary directories;
- deny sockets during collection and execution;
- fake SMTP and Teams helpers.

`tests/test_test_isolation.py` passed. No network-denial assertion fired during the suite.

Read-only post-change health checks, without restarting either process:

```text
GET http://127.0.0.1:8000/healthz -> 200
GET https://offerings-apparent-troy-marker.trycloudflare.com/healthz -> 200
```

## Automated tests

Commands:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest --collect-only -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /usr/bin/time -l .venv/bin/pytest -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /usr/bin/time -l .venv/bin/pytest -q --ignore=tests/test_analysis.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q \
  tests/test_test_isolation.py tests/test_publish.py tests/test_forsta_etl.py \
  tests/test_serving.py tests/test_etl_fixes.py
```

| Run | Before local fixes | After local fixes | Interpretation |
|---|---:|---:|---|
| Safe isolated suite excluding snapshot-dependent `test_analysis.py` | 321 passed; 19.38 s pytest; 20.69 s wall; 339,132,416-byte max RSS | 324 passed; 18.27 s pytest; 19.33 s wall; 350,633,984-byte max RSS | Correctness pass. Suite timing/RSS are not a product benchmark. Three new performance-regression tests account for the pass-count change. |
| Full safe suite | 319 passed, 4 failed, 9 errors; 26.33 s | 324 passed, 4 failed, 9 errors; 18.96 s | The same 13 `test_analysis.py` cases require an absent approved snapshot/database. They fail on the intentionally empty default SQLite DB. They are unavailable, not passes and not regressions from these changes. |
| Focused changed paths | Not separately captured | 85 passed in 7.25 s | Covers isolation, publishing, ingestion, serving, reload/idempotency, parity, and bounded workers. |

No failing test is hidden; the 13 snapshot-dependent cases remain an explicit limitation.

## Query-path benchmark: original vs reused extraction

Method: one local SQLite database; identical synthetic data and process; original path ran database `question_cuts()` plus `people()`; new path ran one `respondent_answers()` extraction reused by both. Each output was canonicalized and compared exactly. p95 is the maximum of the stated small sample, not a production SLO estimate.

### Modest generated Forsta wave

Dataset: 2,000 respondents, 10,000 `srv_answer` rows, 3 reportable questions.

| Metric | Before | After |
|---|---:|---:|
| Samples | 9 | 9 |
| p50 | 19.210 ms | 16.067 ms |
| p95/max | 19.855 ms | 16.593 ms |
| `srv_answer` queries per fresh wave | 2 | 1 |
| Rows returned from `srv_answer` paths | 10,005 | 10,000 |
| Cut-count parity | — | exact |
| Audience-bitset parity | — | exact |

### Wide synthetic wave

Dataset: 2,000 respondents × 40 questions; 80,000 `srv_answer` rows; six demographic dimensions with missing values; 4,800 grouped rows.

| Metric | Before | After |
|---|---:|---:|
| Samples | 7 | 7 |
| p50 | 288.945 ms | 192.076 ms |
| p95/max | 297.352 ms | 194.956 ms |
| `srv_answer` queries per fresh wave | 2 | 1 |
| Rows returned from `srv_answer` paths | 84,800 | 80,000 |
| Cut-count parity | — | exact |
| Audience-bitset parity | — | exact |

Local p50 improved 33.5% on this fixture. This is not a measured MySQL/staging improvement. It proves query elimination and local algorithm/output parity.

## Publisher concurrency benchmark

Dataset: four waves × 1,000 respondents × 20 questions; 80,000 `srv_answer` rows; six demographic dimensions. Each run built a fresh local output tree. Decompressed JSON payload digests were identical across 1, 2, and 4 workers.

| Workers | Samples | p50 wall | p95/max wall |
|---:|---:|---:|---:|
| 1 | 3 | 0.227 s | 0.244 s |
| 2 | 3 | 0.325 s | 0.339 s |
| 4 | 3 | 0.760 s | 0.762 s |

SQLite favored one worker because concurrent local reads/Python work add overhead. Shared Azure MySQL may behave differently. Default remains 4; `CIP_PUBLISH_JOBS=1|2|3|4` enables an approved same-data test without code changes.

## Correctness coverage

Passing tests cover:

- exact counts, percentages, bases, demographic cuts, missing cut values, multi-select/base rows, and ordering;
- published book/cut/people JSON parity and atomic rollback;
- weighted/unweighted calculation tests and missing-profile behavior;
- reload idempotency, dropped respondents, partial failure, failed publish cleanup, and serving rebuilds;
- one Forsta label-delete scan eliminated while displayed labels remain the same;
- one answer delete on shrinking reload;
- no live DB/network/outbound path in pytest.

Limitations:

- No approved large sanitized snapshot was available; synthetic fixtures cannot reproduce MySQL optimizer, network latency, disk spill, lock waits, redo, or Azure resource contention.
- No read-only staging plan/counter was collected.
- Peak memory was captured only for the whole pytest process, not isolated per publisher worker.
- Historical deployment revision, run IDs, retry counts, and simultaneous worker count remain unknown.

