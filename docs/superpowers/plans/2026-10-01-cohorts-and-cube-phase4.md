# Cohorts and Cube — Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Analysts can name a respondent group once ("beauty shoppers") and use it on every wave, and every standard view — one question × one standard cut × one cohort, on one wave or stacked across waves and platforms — answers from a pre-computed cube in under a second.

**Architecture:** Two new modules. `app/data/cohorts.py` (the Deriver) compiles a cohort's JSON rule over *concepts* into one SQL condition and materialises membership per wave with `INSERT … SELECT`. `app/data/cube.py` (the Aggregator) builds `csi_agg_cell` per wave the same way — counts, bases and midpoint sums for every answer × standard cut × cohort. The cube stores the answer's `map_key`, not its concept, and joins `csi_concept_map` when read; confirming a mapping therefore never forces a cube rebuild, only a re-derive of the cohorts that depend on it. The repository answers from the cube when it can and falls back to the existing respondent-level SQL when it cannot, returning identical frames.

**Tech Stack:** Python 3.13, SQLAlchemy 2, PyMySQL, MySQL 8.0 (`dwh_stg`), SQLite 3.53 (tests), Streamlit 1.55, pytest.

**Spec:** `docs/superpowers/specs/2026-09-29-survey-platform-design.md` — §5.4 cohorts, §5.5 cube, §7 serving, §10 Deriver + golden-workbook tests, §11 Phase 4 ("P95 targets met"), §1 goal 4 (standard view < 1 s; ad-hoc cohort on one wave < 3 s; five-wave stack < 5 s, P95 from India over VPN).

## Global Constraints

- Additive schema only, through `app/core/schema_upgrade.py` (idempotent, refuses during a running load).
- Legacy `dwh_sm*` tables are never read or written by this phase.
- Only `confirmed` mappings count — in cohort rules and in concept reads. A proposal waiting on `/mappings` is not the same question yet.
- The cube must return **exactly** what the respondent-level engine (`repository.analyse`) returns for the same view — a parity test proves it for every question and cut of the fixture waves.
- Averages divide by the respondents who *have* a midpoint ("prefer not to say" has none): the workbook's average income is 110,711.5645 / 1,189, not / 1,200.
- Every batched write uses placeholders only (PyMySQL batching); every per-wave step is a constant number of statements.
- `CONCAT` in MySQL returns NULL if any part is NULL (SQLite treats NULL as ''): every `CONCAT` argument is `COALESCE`d.
- **Never run `git commit` or `git push`.** No attribution anywhere.
- Naming: plain 1–4 word names, verb-first functions; match surrounding style.

## Golden targets (read from *Beauty Shopper Profiles*, tab "Age Income Beauty Total")

| Figure | Workbook |
|---|---|
| Waves | the four Beauty waves Oct 2023 – Jun 2024 |
| Respondents | 1,614 (1,613 excl. "prefer not to say" age) |
| Answered "Yes" to buying beauty ("Beauty Yes Only") | **1,200** |
| … by age band 18-29 / 30-44 / 45-60 / over 60 | 255 / 353 / 330 / 262 |
| Average age of beauty buyers (midpoints) | **44.94375** = 53,932.5 / 1,200 |
| Average income, $000 (midpoints, excl. prefer not to say) | **93.1132** = 110,711.5645 / 1,189 |

Known risk: the workbook counts 402 completes for Oct 2023 where the source holds 422 (open question for the data team). A mismatch is reported with its cause, not tuned away.

## Review Focus

1. **A cohort rule's "not asked" branch** — a wave that has no confirmed question for the concept must satisfy `asked: false`; a wave that asked it must not, even for a respondent who skipped it. Test in Task 2.
2. **Cube vs engine parity** on routed questions (base = who answered), multi-selects (base = who answered the question, zeros counted), grids (base per row) and `NULL` cut values. Test in Task 3.
3. **A mapping confirmed after the cube was built** — the concept trend must pick the wave up without a cube rebuild. Test in Task 4.
4. **Stale cohort after a rule edit** — a changed rule creates a new version and the old version's memberships and cube cells stop being read. Test in Task 2.
5. **MySQL NULL semantics** — `CONCAT`, `COALESCE(cohort_id, 0)`, `SUM(CASE …)` behave the same on both engines. Checked by running Task 7 on `dwh_stg`.

## File Map

