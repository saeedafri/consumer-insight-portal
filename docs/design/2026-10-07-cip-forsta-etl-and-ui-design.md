# CIP — Forsta ETL, Schema and UI: Investigation and Design

**Status:** approved 7 Oct 2026 and built (plan: `docs/superpowers/plans/2026-10-07-forsta-etl-build.md`).
Decisions: A rename done (`cip_`); B hibernated waves left alone (no reactivation); C no Azure archive for now
(`cip_raw_archive` not built); D all statuses loaded; E Excel route retired. Partitioning deferred (§3.3).
**Date:** 7 October 2026. **Scope:** the Consumer Insight Portal (CIP) tables in `dwh_stg`
(today prefixed `csi_`), the Forsta (Decipher) API as the single source from now on, the
ETL pipeline, indexes, and the portal UI.

Everything below was verified read-only: Forsta `GET` calls only (no survey, API or
database changed), and the Decipher OpenAPI specification
(`docs.developer.focusvision.com/static/media/decipher-api.yaml`, 174 endpoints).

---

## 1. What the investigation found

### 1.1 Access

| Check | Result |
|---|---|
| Key (in `.env`, never printed) | authenticates as Mohd Saeed Afri — user 879, company 86 |
| Surveys visible | **90** (82 closed, 8 testing), directory "Coresight Research" |
| Datamap + data | full download: 57 questions / 395 variables / 403 respondents in 3.8 s (2 MB) for one wave |
| Hibernated surveys | **56** (45 tracker waves) answer **428 "needs to be reactivated"** — reactivation is a change in Forsta, not done |
| Retention | every survey: `server_delete_days: 365` — **Forsta deletes a survey a year after creation** |

### 1.2 How surveys are posted, deployed and made public

| Pattern | Evidence |
|---|---|
| **One new survey per wave** | path `selfserve/58f/YYMMNN` (e.g. 260906, 260907, 260908); the first wave was `weekly_consumer` (Jun 2025) |
| **Weekly cadence** | 69 tracker waves since 4 Jun 2025; 31 gaps of 7 days, 29 of 6, a few holiday shifts (9, 12, 28 days) |
| **Monday launch** | 63 of 66 launches on Monday, **12–13 UTC** (≈ 17:30–18:30 IST) |
| **Short fielding** | launch → close median **12.8 h** (2.4 h – 6 days) |
| **Fixed sample** | ~400 qualified (~500 total incl. terminates/overquota), panel sample source `114` |
| **Tagging** | `Weekly consumer tracker` (69), `annual tracker` (Holiday ≈ 2,000, Amazon Apparel, Online Grocery, Back-to-school), untagged client studies (T-Mobile, Zebra, APTOS, Rokbot, Simbe, ARC: 100–300 each) |
| **Lifecycle** | `testing` → launched → `closed`; hibernated after ~3–4 months; deleted after 365 days |
| **Public** | surveys are fielded to a panel, not published; the API is the only programmatic way out |

So the right ETL rhythm is **event-driven weekly**: discover new surveys daily, load each
wave as soon as it closes (Monday night / Tuesday morning IST), and never wait months —
a wave not loaded before hibernation needs a manual reactivation.

### 1.3 How questions are structured (23 readable tracker waves, 1,416 questions)

| Shape (type, grouping, variables) | Count | Meaning |
|---|---|---|
| single · cols · 1 variable | 693 | single choice |
| multiple · cols · many | 491 | checkbox list (one 0/1 variable per item) |
| single · rows · many | 73 | grid: one rating per row |
| single · cols · many | 53 | single choice + an "Other (specify)" text variable (`…oe`) |
| single · rows · 1 | 43 | one-row grid / bipolar |
| float / number | 32 | numeric (incl. `qtime`) |
| text | 23 | open text (incl. `start_date`) |

- **A fixed core in every wave (24 items):** screener `q1`–`q5`, demographics `D1`–`D8`,
  outlook `CS1`–`CS2`, and system fields (`status`, `qtime`, `start_date`, `vlist`, `vos`,
  `vbrowser`, `vmobiledevice`, `vmobileos`, `vdropout`).
- **Rotating modules by prefix:** BT beauty, TF tariffs, HX holiday, IN inflation, GP/GU,
  AP, DS, XM, LX, SC, EC, HF, CPG, SHRNK, EAT … (2–5 per wave).
- **Codes are not stable:** the same code carries different wording across waves (`D2`,
  `BT14`, `DS1`–`DS7`). `D2` changed scheme: age **bands** in Oct 2025, **single years**
  from 2026. Questions must be linked by wording (the harmoniser), never by code.
