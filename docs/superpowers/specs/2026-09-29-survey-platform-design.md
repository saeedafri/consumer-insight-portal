# Consumer Insight Portal — Survey Platform Design (Schema v2)

**Status:** approved 29 Sep 2026. Phase 1 (schema v2) and Phase 2 (harmoniser + Mappings page) Phase 3 (Qualtrics history Aug 2022 – May 2025: 142 waves, reconciled against source) Phase 4 (cohorts, cube, cube-first repository; P95 targets met) Phase 5 (publications + drift report; a Beauty chart published and re-verified after a reload) are live. Phase 7 (Forsta API adapter + unattended weekly run) is built and proven against the Excel path; its live exit test waits on a working API key in `dwh_stg` — plans `docs/superpowers/plans/2026-09-29-schema-v2-phase1.md`, `docs/superpowers/plans/2026-09-30-harmoniser-phase2.md`, `docs/superpowers/plans/2026-09-30-legacy-history-phase3.md`, `docs/superpowers/plans/2026-10-01-cohorts-and-cube-phase4.md`, `docs/superpowers/plans/2026-10-01-publications-phase5.md`, `docs/superpowers/plans/2026-10-01-surveymonkey-phase6.md`, `docs/superpowers/plans/2026-10-01-forsta-api-phase7.md`.
**Date:** 29 September 2026
**Scope:** every survey Coresight delivers — Forsta (Aug 2025 →), Qualtrics
(2022 – Apr 2025) and SurveyMonkey (2018 – 2022) — in one schema in `dwh_stg`.
**Supersedes:** the schema sections of `docs/02-schema-design.md` (v1) and the
proposal in `docs/10-analyst-workbook-review-and-schema-v2.md`.

---

## 1. Intent

### What the business asked for
- Survey data lands in MySQL (`dwh_stg`, `csi_` prefix), not in Excel.
- Analysts get any question, any cut, any chart, quickly — dynamic filters,
  Excel export — as good as the Market Data Portal.
- The structure survives questionnaire change: new modules, new question
  types, new platforms.
- Excel source files are never edited.

### What "optimal for every delivered survey" means — the success criteria
1. **Any survey loads without a code or schema change** — a new module, a new
   annual study, a new platform export shape at most needs a new adapter.
2. **Every published number reproduces exactly** from respondent-level data,
   and the load proves it before the wave is visible.
3. **Questions trend across waves and across platforms** — Qualtrics `B10_3`
   and Forsta `BT13r1` are the same "Amazon.com" once an analyst confirms it.
4. **Speed:** a standard view answers in < 1 s; an ad-hoc cohort on one wave
   in < 3 s; a five-wave stack in < 5 s (P95, from the India office over VPN).
5. **A published figure never silently changes.**

### Decisions taken (and why)

| # | Decision | Chosen | Reason |
|---|---|---|---|
| D1 | Which surveys | All three platforms. Load order: Qualtrics history + Forsta first, SurveyMonkey second | Qualtrics is where current trend work lives; the schema takes SurveyMonkey with no change |
| D2 | Who links questions across waves | Loader proposes, analyst confirms; exact matches auto-confirm | Text-only matching already fails in the workbook (reworded B1, `Kohl'sÂ`) |
| D3 | Weighting | Supported (named schemes per wave), none applied yet | One small table now; applying weights would change published numbers |
| D4 | Published numbers | Live analysis **plus** frozen publications with drift flag | Replaces the manual Cross-Check tab |
| D5 | Minimum base | Suppress n < 30, caution n < 90, configurable per view | 90 is the house rule in the Beauty chart; 30 is the usual floor |
| D6 | Significance | Show Forsta's published sig letters; compute two-proportion z-tests (95 %) on demand | No storage cost; matches Forsta's own test |
| D7 | Personal data | Not stored: IP, lat/long, e-mail, names, user agent, URLs. Panel IDs hashed | Nothing in the analysis needs them |
| D8 | Raw files | Archived untouched in Azure Blob with sha256 in the load log | Reprocess any wave; audit any number |
| D9 | Open-ended text | Stored and full-text searchable; coding into themes is an extension, not built | No current requirement |

---

## 2. The surveys we must carry

