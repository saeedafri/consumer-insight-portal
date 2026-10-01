# Publications and Drift — Phase 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A number that leaves Coresight in a report is frozen with its definition, and the portal says — cell by cell — whether today's data still gives the same number. This replaces the analysts' manual *Cross-Check* tab (spec D4, §5.7).

**Architecture:** `app/data/publications.py` holds a publication as a *definition* (concept, waves, cohort, cut, pooled or per wave, minimum base) plus its frozen cells in `csi_publication` / `csi_publication_cell` (both exist since Phase 1). `compute(definition)` is the one function that turns a definition into cells — from the cube via `repository.concept_pooled` / `concept_trend` — so publishing and re-checking cannot disagree about method. `drift(publication_id)` recomputes and compares. A **Publications** page lists every publication with its drift status, shows frozen vs now, lets an analyst publish a new one, and exports the frozen numbers with their footnote.

**Tech Stack:** Python 3.13, SQLAlchemy 2, MySQL 8 (`dwh_stg`), SQLite (tests), Streamlit 1.55, pytest.

**Spec:** `docs/superpowers/specs/2026-09-29-survey-platform-design.md` — D4, D5 (suppress n < 30, caution n < 90), §5.7, §6 step 9 (drift check), §7 (every result carries its base and a generated footnote), §11 Phase 5 exit: *a Beauty chart published and re-verified after a reload*.

## Global Constraints

- No schema change (tables exist). A new publication version never overwrites an old one.
- Only confirmed mappings count (inherited from the concept reads).
- A frozen cell is never updated after publishing; drift is computed, never written back.
- Tolerance on proportions 0.0005 (spec §6), exact on counts.
- **Never `git commit` / `git push`.** No attribution. Plain names; match surrounding style.

## Definition (JSON, stored in `csi_publication.definition`)

```json
{"concept": "BT13_F00B90", "waves": ["2024-06-03", "2024-08-26", "2024-11-25", "2025-02-17", "2025-05-12"],
 "cohort": "BEAUTY_SHOPPER", "cut": "total", "pooled": true, "min_base": 30}
```

Cells: pooled → `row_key` = answer, `col_key` = `"<segment>|pct"`, `"<segment>|avg_age"`, `"<segment>|avg_income_k"`; per wave → `col_key` = `"<wave_label>|pct"`. `n`/`base_n` carried on the pct cell. Cells whose base is under `min_base` are frozen with `value = NULL` (suppressed, D5).

## Review Focus

1. Drift must flag a **moved** cell, a cell that **disappeared** (answer no longer mapped) and a **new** cell — and nothing when the data is unchanged.
2. Suppressed cells (base < min) stay suppressed on recompute and are not reported as moved.
3. Versioning: publishing the same code again creates version + 1; the old version and its cells stay.
4. A definition naming a wave not loaded or a concept that no longer exists fails loudly at publish time, and drift reports it instead of crashing.

## Tasks

### Task 1: `compute` and `publish`
- Tests (`tests/test_phase5.py`, reusing the Phase 3/4 fixtures): pooled definition → cells equal `concept_pooled`'s rows (pct, avg age, avg income); per-wave definition → one pct cell per wave; base < min_base → `value` NULL; unknown concept / wave → `ValueError`; `publish` twice → versions 1 and 2, both kept; footnote generated from the bases and wave range when none given ("Base: N US respondents aged 18+, surveyed <Mon YYYY>–<Mon YYYY>. Averages use range midpoints. Source: Coresight Research.").
- Implement `definition_waves`, `compute`, `footnote`, `publish`, `list_publications`, `cells`.

### Task 2: `drift`
- Tests: unchanged data → all `same`; a changed answer (reject a mapping, or delete one answer and rebuild the cube) → `moved` with published/now/delta; a removed answer → `missing`; a newly mapped answer → `new`; suppressed stays quiet.
- Implement `drift(publication_id) -> DataFrame[row_key, col_key, published, now, delta, status]` and `drift_summary() -> DataFrame[publication, version, cells, moved, missing, new]`; CLI `python -m app.data.publications --drift` (exit 1 when anything moved).

### Task 3: Publications page
- `app/pages/8_Publications.py`: table of publications with drift status; pick one → frozen vs now (moved cells marked), footnote, Excel export (frozen numbers + definition + footnote); "Publish" form (concept, waves, cohort, cut, pooled, name, destination). NAV entry + `main.py` registration.
- Browser check on `dwh_stg`.

### Task 4: Exit test on `dwh_stg`
- Publish *"Beauty retailers — beauty shoppers, Jun 2024 – May 2025"* (definition above). Reload a contributing wave (`python -m etl.legacy_dwh --id SV_0IHGTy1GPAlUsGa`), run `--drift` → every cell `same`. Report the published numbers and the drift result.

### Task 5: Docs
- Spec status, README row, `docs/06-running-locally.md` (`publications --drift`), changed-file list (no commit).
