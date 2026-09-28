# Database Schema — Consumer Insight Portal

**16 tables in four layers**, all prefixed `cip_`, plus six `v_cip_` reporting
views. DDL: `sql/001_schema.sql`, views: `sql/002_views.sql`.

---

## The one design decision that matters

The questionnaire changes every wave. This wave has 375 variables; next wave
will have a different number, different modules, different retailer lists.

A **wide** table (one column per variable) would mean a schema migration every
month, and a portal that breaks whenever a question is renamed. So the fact
table is **long**: one row per respondent × variable. New questions are new
rows, not new columns. No DDL, ever.

The cost is volume, and it is trivial here: 404 respondents × 375 variables ≈
151,000 rows per wave. Twelve monthly waves is under 2 million rows.

Two things soften the usual downsides of a long table:

- `cip_respondent_profile` denormalises the eight demographic cuts the portal
  filters on constantly, so a "GenZ women in the Midwest" filter is one indexed
  join rather than eight EAV lookups.
- `cip_crosstab_cell` stores the published numbers as computed by Forsta, so the
  portal never has to recompute a figure that already appeared in a report.

---

## Layer A — Definition (what was asked)

Loaded from the Forsta datamap. Six tables.

| # | Table | Purpose | Rows this wave |
|---|---|---|---|
| 1 | `cip_survey` | One row per wave. Host, project path, field dates, `survey_family` for trending, `datamap_hash` to detect questionnaire drift. | 1 |
| 2 | `cip_question_group` | Editorial modules — Department Stores, BNPL, GLP-1, Demographics, Paradata. Gives the portal its navigation. | 10 |
| 3 | `cip_question` | One row per question as an analyst thinks of it: `q1`, `DP7`, `CS1`. Carries type, value range, multi-punch flag, base description. | 93 |
| 4 | `cip_question_row` | Statement rows inside a list or grid — `q1r1` "Met up with friends", each retailer in `DP7`. Flags "None of these" as exclusive so it drops out of rankings. | 282 |
| 5 | `cip_answer_option` | Code → label per question. `0=Unchecked/1=Checked`, or `1=Much worse … 6=Don't know`. `is_nonresponse` keeps "Don't know" out of Top-2-Box. | ~450 |
| 6 | `cip_variable` | The physical column map: export header → question + row. **375 rows, matching all 375 columns exactly.** This is the bridge that makes loading mechanical. | 375 |

## Layer B — Fact (what people said)

| # | Table | Purpose | Rows this wave |
|---|---|---|---|
| 7 | `cip_respondent` | One row per interview: status, completion time, length, device, panel source, quota markers. | 404 |
| 8 | `cip_respondent_profile` | Flattened demographics — gender, age, age band, generation, ethnicity, income, urbanicity, state, census region, sentiment. Derived at load. Reserves a `weight` column. | 404 |
| 9 | `cip_response` | **The core fact.** One row per respondent × variable. Holds `value_code`, `value_label`, `value_numeric` and `value_text` so coded, numeric and verbatim answers share one table. | ~151,000 |

## Layer C — Aggregate (the published numbers)

| # | Table | Purpose | Rows this wave |
|---|---|---|---|
| 10 | `cip_banner` | Cross-tab column groups: Gender, Age, Ethnicity, Income, Urbanicity, Politics, Sentiment. | 7 |
| 11 | `cip_segment` | One row per column, with the **Forsta definition expression kept verbatim** (`(D2.ch12 or D2.ch10 or …)`), its base, stat-test letter, and low-base flag. | 40 |
| 12 | `cip_crosstab_run` | The Summary-sheet settings — respondent base, percentage base, filters, stat-test levels. A percentage without these is not defensible. | 1 per export |
| 13 | `cip_crosstab_cell` | Every cell: percentage, count, base, significance letters. Handles Net/Mean/Count stub rows via `stub_kind`. | 33,240 |

## Layer D — Ops (how it got here)

| # | Table | Purpose |
|---|---|---|
| 14 | `cip_ingest_run` | Audit row for every load: source, object, counts read/loaded/rejected, status, error. Nothing enters CIP without one. |
| 15 | `cip_ingest_reject` | Rows that failed validation, with the reason and payload, so an analyst can see what was dropped instead of wondering. |
| — | `cip_datafeed_state` | Watermarks, so incremental pulls never re-read a whole survey. |

---

## Relationships

```
cip_survey ─┬─< cip_question ─┬─< cip_question_row ─┐
            │                 └─< cip_answer_option │
            │                                       │
            ├─< cip_variable >──────────────────────┘
            │        │
            ├─< cip_respondent ──< cip_response >───┘
            │        │
            │        └─1:1─ cip_respondent_profile
            │
            ├─< cip_banner ──< cip_segment ──┐
            │                                │
            └─< cip_crosstab_run ──< cip_crosstab_cell
                                        │
                     (question_id, row_id, segment_id)
```

Read as: a survey has questions; a question has rows and answer options; every
export column is a variable pointing at one question and optionally one row. A
respondent belongs to a survey and has one response per variable. Separately, a
survey has banners of segments, and a cross-tab run fills cells at the
intersection of question, stub row and segment.

Cascades are deliberate: deleting a survey removes its definitions, respondents,
responses and cross-tabs, so a bad wave can be dropped and reloaded cleanly.

---

## Views the portal reads

The app never touches base tables. Six views in `sql/002_views.sql`:

| View | What it answers |
|---|---|
| `v_cip_answers` | Denormalised answer stream with demographics attached — the general-purpose cut. |
| `v_cip_item_incidence` | "% who selected each item" for every multi-punch question. Powers most bar charts. |
| `v_cip_single_distribution` | Answer distribution for single-punch questions. Pie and stacked-bar source. |
| `v_cip_crosstab` | The cross-tab grid as an analyst expects to read it, with bases and significance letters. |
| `v_cip_trend` | Wave-over-wave series keyed on `survey_family`. |
| `v_cip_survey_health` | Field stats — qualified, terminated, overquota, average length. |

---

## Indexing

Beyond the primary and unique keys:

- `cip_response (survey_id, variable_id, value_code)` — the incidence path.
- `cip_respondent_profile (survey_id, generation, gender, income_band)` — the filter path.
- `cip_crosstab_cell (survey_id, question_id, segment_id)` — the grid path.
- `cip_survey (survey_family, wave_date)` — the trend path.

Every table is InnoDB / `utf8mb4_0900_ai_ci`. The utf8mb4 part is not optional:
the retailer lists contain curly apostrophes (`Smith's Food & Drug`), which
silently corrupt under `latin1`.

---

## Deliberate omissions

- **No weighting engine.** `cip_respondent_profile.weight` exists and defaults
  to 1.0. When Coresight starts weighting these waves, the column is there and
  the views multiply through it — but inventing a weighting scheme now would be
  guessing.
- **No partitioning.** At ~2M rows a year it would be premature. Revisit past
  roughly 50M rows in `cip_response`.
- **No verbatim coding tables.** The `…oe` open-ends land in
  `cip_response.value_text`. If the team wants coded verbatims later, that is a
  `cip_verbatim_code` table joining to `response_id` — additive, not a redesign.