| Platform | Years | Identity | Question formats | Where the data is today |
|---|---|---|---|---|
| SurveyMonkey | 2018 – 2022 | numeric ID (`164668935`) | single, multiple, matrix | `dwh_stg.dwh_sm*` (163 surveys) |
| Qualtrics | 2022 – Apr 2025 | `SV_…` | single, multi ("Selected Choice" columns), matrix rows, text entry, numeric | `dwh_stg.dwh_sm*` (149 surveys); Excel exports (e.g. May 2025, missing from DWH) |
| Forsta | Aug 2025 → | path `selfserve/58f/<name>` | single, multi, grid, bipolar grid, numeric, verbatim | Forsta API (key pending); Excel exports |

| Study type | Size | Pattern |
|---|---|---|
| Weekly tracker "Shopping and Spending" | ~400 | fixed core (shopping, sentiment, demographics, AI) + 2–4 rotating modules |
| Annual deep-dive (Online Grocery, Apparel, Social Commerce, CBD) | ~2,000 | own questionnaire, repeats yearly |
| One-off / commissioned | 15 – 2,000 | no repeat |

Legacy volume in `dwh_stg`: 312 surveys, 151k responses, 5.4M answer rows
(2.5 GB, text-keyed).

---

## 3. Approaches considered

| | Approach | Verdict |
|---|---|---|
| **A** | **Extend the CIP respondent-level schema** (v1, long-format answers, already reconciled 100 %) with a harmonisation layer, derived cohorts, weights, a pre-aggregated cube and publications | **Chosen.** Keeps what is proven; adds exactly what the analysts' workbook needs |
| B | Pour Forsta into the legacy `dwh_sm*` tables | Rejected: text-keyed (`varchar(700)` everywhere), no answering base, no demographics per respondent for Forsta, no trend identity; would inherit 2.5 GB of duplicated question text |
| C | One wide table per wave (a column per variable) | Rejected: DDL every week, cannot trend, cannot stack waves |

---

## 4. Architecture

```
 SOURCES                ADAPTERS                     CORE (dwh_stg, csi_)                  SERVING
 Forsta API ─┐                                                                       ┌─ Portal (Streamlit)
 Forsta xlsx ─┼─> platform adapter ─> Wave Package ─> Loader ─> definitions, answers ─┤    repository
 Qualtrics xlsx┤   (one per shape)    (canonical,     │          profiles, weights    │    cube-first
 dwh_sm* (RO) ┘                        validated)     ├─> Harmoniser ─> concept map ──┤─ Excel export
                                                      ├─> Deriver ─> cohorts, bands   │─ Publications
 Raw archive (Blob, untouched, sha256) <──────────────┤─> Aggregator ─> cube          │
                                                      └─> Reconciler ─> verified? ────┘
```

Each unit has one job and one interface:

| Unit | Does | Input → Output | Depends on |
|---|---|---|---|
| **Platform adapter** | reads one source shape | file / API / legacy tables → **Wave Package** | nothing in the core |
| **Wave Package** | the contract between sources and core | survey meta, questions, items, options, fields, records | — |
| **Loader** | writes a package idempotently | Wave Package → `csi_` definition + data tables | schema |
| **Harmoniser** | proposes concept matches, auto-confirms exact ones | new questions → `cip_concept_map` rows (proposed / confirmed) | concepts |
| **Deriver** | profile, bands, midpoints, cohort membership | answers + rules → `cip_profile`, `cip_respondent_cohort` | concept map, config |
| **Aggregator** | pre-computes standard cells | answers × standard dimensions → `cip_agg_cell` | deriver |
| **Reconciler** | proves the wave | computed vs published → pass / fail, per cell | aggregator, published tables |
| **Repository** | the only SQL the portal runs | question + cohort + break → tidy frame | cube, answers |

A new platform or export shape = one new adapter producing a Wave Package.

The legacy adapter (`etl/legacy_dwh.py`) is the one exception: source and
target share a MySQL server, so it sends only the definitions through Python
and moves answers server-side (`INSERT … SELECT`). File and API adapters still
emit a Wave Package.
Nothing downstream changes.

### The Wave Package (adapter contract)