| File | Change | Responsibility |
|---|---|---|
| `sql/001_schema.sql`, `app/core/schema_upgrade.py` | modify | `csi_agg_cell` + `map_key`, `n_age_mid`, `n_income_mid`; index `ix_agg_map` |
| `app/data/cohorts.py` | create | rule compiler, `define_cohort`, `derive`, CLI |
| `config/cohorts.yml` | create | the cohort definitions (BEAUTY_SHOPPER) |
| `app/data/cube.py` | create | `build_cube`, `refresh_wave`, CLI |
| `app/data/repository.py` | modify | cube-first `analyse`, `cohort` criterion, `concept_trend`, `concept_pooled`, `cohort_list`, `concept_catalog` |
| `etl/run_pipeline.py`, `etl/legacy_dwh.py`, `etl/qualtrics_export.py` | modify | call `cube.refresh_wave` after harmonising |
| `app/pages/7_Mappings.py` | modify | re-derive cohorts of the wave after a decision |
| `app/pages/3_Analysis.py` | modify | "Defined cohort" criterion |
| `app/pages/5_Trends.py` | modify | trend a concept across every wave and platform, optionally within a cohort |
| `scripts/perf_check.py` | create | P95 of the three §1 targets against the live database |
| `tests/test_phase4.py` | create | all tests for this phase |

---

### Task 1: Cube columns

**Files:** `sql/001_schema.sql`, `app/core/schema_upgrade.py`; test `tests/test_phase4.py`

- [ ] **Step 1: Failing test** — create `tests/test_phase4.py`:

```python
"""Phase 4: cohorts (Deriver), cube (Aggregator), cube-first repository.

See docs/superpowers/plans/2026-10-01-cohorts-and-cube-phase4.md.
"""
from __future__ import annotations

import sqlalchemy as sa


def columns(engine, table):
    return {c["name"] for c in sa.inspect(engine).get_columns(table)}


def test_cube_cells_carry_their_map_key_and_midpoint_counts(csi_db):
    assert {"map_key", "n_age_mid", "n_income_mid"} <= columns(csi_db, "csi_agg_cell")
    assert "ix_agg_map" in {i["name"] for i in sa.inspect(csi_db).get_indexes("csi_agg_cell")}
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_phase4.py -q` — Expected FAIL (missing columns).
- [ ] **Step 3: Implement.** In `sql/001_schema.sql` `csi_agg_cell`, after `concept_option_id`: `map_key VARCHAR(40) NULL COMMENT 'question:item:option — joins csi_concept_map at read time',`; after `sum_age_mid`: `n_age_mid INT NULL COMMENT 'respondents in n with an age midpoint',`; after `sum_income_mid_k`: `n_income_mid INT NULL,`; add `KEY ix_agg_map (survey_id, map_key, cohort_id, dim),`. In `schema_upgrade.py` append to `COLUMNS`: `("csi_agg_cell", "map_key", "VARCHAR(40) NULL")`, `("csi_agg_cell", "n_age_mid", "INT NULL")`, `("csi_agg_cell", "n_income_mid", "INT NULL")`; to `INDEXES` the `ix_agg_map` entry in the file's existing form.
- [ ] **Step 4: Run** → PASS; `tests/test_schema_v2.py` still passes (upgrade parity). Full suite green.

---

### Task 2: The Deriver (`app/data/cohorts.py`)

**Interfaces:**
- `compile_rule(rule: dict, codes: dict[str, int]) -> tuple[str, dict]` — SQL condition over `r` (a `csi_respondent` row) and params. `codes` maps concept_code → concept_id.
  - `{"concept": C, "option": O}` — the respondent gave concept C's option O (single/grid: that code; multi: the item selected).
  - `{"concept": C, "answered": true}` — answered any question mapped to C.
  - `{"concept": C, "asked": false|true}` — the respondent's wave has (true) / has not (false) a confirmed question for C.
  - `{"all": [...]}`, `{"any": [...]}`, `{"not": {...}}`.
  - Unknown concept code or option → `ValueError` naming it.
- `define_cohort(code, name, rule, base_note=None, owner=None) -> int` — cohort_id of the current version; same rule → same id; changed rule → version + 1, old version `is_current = 0`.
- `derive(cohort_id, survey_ids=None) -> int` — replaces memberships (all waves, or those listed); returns members written.
- `current_cohorts() -> list[dict]` — `{cohort_id, cohort_code, cohort_name, version}`.
- CLI: `python -m app.data.cohorts --sync` (define everything in `config/cohorts.yml`, derive all waves).

