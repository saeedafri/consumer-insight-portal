# Forsta ETL, Schema and UI — Build Plan

**Spec:** `docs/superpowers/specs/2026-10-07-cip-forsta-etl-and-ui-design.md` (approved 7 Oct 2026 with these
decisions: rename to `cip_` — done; hibernated waves left alone; no Azure archive for now; Excel route retired).

## Global Constraints
- Forsta: GET only. Never reactivate, edit or delete a survey. The key stays in `.env`, never printed.
- `dwh_stg`: additive schema; our own `cip_` rows may be replaced by verified API loads.
- All filtering / aggregation server-side; the page reads pre-computed cells.
- TDD for every behaviour; never commit; no attribution.

## Tasks
1. **Rename `csi_` → `cip_`** — `schema_upgrade.rename_statements`, applied to `dwh_stg` and the local copy. ✅
2. **Retire the Forsta Excel route** — remove `ingest_excel`, crosstab ingestion, the Excel datamap/raw parsers, the
   Crosstabs page and the tests that need the export files; keep the shared helpers (`clean_text`, `ParsedQuestion`)
   used by the API, legacy and Qualtrics adapters.
3. **Schema** — register `cip_forsta_survey`; `cip_survey` launch/close/sample/total/tags; `cip_question.is_virtual`;
   `cip_item.left_label/right_label`; `cip_search` (FULLTEXT); indexes per spec §3.3; drop the duplicate
   `ix_answer_field`.
4. **API adapter** — answer labels from question *or* variable; bipolar left/right; `oe` text; flags `t`/`v`;
   technical values kept as values; PII dropped (`userAgent`, `url`, `session`), `RID` hashed.
5. **Pipeline** — `etl/forsta_etl.py`: discover (register) → load every closed, readable, unloaded survey (one
   survey = one wave) → verify → publish → harmonise / cohorts / cube / drift → search index; `--discover`,
   `--due`, `--survey`; weekly runner uses it.
6. **Backfill on `dwh_stg`** — every readable closed survey; the two Excel-loaded Forsta waves replaced by their
   API loads once verified; SurveyMonkey reload completed.
7. **UI** — search box (one FULLTEXT read); survey report with every question charted by shape (bar, donut,
   ranked bar, diverging stack, heatmap, bipolar butterfly, numeric distribution, verbatims); smooth transitions;
   P95 < 2 s.
8. **Review, docs, memory.**
