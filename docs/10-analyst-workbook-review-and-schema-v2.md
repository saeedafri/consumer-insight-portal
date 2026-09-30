# Analyst Workbook Review → Schema v2

Every file and every tab was read (values **and** formulas, pivot definitions,
the chart's source ranges). Nothing was edited — the workbooks were opened
read-only and their modified times are unchanged.

The point of this review: the portal's schema should let an analyst get what
these workbooks give them — in one query, across any set of waves, without
copying columns between sheets.

---

## 1. Inventory

### Forsta exports (2026)

| File | Tabs | Content |
|---|---|---|
| `Raw Data 09_21_26.xlsx`, `raw data 09-28-2026 2.xlsx` | `A1`, `Datamap` | one row per respondent (labels, `NO TO:` for unselected); question dictionary |
| `Cross Tabs 09_21_26.xlsx`, `Shopping and Spending … Cross tab 09-28- 2026  2.xlsx` | `Summary`, `Percentages`, `Counts` | run settings + banner definitions; 78 / 80 stacked tables × 40 banner columns |

Already loaded and reconciled (docs/05, docs/09).

### Qualtrics exports (2024–2025) — five Beauty waves

| Wave | File date | Respondents | Columns |
|---|---|---|---|
| Beauty + Health Tech + Mother's Day Retro + Inflation | Jun 4 2024 | 401 | 353 |
| Beauty + Black Friday + Inflation | Aug 26 2024 | 405 | 362 |
| Beauty + Holiday Retailers + Inflation | Nov 25 2024 | 402 | 366 |
| Beauty + Shrink + Valentine's Retro + Inflation | Feb 17 2025 | 406 | 351 |
| Beauty + Inflation + Tariffs | May 20 2025 | 405 | 359 |

One tab each (`Sheet0`): row 1 = column codes (`B10_3`), row 2 = question text,
then respondents (`ResponseId` = `R_…`). 284 columns are common to all five.
Beauty module **B1–B12** is in every wave — the same questions Forsta asks as
**BT1–BT15** in 09/28/26.

In `dwh_stg` (legacy `dwh_sm*` tables): the first four are present
(`SV_2gVtzEXhcL4sFIq`, `SV_0HupbIPhUyQyPWu`, `SV_4Uh7R7ZdGnYveCy`,
`SV_0IHGTy1GPAlUsGa`; Feb 2025 matched respondent-for-respondent).
**May 2025 is missing** — the Excel file is its only source.

### `Beauty Shopper Profiles - Copy.xlsx` — the data team's analysis (11 tabs)

| # | Tab | What it is | How it is built |
|---|---|---|---|
| 1 | Collated Four Waves | 1,614 respondents, Oct 2023 · Dec 2023 · Mar 2024 · Jun 2024 | raw rows pasted under question-text headers; 26 analyst columns added |
| 2 | Cross-Check | respondents per retailer, per wave, vs the pivot total | 4 SharePoint dashboards typed in by hand, `SUM` per row |
| 3 | Updated–Five Waves Combined | 2,019 respondents, Jun 2024 → May 2025 | same stacking; 24 analyst columns |
| 4 | Updted–Avg age, Income & Gender | per retailer: count by income / urbanicity / gender / age; avg age and income | 1 pivot + formulas (`SUMPRODUCT` on range midpoints) |
| 5 | Beauty Pivot Age and Income | same for the four-wave set, plus B2 "why buy" and B7/B8 products by gender | 5 pivots + formulas |
| 6 | Men Beauty | gender shares, pasted as values | copied from tab 5 |
| 7 | BUBBLE CHART | retailer × avg age × avg income × n; retailers with n < 90 removed by hand | cell references into tab 5 + a bubble chart |
| 8 | Age Income Beauty Total | avg age / income of all beauty shoppers | 1 pivot + midpoint formulas |
| 9 | Base Footnote for Dashboard | "Base: 1,614 US respondents aged 18+, surveyed October 2023–June 2024 …" | typed |
| 10 | Updated–Base Footnote | "Base: 2,019 … June 2024–May 2025 …" | typed |
| 11 | Updated Source | five SharePoint links, one per wave | typed |

---

## 2. What the analysts actually compute

Read from the pivots and formulas, not guessed:

1. **Stack waves.** Same question across 4–5 waves into one table, matched on question text.
2. **Rename answer columns.** B10's 21 retailer columns become `Amazon.com`, `CVS`, … (with stray leading spaces and a `Kohl'sÂ` encoding artefact).
3. **Define a segment by rule.** *Beauty shopper* = B1 = Yes, **or** not asked B1 (split sample in Dec 2023 / Jun 2024) but answered the spend question B12. 911 B1-Yes becomes 1,200 shoppers.
4. **Count respondents** choosing each option, broken by income, age group, gender, urbanicity.
5. **Composition (column %).** e.g. of Amazon beauty buyers, 55% female.
6. **Averages from bands.** Age and income averaged on range midpoints: 18–29 → 23.5, over 60 → 67, $50k–$99,999 → 74.9995, $200k+ → 225, excluding "prefer not to say".
7. **Suppress small bases.** n < 90 removed from the chart by hand.
8. **Cross-check** counts against earlier dashboards, per wave.
9. **Footnote.** Base n, population, fieldwork period, method note, source.

## 3. Defects found in the workbook

| Where | Defect | Evidence |
|---|---|---|
| BUBBLE CHART | **19 of 21 bubbles show another retailer's numbers.** Row 4–6 references pull by column position from tab 5, whose age pivot orders retailers differently from the chart header. | "Amazon.com" bubble: n = 46, age 35.0 — that is *A brand's livestream*. Real Amazon: n = 451, age 45.0. The chart plots `'BUBBLE CHART'!B4:W6`. Only Instagram and Sephora line up, by coincidence. |
| Men Beauty (rows 1–5) | **"52% male" is not men's share of beauty buyers.** The pivot counts everyone who *answered* B1 — including "No". | Men are **43.1 %** of beauty shoppers (45.3 % of B1 = Yes); 59.6 % of men asked bought beauty vs 78.4 % of women. |
| All stacked tabs | Question-text matching across waves; labels with leading spaces and `Â`. | Fragile: a reworded question silently becomes a new column. |
| BUBBLE CHART | n < 90 exclusion applied by deleting chart points; the "before exclusions" row keeps different n (527, 119, …) with no stated base. | Not reproducible. |

These go back to the data team; the portal will compute all of it from the database so none of it can recur.

---

## 4. Schema v2 — what changes

The v1 schema (19 tables, docs/02) already stores every answer long-format per
wave. It cannot yet do three things the workbook needs: **link the same
question across waves and platforms**, **store analyst-defined segments**, and
**average banded answers**. Five tables and three columns close the gap.

### New tables

| Table | Purpose | Key columns |
|---|---|---|
| `csi_concept` | one canonical question across waves and platforms — "Beauty retailers used, past 3 months" | `concept_code` (`BEAUTY_RETAILER_3M`), `concept_name`, `topic_id`, `qtype` |
| `csi_concept_option` | canonical answer — "Amazon.com", "$50,000–$99,999" — with a numeric midpoint when it is a band | `concept_id`, `option_code`, `option_label`, `midpoint`, `sort_order` |
| `csi_concept_map` | wave-specific → canonical: Qualtrics `B10_3`, Forsta `BT13r1`, legacy `dwh_smanswer.id` all map to `BEAUTY_RETAILER_3M / amazon` | `survey_id`, `question_id`, `item_id` / `option_id`, `concept_option_id`, `mapped_by` (rule · manual), `mapped_at` |
| `csi_segment_def` | a named, versioned cohort rule — *Beauty shopper* — as JSON over concepts | `segment_code`, `segment_name`, `rule_json`, `base_note`, `version` |
| `csi_respondent_segment` | materialised membership, rebuilt when a rule or a wave changes | `respondent_id`, `survey_id`, `segment_code` |

### Changed tables

| Table | Change | Why |
|---|---|---|
| `csi_survey` | + `platform` (`forsta` · `qualtrics`), + `source_ref` (`selfserve/58f/beauty`, `SV_0IHGTy1GPAlUsGa`) | two platforms feed one family; one identity column each |
| `csi_profile` | + `age_mid`, + `income_mid_k` (from `csi_concept_option.midpoint`) | "average age / income" becomes `AVG()` in SQL, with the same midpoints the analysts use |

### Relationships

```
csi_survey ─< csi_question ─< csi_item / csi_option
                  │                    │
                  └──── csi_concept_map ┘──> csi_concept_option >── csi_concept
csi_respondent ─< csi_answer   (unchanged, long format)
csi_respondent ─< csi_respondent_segment >── csi_segment_def
csi_respondent ── csi_profile  (+ age_mid, income_mid_k)
```

### Every tab becomes one query

| Workbook tab | Portal equivalent |
|---|---|
| Collated Four / Five Waves | pick waves + concepts → `v_csi_concept_answers` stacks them; Excel export of the stacked rows |
| Cross-Check | concept option × wave counts; the published totals come from the same rows, so there is nothing to cross-check by hand |
| Avg age, Income & Gender / Beauty Pivot | concept option × profile dimension: count, column %, `AVG(age_mid)`, `AVG(income_mid_k)`, over any segment |
| Men Beauty | same query, break = gender, measure = composition — with the base printed |
| BUBBLE CHART | the pivot above, drawn as a bubble chart, labels joined by key (cannot drift), `min_base` filter instead of deleting points |
| Base Footnote | generated: n, population, first–last fieldwork month, method note, source |
| Updated Source | `csi_survey.source_ref` + `csi_load_log.source_ref` per wave |

## 5. Loading plan

| Source | Waves | Route |
|---|---|---|
| Forsta API (key pending) or Forsta Excel | Aug 2025 → | existing pipeline |
| `dwh_stg.dwh_sm*` (legacy Qualtrics) | 2018 → Aug 2025, incl. Oct 2023 · Dec 2023 · Mar 2024 and 4 of the 5 Beauty waves | new read-only loader into `csi_` |
| Qualtrics Excel | May 2025 (not in `dwh_stg`) | new parser for the two-header-row export |

`scripts/reconcile.py` extends to Qualtrics waves: every loaded wave's Beauty
counts must equal the workbook's pivots (e.g. Amazon = 492 across the five
waves, beauty shoppers = 1,200 across the four).

## 6. Open questions for the data team

1. Is *Beauty shopper* always "B1 = Yes, or not asked B1 but answered B12"? Or was that a one-off for the split-sample waves?
2. Is **n < 90** the house minimum base for charts, or chart-specific?
3. Should Oct 2023 / Dec 2023 use the "Last Mile" or the "Last Mile – RIWI" survey (both are in `dwh_stg`, 438 vs 435 responses)?
4. The workbook keeps 402 (Oct 2023) and 405 (Mar 2024) respondents where `dwh_stg` records 422 and 416 responses. Which filter removes the rest — completes only, quality checks, or something else? The loader must apply the same rule.
