# Implementation Plan — Consumer Insight Portal

**Goal.** Replace the Excel round-trip with survey data landing directly in the
STG (DWH) MySQL database, and give analysts a Streamlit portal that charts any
question, any cut, any wave.

**Current state.** A survey closes in Forsta, someone exports two workbooks, and
analysis happens in Excel. The numbers are fine; the process is manual, the
history lives in files, and nothing is queryable across waves.

---

## Phase 0 — Done

- All four exports parsed: 09/21/26 (93 question blocks, 375 columns, 404
  respondents) and 09/28/26 (103 blocks, 519 columns, 403 respondents), raw +
  cross-tab for each. See `05-source-data-analysis.md`.
- Forsta platform identified; API host and auth scheme verified live. See
  `03-forsta-integration.md`.
- Schema: 19 tables, 8 views. See `02-schema-design.md`.
- Data flow diagram: `.archify/dataflow-cip-ingestion-20260929-162000/cip-dataflow.html`.

## Phase 1 — Credentials — one item left

- **STG (DWH) MySQL — resolved.** `dwh_stg` on
  `csr-mysql8-flex-stg.mysql.database.azure.com`, account `dwh_app_access`.
- **Forsta API — blocked.** The key on file is rejected:
  `401 API user account is not valid: account disabled`. IT must re-enable the
  user or issue a new key. See `04-it-requirements-checklist.md`.

## Phase 2 — Schema deployment — done 29 Sep 2026

`scripts/init_db.py` applied 001 → 002 → 003 to `dwh_stg`.
`004_grants.sql` (read-only `csi_app` for the portal) still goes to the DBA.

## Phase 3 — Excel backfill — done 29 Sep 2026

```bash
python -m etl.run_pipeline --source excel --raw "Raw Data 09_21_26.xlsx" \
    --crosstab "Cross Tabs 09_21_26.xlsx" --wave 2026-09-21
python -m etl.run_pipeline --source excel --raw "raw data 09-28-2026 2.xlsx" \
    --crosstab "Shopping and Spending - inc Beauty + Holiday + Inflation + Cross tab 09-28- 2026  2.xlsx" \
    --wave 2026-09-28
python scripts/reconcile.py
```

Each fielding week is its own wave (`--wave YYYY-MM-DD`). The Excel loader stays
as a permanent fallback for any wave that predates the API.

**Acceptance (met):** `scripts/reconcile.py` reproduces every published Total
cell from raw answers — 667/667 (09/21) and 788/788 (09/28). See
`09-data-verification.md`.

## Phase 4 — API pipeline (2 days, once the key lands)

```bash
python -m etl.run_pipeline --source api --wave 2026-10 --family CSI-US
```

Runs the same loaders; only the reader changes. Work in this phase:

- Reconcile the API datamap's JSON shape against the Excel-derived model
  (`_questions_from_api_datamap` is written against the documented shape and
  will need a pass against the real payload).
- Confirm whether a codes layout exists and switch to it if so.
- Verify an API-loaded wave reproduces the Excel-loaded wave row for row. Load
  09/21/26 both ways and diff — this is the acceptance test.
- Schedule: daily 02:00 IST, plus on-demand at field close.

## Phase 5 — Portal build-out (1 week)

Five pages ship in the scaffold: Overview, Question explorer, Cross-tabs,
Trends, Data health. Remaining work is analyst-driven:

- Wire Coresight SSO, matching SIP-Prod's `auth_manager`.
- Export to PowerPoint in house template, and to Excel.
- Saved views, so an analyst can bookmark a cut.
- Significance-test display on the cross-tab grid.

## Phase 6 — Hardening

Low-base suppression rules agreed with the research team; a reconciliation job
that compares recomputed percentages against `csi_crosstab` and alerts on
drift; alerting on failed ingest runs; a runbook.

---

## Two things worth deciding early

**1. Does the portal show recomputed numbers or Forsta's numbers?**

Both are stored, and they will occasionally disagree in the last decimal —
different rounding, different handling of "Total Answering" versus "Total
Respondents". The recommendation is: **cross-tab cells are the published
figures; recomputed incidence is for exploratory cuts Forsta didn't tabulate**,
and the portal labels which is which. Getting 52.8% on a slide where the report
said 52.7% is a credibility problem, not a rounding one.

**2. Weighting.**

These waves appear unweighted — the cross-tab bases are raw counts. If
Coresight starts weighting, `csi_profile.weight` and the views are
ready, but the scheme has to come from the research team, not from the
pipeline.

---

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| API key delayed | blocks Phase 4 | Excel loader is a complete path; Phases 2–3 and 5 proceed regardless |
| Questionnaire changes between waves | trend series break | `datamap_hash` flags drift; long fact table absorbs new questions with no DDL |
| API datamap JSON differs from the documented shape | rework in Phase 4 | isolated to one adapter function |
| Low bases charted as if solid | wrong conclusions in client work | `low_base` carried through; portal warns |
| Recomputed vs published divergence | credibility | `scripts/reconcile.py` after every load; exits 1 on any mismatch |

---

## Diagrams — Archify

The "Arcify" skill is **Archify** (installed at `~/.claude/skills/archify`).
It produced the ingestion data-flow diagram above (Forsta / Excel → ETL →
`csi_` table groups → `v_csi_` views → portal), validated and browser-checked.
Regenerate after an architecture change with
`node ~/.claude/skills/archify/bin/archify.mjs finalize dataflow <candidate.json> <out.html> --quality showcase`.