- [ ] **Step 1: Failing tests** — append a fixture that loads the Phase 3 legacy fixture waves and confirms their maps, then:

```python
import pytest

from app.data import cohorts, harmonise
from tests.test_phase3 import LEGACY_DDL  # noqa: F401  (fixture tables)
from tests.test_phase3 import legacy  # noqa: F401  pytest fixture re-export
from etl import legacy_dwh


def concept_code(engine, sid, qcode):
    with engine.connect() as conn:
        return conn.execute(sa.text(
            "SELECT c.concept_code FROM csi_concept c JOIN csi_concept_map m ON m.concept_id = c.concept_id"
            " JOIN csi_question q ON q.question_id = m.question_id"
            " WHERE m.survey_id = :s AND q.qcode = :q AND m.concept_option_id IS NULL"), {"s": sid, "q": qcode}).scalar()


@pytest.fixture()
def wave(legacy):
    sid = legacy_dwh.load_legacy("SV_T")       # B1 = Q1 (yes/no), B10 = Q2 (multi), age = Q3
    return legacy, sid, concept_code(legacy, sid, "Q1"), concept_code(legacy, sid, "Q2")


def members(engine, cohort_id):
    with engine.connect() as conn:
        return sorted(r[0] for r in conn.execute(sa.text(
            "SELECT r.forsta_uuid FROM csi_respondent_cohort c JOIN csi_respondent r"
            " ON r.respondent_id = c.respondent_id WHERE c.cohort_id = :c"), {"c": cohort_id}))


def test_option_rule_selects_who_gave_that_answer(wave):
    engine, sid, b1, _ = wave
    cid = cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "yes"})
    assert cohorts.derive(cid) == 2
    assert members(engine, cid) == ["R_1", "R_2"]


def test_multi_option_rule_selects_who_ticked_the_item(wave):
    engine, sid, _, b10 = wave
    cid = cohorts.define_cohort("AMAZON", "Bought beauty on Amazon", {"concept": b10, "option": "amazon_com"})
    cohorts.derive(cid)
    assert members(engine, cid) == ["R_1"]


def test_not_asked_branch_is_decided_by_the_wave_not_the_respondent(wave):
    engine, sid, b1, b10 = wave
    rule = {"any": [{"concept": b1, "option": "yes"},
                    {"all": [{"concept": b1, "asked": False}, {"concept": b10, "answered": True}]}]}
    cid = cohorts.define_cohort("BEAUTY_SHOPPER", "Beauty shoppers", rule)
    cohorts.derive(cid)
    # B1 WAS asked in this wave, so R_3 (said No) is out even though the not-asked branch exists
    assert members(engine, cid) == ["R_1", "R_2"]


def test_changed_rule_is_a_new_version_and_the_old_one_stops_being_current(wave):
    engine, sid, b1, _ = wave
    first = cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "yes"})
    assert cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "yes"}) == first
    second = cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "no"})
    assert second != first
    assert [c["version"] for c in cohorts.current_cohorts() if c["cohort_code"] == "BEAUTY_YES"] == [2]


def test_unknown_concept_or_option_is_refused_by_name(wave):
    _, _, b1, _ = wave
    with pytest.raises(ValueError, match="NOPE"):
        cohorts.define_cohort("X", "x", {"concept": "NOPE", "option": "yes"})
    with pytest.raises(ValueError, match="maybe"):
        cohorts.define_cohort("X", "x", {"concept": b1, "option": "maybe"})
```

- [ ] **Step 2: Run** → FAIL (`No module named 'app.data.cohorts'`).
- [ ] **Step 3: Implement `app/data/cohorts.py`** — `_codes(conn)` (concept_code → id and (concept_id, option_code) → concept_option_id), `compile_rule` recursive with numbered params, leaf SQL:

```sql
-- option
EXISTS (SELECT 1 FROM csi_answer a JOIN csi_field f ON f.field_id = a.field_id
          JOIN csi_concept_map m ON m.survey_id = a.survey_id AND m.question_id = f.question_id
               AND COALESCE(m.item_id, 0) = COALESCE(f.item_id, 0)
               AND m.status = 'confirmed' AND m.concept_option_id = :co
          LEFT JOIN csi_option o ON o.option_id = m.option_id
         WHERE a.respondent_id = r.respondent_id AND a.value_code = COALESCE(o.value_code, 1))
-- answered
EXISTS (SELECT 1 FROM csi_answer a JOIN csi_field f ON f.field_id = a.field_id
          JOIN csi_concept_map m ON m.survey_id = a.survey_id AND m.question_id = f.question_id
               AND m.status = 'confirmed' AND m.concept_option_id IS NULL AND m.concept_id = :c
         WHERE a.respondent_id = r.respondent_id AND a.value_code IS NOT NULL)
-- asked (NOT EXISTS for asked: false)
EXISTS (SELECT 1 FROM csi_concept_map m WHERE m.survey_id = r.survey_id AND m.concept_id = :c
          AND m.status = 'confirmed' AND m.concept_option_id IS NULL)
```

`define_cohort` compares `json.dumps(rule, sort_keys=True)` with the current version's; `derive` is one `DELETE` + one `INSERT INTO csi_respondent_cohort (cohort_id, respondent_id, survey_id) SELECT :cid, r.respondent_id, r.survey_id FROM csi_respondent r WHERE r.is_qualified = 1 [AND r.survey_id IN :ids] AND <rule>`. `rule_json` is written with `json.dumps`.

- [ ] **Step 4: Run** → 5 pass; full suite green.

---

### Task 3: The Aggregator (`app/data/cube.py`) with engine parity

