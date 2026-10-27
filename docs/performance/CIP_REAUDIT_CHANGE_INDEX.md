# CIP re-audit change index

Date: 2026-10-27  
Repository: `/Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal`  
Branch: `master`  
Base HEAD: `6f978b0595b2c71c064991ae10b832514637a0da`

The base HEAD is not a fix commit. All reviewed changes remain uncommitted working-tree changes. Nothing was staged, committed, pushed, deployed or applied to a shared database.

## State preservation

At the start of this follow-up, the previously reported source/test diff was still present. The only additional artifact since the prior report was the requested untracked ZIP. Pre-existing untracked `docs/notebooklm_sources/` was preserved. This re-audit then added focused tests, corrected the unsafe Python grouping optimization, strengthened test isolation and created the files in this re-audit bundle.

Review commands:

```text
pwd
git branch --show-current
git rev-parse HEAD
git status --porcelain=v1
git diff --stat
git diff --check
git diff --cached --name-only
git ls-files --others --exclude-standard
```

No staged files were found. `git diff --check` passed after the re-audit.

The sanitized source/test patch is `docs/performance/CIP_REAUDIT_REVIEW_PATCH.diff`. It excludes `.env`, databases, logs, generated publications, NotebookLM evidence and documentation prose. It includes the new untracked `tests/test_test_isolation.py`.

## Changed-function map

| Current function | Previous behavior | Current behavior and business contract | SQL before / after | Tests |
|---|---|---|---|---|
| `etl.forsta_etl._answer` | Stored the item/option label on each coded `cip_answer`; the same load later cleared metadata-derived labels. | Coded answers store only `value_code`; stable display labels still resolve from `cip_item`/`cip_option`. Free text, numeric values and non-coded string fallbacks are unchanged. | Before: insert label, then bulk `UPDATE cip_answer ... SET value_label=NULL`. After: insert `NULL`; no Forsta cleanup update. | `test_forsta_does_not_write_then_clear_metadata_labels`; `test_coded_labels_preserve_metadata_case_spacing_and_unknown_code_contract`; existing load/view tests. |
| `etl.forsta_etl.load_survey` | Called `_rebuild_question_bases()` and therefore label cleanup after every Forsta write. | Passes `drop_labels=False` because the Forsta writer no longer inserts derived labels. All profile, base, harmonisation, cube, search and serving steps remain in the same order. | Removes only the redundant cleanup update from the Forsta path. | Entire `tests/test_forsta_etl.py`; SQL spy above. |
| `etl.forsta_etl._write` | If respondents disappeared, deleted every wave answer, deleted respondent children/parents, then unconditionally deleted every wave answer again. | Deletes respondent cohort/profile/parent rows first; declared FKs cascade their dependent answer/weight rows. The single unconditional wave-answer delete then precedes the replacement insert. All operations remain inside one `engine.begin()` transaction. | Two survey-wide answer deletes in shrinking reload -> one. | FK-on shrink, all child tables, `foreign_key_check`, idempotent rerun and injected rollback tests. |
| `etl.run_pipeline._rebuild_question_bases` | Always ran `drop_derived_labels`. | Optional `drop_labels=True`; Qualtrics and legacy callers retain the previous default. Only Forsta passes false. Base calculation is unchanged. | Legacy/Qualtrics unchanged; Forsta cleanup update removed. | Forsta SQL spy; existing Qualtrics/legacy suite coverage. |
| `etl.publish.worker_count` | Fixed default argument of four; no environment control or bounds validation. | CLI argument has highest precedence, then `CIP_PUBLISH_JOBS`, then four. Only integers 1–4 are accepted. Default remains four pending owner/DBA capacity approval. | No SQL change. | Absent environment, environment value, CLI override and invalid values. |
| `etl.publish.build`, `publish`, `main` | Passed a default of four directly; manifest omitted worker count. | Resolve bounded worker count once; CLI exposes the environment fallback; manifest records jobs. | No query-shape change. | Publisher integration and worker validation tests. |
| `etl.publish._build.wave` | Executed MySQL `GROUP BY` for cuts and a separate respondent extraction without call-site timing. | Still executes the same two `srv_answer` reads. Adds privacy-safe wave ID, fingerprint, query count, worker count and elapsed time. No parameters, respondent IDs or answers are logged. | Before: group query + extraction. After: the same two queries. | SQL spy requires exactly one group query and two `srv_answer` statements; canonical cut/people bytes match direct payload encoders. |
| `tests.conftest.csi_db` | SQLite foreign keys were not guaranteed before schema/test transactions. | Registers `PRAGMA foreign_keys=ON` on DBAPI connect before schema creation; tests assert it is one. | Test-only. | Shrink/cascade/rollback tests and `PRAGMA foreign_key_check`. |
| `tests.conftest` network/integration gate | Publication output was isolated and notification functions were mocked, but live-capable `.env` values could load before test overrides and only application-level mocks covered some routes. | Before collection, forces temporary SQLite/publication paths, blanks known live credentials and endpoints, and blocks Python TCP connect/connect_ex, UDP sendto/sendmsg and `socket.create_connection`. SMTP/Teams remain mocked/in-memory. | Test-only. | `tests/test_test_isolation.py`; full/focused suite execution. |

## Corrected and withdrawn change

The earlier patch added Python dictionary grouping over extracted `srv_answer` rows. This is removed. Checked-in MySQL schema uses `utf8mb4_0900_ai_ci`; raw Python strings do not implement its case/accent comparison semantics. The earlier one-query and 33.5% local improvement claims are withdrawn. Live ad-hoc and publisher cut aggregation both retain the original database `GROUP BY` path.

## Rollback

Before deployment, rollback is deletion of the uncommitted diff or selective reversal of the hunks in `CIP_REAUDIT_REVIEW_PATCH.diff`. No database rollback is required because no database/schema/deployment action occurred. Preserve unrelated untracked material when reverting.
