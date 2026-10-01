# SurveyMonkey History — Phase 6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The SurveyMonkey years (Jan 2018 – Jul 2022: 145 waves with completes, 81,995 completed responses) load through the Phase 3 legacy adapter, with their grids, their panel demographics and their bases, and every wave reconciles against `dwh_sm*`.

**Architecture:** Same adapter (`etl/legacy_dwh.py`, era `surveymonkey`), three additions the SurveyMonkey data needs and Qualtrics did not: (1) **matrix questions** — `dwh_smanswer` lists row labels and scale columns together; each response row stores `"<row> | <column>"` in `answer_text` with `answer_id` = the column, so the temp answer map gains a `match_text` column and grid cells join on (answer_id, answer_text); (2) **panel demographics** — SurveyMonkey Audience supplies age, gender, income and Census *division* per response in `dwh_smdemography`, not as questions; they fill the profile where no question did; (3) **their labels** — `"< 18"`, `"> 60"`, `$25,000-$49,999`-style income ranges and divisions mapped to the four Census regions.

**Spec:** §2 (SurveyMonkey row), §11 Phase 6 exit: *every wave verified*.

## Evidence (read-only probes, 1 Oct 2026)

| Fact | Value |
|---|---|
| Waves with completed responses | 145 (`legacy_surveys(era="surveymonkey")`), Jan 2018 – Jul 2022 |
| Families | single_choice 926, multiple_choice 1,475, matrix 21 (with 22k+ answer rows) |
| Matrix storage | `answer_text` = `"Trendy fashion/style | 7"`, `answer_id` = column "7"; 9 rows per response for a 9-row grid |
| `answer_othertext` | literal `'None'` (1.56 M rows); other-specify text also inside `answer_text` as `"Other | …"` |
| `dwh_smdemography` | 72,053 rows / 70,040 responses (≈2,000 duplicated) — age `18-29 … > 60`, `< 18`; gender; income `$0-$9,999 … $200,000+`, `Prefer not to answer`; region = Census division |

## Global Constraints

- Legacy tables read, never written. Additive only; no schema change (the temp map is a session temp table).
- A profile value from a question is never overwritten by the panel's; the panel fills gaps.
- Income midpoint of a closed range = (low + high) / 2 in $000 — the workbook's own convention (`$25,000 - $49,999` → 37.4995); open top `$200,000+` → 225 (as `$200,000 or greater`).
- Reconcile per matrix cell (row | column), not per column id.
- Never commit/push; no attribution.

## Review Focus

1. A matrix answer must land on its **row**, not every row sharing that column id.
2. A duplicated demography row must not duplicate or flip a profile.
3. Reloading a SurveyMonkey wave stays idempotent (answers, profiles, cube).
4. Qualtrics waves are unaffected (their reconcile stays 0 differences).

## Tasks

### Task 1: SurveyMonkey labels
- Tests: `classify_age("< 18")` → age 17, no band; `classify_age("> 60")` → Over 60; `income_mid_k("$25,000-$49,999") == 37.4995`, `("$0-$9,999") == 4.9995`, `("$200,000+") == 225`, `("Prefer not to answer") is None`; `census_region_of_division("South Atlantic") == "South"`.
- Implement in `etl/survey_map.py` + `config/survey_map.yml` (`census_divisions`, extra income label).

### Task 2: Matrix questions
- Fixture: a SurveyMonkey survey with a 2-row × 3-column matrix and a respondent per row pattern.
- Tests: `legacy_qtype("matrix", …, 2, 5)` → `"grid"`; load → `grid_single` question with rows and scale in column order; each respondent's row answers land on the right row field and code; `reconcile_legacy` checks each row | column cell (and flags a tampered one).
- Implement: `_definitions` matrix branch (rows/columns from the response texts and `dwh_smanswer.srt`), temp map `match_text`, join `(m.match_text IS NULL OR m.match_text = x.answer_text)`, reconcile keyed on (answer_id, match_text).

### Task 3: Panel demographics
- Fixture: `dwh_smdemography` rows incl. a duplicate and a respondent with a demographic question answer.
- Tests: profile gets age band/midpoint, gender, income band/midpoint, Census region from the panel; a question-derived value is kept; the duplicate row changes nothing; reload idempotent.
- Implement `_panel_profiles(survey_id, legacy_id)` in `legacy_dwh.py`, called after `_rebuild_profiles`.

### Task 4: Load and verify on `dwh_stg`
- One wave with a matrix first (timed, reconciled); then all 145 (`--era surveymonkey`, oldest first, resume-safe by skipping waves already verified after the run started); reconcile every wave; Qualtrics reconcile spot check unchanged; publications drift unchanged.

### Task 5: Docs
- Spec status, README, running-locally, changed files.
