# CIP performance fixes implemented

> **Re-audit correction, 2026-10-27:** the Python cut-grouping/query-reuse change described below was removed because it did not preserve MySQL `utf8mb4_0900_ai_ci` grouping semantics. The final publisher still performs the original group query plus respondent extraction. See `CIP_REAUDIT_FINDINGS.md` and `CIP_REAUDIT_REVIEW_PATCH.diff`.

Date: 2026-10-26  
State: local working tree only; not committed, pushed, deployed, or run against staging/production.

## Changes

### 1. Fail-closed local test isolation

Files: `tests/conftest.py`, `tests/test_test_isolation.py`

- Before any application import, force `APP_ENV=LOCAL`, a temporary `LOCAL_SQLITE_PATH`, and a temporary publish directory.
- Shadow live-capable DB, Forsta, Anthropic, SMTP, Teams, OIDC, Blob, and nginx-warming variables with empty values so `load_dotenv()` cannot repopulate them.
- Deny all socket connections during test collection and execution.
- Keep existing fake SMTP/Teams assertions and isolated notification throttle state.
- Add assertions that both DB roles resolve to SQLite, integration credentials are blank, and sockets fail closed.

Rollback: revert the two test files. Do not run local tests against this checkout before replacing them with an equivalent isolation gate; the repository `.env` is live-capable.

### 2. One `srv_answer` read for published cuts and audience bitsets

Files: `app/data/payloads.py`, `etl/publish.py`, `tests/test_publish.py`

- Add `RespondentAnswer` and `respondent_answers()` for the row shape already required by audience bitsets.
- Allow `people()` and `question_cuts()` to consume the same in-memory rows.
- Publisher extracts one wave once, derives exact cut counts locally, and builds bitsets from the same rows.
- Live/ad-hoc crosstabs still use the database aggregate path; their bounded qcode/week behavior is unchanged.
- Add per-wave privacy-safe logging: wave ID, stable fingerprint name, query count, row count, worker count, and elapsed seconds. No SQL values, respondent IDs, answers, emails, or credentials are logged.

Effect: fresh-wave publication removes one `srv_answer` aggregate query and one database traversal per wave. Output parity is tested for counts and bitsets.

Rollback: restore the publisher's separate `question_cuts(conn,[sid])` and `people(conn,sid)` calls; remove the optional row-reuse path and instrumentation.

### 3. Do not write Forsta labels only to clear them

Files: `etl/forsta_etl.py`, `etl/run_pipeline.py`, `tests/test_forsta_etl.py`

- Coded Forsta answers now store `value_label=NULL`; the authoritative label remains in `cip_option`/`cip_item` and readers already reconstruct it with `COALESCE`.
- `_rebuild_question_bases(..., drop_labels=False)` skips the multi-table cleanup only for Forsta.
- Legacy and Qualtrics callers keep the default cleanup because their label/fallback semantics were not changed.
- Unknown non-coded values still retain their fallback label.
- Test SQL spies prove a Forsta load executes no `UPDATE cip_answer` and visible labels remain unchanged.

Rollback: restore `_answer()`'s derived label assignment and call `_rebuild_question_bases(survey_id)` with cleanup enabled.

### 4. Remove duplicate wave answer deletion

Files: `etl/forsta_etl.py`, `tests/test_forsta_etl.py`

- When respondents disappear on reload, their dependent records are removed, then the existing unconditional wave-answer delete runs once.
- A SQL-spy test proves one delete during a shrinking reload; respondent and answer parity tests continue to pass.

Rollback: restore the first delete. This is safe but reintroduces redundant transactional work.

### 5. Bounded/configurable publisher concurrency

Files: `etl/publish.py`, `tests/test_publish.py`

- `CIP_PUBLISH_JOBS` selects 1–4 workers; CLI `--jobs` overrides it.
- Values outside 1–4 fail before a build starts.
- Default remains 4. The SQLite concurrency benchmark favored 1, but that is not evidence for shared MySQL, so no default reduction was made.
- Manifest now records `jobs`.

Rollback: restore the fixed default. This removes the operational control and bound.

## Intentionally not applied

- No `(survey_id,qcode)` index: redundant with the primary key.
- No `cip_agg_cell` index or serving-query rewrite: no current safe plan proves the correct column order or mechanism.
- No MySQL global/session memory change: spill and allocation claims are unproven; publisher does not use `ETL_SESSION`.
- No LOAD DATA replacement/chunking change: current path is one transactional bulk operation with fallback and idempotency protections.
- No `srv_result` discovery rewrite: current alternative may increase transfer; staging plan absent.
- No `v_cip_answer_long` materialization: no current application caller or required count semantics.
- No scheduler, deployment, cloud, notification, or cross-product change.