```
survey:    platform, source_ref, title, study_type, family, wave_label, field dates, country, language
questions: qcode, text, qtype, is_multi, order, routing note
items:     item_code, label, order               (rows of a list or grid)
options:   value_code, label, order, is_nonresponse
fields:    field_name → (question, item)          (every source column / variable)
records:   respondent key (hashed), status, timestamps, {field_name: value}
checks:    source totals (respondents, per-question counts where the source publishes them)
```

Adapters must supply option **order**. Qualtrics exports carry labels without
codes: its adapter takes order from `dwh_smanswer.srt` when the survey is in
the DWH, otherwise from the confirmed concept's option order (§5.2).

---

## 5. Schema v2

29 tables in seven groups (19 existing, 10 new) plus views. All `utf8mb4`,
InnoDB, prefix `csi_`. Every change to an existing table is **additive** —
no v1 column is dropped or renamed.

### 5.1 Definition — what was asked (per wave)

| Table | Status | Purpose / key columns |
|---|---|---|
| `cip_survey` | changed | one row per wave. **+ `platform`** (`forsta`·`qualtrics`·`surveymonkey`), **+ `source_ref`**, **+ `study_type`** (`tracker`·`annual`·`adhoc`), **+ `load_status`** (`loading`·`verified`·`failed`·`superseded`), **+ `language`**. Unique `(platform, source_ref, wave_label)` |
| `cip_topic` | kept | editorial modules (Beauty, Tariffs, …) |
| `cip_question` | kept | per-wave question with its answering base and routing note |
| `cip_item` | kept | list items / grid rows |
| `cip_option` | kept | code → label per question |
| `cip_field` | kept | source column → question / item |

`load_status` defaults to `verified` until the Phase 3 loader sets `loading` → `verified`.

### 5.2 Harmonisation — the same question across waves and platforms (new)

| Table | Purpose / key columns |
|---|---|
| `cip_concept` | canonical question: `concept_code` (`BEAUTY_RETAILER_3M`), `concept_name`, `topic_id`, `qtype`, `description` |
| `cip_concept_option` | canonical answer: `concept_id`, `option_code` (`amazon`), `option_label`, `sort_order`, `midpoint` (bands: age 23.5, income 74.9995), `net_group` (`TOP2`, `ANY_DRUGSTORE`) |
| `cip_concept_map` | wave object → canonical: `survey_id`, `question_id`, `item_id` / `option_id` → `concept_id`, `concept_option_id`; `status` (`proposed`·`confirmed`·`rejected`), `method` (`exact_text`·`similar_text`·`manual`), `confidence`, `reviewed_by`, `reviewed_at` |

