# CIP final remediation — full test closure

Date: 2026-10-27  
Repository: `consumer-insight-portal`  
Base HEAD: `6f978b0595b2c71c064991ae10b832514637a0da`  
State: uncommitted local patch  
Cross-links: [verdict](00_EXECUTIVE_VERDICT.md), [benchmarks](03_BENCHMARK_BEFORE_AFTER.md), [safety](05_SAFETY_AND_NO_MESSAGE_ATTESTATION.md)

## Original non-passing state

Prior captured full run: `327 passed, 4 failed, 9 errors in 19.63s`.

All 13 cases reached `sqlite3.OperationalError: no such table: cip_question`. `tests/test_analysis.py` used the existence of ignored `data/csi_local.db` as a run marker while `tests/conftest.py` correctly redirected application engines to a new empty safe database.

The affected IDs were:

- `test_single_punch_answers_keep_distinct_codes`
- `test_gate_question_cohorts_match_published_bases[BN1-133]`
- `test_gate_question_cohorts_match_published_bases[DP1-222]`
- `test_gate_question_cohorts_match_published_bases[GP1-71]`
- `test_demographic_cohorts_match_the_crosstab_summary`
- `test_criteria_intersect_rather_than_union`
- `test_unfiltered_analysis_matches_the_published_crosstab`
- `test_routed_question_keeps_its_own_base_after_filtering`
- `test_break_by_splits_without_losing_the_total`
- `test_excel_export_is_a_readable_workbook_with_provenance`
- `test_multi_select_base_is_everyone_answering_the_question`
- `test_every_single_punch_answer_resolves_to_a_code`
- `test_grid_rows_are_separate_distributions`

## Fixture repair

`tests/analysis_fixture.py` installs the checked-in schema with SQLite foreign keys enabled before transactions and seeds:

- 2 waves; 404 and 403 qualified synthetic respondents.
- 8 reportable questions covering single, multi and grid.
- 807 profiles and 3,192 answers.
- Exact asserted counts: BN1 133/248/four answers, DP1 222, GP1 71, GenZ 54, Millennials 159, Walmart 241/404, BT8 Mascara 40/264, HX1 seven groups totaling 403, and two routed BT14 rows.
- `cip_agg_cell` intentionally empty so the raw-answer analysis SQL is exercised.

`tests/test_trends_multiwave.py` now creates two synthetic waves in `csi_db`; it no longer copies or checks `data/csi_local.db`.

No expectation was weakened. The wave-2 skip was replaced by an assertion that required questions exist.

## Actual results

Focused closure:

```text
.venv/bin/python -m pytest tests/test_analysis.py -q -ra
13 passed in 1.19s
```

Clean detached worktree, no `data/csi_local.db`:

```text
/Users/.../.venv/bin/python -m pytest -q -ra
350 passed in 17.78s
```

Same clean worktree with a zero-byte dummy `data/csi_local.db` marker:

```text
pytest tests/test_analysis.py tests/test_trends_multiwave.py -q -ra
15 passed in 0.66s
marker remained 0 bytes
```

Focused remediation suite, repeated in the detached patched worktree:

```text
pytest tests/test_analysis.py tests/test_trends_multiwave.py tests/test_forsta_etl.py \
  tests/test_phase3.py tests/test_publish.py tests/test_api_speed.py \
  tests/test_serving.py tests/test_test_isolation.py -q -ra
run 1: 125 passed in 8.21s
run 2: 125 passed in 8.13s
run 3: 125 passed in 7.94s
```

Additional checks:

```text
python -m compileall -q api app etl tests
git diff --check
web: npm run check        -> stats checks passed
web: npm run build        -> TypeScript/Vite build passed
```

Final totals: **350 passed, 0 failed, 0 errors, 0 skipped, 0 xfailed**. The web check and build also passed.

## Scenario coverage

- Fresh, same-wave, shrinking and empty Forsta loads.
- Label metadata case/accent/trailing-space preservation, unknown codes, explicit multi 0/1 options and label-only reconciliation.
- FK child cleanup, `PRAGMA foreign_key_check`, idempotent rerun and injected rollback.
- Full-pipeline rebuild of `cip_tracker_line` and `srv_answer` after respondent removal.
- Fresh/repeated/shrinking/empty Qualtrics snapshot and injected answer failure rollback.
- Publisher 1/2/4 workers, environment/CLI precedence, artifact bytes, question removal, rule invalidation, failed gate and rollback.
- HTTP and MCP published-crosstab reuse with live fallback.
- SMTP/Teams fakes and TCP/UDP fail-closed tests.

## Unavailable checks

- MySQL 8: no Docker MySQL image; local `mysqld` is a broken MySQL 9.4 installation with a missing dynamic library. Nothing was downloaded or repaired.
- `pip-audit`: not run because dependency advisory refresh can require external network access.
- Container image/boot check: not run because it starts a service and the required local image/toolchain was not established offline.
