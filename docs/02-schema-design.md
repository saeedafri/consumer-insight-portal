# Database Schema — CSI Tables in `dwh_stg`

> Schema v2 (29 tables) is live in dwh_stg — see docs/superpowers/specs/2026-09-29-survey-platform-design.md §5. This document describes the 19 v1 tables, all of which v2 keeps unchanged.

**19 tables**, prefix `csi_`, plus eight `v_csi_` views.
DDL: `sql/001_schema.sql` · views: `sql/002_views.sql` · seed: `sql/003_seed_topics.sql`

---

## The two decisions that shape everything

### 0. The survey is treated as data, not as code

The questionnaire is not a fixed thing this system knows about. Which questions
exist, what they are called, which module they belong to and which one supplies
"gender" are all **resolved per wave**:

| Concern | Where it lives | What happens to an unseen wave |
|---|---|---|
| question → module | `config/survey_map.yml` topic rules | unmatched questions get an `Unclassified` topic; nothing fails |
| module → is it technical | the same rules | unknown modules load and are visible |
| demographic cut → question | config for a known family, otherwise auto-detected from the question wording | an undetected cut is simply absent and the portal hides that filter |
| the resolution itself | `cip_profile_map`, written every load | an analyst can correct it in the table, no code change |
| age bands, generations, census regions | `config/survey_map.yml` | edit the YAML |

On the 09/21/26 wave the loader resolved all ten demographic cuts on its own
(`age<-D2, ethnicity<-D4, gender<-D1, income_band<-D5, …`) and classified 91 of
93 questions into modules, with 2 open-end variables left `Unclassified` —
loaded, visible, and harmless.

### 1. The fact table is long, not wide

The questionnaire changes every wave. This one has 375 columns; the next will
differ. A wide table means a migration every month and a portal that breaks
when a question is renamed. `cip_answer` holds **one row per respondent ×
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
| `seg_base_n` | `cip_segment` | how many people are in the column | 404 |
| `answer_base_n` | `cip_crosstab` | the denominator behind the percentage | 222 |
| `base_n` | `cip_question` | how many reached the question at all | 222 |

`answer_base_n` is recovered exactly as `count_n / pct` and is left **NULL**
when a 0% cell makes it unrecoverable — substituting the segment size is the
precise error this column exists to prevent.

---

## DEFINITION — what was asked

Loaded from the Forsta datamap.

| Table | Purpose | Rows, 09/21/26 |
|---|---|---|
| `cip_survey` | one row per **fielding week**: host, project path, `wave_label` (`2026-09-28`), field dates, `survey_family` for trending, `datamap_hash` to catch questionnaire drift. Unique on host + path + `wave_label`, because one Forsta project is re-fielded weekly with rotating modules | 1 per week |
| `cip_topic` | report modules — Department Stores, BNPL, GLP-1, Demographics, Technical | 10 |
| `cip_question` | one row per question as an analyst names it, **with its own `base_n` and `base_desc`** | 93 |
| `cip_item` | statement rows in a list or grid — `q1r1`, each retailer in `DP7`. Flags "None of these" so it drops out of rankings | 282 |
| `cip_option` | code → label. `0=Unchecked/1=Checked`, `1=Much worse … 6=Don't know`. `is_nonresponse` keeps "Don't know" out of Top-2-Box | ~450 |
| `cip_field` | the export column map: header → question + item. **375 rows, matching all 375 columns exactly** | 375 |

## DATA — what people said

| Table | Purpose | Rows |
|---|---|---|
| `cip_respondent` | one row per interview: status, timing, device, panel source, quota markers | 404 |
| `cip_profile` | flattened demographics — gender, age, band, generation, ethnicity, income, urbanicity, state, region, sentiment. Derived at load so a filter is one indexed join | 404 |
| `cip_answer` | **the fact table.** `value_code`, `value_label`, `value_number`, `value_text` in one row per respondent × field | ~151,000 |

## TABULATION — the published numbers

| Table | Purpose | Rows |
|---|---|---|
| `cip_banner` | cross-tab column groups: Gender, Age, Ethnicity, Income, Urbanicity, Politics, Sentiment | 7 |
| `cip_segment` | one row per column, with the **Forsta definition kept verbatim** (`(D2.ch12 or D2.ch10 or …)`), segment size, stat-test letter, low-base flag | 40 |
| `cip_crosstab_run` | the Summary-sheet settings — respondent base, percentage base, filters, stat tests | 1 per export |
| `cip_crosstab` | every cell: percentage, count, **true denominator**, significance letters. `item_label` disambiguates grid sub-tables; `stub_type` separates item rows from Net / Mean / Count | 31,800 |

## LOADING — how it got here

| Table | Purpose |
|---|---|
| `cip_load_log` | audit row per load: source, object, rows read/loaded/bad, status, error |
| `cip_load_error` | rows that failed validation, with reason and payload |
| `cip_load_state` | watermarks, so incremental pulls never re-read a whole survey |
| `cip_profile_map` | which question fed each demographic cut this wave, and whether that came from config or detection |

---

## Relationships

```
cip_survey ─┬─< cip_question ─┬─< cip_item ──┐
            │                 └─< cip_option │
            │                                │
            ├─< cip_field >──────────────────┘
            │        │
            ├─< cip_respondent ──< cip_answer >──┘
            │        └─1:1─ cip_profile
            │
            ├─< cip_banner ──< cip_segment ──┐
            │                                │
            └─< cip_crosstab_run ──< cip_crosstab
                                         │
                      (question_id, item_id, segment_id)
```

Deleting a survey cascades to its definitions, respondents, answers and
cross-tabs, so a bad wave can be dropped and reloaded cleanly.

---

## Views

| View | What it answers |
|---|---|
| `v_cip_answers` | denormalised answer stream with demographics attached |
| `v_cip_item_incidence` | "% who selected each item", **on the question's own base** |
| `v_cip_single_distribution` | single-punch distributions, with base |
| `v_cip_grid` | grid questions — item × scale point (DP7 retailers, GP6 categories) |
| `v_cip_crosstab` | the cross-tab grid, carrying both the segment size and the denominator |
| `v_cip_trend` | wave-over-wave series keyed on `survey_family` |
| `v_cip_survey_health` | field stats — qualified, terminated, overquota, average length |
| `v_cip_question_base` | every question with its base and what share of the wave it represents |

---

## Indexing

- `cip_answer (survey_id, field_id, value_code)` — the incidence path
- `cip_profile (survey_id, generation, gender, income_band)` — the filter path
- `cip_crosstab (survey_id, question_id, segment_id)` — the grid path
- `cip_survey (survey_family, wave_date)` — the trend path

InnoDB, `utf8mb4_0900_ai_ci` throughout. The utf8mb4 is not optional — retailer
names carry curly apostrophes (`Smith's Food & Drug`) that corrupt under latin1.

## Deliberate omissions

- **No weighting engine.** `cip_profile.weight` defaults to 1.0 and the views
  multiply through it. These waves are unweighted; the scheme has to come from
  the research team, not the pipeline.
- **No partitioning.** Premature at ~2M rows a year. Revisit past ~50M.
- **No verbatim coding.** Open-ends land in `cip_answer.value_text`. Coded
  verbatims later would be a `csi_verbatim_code` table joining on `answer_id` —
  additive, not a redesign.