Rules:
- The Harmoniser normalises text (whitespace incl. non-breaking spaces,
  encoding debris `Â`, case, trailing instructions such as "Select all that
  apply") before matching.
- A grid is stored as one concept per grid row; rows of one grid share
  `concept_group`.
- Unique keys use a computed `map_key` (and, in `cip_agg_cell`, `cell_key`)
  because MySQL allows repeated NULLs in unique indexes.
- `cip_concept.match_text` (≤ 2,000 chars) holds the normalised wording matched
  on; `concept_name` is the display label, truncated to 255.
- A unit with no exact or similar candidate becomes a new, confirmed concept —
  creating a concept claims no trend. Answers a wave drops do not block an
  exact match; answers it adds do.
- **Exact match → `confirmed`**, where exact means the normalised question
  text is identical **and** every answer option maps to an existing concept
  option. Same text with a changed option list → `proposed`. Anything else →
  `proposed`, shown in the portal's review queue; nothing trends until
  confirmed.
- A concept option can map from many wave options (aliases:
  "Kohl's (excluding Sephora at Kohl's)", "Kohl'sÂ (excluding …)").

### 5.3 Data — what people said (per wave)

| Table | Status | Purpose / key columns |
|---|---|---|
| `cip_respondent` | changed | one per interview. **+ `respondent_key`** (sha256 of the panel/respondent ID), **+ `quality_flag`**. No IP, geo, e-mail, user agent |
| `cip_profile` | changed | flattened demographics per respondent. **+ `age_mid`**, **+ `income_mid_k`** from concept midpoints, so averages are `AVG()` |
| `cip_answer` | changed | the fact table, one row per respondent × field; **+ FULLTEXT on `value_text`**. Not partitioned: InnoDB forbids foreign keys on partitioned tables, and a wave's rows are already physically adjacent because a wave is loaded in one pass (auto-increment clustered key). The covering index below keeps reads within one wave |
| `cip_weight_scheme` | **new** | named weighting per wave: `scheme_code`, `survey_id`, `method`, `targets` (JSON), `created_at` |
| `cip_weight` | **new** | `respondent_id`, `scheme_id` (foreign key to `cip_weight_scheme`), `weight` |

### 5.4 Derived — analyst rules made data (new)

| Table | Purpose / key columns |
|---|---|
| `cip_cohort_def` | a named, versioned respondent rule over concepts: `cohort_code` (`BEAUTY_SHOPPER`), `name`, `rule_json`, `base_note`, `version`, `owner` |
| `cip_respondent_cohort` | materialised membership: `cohort_id` (identifies code + version), `respondent_id`, `survey_id` |

Example — the workbook's beauty shopper, stored once and applied to every wave:
```json
{"any": [
  {"concept": "BEAUTY_PURCHASED_3M", "option": "yes"},
  {"all": [{"concept": "BEAUTY_PURCHASED_3M", "asked": false},
           {"concept": "BEAUTY_SPEND_3M",     "answered": true}]}
]}
```
(Named `cohort`, not `segment`, because `cip_segment` already means a Forsta
banner column.)

### 5.5 Aggregates — the speed layer (new)

| Table | Purpose / key columns |
|---|---|
| `cip_agg_cell` | pre-computed at load: `survey_id`, `concept_option_id` (or `option_id` when unmapped), `cohort_code` (`ALL` or a cohort), `dim` (`total`·`gender`·`age_band`·`generation`·`income_band`·`region`·`urbanicity`·…), `dim_value`, `n`, `base_n`, `n_weighted`, `base_weighted`, `sum_age_mid`, `sum_income_mid_k`, `built_at` |

- Covers every "one question × one standard cut × one cohort" view — the
  Beauty pivots, Men Beauty, the bubble chart, Cross-Check — as a single
  indexed read returning tens of rows, not thousands (the MDP lesson: cost is
  rows fetched).
- Averages come from the stored sums: `sum_age_mid / base_n`.
- Rebuilt per wave on load and on a cohort version change. Cells store the
  answer's `map_key` (question:item:option), not its concept, and join
  `cip_concept_map` when read — so a confirmed mapping change needs no
  rebuild; only the cohorts whose membership it changes are re-derived
  (`cube.refresh_cohorts`). Size: ~50k rows per wave.
- Anything not in the cube (a cohort built from prior answers, an unusual
  break) falls back to respondent-level SQL on `cip_answer` — correct, just
  slower.

### 5.6 Published — Forsta's own tables (kept)

`cip_banner`, `cip_segment`, `cip_crosstab_run`, `cip_crosstab` — the
cross-tabs exactly as delivered, both bases kept. These are what the
Reconciler proves against.

### 5.7 Publications — frozen deliverables (new)

| Table | Purpose / key columns |
|---|---|
| `cip_publication` | a delivered chart/table: `name`, `owner`, `version`, `published_at`, `definition` (JSON: waves, concepts, cohort, break, weight scheme, min base), `footnote`, `destination` (e.g. SharePoint URL), `status` |
| `cip_publication_cell` | the frozen numbers: `publication_id`, `row_key`, `col_key`, `n`, `base_n`, `value` |

On any reload / remap / cohort change the portal recomputes the publication's
definition and flags cells whose value moved — the drift report replaces the
manual Cross-Check tab.

### 5.8 Operations (kept)

`cip_load_log` (+ `archive_uri`, `archive_sha256`), `cip_load_error`,
`cip_load_state`, `cip_profile_map`, `cip_auth_session`, `cip_saved_view`.

### Relationships

```
cip_survey 1─< cip_question 1─< cip_item
     │               │      1─< cip_option
     │               └────────< cip_field >── cip_item
     │
     ├─< cip_respondent 1─1 cip_profile
     │        │ 1─< cip_answer >── cip_field
     │        │ 1─< cip_weight >── cip_weight_scheme >── cip_survey
     │        └ 1─< cip_respondent_cohort >── cip_cohort_def
     │
     ├─< cip_concept_map >── cip_concept_option >── cip_concept >── cip_topic
     │         (question / item / option of this wave)
     ├─< cip_agg_cell >── cip_concept_option
     ├─< cip_banner 1─< cip_segment ;  cip_crosstab_run 1─< cip_crosstab
     └─< cip_load_log 1─< cip_load_error

cip_publication 1─< cip_publication_cell
```

### Views (the portal reads these)

| View | Returns |
|---|---|
| `v_csi_concept_answers` | respondent × concept option × wave with profile — any set of waves stacked (replaces "Five Waves Combined") |
| `v_csi_concept_cells` | `cip_agg_cell` joined to labels, with % and averages computed |
| `v_cip_mapping_queue` | proposed mappings awaiting review, with the evidence |
| existing `v_csi_*` | unchanged |

### Indexes that carry the load
- `cip_answer (survey_id, field_id, value_code, respondent_id)` covering — item incidence without touching the base row.
- `cip_agg_cell (concept_option_id, cohort_code, dim, survey_id)` — trend across waves for one answer.
- `cip_concept_map (survey_id, question_id)` and `(concept_option_id)`.
- `cip_respondent_cohort (cohort_code, survey_id, respondent_id)`.

### Volume

| | Waves | `cip_answer` rows | `cip_agg_cell` rows |
|---|---|---|---|
| Forsta, per year | ~52 | ~8M | ~2.6M |
| Qualtrics history (B) | 149 | ~20M | ~7M |
| SurveyMonkey (C) | 163 | ~15M | ~8M |

Tens of millions of long rows is ordinary for InnoDB when every read leads
with `survey_id`; the portal's hot path reads the cube. Partitioning is the
upgrade path if `cip_answer` passes ~100M rows (it would mean moving
integrity checks from foreign keys into the loader).

---

## 6. Data flow — one wave, end to end

1. **Fetch.** Adapter reads the source (API, file, or legacy tables). The
   untouched original goes to Blob; its sha256 is logged.
2. **Package.** Adapter emits a Wave Package; schema checks (every field
   mapped, every option ordered, respondent keys unique).
3. **Load.** `cip_survey.load_status = loading`. Definitions and answers are
   upserted. Personal fields are dropped here, never written.
4. **Harmonise.** Exact matches confirmed; the rest queued for review.
5. **Derive.** Profiles, midpoints, cohort membership.
6. **Aggregate.** Cube cells for the wave.
7. **Reconcile.** Against Forsta's published cross-tab; for legacy waves
   against the legacy tables themselves (respondent count per survey, answer
   counts per question from `dwh_smresponseqa`) and `dwh_smsurveytrend` where
   that wave has trend rows. Tolerance
   0.0005 on proportions; exact on counts. Known source defects are listed,
   not failed (e.g. Forsta's region banner omitting MD/MO).
8. **Publish the wave.** Pass → `verified`, visible in the portal.
   Fail → `failed`, invisible, errors in `cip_load_error`, alert.
9. **Drift check.** Publications that use the wave are recomputed; moved
   cells are flagged.

Re-running any step is safe: every write is an upsert keyed on source identity.

### Change handling

| Change | What happens |
|---|---|
| New rotating module | new questions → new concepts proposed; no DDL |
| Reworded question | similar-text proposal → analyst confirms or keeps separate |
| Questionnaire drift within a wave | `datamap_hash` differs → new package version, old one `superseded` |
| New question type | adapter maps to `qtype`; if genuinely new, one enum value |
| New platform | one new adapter |
| Cohort rule edited | new `version`; memberships and cube cells rebuilt for that cohort |

---

## 7. Serving — how the portal answers

- **Cube first.** The repository asks: is this view (question/concept ×
  standard dim × cohort × waves) in `cip_agg_cell`? If yes, one indexed read.
- **Respondent-level fallback** for everything else, always aggregated in SQL
  (`GROUP BY`), never rows to Python.
- **Every result carries its base** (unweighted n, and weighted n when a
  scheme is chosen), its min-base flag (D5), and a generated footnote:
  *"Base: 2,019 US respondents aged 18+, surveyed June 2024–May 2025.
  Averages use range midpoints. Source: Coresight Research."*
- **Charts join labels by key**, never by column position — the bubble-chart
  defect cannot recur.
- **Caching:** Streamlit `st.cache_data` keyed on (view definition, wave
  `built_at`), so a reload invalidates exactly what changed.

---

## 8. Error handling

| Failure | Behaviour |
|---|---|
| Source unreachable / 401 | load not started; `cip_load_log` failed with the source's message (e.g. "account disabled") |
| Package invalid (unmapped field, missing option order) | wave `failed`; the exact fields listed in `cip_load_error` |
| Partial write | wave stays `loading` → never visible; next run resumes by upsert |
| Reconciliation mismatch | wave `failed`, per-cell differences stored; portal shows nothing from it |
| Unconfirmed mapping | wave visible on its own; excluded from cross-wave trends until confirmed |

---

## 9. Security and governance

- Portal connects as read-only `csi_app` (grant script ready,
  `sql/004_grants.sql`); only the loader writes.
- No direct identifiers stored (D7). Raw archive access limited to the ETL
  identity.
- Sign-in: OIDC/SSO as in MDP and SIP; local bypass only with
  `APP_ENV=LOCAL` + `DEBUG=true`.
- Every load, mapping decision, cohort version and publication records who
  and when.
- Legacy `dwh_sm*` tables are **read, never written**.

---

## 10. Testing

| Level | Test |
|---|---|
| Adapter | fixture files per platform shape (Forsta labels, Qualtrics two-header, legacy rows) → expected Wave Package |
| Harmoniser | normalisation cases (`\xa0`, `Â`, reworded B1), exact vs proposed |
| Deriver | cohort rules incl. "not asked" branches; midpoints; "Under 18" |
| Reconciliation (integration) | every loaded wave: 100 % of published cells |
| Golden workbook | reproduce *Beauty Shopper Profiles*: Amazon 492 buyers over five waves; 1,200 beauty shoppers over four; average age 44.94; the bubble chart with correct labels |
| Performance | P95 targets in §1 against `dwh_stg` over VPN |

---

## 11. Rollout

| Phase | Delivers | Exit test |
|---|---|---|
| 1 | Schema v2 migration (additive) | v1 data and reconciliation unchanged |
| 2 | Harmoniser + review queue in the portal | 09/21 and 09/28 core questions confirmed |
| 3 | Legacy loader (`dwh_sm*` → `csi_`) for Qualtrics 2022–25; Qualtrics Excel adapter for May 2025 | every Qualtrics wave verified; golden workbook reproduced |
| 4 | Deriver, cohorts, cube, cube-first repository | P95 targets met |
| 5 | Publications + drift report | a Beauty chart published and re-verified after a reload |
| 6 | SurveyMonkey 2018–22 through the legacy loader | every wave verified |
| 7 | Forsta API adapter live (when the key works) | weekly wave loads and verifies unattended |

Phases 1–4 unblock the analysts; 5–7 are independent of each other. Each
phase gets its own implementation plan, reviewed before it starts.

---

## 12. Known limits

- **Qualtrics option order** is recovered, not given: from `dwh_smanswer.srt`
  or the confirmed concept. A wave with neither needs one manual ordering.
- **Legacy matrix questions** (21 across 8 surveys in `dwh_smquestion`) need
  adapter-specific handling; their shape is known but not yet parsed.
- **The Forsta API** remains blocked on a working key; the Excel adapter is
  the route until then.
- **Weights** are supported, not computed: a scheme must be supplied.
- **Legacy grids were never imported.** Questions with no rows in
  `dwh_smresponseqa` (grids such as Beauty B11) are skipped by the legacy
  adapter; grid history exists only where an Excel export survives.
- **Legacy question types are inferred**: the `family` label says
  `multiple_choice` for yes/no questions, so the adapter reads the data
  (more than one answer per respondent, or "select all" wording).
- **Hand-entered summary waves** (`SV_MS240725`: 8 rows keyed
  `<survey>_Q1_R1`) are not respondent data and are not loaded.
- **Qualtrics exports number demographics differently** (D7 = state, D8 =
  political — Forsta is the reverse), so their profiles resolve by wording.
- **Qualtrics Excel option order** is order of first appearance; trend charts
  use the concept's order (set by the earliest legacy wave), so only that
  wave's own tables show the Excel order.
