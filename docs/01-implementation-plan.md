# Implementation Plan — Consumer Insight Portal

**Goal.** Replace the Excel round-trip with survey data landing directly in the
STG (DWH) MySQL database, and give analysts a Streamlit portal that charts any
question, any cut, any wave.

**Current state.** A survey closes in Forsta, someone exports two workbooks, and
analysis happens in Excel. The numbers are fine; the process is manual, the
history lives in files, and nothing is queryable across waves.

---

## Phase 0 — Done

- Both 09/21/26 exports parsed and reverse-engineered end to end: 93 questions,
  375 variables matching all 375 export columns exactly, 404 respondents,
  40 banner segments, 78 cross-tab tables, 33,240 cells. See
  `05-source-data-analysis.md`.
- Forsta platform identified and the API verified live against
  `se1.decipherinc.com`. See `03-forsta-integration.md`.
- Schema drafted — 16 tables, 6 views. See `02-schema-design.md`.
- Repository scaffolded with a working Excel loader, an API client, and the
  Streamlit app.

## Phase 1 — Credentials (blocked on IT)

Hand `04-it-requirements-checklist.md` to IT. Four blocking items: the Forsta
service-account API key, directory `58f` permissions, the STG MySQL connection
with two accounts, and a firewall rule.

**This phase is the critical path. Nothing downstream needs anything else.**

## Phase 2 — Schema deployment (½ day once credentials land)

```bash
python scripts/test_connection.py     # verify both integrations
python scripts/init_db.py             # apply 001 → 002 → 003
```

`004_grants.sql` goes to the DBA rather than being run by the app.

## Phase 3 — Excel backfill (1 day) — does not wait for the API key

The Excel path works today. Load the 09/21/26 wave and any historic waves the
team has on disk:

```bash
python -m etl.run_pipeline --source excel \
    --raw "Raw Data 09_21_26.xlsx" \
    --crosstab "Cross Tabs 09_21_26.xlsx" \
    --wave 2026-09 --family CSI-US
```

Doing this before the API arrives means the portal has real data to build
against, and the Excel loader stays as a permanent fallback for any wave that
predates the integration.

**Acceptance:** `csi_field` has 375 rows; `csi_respondent` has 404;
`v_csi_item_incidence` for `q1` returns 52.7% for "Met up with friends or
family locally", matching the cross-tab to the decimal.

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
| Recomputed vs published divergence | credibility | store both, label both, reconcile in Phase 6 |

---

## Note on the "Arcify" skill

There is no skill named Arcify available in this workspace — not in the
installed set, and no match in the skills catalogue. It may be an internal tool
under a different name, or not yet published. The implementation plan above was
produced without it.

If you can point me at where Arcify lives — a repo, a marketplace, a package
name — I will install it and redo the plan through it. If it turns out to be a
house convention rather than a tool, tell me what it prescribes and I will
restructure these documents to match.
