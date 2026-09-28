# Database Schema — CSI Tables in `dwh_stg`

**16 tables**, prefix `csi_`, plus eight `v_csi_` views.
DDL: `sql/001_schema.sql` · views: `sql/002_views.sql` · seed: `sql/003_seed_topics.sql`

---

## The two decisions that shape everything

### 1. The fact table is long, not wide

The questionnaire changes every wave. This one has 375 columns; the next will
differ. A wide table means a migration every month and a portal that breaks
when a question is renamed. `csi_answer` holds **one row per respondent ×
field**, so new questions are new rows and no DDL is ever needed.

Volume is trivial: 404 × 375 ≈ 151,000 rows per wave, under 2 million for a
year of monthly waves.

### 2. Every percentage carries its own base

This is the important one, and it came out of reading the files.

**Most of this questionnaire is routed.** Only 222 of 404 respondents bought
from a department store, so DP2–DP8 were asked of 222. Only 133 use BNPL, so
BN2–BN8 were asked of 133. Only 71 take a GLP-1 drug, so GP2–GP10 were asked
of 71. Forsta prints `N=404` in the cross-tab header — that is the *segment
size* — but divides by the *answering base*. Read the header and you overstate
the denominator by up to 6×.

So the schema keeps the two apart, deliberately:

| Column | Table | Meaning | DP2 example |
|---|---|---|---|
| `seg_base_n` | `csi_segment` | how many people are in the column | 404 |
| `answer_base_n` | `csi_crosstab` | the denominator behind the percentage | 222 |
| `base_n` | `csi_question` | how many reached the question at all | 222 |

`answer_base_n` is recovered exactly as `count_n / pct` and is left **NULL**
when a 0% cell makes it unrecoverable — substituting the segment size is the
precise error this column exists to prevent.

---

## DEFINITION — what was asked

Loaded from the Forsta datamap.

| Table | Purpose | Rows, 09/21/26 |
|---|---|---|
| `csi_survey` | one row per wave: host, project path, field dates, `survey_family` for trending, `datamap_hash` to catch questionnaire drift | 1 |
| `csi_topic` | report modules — Department Stores, BNPL, GLP-1, Demographics, Technical | 10 |
| `csi_question` | one row per question as an analyst names it, **with its own `base_n` and `base_desc`** | 93 |
| `csi_item` | statement rows in a list or grid — `q1r1`, each retailer in `DP7`. Flags "None of these" so it drops out of rankings | 282 |
| `csi_option` | code → label. `0=Unchecked/1=Checked`, `1=Much worse … 6=Don't know`. `is_nonresponse` keeps "Don't know" out of Top-2-Box | ~450 |
| `csi_field` | the export column map: header → question + item. **375 rows, matching all 375 columns exactly** | 375 |

## DATA — what people said

| Table | Purpose | Rows |
|---|---|---|
| `csi_respondent` | one row per interview: status, timing, device, panel source, quota markers | 404 |
| `csi_profile` | flattened demographics — gender, age, band, generation, ethnicity, income, urbanicity, state, region, sentiment. Derived at load so a filter is one indexed join | 404 |
| `csi_answer` | **the fact table.** `value_code`, `value_label`, `value_number`, `value_text` in one row per respondent × field | ~151,000 |

## TABULATION — the published numbers

| Table | Purpose | Rows |
|---|---|---|
| `csi_banner` | cross-tab column groups: Gender, Age, Ethnicity, Income, Urbanicity, Politics, Sentiment | 7 |
| `csi_segment` | one row per column, with the **Forsta definition kept verbatim** (`(D2.ch12 or D2.ch10 or …)`), segment size, stat-test letter, low-base flag | 40 |
| `csi_crosstab_run` | the Summary-sheet settings — respondent base, percentage base, filters, stat tests | 1 per export |
| `csi_crosstab` | every cell: percentage, count, **true denominator**, significance letters. `stub_type` separates item rows from Net / Mean / Count rows | 33,240 |

## LOADING — how it got here

| Table | Purpose |
|---|---|
| `csi_load_log` | audit row per load: source, object, rows read/loaded/bad, status, error |
| `csi_load_error` | rows that failed validation, with reason and payload |
| `csi_load_state` | watermarks, so incremental pulls never re-read a whole survey |

---

## Relationships

```
csi_survey ─┬─< csi_question ─┬─< csi_item ──┐
            │                 └─< csi_option │
            │                                │
            ├─< csi_field >──────────────────┘
            │        │
            ├─< csi_respondent ──< csi_answer >──┘
            │        └─1:1─ csi_profile
            │
            ├─< csi_banner ──< csi_segment ──┐
            │                                │
            └─< csi_crosstab_run ──< csi_crosstab
                                         │
                      (question_id, item_id, segment_id)
```

Deleting a survey cascades to its definitions, respondents, answers and
cross-tabs, so a bad wave can be dropped and reloaded cleanly.

---

## Views

| View | What it answers |
|---|---|
| `v_csi_answers` | denormalised answer stream with demographics attached |
| `v_csi_item_incidence` | "% who selected each item", **on the question's own base** |
| `v_csi_single_distribution` | single-punch distributions, with base |
| `v_csi_grid` | grid questions — item × scale point (DP7 retailers, GP6 categories) |
| `v_csi_crosstab` | the cross-tab grid, carrying both the segment size and the denominator |
| `v_csi_trend` | wave-over-wave series keyed on `survey_family` |
| `v_csi_survey_health` | field stats — qualified, terminated, overquota, average length |
| `v_csi_question_base` | every question with its base and what share of the wave it represents |

---

## Indexing

- `csi_answer (survey_id, field_id, value_code)` — the incidence path
- `csi_profile (survey_id, generation, gender, income_band)` — the filter path
- `csi_crosstab (survey_id, question_id, segment_id)` — the grid path
- `csi_survey (survey_family, wave_date)` — the trend path

InnoDB, `utf8mb4_0900_ai_ci` throughout. The utf8mb4 is not optional — retailer
names carry curly apostrophes (`Smith's Food & Drug`) that corrupt under latin1.

## Deliberate omissions

- **No weighting engine.** `csi_profile.weight` defaults to 1.0 and the views
  multiply through it. These waves are unweighted; the scheme has to come from
  the research team, not the pipeline.
- **No partitioning.** Premature at ~2M rows a year. Revisit past ~50M.
- **No verbatim coding.** Open-ends land in `csi_answer.value_text`. Coded
  verbatims later would be a `csi_verbatim_code` table joining on `answer_id` —
  additive, not a redesign.