- **Flags:** `t` = technical (conditions, qtime, start_date), `v` = virtual/derived
  (vlist, vos, vbrowser). Neither is an analysis question.
- **Answer labels live in two places:** on the question (35 in one wave) and on each
  variable (64). Bipolar grids (`HX6`) have **blank** option titles — the meaning is the
  row's left statement (code 1) vs right statement (code 2, in the `_r` variable).

### 1.4 How answers are formatted

- `format=json` returns one object per respondent, **every value a string**: status `"3"`
  (1 terminated · 2 overquota · 3 qualified · 4 partial), checkbox `"0"`/`"1"`, single
  choice `"1"`…`"n"`, numbers as text, verbatims as text, date `"09/28/2026 10:56"`.
- Records also carry `userAgent`, `url`, `session`, `RID` (panel id), `dcua`, `markers`.
  **`userAgent`, `url`, `session` are not to be stored; `RID` is stored only as a hash**
  (design decision D7).

### 1.5 The API compared with what is stored today

Wave 2026-09-28 (`260907`): all 403 respondents and every API field exist in `dwh_stg`;
**120,861 of 128,712 values identical.** The rest:

- **HX6 bipolar grid — ~3,300 answers lost** by the Excel route (blank labels → no code).
  The API gives the codes; the API route is the more complete one.
- `list`, `qtime`, `record` stored as code 1 instead of their value (technical only).

### 1.6 What `dwh_stg` holds today

| | |
|---|---|
| Waves | Forsta 2 · Qualtrics 142 · SurveyMonkey 16 of 145 (reload interrupted) |
| Rows | `cip_answer` 12.2 M (3.9 GB) · `cip_agg_cell` 1.2 M · 88 k respondents |
| Harmonisation | 934 concepts; 3,530 confirmed links; 1,050 proposals waiting |
| Housekeeping | 3 load runs stuck `running` (interrupted sessions) |

---

## 2. How others store survey data (and what we take)

| Approach | Used by | Fit for CIP |
|---|---|---|
| **Wide table** (one column per variable) | SPSS / Excel exports, Forsta "flat" | breaks every week as modules rotate — **rejected** |
| **Long fact table** (respondent × variable × value) + dimensions | survey warehouses, Qualtrics/Decipher back ends, EAV | schema never changes with the questionnaire — **kept** (already `cip_answer`) |
| **Star schema** with conformed dimensions (survey, question, option, respondent, demographic) | BI warehouses | **kept**: concept + concept option are the conformed "question" dimension across waves |
| **Pre-aggregated cube** (OLAP cells) | Tableau extracts, Power BI aggregations, ClickHouse materialized views | **kept**: `cip_agg_cell`, 0.35 s P95 for a standard view |
| Columnar engine (ClickHouse / BigQuery) | very large panels | not needed at < 100 M rows; MySQL is the given platform |

---

## 3. Proposed design

### 3.1 Naming: `csi_` → `cip_`

All 29 tables and 9 views renamed in **one atomic `RENAME TABLE … TO …` statement**
(metadata only in MySQL — no data copied, seconds). Views recreated under the new names.
Code switches through one constant. **Needs explicit approval**: it is a change to the
shared STG database, and the old names stop working at that moment.

### 3.2 Schema changes (additive)

| Change | Why |
|---|---|
| `cip_survey`: `launched_at`, `closed_at`, `sample_source`, `total_n`, `forsta_state`, `tags` (JSON) | cadence, fielding window, sample — from the survey list |
| `cip_survey.study_type` from tags (`tracker` / `annual` / `adhoc`) | filters by study |
| `cip_question.is_virtual` (flag `v`), technical from flag `t` | keep system fields out of reports |
| `cip_item.left_label`, `cip_item.right_label` | bipolar grids: what codes 1 and 2 mean per row |
| `cip_raw_archive` (survey, kind, sha256, blob uri, fetched_at) | Forsta deletes after 365 days — our copy is the record (D8) |
| `cip_search` (survey, question, concept, text, FULLTEXT) | instant report search |
| `cip_forsta_survey` (path, title, state, hibernated, launched/closed, last_seen, load_state) | discovery register — the ETL's to-do list |

### 3.3 Indexes