**Interfaces:**
- `CUBE_DIMS = ("total", "gender", "age_band", "generation", "income_band", "census_region", "urbanicity")` — the dims whose values fit `cell_key` (≤ 40 chars each).
- `build_cube(survey_id, cohort_ids=None) -> int` — replaces the wave's cells (all, or only those cohorts' cells); returns cells written. Cohorts = `None` (everyone) + every current cohort.
- `refresh_wave(survey_id) -> None` — derive every current cohort for the wave, then `build_cube(survey_id)`.
- Cell: `map_key` = `"{question_id}:{item_id or 0}:{option_id or 0}"` (the harmoniser's own key), `cohort_id` NULL = everyone, `dim_value` `''` = no value for that cut.
- `repository.analyse_cube(survey_id, question_id, cohort_id=None, break_dimension=None) -> DataFrame` — same columns and order as `analyse`.

- [ ] **Step 1: Failing tests:**

```python
from app.data import cube, repository

strip = lambda fn: getattr(fn, "__wrapped__", fn)


def engine_frame(sid, qid, dim):
    frame = strip(repository.analyse)(sid, qid, (), None if dim == "total" else dim)
    return frame.reset_index(drop=True)


def test_cube_equals_the_engine_for_every_question_and_cut(wave):
    engine, sid, _, _ = wave
    cube.build_cube(sid)
    with engine.connect() as conn:
        qids = [r[0] for r in conn.execute(sa.text(
            "SELECT question_id FROM csi_question WHERE survey_id = :s AND qtype IN ('single','multi','grid_single')"),
            {"s": sid})]
    for qid in qids:
        for dim in cube.CUBE_DIMS:
            want = engine_frame(sid, qid, dim)
            got = repository.analyse_cube(sid, qid, None, None if dim == "total" else dim)
            assert got.to_dict("records") == want.to_dict("records"), (qid, dim)


def test_cube_equals_the_engine_on_a_grid(csi_db, tmp_path):
    from etl import qualtrics_export
    from tests.test_phase3 import qualtrics_file
    sid = qualtrics_export.ingest_export(qualtrics_file(tmp_path), "2025-05-12")
    cube.build_cube(sid)
    with csi_db.connect() as conn:
        qid = conn.execute(sa.text("SELECT question_id FROM csi_question WHERE survey_id = :s AND qcode = 'B11'"),
                           {"s": sid}).scalar()
    assert repository.analyse_cube(sid, qid).to_dict("records") == engine_frame(sid, qid, "total").to_dict("records")


def test_cube_keeps_midpoint_sums_and_counts(wave):
    engine, sid, _, _ = wave
    cube.build_cube(sid)
    with engine.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT c.n, c.sum_age_mid, c.n_age_mid FROM csi_agg_cell c JOIN csi_question q ON q.question_id = c.question_id"
            " JOIN csi_option o ON o.option_id = c.option_id"
            " WHERE c.survey_id = :s AND q.qcode = 'Q1' AND o.value_label = 'Yes' AND c.dim = 'total' AND c.cohort_id IS NULL"),
            {"s": sid}).one()
    assert (row.n, float(row.sum_age_mid), row.n_age_mid) == (2, 23.5 + 67.0, 2)


def test_rebuilding_a_wave_replaces_its_cells(wave):
    engine, sid, _, _ = wave
    first = cube.build_cube(sid)
    assert cube.build_cube(sid) == first
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM csi_agg_cell WHERE survey_id = :s"), {"s": sid}).scalar() == first
```

- [ ] **Step 2: Run** → FAIL (`No module named 'app.data.cube'`).
- [ ] **Step 3: Implement `app/data/cube.py`.** Per cohort (everyone + each current cohort) × dim: two `INSERT … SELECT` statements.
  - *single / grid rows* — `JOIN csi_option o ON o.question_id = f.question_id AND o.value_code = a.value_code`; `n = COUNT(*)`; `base_n = SUM(COUNT(*)) OVER (PARTITION BY f.question_id, f.item_id, <dim value>)`; sums/counts of `p.age_mid`, `p.income_mid_k`.
  - *multi items* — `n = SUM(CASE WHEN a.value_code = 1 THEN 1 ELSE 0 END)`; `base_n` from a derived table of `COUNT(DISTINCT respondent_id)` answering the question per dim value; midpoint sums only over `value_code = 1`.
  - dim value: `'Total'` for total, else `COALESCE(p.<dim>, '')`; cohort: `JOIN csi_respondent_cohort rc ON rc.respondent_id = r.respondent_id AND rc.cohort_id = :cohort` or none.
  - `cell_key = CONCAT(COALESCE(question,0), ':', COALESCE(item,0), ':', COALESCE(option,0), ':', COALESCE(cohort,0), ':0:', dim, ':', value)`; `map_key` = first three parts.
  - `DELETE FROM csi_agg_cell WHERE survey_id = :sid [AND COALESCE(cohort_id, 0) IN :cohorts]` first, all in one transaction.
  In `repository.py` add `analyse_cube`: read cells for `(survey_id, question_id, COALESCE(cohort_id,0) = :coh, dim)`, join item/option labels, rebuild `segment` (`'Total'`, or `dim_value` with `''` → `None`), `answer` (grid: `item — option`), order (`item_order * 1000 + option order` for single/grid, item order for multi), `pct = n / base_n` — the exact frame `analyse` returns.
- [ ] **Step 4: Run** → parity for every question and cut; full suite green.

---

### Task 4: Cube-first repository

**Interfaces:**
- Criterion `{"kind": "cohort", "cohort_id": int}` in `_cohort_sql` (`EXISTS` in `csi_respondent_cohort`) — any mix of criteria still works through the engine.
- `analyse(...)` routes to `analyse_cube` when the criteria are empty or exactly one cohort criterion and the break is `None` or in `cube.CUBE_DIMS`, **and** the wave has cells; otherwise the engine. Same frame either way.
- `concept_trend(concept_id, cohort_id=None) -> DataFrame[wave_label, wave_date, platform, answer, answer_order, n, base_n, pct]` — one indexed read across every wave with a confirmed mapping.
- `concept_pooled(concept_id, survey_ids, cohort_id=None, dim="total") -> DataFrame[segment, answer, n, base_n, pct, avg_age, avg_income_k]` — waves stacked (the workbook's "Five Waves Combined"); base = sum of each wave's base.
- `concept_catalog(qtype=None)`, `cohort_list()` for the pickers.

- [ ] **Step 1: Failing tests:**

```python
def test_analyse_answers_from_the_cube_when_it_can(wave):
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    qid = int(repository.question_lookup.__wrapped__(sid).query("qcode == 'Q1'").question_id.iloc[0])
    reads = []
    listener = lambda conn, cur, stmt, *a: reads.append(stmt)
    sa.event.listen(engine, "before_cursor_execute", listener)
    frame = strip(repository.analyse)(sid, qid, (), "age_band")
    sa.event.remove(engine, "before_cursor_execute", listener)
    assert any("csi_agg_cell" in s for s in reads) and not any("csi_answer" in s for s in reads)
    assert frame.equals(engine_frame(sid, qid, "age_band")) or frame.to_dict("records") == engine_frame(sid, qid, "age_band").to_dict("records")


def test_a_cohort_criterion_reads_the_same_either_way(wave):
    engine, sid, b1, _ = wave
    cid = cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "yes"})
    cohorts.derive(cid)
    cube.build_cube(sid)
    qid = int(repository.question_lookup.__wrapped__(sid).query("qcode == 'Q2'").question_id.iloc[0])
    crit = ({"kind": "cohort", "cohort_id": cid},)
    from_cube = strip(repository.analyse)(sid, qid, crit, None)
    by_engine = strip(repository.analyse)(sid, qid, crit + ({"kind": "profile", "dimension": "gender", "values": []},), None)
    assert from_cube.to_dict("records") == by_engine.to_dict("records")


def test_concept_trend_picks_up_a_mapping_confirmed_after_the_cube_was_built(wave, legacy):
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    with engine.connect() as conn:
        cid = conn.execute(sa.text("SELECT concept_id FROM csi_concept WHERE concept_code = :c"), {"c": b1}).scalar()
    before = strip(repository.concept_trend)(cid)
    assert set(before.wave_label) == {"2025-02-17"}
    assert before.set_index("answer").n.to_dict() == {"Yes": 2, "No": 1}
```

(The third test pins the read path through `csi_concept_map`; the second wave that proves "confirmed later" is loaded in Task 7 on real data, where proposals exist.)

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** in `repository.py`. **Step 4: Run** → pass; full suite green.

---

### Task 5: Wiring — loads and mapping decisions keep cohorts and cube current

- [ ] **Step 1: Failing test** — loading a legacy wave builds its cube:

```python
def test_loading_a_wave_builds_its_cube(legacy):
    sid = legacy_dwh.load_legacy("SV_T")
    with legacy.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM csi_agg_cell WHERE survey_id = :s"), {"s": sid}).scalar() > 0
```

- [ ] **Step 2: Run** → FAIL. **Step 3:** call `cube.refresh_wave(survey_id)` after `harmonise_survey` in `legacy_dwh.load_legacy`, `qualtrics_export.ingest_export`, and both `run_pipeline` paths; in `7_Mappings.py` `decide()` call `cohorts.derive(c, [survey_id])` + `cube.build_cube(survey_id, cohort_ids=[...])` for the current cohorts (the survey id is the decided row's). **Step 4:** full suite green.

---

### Task 6: Pages

- [ ] **Analysis Builder** — in "Add a criterion", a third choice "Defined cohort" (`repo.cohort_list()`), appending `{"kind": "cohort", "cohort_id": id, "label": "Cohort: <name>"}`.
- [ ] **Trends** — a "By concept (every wave and platform)" mode: pick a concept (`repo.concept_catalog()`), optional cohort, items; `repo.concept_trend`; base tiles and the moving-base warning as today; Excel export. The existing family/qcode mode stays for Forsta waves.
- [ ] Verify both in the browser on `dwh_stg` (Task 7).

---

### Task 7: Build on `dwh_stg`, prove it, time it

- [ ] **Step 1:** `init_db.py --dry-run` (the three columns + index), then apply.
- [ ] **Step 2: Cohort definitions.** Find the concept codes for the beauty-purchase question (Oct 2023 – Jun 2024 waves) and the spend question; write `config/cohorts.yml` with `BEAUTY_SHOPPER` (spec §5.4 rule). Any golden-wave Beauty question still *proposed* is listed — confirmation is an analyst decision; the report names each one.
- [ ] **Step 3:** `python -m app.data.cohorts --sync`, then `python -m app.data.cube --all` (every wave).
- [ ] **Step 4: Golden** — `concept_pooled(B1, four waves)`: Yes n = 1,200; base 1,614; by age band 255/353/330/262; avg age 44.94375; avg income 93.1132; and BEAUTY_SHOPPER size over the four waves. Differences reported with cause.
- [ ] **Step 5: Performance** — `scripts/perf_check.py` (20 runs each, uncached): standard view (`analyse` from cube, one wave, age-band break) < 1 s; ad-hoc cohort on one wave (engine, two criteria) < 3 s; five-wave stack (`concept_pooled`, five waves) < 5 s — P95.
- [ ] **Step 6: UI** — Analysis Builder with the cohort criterion; Trends by concept (Amazon.com, 2022 – 2025) — screenshots, URL stated.

### Task 8: Docs

- [ ] Spec status (Phase 4 live), §5.5 note that the cube joins mappings at read time; README status rows; `docs/06-running-locally.md` (`cohorts --sync`, `cube --all`); final list of changed files (no commit).
