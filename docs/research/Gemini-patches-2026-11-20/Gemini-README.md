# Gemini Isolated Patch & Regression Test Bundle (2026-11-20)

These patches were developed and verified **strictly inside an isolated APFS snapshot** (`Gemini-snap-patched`) cloned from the `cip-test` working tree (`HEAD 312e769` + Codex's local working-tree edits synced `2026-11-19T21:00:25Z`, including `api/assistant.py` SHA-256 `549c2ea2...`). **Zero tracked files in `/Users/mohdsaeedafri/All-Code-Base/cip-test` were modified.**

## Files in this Directory

| File | Scope | Linked Findings |
|---|---|---|
| `Gemini-patch-01-security-scope-and-db-role.diff` | `shared/core/config.py` (`api_write` uses `APP_DB_USER` / `API_WRITE_DB_USER`, never `STG_DB_USER`), `shared/core/access.py` (`scope()` separates `staff` vs `client` while preserving `"<client>:<tier>"` for named clients), `api/main.py` (`check_settings()` uses canonical `config.environment`; `/readyz` requires valid `manifest.json` + `waves.json.gz`), `api/signin.py` (`renew()` fails closed on DB error). | `GEM-001`, `GEM-002`, `GEM-005`, `GEM-014` (`SEC-03`, `ETL-03`) |
| `Gemini-patch-02-publish-swap-and-etl.diff` | `etl/publish.py` (`swap()` never deletes the just-activated `target` directory), `etl/cohorts.py` (`parents[1]` resolves `config/cohorts.yml`), `etl/sharepoint_china.py` (`folder_week()` adds `(?!\d)` word boundary so `"May 2026"` is not misparsed as `2026-05-20`). | `GEM-009`, `GEM-015`, `GEM-016` |
| `Gemini-patch-03-ask-and-frontend.diff` | `api/ask_index.py` (scopes `correct_spelling()` to caller-visible words), `api/assistant.py` (closes regex bypasses on `weighted`, `overlap`/`both`, `either … or` union, and `mean`/`on average` spend), `frontend/src/screens/Ask.tsx` (preserves user query/dates across all suggestion clicks; accepts `checked.mode === "none"` AI refusals), `frontend/src/screens/Explorer.tsx` (case-insensitive question lookup + explicit missing-question state), `frontend/src/theme.ts` & `frontend/src/screens/Retailers.tsx` (repairs inline `//` comments that swallowed code properties). | `GEM-008`, `GEM-017`, `GEM-018`, `GEM-019`, `GEM-022`, `GEM-024` (`UX-01`) |
| `Gemini-regression-tests-2026-11-20.py` | 9 targeted pytest regression tests covering all patches above. | All above |

## Verified Red → Green Results (Isolated Snapshots)

1. **Before patches (`Gemini-snap-worktree`):** `pytest -q tests/test_gemini_regressions.py` → **9 failed, 0 passed** (every defect reproduced deterministically).
2. **After applying `Gemini-patch-01..03` (`Gemini-snap-patched`):**
   - `pytest -q tests/test_gemini_regressions.py tests/test_assistant.py tests/test_publish.py tests/test_ask_golden.py tests/test_ask_colab.py tests/test_api_speed.py` → **124 passed, 0 failed**.
   - `npx tsc --noEmit` in `frontend/` → **exit 0**.

## Intentional Existing-Test Adjustments When Merging Patch 01

Applying `Gemini-patch-01` intentionally tightens two unsafe baseline behaviors that two existing tests in `tests/test_access.py` assert:

1. `tests/test_access.py::test_a_revoked_session_stays_out_after_a_restart` (around line 567) currently expects `200` when the database is unavailable during `signin.renew()` (testing old fail-open behavior). Once fail-closed `renew()` is adopted (`GEM-005`), update that assertion to expect `401` (or an explicit degraded-auth error).
2. `tests/test_access.py::test_suggestions_while_typing_and_readiness_answer_over_the_api` uses a synthetic `portal` fixture without `manifest.json`. Once `/readyz` enforces `manifest.json` presence (`ETL-03` / `GEM-014`), add a minimal valid `manifest.json` to that fixture.

## How to Apply in an Isolated Copy

```bash
git apply --check docs/research/Gemini-patches-2026-11-20/Gemini-patch-01-security-scope-and-db-role.diff
git apply --check docs/research/Gemini-patches-2026-11-20/Gemini-patch-02-publish-swap-and-etl.diff
git apply --check docs/research/Gemini-patches-2026-11-20/Gemini-patch-03-ask-and-frontend.diff
```