| Index | Serves |
|---|---|
| `cip_answer (survey_id, field_id, value_code, respondent_id)` covering — exists | item incidence, cube build |
| `cip_answer (respondent_id, field_id)` unique — exists | upsert, cohort rules |
| `cip_agg_cell (survey_id, map_key, cohort_id, dim)` — exists | concept trends (one indexed read) |
| `cip_agg_cell (survey_id, question_id, dim)` — exists | standard views |
| `cip_concept_map (concept_option_id)`, `(survey_id, question_id)` — exist | trend joins |
| **new** `cip_search` FULLTEXT `(text)` | search box |
| **new** `cip_survey (load_status, study_type, wave_date)` | wave pickers |
| **new** `cip_respondent (survey_id, is_qualified)` covering | bases |
| **drop** `ix_answer_field` | duplicated by the covering index (saves write cost) |

**Partitioning:** not now. InnoDB does not allow foreign keys on partitioned tables, and
at 12 M rows (≈ 25 M once the Forsta history and SurveyMonkey are in) every hot read
already leads with `survey_id` on an index. Trigger to revisit: `cip_answer` > 100 M rows
→ `PARTITION BY HASH(survey_id)` with integrity moved into the loader.
Re-measured 8 Oct 2026: `cip_answer` 14.3 M rows, 1.3 GB data + 2.9 GB index; it also
carries a FULLTEXT index (verbatims), which InnoDB likewise cannot partition. Applied
instead: logical partitioning by wave (survey_id leads every hot index; a wave loads,
verifies and is replaced as one unit; reads go to the pre-computed cube and
`cip_tracker_line`). Physical partitioning stays at the 100 M-row trigger, with
verbatim search moving to `cip_search` at the same time.

### 3.4 ETL pipeline (all filtering, transformation and aggregation server-side)

```
Discover ─► Fetch ─► Archive ─► Transform ─► Stage ─► Verify ─► Publish ─► Derive ─► Alert
 daily      datamap   raw JSON   types,      per-wave  payload   load_status harmonise   new/failed
 survey     + data    sha256     labels,     batched   counts,   → verified  cohorts,    waves,
 list       (json)    to Blob    PII drop    upserts   datamap             cube, drift  near-hibernation
```

1. **Discover** (daily 06:00 IST + Tuesday 06:00 IST after the Monday wave): list surveys,
   upsert the register, classify by tag, mark `closed & not loaded` as due.
2. **Fetch** datamap + data (`format=json`, all statuses — health needs terminates).
3. **Archive** the raw payloads with sha256 before any transform.
4. **Transform**: shapes from §1.3; labels from question or variable; bipolar left/right;
   `oe` text; flags `t`/`v`; codes as integers; dates parsed; drop `userAgent`/`url`/
   `session`; hash `RID`.
5. **Stage + load** per wave in one transaction (`load_status = loading` → invisible).
6. **Verify**: every record a respondent, every field's count equal to the payload,
   every datamap variable a field; failure → `failed`, alert.
7. **Publish** → `verified`; then harmonise, cohorts, cube, publication drift.
8. **Alert** on failures, on waves approaching hibernation unloaded, and on drift.

Incremental and idempotent: every write is an upsert keyed on the survey path and the
Forsta record. A rerun after a failure resumes the wave, never duplicates it.

### 3.5 UI (Streamlit, server-side only)

- **Search box**: one FULLTEXT query over `cip_search` → surveys, questions and concepts
  as you type (< 200 ms target).
- **Survey report**: every question auto-charted by shape — single → bar or pie/donut,
  checkbox → ranked bar, grid → diverging stacked bar or heatmap, **bipolar → butterfly
  bar** (left vs right statement), numeric → distribution with mean/median, text →
  searchable verbatims; each with question wording, base and footnote.
- **Trends** across all waves and platforms (concept), cohorts, cuts, publications,
  Excel / PDF / slide export.
- **Speed**: every chart reads the cube (one indexed read, ≤ 0.35 s measured); results
  cached per view; Plotly transitions for smooth updates; target < 2 s for any page.

---

## 4. Decisions needed before the build

| # | Decision | Recommendation |
|---|---|---|
| A | Rename `csi_` → `cip_` on `dwh_stg` | yes, in one atomic statement, in a quiet window |
| B | Reactivate the 45 hibernated tracker waves (a change in Forsta) | yes, by Philip, in batches; we load each right after |
| C | Archive raw payloads in Azure Blob | yes (Forsta deletes after 365 days) |
| D | Load all statuses or qualified only | all (health, dropout); analysis uses qualified |
| E | Excel route for Forsta | retire once the API backfill reconciles |

## 5. Testing plan

- Fixtures for every question shape in §1.3, incl. bipolar and `oe`.
- API-vs-stored comparison per wave (as in §1.5) must be exact before a wave is verified.
- Performance check (`scripts/perf_check.py`) after every load; P95 < 2 s for any view.
- Browser check of every chart type on real waves.
