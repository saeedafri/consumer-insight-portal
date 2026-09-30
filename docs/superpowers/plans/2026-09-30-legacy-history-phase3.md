# Legacy Survey History — Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every Qualtrics-era survey Coresight delivered (2022 – Aug 2025, 142 waves with completes) plus the May 2025 Beauty wave that only exists as an Excel export is loaded into the `csi_` schema, linked to concepts, and proven against its source — so the Beauty history and the weekly tracker trend back years.

**Architecture:** Two new adapters feed the existing loader. `etl/legacy_dwh.py` reads the legacy `dwh_sm*` tables; because they sit on the same MySQL server as `csi_*`, answers are moved **server-side** with `INSERT … SELECT` and only the small question definitions travel. `etl/qualtrics_export.py` parses Qualtrics' two-header-row Excel export into the loader's existing records. Three speed fixes make 142 waves loadable over the India–Azure VPN: batched definitions, batched harmonisation, and the server-side answer move.

**Tech Stack:** Python 3.13, SQLAlchemy 2, PyMySQL, MySQL 8.0 (`dwh_stg`), SQLite (tests), openpyxl, Streamlit 1.55, pytest.

**Spec:** `docs/superpowers/specs/2026-09-29-survey-platform-design.md` (§2, §4 adapters + Wave Package, §6 data flow, §11 Phase 3). Evidence: `docs/11-dwh-prod-review.md`.

## Global Constraints

- Source: `dwh_stg.dwh_sm*` (identical to production — `docs/11-dwh-prod-review.md`). **Legacy tables are read, never written.**
- Target: `csi_*` in `dwh_stg` via `dwh_app_access`. Additive schema only.
- The user's Excel files are never modified; tests build their own fixture workbooks in `tmp_path`.
- Personal data is not stored (spec D7): Qualtrics `IPAddress`, `LocationLatitude/Longitude`, `Recipient*` columns are dropped; respondent ids are stored as given (they are Qualtrics response ids, not panel ids) and `respondent_key` holds their sha256.
- Every wave must reconcile before the phase is done: respondent counts and every answer's count equal the source.
- Load order oldest first, so the earliest wording seeds each concept (`harmonise_all`).
- Round trips cost ~250 ms over the VPN: a per-wave step must use a constant number of statements, not one per row.
- **Never run `git commit` or `git push`.** Checkpoints list changed files.
- Naming: plain 1–4 word names, verb-first functions; match surrounding style.

## Evidence this plan is built on (measured 30 Sep 2026)

| Fact | Value |
|---|---|
| Qualtrics-era legacy surveys with completed responses | 142 (70,276 responses, 2,938,735 answer rows) |
| Legacy `family` label | unreliable for Qualtrics — 45 of 46 questions in the Feb 2025 wave say `multiple_choice`, including yes/no B1 |
| Legacy questions with no answer rows | 387 of 4,388 Qualtrics (grids such as B11 were never imported) |
| `answer_othertext` | Qualtrics: empty; SurveyMonkey: the literal string `'None'` |
| Demographics | `dwh_smdemography` covers SurveyMonkey only; Qualtrics waves ask "What is your age group?" (140 waves) with bands `under 18`, `18 - 29`, `30 - 44`, `45 - 60`, `over 60` |
| Income labels | identical in Forsta and Qualtrics: `under $25,000` … `$200,000 or greater` |
| Reading one wave's answers over the VPN | 26,235 rows in 8.9 s |
| Current per-row writes | load_definitions ≈ 1,000 round trips/wave; harmonise ≈ 4/unit; respondents ≈ 5/respondent |

## Review Focus

1. **A legacy question whose family says "multiple_choice" but every respondent gave one answer** (yes/no, scales) — must load as single-choice with its options, or cross-tabs and filters treat "Yes" as a checkbox. Test in Task 4.
2. **A respondent who answered a multi-select** — unselected items must carry 0, so the answering base (spec: "Total Answering") is correct. Test in Task 4.
3. **Reloading a legacy wave** — must replace its answers, not duplicate them, and keep concept decisions. Test in Task 4.
4. **A banded age answer** ("18 - 29") — must set age band and midpoint and leave generation empty, never GenZ. Test in Task 1.
5. **A Qualtrics export column that is a grid row vs a multi-select item** (both `B11_1`-style codes) — must be told apart by their values. Test in Task 6.

## File Map

| File | Change | Responsibility |
|---|---|---|
| `config/survey_map.yml`, `etl/survey_map.py` | modify | age-band + income midpoints; study family rules |
| `etl/run_pipeline.py` | modify | profiles write band/midpoints |
| `etl/loaders.py` | modify | batched `load_definitions`; `upsert_survey(study_type=…)` |
| `app/data/harmonise.py` | modify | two-pass, batched `harmonise_survey` |
| `etl/legacy_dwh.py` | create | legacy adapter: list, load (server-side answers), reconcile, CLI |
| `etl/qualtrics_export.py` | create | Qualtrics two-header export → questions + records; ingest |
| `scripts/reconcile.py` | modify | legacy waves reconcile against their source |
| `app/pages/7_Mappings.py` | modify | wave filter + 25 per page (the queue will hold hundreds) |
| `tests/test_phase3.py` | create | all tests for this phase |

---

### Task 1: Banded demographics and midpoints

**Files:** `config/survey_map.yml`, `etl/survey_map.py`, `etl/run_pipeline.py` (`_rebuild_profiles`); test `tests/test_phase3.py`

**Interfaces:**
- Produces: `survey_map.parse_age_band(label) -> tuple[Optional[str], Optional[float]]` — `("18-29", 23.5)` for a banded answer, `(None, None)` otherwise (`"under 18"` → `(None, None)`: outside every band).
- Produces: `survey_map.income_mid_k(label) -> Optional[float]`.
- `_rebuild_profiles` writes `age_mid` (band midpoint, or the exact age for single-year answers) and `income_mid_k`; a banded age leaves `age_years` and `generation` NULL.

- [ ] **Step 1: Write the failing tests** — create `tests/test_phase3.py`:

```python
"""Phase 3: legacy survey history and the Qualtrics Excel export.

See docs/superpowers/plans/2026-09-30-legacy-history-phase3.md.
"""
from __future__ import annotations

from etl import survey_map


def test_age_bands_parse_to_band_and_midpoint():
    assert survey_map.parse_age_band("18 - 29") == ("18-29", 23.5)
    assert survey_map.parse_age_band("over 60") == ("Over 60", 67.0)
    assert survey_map.parse_age_band("> 60") == ("Over 60", 67.0)
    assert survey_map.parse_age_band("under 18") == (None, None)
    assert survey_map.parse_age_band("34") == (None, None)       # a single year is not a band


def test_income_midpoints_match_the_analysts_workbook():
    assert survey_map.income_mid_k("$50,000 - $99,999") == 74.9995
    assert survey_map.income_mid_k("under $25,000") == 13
    assert survey_map.income_mid_k("$200,000 or greater") == 225
    assert survey_map.income_mid_k("prefer not to say") is None
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_phase3.py -v` — Expected: 2 FAIL, `AttributeError: … no attribute 'parse_age_band'`.

- [ ] **Step 3: Config** — append to `config/survey_map.yml`:

```yaml
# Banded age answers (Qualtrics "What is your age group?") and the midpoints
# the analysts average on (Beauty Shopper Profiles, "Age Income Beauty Total").
age_band_labels:
  - {pattern: "^18\\s*-\\s*29$",               band: "18-29",   mid: 23.5}
  - {pattern: "^30\\s*-\\s*44$",               band: "30-44",   mid: 37}
  - {pattern: "^45\\s*-\\s*60$",               band: "45-60",   mid: 52.5}
  - {pattern: "^(over 60|>\\s*60|60\\s*\\+)$", band: "Over 60", mid: 67}

# Household income midpoints, $000 — identical labels in Forsta and Qualtrics.
income_midpoints_k:
  "under $25,000": 13
  "$25,000 - $49,999": 37.4995
  "$50,000 - $99,999": 74.9995
  "$100,000 - $149,999": 124.9995
  "$150,000 - $199,999": 174.9995
  "$200,000 or greater": 225
```

- [ ] **Step 4: Implement in `etl/survey_map.py`** (after `generation`):

```python
def parse_age_band(label: Optional[str]) -> tuple[Optional[str], Optional[float]]:
    """A banded age answer -> (band, midpoint). A single-year answer is not a
    band; "under 18" matches no band on purpose (outside every cut)."""
    value = " ".join(str(label or "").split()).lower()
    for rule in load_config().get("age_band_labels") or []:
        if re.match(rule["pattern"], value):
            return rule["band"], float(rule["mid"])
    return None, None


def income_mid_k(label: Optional[str]) -> Optional[float]:
    table = {k.lower(): v for k, v in (load_config().get("income_midpoints_k") or {}).items()}
    return table.get(" ".join(str(label or "").split()).lower())
```

- [ ] **Step 5: Use it in `_rebuild_profiles`** (`etl/run_pipeline.py`). Replace the two lines

```python
        age = survey_map.parse_age(values.get("age"))
        state = values.get("state_name")
```

with

```python
        band, band_mid = survey_map.parse_age_band(values.get("age"))
        # A band ("18 - 29") gives band and midpoint but no single age, so no
        # generation: 18-29 spans GenZ and Millennials.
        age = None if band else survey_map.parse_age(values.get("age"))
        state = values.get("state_name")
```

in the payload dict replace `"band": survey_map.age_band(age),` with `"band": band or survey_map.age_band(age),` and add

```python
            "age_mid": band_mid if band else age,
            "inc_mid": survey_map.income_mid_k(values.get("income_band")),
```

and in the INSERT add `age_mid, income_mid_k` to the column list, `:age_mid, :inc_mid` to VALUES, and `age_mid = VALUES(age_mid), income_mid_k = VALUES(income_mid_k),` to the update list.

- [ ] **Step 6: Run** `.venv/bin/python -m pytest tests/test_phase3.py -v` → 2 passed; then the full suite (`APP_ENV=LOCAL LOCAL_SQLITE_PATH=data/csi_local.db CSI_TEST_RAW=… CSI_TEST_XTAB=… .venv/bin/python -m pytest -q`) → 93 passed (91 + 2).

---

### Task 2: Batched definitions (`load_definitions`)

**Files:** `etl/loaders.py`; test `tests/test_phase3.py`

**Interfaces:**
- `load_definitions(survey_id, questions, family=None) -> dict[str, int]` — same signature and result, a constant number of statements per wave.
- `upsert_survey(..., study_type: str = "tracker")` — new optional keyword, written on insert and update.

- [ ] **Step 1: Write the failing tests** — append:

```python
import sqlalchemy as sa

from etl import excel_parsers as xp
from etl.loaders import load_definitions, upsert_survey


def wave_questions(n_questions: int) -> list:
    return [xp.ParsedQuestion(qcode=f"Q{i}", qtext=f"Question {i}?", qtype="single",
                              value_min=1, value_max=3,
                              options=[(1, "Yes"), (2, "No"), (3, "Not sure")])
            for i in range(n_questions)] + [
        xp.ParsedQuestion(qcode="M1", qtext="Which apply?", qtype="multi", value_min=0, value_max=1,
                          rows=[(f"M1r{i}", f"Item {i}") for i in range(20)])]


def statements(engine, action) -> int:
    seen = []
    listener = lambda *args: seen.append(1)
    sa.event.listen(engine, "before_cursor_execute", listener)
    action()
    sa.event.remove(engine, "before_cursor_execute", listener)
    return len(seen)


def test_definitions_cost_the_same_round_trips_whatever_the_wave_size(csi_db):
    small = upsert_survey(host="h", path="p", title="t", wave_label="2025-01-01")
    large = upsert_survey(host="h", path="p", title="t", wave_label="2025-01-08")
    few = statements(csi_db, lambda: load_definitions(small, wave_questions(3)))
    many = statements(csi_db, lambda: load_definitions(large, wave_questions(40)))
    assert few == many <= 15


def test_definitions_map_every_column(csi_db):
    sid = upsert_survey(host="h", path="p", title="t", wave_label="2025-01-01")
    fields = load_definitions(sid, wave_questions(2))
    assert set(fields) == {"Q0", "Q1"} | {f"M1r{i}" for i in range(20)}
    again = load_definitions(sid, wave_questions(2))                 # reload is an upsert
    assert again == fields


def test_upsert_survey_records_study_type(csi_db):
    sid = upsert_survey(host="h", path="p", title="Online Grocery 2025", wave_label="2025-03-25",
                        study_type="annual")
    with csi_db.connect() as conn:
        assert conn.execute(sa.text("SELECT study_type FROM csi_survey WHERE survey_id = :s"),
                            {"s": sid}).scalar() == "annual"
```

- [ ] **Step 2: Run** → the round-trip test FAILS (statement count grows with question count), the study-type test FAILS (`unexpected keyword argument 'study_type'`); `test_definitions_map_every_column` passes already (it pins behaviour through the refactor).

- [ ] **Step 3: Implement** — in `etl/loaders.py`:

`upsert_survey`: add parameter `study_type: str = "tracker",`; add `study_type` to the INSERT column list and `:study_type` to VALUES, `study_type = VALUES(study_type),` to the ON DUPLICATE list, and `"study_type": study_type,` to the parameters.

Replace the body of `load_definitions` with:

```python
    """Insert questions, rows, options and variables. Returns {field_name: field_id}.

    Batched: a constant number of statements per wave (each round trip is
    ~250 ms from the India office), whatever the number of questions."""
    with get_engine("etl").begin() as conn:
        topic_ids: dict[str, Optional[int]] = {}
        question_rows = []
        for order, q in enumerate(questions, start=1):
            topic_code = classify_group(q.qcode, q.qtext, family)
            if topic_code not in topic_ids:
                topic_ids[topic_code] = ensure_topic(conn, topic_code)
            question_rows.append({
                "sid": survey_id, "gid": topic_ids[topic_code], "qcode": q.qcode[:50],
                "qtext": q.qtext, "short": short_label(q.qtext), "qtype": q.qtype,
                "vmin": q.value_min, "vmax": q.value_max,
                "sys": 1 if survey_map.is_technical(topic_code) else 0,
                "multi": 1 if q.is_multi else 0, "ord": order,
            })
        if question_rows:
            conn.execute(text(
                """
                INSERT INTO csi_question
                    (survey_id, topic_id, qcode, qtext, qtext_short, qtype,
                     value_min, value_max, is_technical, is_multi, sort_order)
                VALUES (:sid, :gid, :qcode, :qtext, :short, :qtype,
                        :vmin, :vmax, :sys, :multi, :ord)
                ON DUPLICATE KEY UPDATE
                    topic_id = VALUES(topic_id), qtext = VALUES(qtext),
                    qtext_short = VALUES(qtext_short), qtype = VALUES(qtype),
                    value_min = VALUES(value_min), value_max = VALUES(value_max),
                    is_technical = VALUES(is_technical), is_multi = VALUES(is_multi),
                    sort_order = VALUES(sort_order)
                """), question_rows)
        qid = dict(conn.execute(text(
            "SELECT qcode, question_id FROM csi_question WHERE survey_id = :sid"),
            {"sid": survey_id}).all())

        option_rows = [
            {"qid": qid[q.qcode[:50]], "code": code, "label": (label or "")[:500],
             "nr": 1 if _is_nonresponse(label) else 0, "ord": i}
            for q in questions for i, (code, label) in enumerate(q.options, start=1)]
        if option_rows:
            conn.execute(text(
                """
                INSERT INTO csi_option
                    (question_id, value_code, value_label, is_nonresponse, sort_order)
                VALUES (:qid, :code, :label, :nr, :ord)
                ON DUPLICATE KEY UPDATE
                    value_label = VALUES(value_label),
                    is_nonresponse = VALUES(is_nonresponse),
                    sort_order = VALUES(sort_order)
                """), option_rows)

        item_rows = [
            {"qid": qid[q.qcode[:50]], "rc": item_code[:50], "rl": (item_label or "")[:1000],
             "rs": short_label(item_label or "", 80),
             "excl": 1 if _is_exclusive(item_label) else 0,
             "oe": 1 if item_code.endswith("oe") else 0, "ord": i}
            for q in questions for i, (item_code, item_label) in enumerate(q.rows, start=1)]
        if item_rows:
            conn.execute(text(
                """
                INSERT INTO csi_item
                    (question_id, item_code, item_label, item_short,
                     is_exclusive, is_other, sort_order)
                VALUES (:qid, :rc, :rl, :rs, :excl, :oe, :ord)
                ON DUPLICATE KEY UPDATE
                    item_label = VALUES(item_label), item_short = VALUES(item_short),
                    is_exclusive = VALUES(is_exclusive), is_other = VALUES(is_other),
                    sort_order = VALUES(sort_order)
                """), item_rows)
```

Keep the two existing `INSERT IGNORE INTO csi_field … SELECT` statements and the final `SELECT field_name, field_id` unchanged, now after the batched inserts (same indentation, inside the `with`).

- [ ] **Step 4: Run** `tests/test_phase3.py` → 5 passed. Rebuild the local copy (`rm -f data/csi_local.db`, `init_db`, both `run_pipeline --source excel` loads, `reconcile.py`) → `Harmonised` lines unchanged (101 / 33·2·0·89), 667/667 and 788/788. Full suite → 96 passed.

---

### Task 3: Batched harmonisation

**Files:** `app/data/harmonise.py`; test `tests/test_phase3.py`

**Interfaces:**
- `harmonise_survey(survey_id) -> dict[str, int]` — same result and rules; two passes: decide every unit against the concepts that existed before the wave, then write new concepts, options and map rows in batches (a constant number of statements per wave).
- New internal: `_create_concepts(conn, units, concepts) -> list[Concept]` (batch of `_create_concept`), `_add_options_many(conn, pairs)` (batch of `_add_options` over `(concept, unit)` pairs), `_map_units(conn, rows)`, `_map_choices_many(conn, survey_id, pairs)`. The single-unit helpers used by `confirm` / `keep_separate` stay.

- [ ] **Step 1: Write the failing test** — append:

```python
from app.data import harmonise


def test_harmonising_a_wave_costs_the_same_whatever_its_size(csi_db):
    small = upsert_survey(host="h", path="p", title="t", wave_label="2025-01-01")
    large = upsert_survey(host="h", path="p", title="t", wave_label="2025-01-08")
    load_definitions(small, [q for q in wave_questions(3)])
    load_definitions(large, [xp.ParsedQuestion(qcode=f"Z{i}", qtext=f"Other question {i}?",
                                               qtype="single", options=[(1, "A"), (2, "B")])
                             for i in range(40)])
    few = statements(csi_db, lambda: harmonise.harmonise_survey(small))
    many = statements(csi_db, lambda: harmonise.harmonise_survey(large))
    assert few == many <= 20
```

- [ ] **Step 2: Run** → FAIL (many > few: four statements per new unit).

- [ ] **Step 3: Implement.** In `app/data/harmonise.py` add, after `_create_concept`:

```python
def _new_code(unit: Unit, taken: set[str]) -> str:
    base = f"{slug(unit.qcode, 20).upper()}_{_digest(unit.qtype + unit.match_text)}"
    code, n = base, 1
    while code in taken:
        n += 1
        code = f"{base}_{n}"
    taken.add(code)
    return code


def _create_concepts(conn, units: list[Unit], concepts: dict[int, Concept]) -> list[Concept]:
    """One INSERT and one SELECT for every new concept a wave needs."""
    if not units:
        return []
    taken = {c.code for c in concepts.values()}
    rows = [{"code": _new_code(u, taken), "name": u.wording[:255], "grp": u.group,
             "topic": u.topic_id, "qtype": u.qtype, "match": u.match_text[:2000]} for u in units]
    conn.execute(text(
        "INSERT INTO csi_concept (concept_code, concept_name, concept_group, topic_id, qtype, match_text)"
        " VALUES (:code, :name, :grp, :topic, :qtype, :match)"), rows)
    ids = dict(conn.execute(text(
        "SELECT concept_code, concept_id FROM csi_concept WHERE concept_code IN :codes")
        .bindparams(bindparam("codes", expanding=True)), {"codes": [r["code"] for r in rows]}).all())
    created = []
    for unit, row in zip(units, rows):
        concepts[ids[row["code"]]] = Concept(ids[row["code"]], row["code"], unit.qtype, unit.match_text)
        created.append(concepts[ids[row["code"]]])
    return created


def _add_options_many(conn, pairs: list) -> None:
    """_add_options for many (concept, unit) pairs: one INSERT, one SELECT."""
    new, owner = [], {}
    for concept, unit in pairs:
        for _, _, label, nonresponse, order in unit.choices:
            key = normalise_text(label)
            if key in concept.options or (concept.concept_id, key) in owner.values():
                continue
            code, n = slug(label), 1
            while code in concept.option_codes:
                n += 1
                code = f"{slug(label, 55)}_{n}"
            concept.option_codes.add(code)
            owner[(concept.concept_id, code)] = (concept.concept_id, key)
            new.append({"cid": concept.concept_id, "code": code, "label": str(label)[:500],
                        "ord": order or 0, "nr": nonresponse or 0})
    if not new:
        return
    conn.execute(text(
        "INSERT INTO csi_concept_option (concept_id, option_code, option_label, sort_order, is_nonresponse)"
        " VALUES (:cid, :code, :label, :ord, :nr)"), new)
    by_id = {c.concept_id: c for c, _ in pairs}
    for cid, coid, code in conn.execute(text(
            "SELECT concept_id, concept_option_id, option_code FROM csi_concept_option"
            " WHERE concept_id IN :ids").bindparams(bindparam("ids", expanding=True)),
            {"ids": sorted(by_id)}):
        if (cid, code) in owner:
            by_id[cid].options[owner[(cid, code)][1]] = coid
```

(add `from sqlalchemy import bindparam, text` to the imports.)

Replace `harmonise_survey`'s loop body with the two-pass form:

```python
        decisions = []                           # (unit, kind, concept, confidence, evidence)
        for unit in _units(conn, survey_id):
            if unit.key in done:
                counts["skipped"] += 1
                continue
            kind, concept, confidence, evidence = _decide(unit, concepts, used)
            if concept is not None:
                used.add(concept.concept_id)
            decisions.append([unit, kind, concept, confidence, evidence])
            counts[kind] += 1

        fresh = [d for d in decisions if d[1] == "new"]
        for d, concept in zip(fresh, _create_concepts(conn, [d[0] for d in fresh], concepts)):
            d[2] = concept
        settled = [(d[2], d[0]) for d in decisions if d[1] in ("exact", "new")]
        _add_options_many(conn, settled)

        unit_rows = [{"sid": survey_id, "key": u.key, "qid": u.question_id, "item": u.item_id,
                      "cid": c.concept_id,
                      "status": "confirmed" if k in ("exact", "new") else "proposed",
                      "method": "similar_text" if k == "similar" else "exact_text",
                      "conf": conf, "evidence": ev}
                     for u, k, c, conf, ev in decisions]
        if unit_rows:
            conn.execute(text(
                "INSERT INTO csi_concept_map (survey_id, map_key, question_id, item_id, concept_id,"
                " status, method, confidence, evidence)"
                " VALUES (:sid, :key, :qid, :item, :cid, :status, :method, :conf, :evidence)"), unit_rows)
        choice_rows = [{"sid": survey_id, "key": f"{u.question_id}:{item or 0}:{option or 0}",
                        "qid": u.question_id, "item": item, "option": option,
                        "cid": c.concept_id, "coid": c.options[normalise_text(label)], "who": None}
                       for c, u in settled for item, option, label, _, _ in u.choices]
        if choice_rows:
            conn.execute(text(
                "INSERT INTO csi_concept_map (survey_id, map_key, question_id, item_id, option_id,"
                " concept_id, concept_option_id, status, method, confidence, reviewed_by)"
                " VALUES (:sid, :key, :qid, :item, :option, :cid, :coid, 'confirmed', 'exact_text', 1, :who)"),
                choice_rows)
```

- [ ] **Step 4: Run** `tests/test_phase3.py tests/test_harmonise.py` → all pass (the 25 Phase 2 tests pin the rules). Local rebuild → `Harmonised` lines unchanged. Full suite → 97 passed.

---

### Task 4: The legacy adapter

**Files:** create `etl/legacy_dwh.py`; test `tests/test_phase3.py`

**Interfaces:**
- `legacy_qtype(family, title, max_per_response, n_answers) -> Optional[str]` — `"single"`, `"multi"`, `"text"`, or `None` (no answer rows, or a `matrix` question — not imported).
- `study_for(title, completes) -> tuple[str, str]` — `(survey_family, study_type)`: titles starting "Shopping and Spending" / "Shopping, spending" → `("CSI-US", "tracker")`; otherwise the title's slug upper-cased and `"annual"` when completes ≥ 1,500, else `"adhoc"`.
- `legacy_surveys(conn, era="qualtrics") -> list[dict]` — id, title, first completed date, completes; `era="surveymonkey"` for Phase 6.
- `load_legacy(legacy_id) -> int` — survey_id; idempotent.
- `LEGACY_STATUS = {"completed": (3, "Qualified"), "partial": (4, "Partial"), "disqualified": (1, "Terminated"), "overquota": (2, "Overquota")}`.

- [ ] **Step 1: Write the failing tests** — append:

```python
import pytest

from etl import legacy_dwh

LEGACY_DDL = [
    "CREATE TABLE dwh_smsurveydetail (id VARCHAR(100) PRIMARY KEY, title VARCHAR(700),"
    " date_created DATETIME, response_count INT, isvalid INT)",
    "CREATE TABLE dwh_smquestion (id VARCHAR(100) PRIMARY KEY, family VARCHAR(700), title VARCHAR(700),"
    " srt1 INT, srt2 INT, survey_id VARCHAR(100))",
    "CREATE TABLE dwh_smanswer (id VARCHAR(100) PRIMARY KEY, srt INT, title VARCHAR(700),"
    " question_id VARCHAR(100), survey_id VARCHAR(100))",
    "CREATE TABLE dwh_smresponse (id VARCHAR(100) PRIMARY KEY, response_status VARCHAR(700),"
    " date_filled DATETIME, total_time_spent INT, survey_id VARCHAR(100))",
    "CREATE TABLE dwh_smresponseqa (id INTEGER PRIMARY KEY, answer_text VARCHAR(700), question_text VARCHAR(700),"
    " answer_othertext VARCHAR(700), question_id VARCHAR(100), response_id VARCHAR(100),"
    " answer_id VARCHAR(100), survey_id VARCHAR(100))",
]


@pytest.fixture()
def legacy(csi_db):
    """A two-question Qualtrics-era survey in legacy form: B1 (yes/no, stored as
    'multiple_choice' like the real ones) and B10 (a real multi-select), plus
    the age question. Three completed responses and one disqualified."""
    with csi_db.begin() as conn:
        for ddl in LEGACY_DDL:
            conn.execute(sa.text(ddl))
        conn.execute(sa.text("INSERT INTO dwh_smsurveydetail VALUES ('SV_T', "
                             "'Shopping and Spending - inc Beauty', '2025-02-11', 4, 1)"))
        conn.execute(sa.text("INSERT INTO dwh_smquestion VALUES "
                             "('QB1', 'multiple_choice', 'Have you purchased beauty products?', 0, 0, 'SV_T'),"
                             "('QB10', 'multiple_choice', 'Where did you buy beauty? Select all that apply', 1, 0, 'SV_T'),"
                             "('QAGE', 'multiple_choice', 'What is your age group?', 2, 0, 'SV_T'),"
                             "('QGRID', 'single_choice', 'How do you feel about each retailer?', 3, 0, 'SV_T')"))
        conn.execute(sa.text("INSERT INTO dwh_smanswer VALUES "
                             "('A_yes', 0, 'Yes', 'QB1', 'SV_T'), ('A_no', 1, 'No', 'QB1', 'SV_T'),"
                             "('A_amz', 0, 'Amazon.com', 'QB10', 'SV_T'), ('A_cvs', 1, 'CVS', 'QB10', 'SV_T'),"
                             "('A_wmt', 2, 'Walmart', 'QB10', 'SV_T'),"
                             "('A_1829', 0, '18 - 29', 'QAGE', 'SV_T'), ('A_60', 1, 'over 60', 'QAGE', 'SV_T'),"
                             "('A_pos', 0, 'Positive', 'QGRID', 'SV_T')"))
        conn.execute(sa.text("INSERT INTO dwh_smresponse VALUES "
                             "('R_1', 'completed', '2025-02-17 08:00', 120, 'SV_T'),"
                             "('R_2', 'completed', '2025-02-17 09:00', 130, 'SV_T'),"
                             "('R_3', 'completed', '2025-02-18 10:00', 140, 'SV_T'),"
                             "('R_4', 'disqualified', '2025-02-17 11:00', 20, 'SV_T')"))
        conn.execute(sa.text("INSERT INTO dwh_smresponseqa (answer_text, question_text, answer_othertext,"
                             " question_id, response_id, answer_id, survey_id) VALUES "
                             "('Yes','',NULL,'QB1','R_1','A_yes','SV_T'), ('Yes','',NULL,'QB1','R_2','A_yes','SV_T'),"
                             "('No','',NULL,'QB1','R_3','A_no','SV_T'),"
                             "('Amazon.com','','None','QB10','R_1','A_amz','SV_T'), ('CVS','','None','QB10','R_1','A_cvs','SV_T'),"
                             "('Walmart','','None','QB10','R_2','A_wmt','SV_T'),"
                             "('18 - 29','',NULL,'QAGE','R_1','A_1829','SV_T'), ('over 60','',NULL,'QAGE','R_2','A_60','SV_T'),"
                             "('18 - 29','',NULL,'QAGE','R_3','A_1829','SV_T')"))
    return csi_db


def answers(engine, sid, field):
    with engine.connect() as conn:
        return sorted(conn.execute(sa.text(
            "SELECT r.forsta_uuid, a.value_code FROM csi_answer a JOIN csi_field f USING (field_id)"
            " JOIN csi_respondent r USING (respondent_id) WHERE a.survey_id = :s AND f.field_name = :f"),
            {"s": sid, "f": field}).all())


def test_legacy_types_are_inferred_from_the_data_not_the_family_label():
    assert legacy_dwh.legacy_qtype("multiple_choice", "Have you purchased beauty?", 1, 2) == "single"
    assert legacy_dwh.legacy_qtype("multiple_choice", "Where? Select all that apply", 1, 3) == "multi"
    assert legacy_dwh.legacy_qtype("multiple_choice", "Which do you use?", 2, 3) == "multi"
    assert legacy_dwh.legacy_qtype("single_choice", "How do you feel about each?", None, 5) is None
    assert legacy_dwh.legacy_qtype("matrix", "Rate each", 3, 5) is None


def test_study_family_and_type_come_from_the_title():
    assert legacy_dwh.study_for("Shopping and Spending - inc Beauty", 406) == ("CSI-US", "tracker")
    assert legacy_dwh.study_for("Online Grocery 2024", 2110) == ("ONLINE_GROCERY_2024", "annual")
    assert legacy_dwh.study_for("Livestream 13 Q survey for $ quote", 300)[1] == "adhoc"


def test_a_legacy_wave_loads_with_the_right_types_codes_and_zeros(legacy):
    sid = legacy_dwh.load_legacy("SV_T")
    with legacy.connect() as conn:
        survey = conn.execute(sa.text(
            "SELECT platform, source_ref, wave_label, survey_family, study_type FROM csi_survey"
            " WHERE survey_id = :s"), {"s": sid}).one()
        types = dict(conn.execute(sa.text(
            "SELECT qtext, qtype FROM csi_question WHERE survey_id = :s"), {"s": sid}).all())
        qualified = conn.execute(sa.text(
            "SELECT COUNT(*) FROM csi_respondent WHERE survey_id = :s AND is_qualified = 1"),
            {"s": sid}).scalar()
    assert tuple(survey) == ("qualtrics", "SV_T", "2025-02-17", "CSI-US", "tracker")
    assert types["Have you purchased beauty products?"] == "single"
    assert types["Where did you buy beauty? Select all that apply"] == "multi"
    assert "How do you feel about each retailer?" not in types          # no answer rows
    assert qualified == 3
    assert answers(legacy, sid, "Q1") == [("R_1", 1), ("R_2", 1), ("R_3", 2)]
    # R_1 chose Amazon + CVS; R_2 chose Walmart — everyone else who answered gets a 0
    assert answers(legacy, sid, "Q2r1") == [("R_1", 1), ("R_2", 0)]
    assert answers(legacy, sid, "Q2r3") == [("R_1", 0), ("R_2", 1)]


def test_banded_ages_reach_the_profile(legacy):
    sid = legacy_dwh.load_legacy("SV_T")
    with legacy.connect() as conn:
        rows = sorted(conn.execute(sa.text(
            "SELECT r.forsta_uuid, p.age_band, p.age_mid, p.generation FROM csi_profile p"
            " JOIN csi_respondent r USING (respondent_id) WHERE p.survey_id = :s"), {"s": sid}).all())
    assert rows[:2] == [("R_1", "18-29", 23.5, None), ("R_2", "Over 60", 67.0, None)]


def test_reloading_a_legacy_wave_replaces_not_duplicates(legacy):
    sid = legacy_dwh.load_legacy("SV_T")
    before = count(legacy, f"SELECT COUNT(*) FROM csi_answer WHERE survey_id = {sid}")
    maps_before = count(legacy, f"SELECT COUNT(*) FROM csi_concept_map WHERE survey_id = {sid}")
    assert legacy_dwh.load_legacy("SV_T") == sid
    assert count(legacy, f"SELECT COUNT(*) FROM csi_answer WHERE survey_id = {sid}") == before
    assert count(legacy, f"SELECT COUNT(*) FROM csi_concept_map WHERE survey_id = {sid}") == maps_before


def count(engine, sql):
    with engine.connect() as conn:
        return conn.execute(sa.text(sql)).scalar()
```

- [ ] **Step 2: Run** → the five new tests FAIL (`ModuleNotFoundError: No module named 'etl.legacy_dwh'`).

- [ ] **Step 3: Implement `etl/legacy_dwh.py`**

```python
"""Load a legacy survey (dwh_sm* — the Qualtrics and SurveyMonkey years) into CSI.

The legacy tables sit on the same MySQL server as csi_*, so answers are moved
server-side (INSERT … SELECT): only the small question definitions travel to
this process. That is what makes 142 waves loadable over the India–Azure link.

The legacy `family` label cannot be trusted for Qualtrics waves (yes/no
questions are stored as 'multiple_choice'), so the type is inferred from the
data: more than one answer from any respondent, or "select all" wording,
means multi-select. Questions with no answer rows (grids such as B11 were never
imported) are skipped and counted.

    python -m etl.legacy_dwh --all            # every Qualtrics-era wave, oldest first
    python -m etl.legacy_dwh --id SV_0IHGTy1GPAlUsGa
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import re
from typing import Optional

from sqlalchemy import text

from app.core.database import get_engine
from app.data import harmonise
from etl import excel_parsers as xp
from etl.loaders import finish_run, load_definitions, start_run, upsert_survey

log = logging.getLogger("cip.legacy")

LEGACY_STATUS = {"completed": (3, "Qualified"), "partial": (4, "Partial"),
                 "disqualified": (1, "Terminated"), "overquota": (2, "Overquota")}
_MULTI_WORDING = re.compile(r"select all|all that apply|select up to|select (two|three)", re.I)
_TRACKER = re.compile(r"^\s*shopping(,| and)\s+spending", re.I)


def legacy_qtype(family: Optional[str], title: str, max_per_response: Optional[int],
                 n_answers: int) -> Optional[str]:
    if max_per_response is None or family == "matrix":
        return None
    if n_answers == 0:
        return "text"
    if max_per_response > 1 or _MULTI_WORDING.search(title or ""):
        return "multi"
    return "single"


def study_for(title: str, completes: int) -> tuple[str, str]:
    if _TRACKER.match(title or ""):
        return "CSI-US", "tracker"
    family = re.sub(r"[^A-Z0-9]+", "_", (title or "").upper()).strip("_")[:60] or "ADHOC"
    return family, "annual" if completes >= 1500 else "adhoc"


def legacy_surveys(conn, era: str = "qualtrics") -> list[dict]:
    where = "d.id LIKE 'SV\\_%'" if era == "qualtrics" else "d.id NOT LIKE 'SV\\_%'"
    rows = conn.execute(text(f"""
        SELECT d.id, d.title, MIN(r.date_filled), COUNT(*)
          FROM dwh_smsurveydetail d
          JOIN dwh_smresponse r ON r.survey_id = d.id AND r.response_status = 'completed'
         WHERE {where} AND COALESCE(d.isvalid, 1) = 1
         GROUP BY d.id, d.title
         ORDER BY MIN(r.date_filled), d.id""")).all()
    return [{"id": i, "title": t, "first": f, "completes": n} for i, t, f, n in rows]


def _definitions(conn, legacy_id: str):
    """-> (ParsedQuestions, answer map rows, skipped question count)."""
    questions = conn.execute(text("""
        SELECT q.id, q.family, q.title, q.srt1, q.srt2,
               (SELECT MAX(n) FROM (SELECT COUNT(*) AS n FROM dwh_smresponseqa x
                                     WHERE x.question_id = q.id GROUP BY x.response_id) t)
          FROM dwh_smquestion q WHERE q.survey_id = :lid ORDER BY q.srt1, q.srt2, q.id"""),
        {"lid": legacy_id}).all()
    answers: dict[str, list] = {}
    for aid, qid, title, srt in conn.execute(text(
            "SELECT id, question_id, title, srt FROM dwh_smanswer WHERE survey_id = :lid"
            " ORDER BY question_id, srt, id"), {"lid": legacy_id}):
        answers.setdefault(qid, []).append((aid, title, srt))

    parsed, amap, skipped, seen = [], [], 0, set()
    for qid, family, title, srt1, srt2, max_n in questions:
        qtype = legacy_qtype(family, title, max_n, len(answers.get(qid, [])))
        if qtype is None:
            skipped += 1
            continue
        qcode = f"Q{(srt1 or 0) + 1}" + (f"_{srt2}" if srt2 else "")
        while qcode in seen:
            qcode += "b"
        seen.add(qcode)
        title = xp.clean_text(title)
        opts = answers.get(qid, [])
        if qtype == "multi":
            rows = [(f"{qcode}r{i}", xp.clean_text(t)) for i, (_, t, _) in enumerate(opts, start=1)]
            parsed.append(xp.ParsedQuestion(qcode=qcode, qtext=title, qtype="multi",
                                            value_min=0, value_max=1, rows=rows))
            amap += [{"aid": aid, "qcode": qcode, "field": code, "code": 1, "label": lab}
                     for (aid, _, _), (code, lab) in zip(opts, rows)]
        elif qtype == "single":
            options = [(i, xp.clean_text(t)) for i, (_, t, _) in enumerate(opts, start=1)]
            parsed.append(xp.ParsedQuestion(qcode=qcode, qtext=title, qtype="single",
                                            value_min=1, value_max=len(options), options=options))
            amap += [{"aid": aid, "qcode": qcode, "field": qcode, "code": code, "label": lab}
                     for (aid, _, _), (code, lab) in zip(opts, options)]
        else:
            parsed.append(xp.ParsedQuestion(qcode=qcode, qtext=title, qtype="text"))
    return parsed, amap, skipped


def load_legacy(legacy_id: str) -> int:
    eng = get_engine("etl")
    with eng.connect() as conn:
        title, created = conn.execute(text(
            "SELECT title, date_created FROM dwh_smsurveydetail WHERE id = :lid"),
            {"lid": legacy_id}).one()
        responses = conn.execute(text(
            "SELECT id, response_status, date_filled, total_time_spent FROM dwh_smresponse"
            " WHERE survey_id = :lid ORDER BY id"), {"lid": legacy_id}).all()
        questions, amap, skipped = _definitions(conn, legacy_id)

    completes = sum(1 for r in responses if r[1] == "completed")
    first = min((r[2] for r in responses if r[1] == "completed" and r[2]), default=created)
    wave = str(first)[:10]
    family, study_type = study_for(title, completes)
    platform = "qualtrics" if str(legacy_id).startswith("SV_") else "surveymonkey"
    survey_id = upsert_survey(host=platform, path=legacy_id, title=xp.clean_text(title)[:500],
                              survey_family=family, wave_label=wave, wave_date=wave,
                              platform=platform, source_ref=legacy_id, study_type=study_type)
    run = start_run(survey_id, "manual", "data", f"dwh_stg.dwh_sm*:{legacy_id}")
    fields = load_definitions(survey_id, questions, family)

    respondents = [{"sid": survey_id, "rec": n, "uuid": str(rid)[:64],
                    "sc": LEGACY_STATUS.get(status, (None, status))[0],
                    "sl": LEGACY_STATUS.get(status, (None, status))[1][:30] if status else None,
                    "qual": 1 if status == "completed" else 0, "done": filled, "secs": secs,
                    "key": hashlib.sha256(str(rid).encode()).hexdigest(), "run": run}
                   for n, (rid, status, filled, secs) in enumerate(responses, start=1)]
    with eng.begin() as conn:
        if respondents:
            conn.execute(text("""
                INSERT INTO csi_respondent (survey_id, record_no, forsta_uuid, status_code, status_label,
                                            is_qualified, completed_at, interview_secs, respondent_key, load_id)
                VALUES (:sid, :rec, :uuid, :sc, :sl, :qual, :done, :secs, :key, :run)
                ON DUPLICATE KEY UPDATE status_code = VALUES(status_code), status_label = VALUES(status_label),
                    is_qualified = VALUES(is_qualified), completed_at = VALUES(completed_at),
                    interview_secs = VALUES(interview_secs), respondent_key = VALUES(respondent_key),
                    load_id = VALUES(load_id)"""), respondents)
        conn.execute(text("DELETE FROM csi_answer WHERE survey_id = :sid"), {"sid": survey_id})
        conn.execute(text("""CREATE TEMPORARY TABLE IF NOT EXISTS csi_tmp_answer_map (
            answer_id VARCHAR(100) PRIMARY KEY, field_id INTEGER, value_code INTEGER, value_label VARCHAR(500))"""))
        conn.execute(text("DELETE FROM csi_tmp_answer_map"))
        rows = [{"aid": m["aid"], "fid": fields[m["field"]], "code": m["code"], "label": m["label"][:500]}
                for m in amap if m["field"] in fields]
        if rows:
            conn.execute(text("INSERT INTO csi_tmp_answer_map VALUES (:aid, :fid, :code, :label)"), rows)
        # the answers people gave — moved inside MySQL, never through this process
        conn.execute(text("""
            INSERT INTO csi_answer (respondent_id, survey_id, field_id, value_code, value_label)
            SELECT r.respondent_id, r.survey_id, m.field_id, MIN(m.value_code), MIN(m.value_label)
              FROM dwh_smresponseqa x
              JOIN csi_tmp_answer_map m ON m.answer_id = x.answer_id
              JOIN csi_respondent r ON r.survey_id = :sid AND r.forsta_uuid = x.response_id
             WHERE x.survey_id = :lid
             GROUP BY r.respondent_id, r.survey_id, m.field_id"""), {"sid": survey_id, "lid": legacy_id})
        # multi-select items a respondent saw but did not choose -> 0 ("Total Answering" base)
        conn.execute(text("""
            INSERT INTO csi_answer (respondent_id, survey_id, field_id, value_code, value_label)
            SELECT a.respondent_id, :sid, f.field_id, 0, i.item_label
              FROM (SELECT DISTINCT z.respondent_id, f2.question_id
                      FROM csi_answer z JOIN csi_field f2 ON f2.field_id = z.field_id
                      JOIN csi_question q ON q.question_id = f2.question_id
                     WHERE z.survey_id = :sid AND q.is_multi = 1) a
              JOIN csi_field f ON f.question_id = a.question_id AND f.item_id IS NOT NULL
              JOIN csi_item  i ON i.item_id = f.item_id
             WHERE NOT EXISTS (SELECT 1 FROM csi_answer y
                                WHERE y.respondent_id = a.respondent_id AND y.field_id = f.field_id)"""),
            {"sid": survey_id})
        loaded = conn.execute(text("SELECT COUNT(*) FROM csi_answer WHERE survey_id = :sid"),
                              {"sid": survey_id}).scalar()

    from etl.run_pipeline import _rebuild_profiles, _rebuild_question_bases
    _rebuild_profiles(survey_id, None, family)
    _rebuild_question_bases(survey_id)
    finish_run(run, len(responses), completes,
               error=f"{skipped} questions without answer rows skipped" if skipped else None)
    log.info("%s -> survey_id=%s wave=%s: %d respondents, %d answers, %d skipped questions; harmonised %s",
             legacy_id, survey_id, wave, completes, loaded, skipped, harmonise.harmonise_survey(survey_id))
    return survey_id


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    ap = argparse.ArgumentParser(description="Load legacy (dwh_sm*) surveys into CSI")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--id", help="one legacy survey id")
    group.add_argument("--all", action="store_true", help="every Qualtrics-era wave, oldest first")
    args = ap.parse_args()
    if args.id:
        load_legacy(args.id)
        return 0
    with get_engine("etl").connect() as conn:
        surveys = legacy_surveys(conn)
    for n, s in enumerate(surveys, start=1):
        log.info("[%d/%d] %s %s", n, len(surveys), s["id"], s["title"][:60])
        load_legacy(s["id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run** `tests/test_phase3.py` → 12 passed. Full suite → 104 passed.

---

### Task 5: Reconcile legacy waves against their source

**Files:** `etl/legacy_dwh.py` (add `reconcile_legacy`), `scripts/reconcile.py`; test `tests/test_phase3.py`

**Interfaces:**
- `legacy_dwh.reconcile_legacy(survey_id) -> tuple[int, list[str]]` — (answers checked, problems). Checks: qualified respondents = source completed responses; for every mapped legacy answer, CSI respondents with that answer = distinct source responses with it (completed only).
- `scripts/reconcile.py`: waves with a current cross-tab run reconcile as today; waves whose `source_ref` is a legacy id reconcile with `reconcile_legacy`; others print "no published source to reconcile against".

- [ ] **Step 1: Write the failing test** — append:

```python
def test_a_loaded_legacy_wave_reconciles_and_a_tampered_one_does_not(legacy):
    sid = legacy_dwh.load_legacy("SV_T")
    checked, problems = legacy_dwh.reconcile_legacy(sid)
    assert checked == 7 and problems == []           # 2 + 3 + 2 mapped answers
    with legacy.begin() as conn:
        conn.execute(sa.text("DELETE FROM csi_answer WHERE survey_id = :s AND value_code = 2"), {"s": sid})
    assert legacy_dwh.reconcile_legacy(sid)[1]
```

- [ ] **Step 2: Run** → FAIL (`no attribute 'reconcile_legacy'`).

- [ ] **Step 3: Implement** — append to `etl/legacy_dwh.py`:

```python
def reconcile_legacy(survey_id: int) -> tuple[int, list[str]]:
    """Every loaded count must equal the legacy source (spec §6 step 7)."""
    eng = get_engine("etl")
    with eng.connect() as conn:
        legacy_id = conn.execute(text("SELECT source_ref FROM csi_survey WHERE survey_id = :s"),
                                 {"s": survey_id}).scalar()
        _, amap, _ = _definitions(conn, legacy_id)
        fields = dict(conn.execute(text(
            "SELECT field_name, field_id FROM csi_field WHERE survey_id = :s"), {"s": survey_id}).all())
        ours = {(f, c): n for f, c, n in conn.execute(text("""
            SELECT a.field_id, a.value_code, COUNT(*) FROM csi_answer a
              JOIN csi_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
             WHERE a.survey_id = :s AND a.value_code > 0 GROUP BY a.field_id, a.value_code"""),
            {"s": survey_id})}
        source = dict(conn.execute(text("""
            SELECT x.answer_id, COUNT(DISTINCT x.response_id) FROM dwh_smresponseqa x
              JOIN dwh_smresponse r ON r.id = x.response_id AND r.response_status = 'completed'
             WHERE x.survey_id = :lid GROUP BY x.answer_id"""), {"lid": legacy_id}).all())
        qualified = conn.execute(text(
            "SELECT COUNT(*) FROM csi_respondent WHERE survey_id = :s AND is_qualified = 1"),
            {"s": survey_id}).scalar()
        completes = conn.execute(text(
            "SELECT COUNT(*) FROM dwh_smresponse WHERE survey_id = :lid AND response_status = 'completed'"),
            {"lid": legacy_id}).scalar()
    problems = [] if qualified == completes else [f"respondents: ours {qualified}, source {completes}"]
    checked = 0
    for m in amap:
        if m["field"] not in fields:
            continue
        checked += 1
        got, want = ours.get((fields[m["field"]], m["code"]), 0), source.get(m["aid"], 0)
        if got != want:
            problems.append(f"{m['qcode']} '{m['label'][:50]}': ours {got}, source {want}")
    return checked, problems
```

In `scripts/reconcile.py` `main()`, replace the per-survey body with:

```python
    for s in surveys.itertuples():
        has_crosstab = not query_df(
            "SELECT 1 FROM csi_crosstab_run WHERE survey_id = :s AND is_current = 1",
            {"s": int(s.survey_id)}).empty
        if not has_crosstab:
            ref = query_df("SELECT platform, source_ref FROM csi_survey WHERE survey_id = :s",
                           {"s": int(s.survey_id)}).iloc[0]
            if ref.platform in ("qualtrics", "surveymonkey") and not str(ref.source_ref).startswith("xlsx:"):
                from etl.legacy_dwh import reconcile_legacy
                checked, problems = reconcile_legacy(int(s.survey_id))
                bad += len(problems)
                print(f"{s.wave_label}  {s.title}\n  {checked - len(problems)}/{checked} legacy answers match the source")
                for p in problems[:20]:
                    print("   ✗", p)
            else:
                print(f"{s.wave_label}  {s.title}\n  no published source to reconcile against")
            continue
        # … existing cross-tab reconciliation block, unchanged …
```

- [ ] **Step 4: Run** `tests/test_phase3.py` → 13 passed; local `scripts/reconcile.py` still 667/667, 788/788. Full suite → 105 passed.

---

### Task 6: The Qualtrics Excel export (May 2025)

**Files:** create `etl/qualtrics_export.py`; test `tests/test_phase3.py`

**Interfaces:**
- `parse_export(path) -> tuple[list[ParsedQuestion], list[dict]]` — questions and loader-ready records (`record`, `uuid`, `status`, `date`, `qtime`, plus one key per field in the Forsta label convention: a multi item holds its label when chosen and `"NO TO: <label>"` when the respondent answered the question but not this item).
- `ingest_export(path, wave, family="CSI-US") -> int` — survey_id (platform `qualtrics`, `source_ref = "xlsx:" + title`).
- Rules: columns grouped by the code before the first `_`; `_TEXT` columns → text questions; a group whose every non-blank value equals its column's label (text after the last " - ") is multi-select; a group with several columns otherwise is a grid (`grid_single`, rows = column labels, options = distinct values ordered by first appearance); a single column is single-choice. Dropped: `StartDate`, `IPAddress`, `Progress`, `Finished`, `RecipientLastName`, `RecipientFirstName`, `RecipientEmail`, `ExternalReference`, `LocationLatitude`, `LocationLongitude`, `DistributionChannel`, `UserLanguage`, `RecordedDate`, `Status`; technical: `CINTID`, `RID`, `COMPLETE`, `SC0`, `fin`, `C3`.

- [ ] **Step 1: Write the failing tests** — append:

```python
import openpyxl

from etl import qualtrics_export


def qualtrics_file(tmp_path):
    """The two-header-row shape of a real Qualtrics export, three respondents."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["StartDate", "EndDate", "IPAddress", "Duration (in seconds)", "ResponseId",
               "B1", "B10_1", "B10_2", "B11_1", "B11_2", "B3_16_TEXT", "CINTID"])
    ws.append(["Start Date", "End Date", "IP Address", "Duration (in seconds)", "Response ID",
               "Have you purchased any beauty products?",
               "Where did you buy beauty? Select all that apply - Selected Choice - Amazon.com",
               "Where did you buy beauty? Select all that apply - Selected Choice - CVS",
               "How do you feel about each retailer? - Amazon.com",
               "How do you feel about each retailer? - CVS",
               "Where do you discover beauty? - Other (please specify) - Text", "CINTID"])
    ws.append(["2025-05-12 08:00:00", "2025-05-12 08:02:00", "1.2.3.4", 120, "R_a",
               "Yes", "Amazon.com", None, "Very positive", "Neutral", "TikTok", "111"])
    ws.append(["2025-05-12 09:00:00", "2025-05-12 09:03:00", "5.6.7.8", 180, "R_b",
               "Yes", None, "CVS", "Neutral", None, None, "222"])
    ws.append(["2025-05-12 10:00:00", "2025-05-12 10:01:00", "9.9.9.9", 60, "R_c",
               "No", None, None, None, None, None, "333"])
    path = tmp_path / "export.xlsx"
    wb.save(path)
    return path


def test_qualtrics_export_parses_types_and_drops_personal_data(tmp_path):
    questions, records = qualtrics_export.parse_export(qualtrics_file(tmp_path))
    kinds = {q.qcode: q.qtype for q in questions}
    assert kinds["B1"] == "single" and kinds["B10"] == "multi" and kinds["B11"] == "grid_single"
    assert kinds["B3_16_TEXT"] == "text" and kinds["CINTID"] == "text"
    assert all("IPAddress" not in r for r in records)
    assert records[0]["B10_2"] == "NO TO: CVS" and records[2].get("B10_1") is None   # R_c never answered B10
    grid = next(q for q in questions if q.qcode == "B11")
    assert [label for _, label in grid.rows] == ["Amazon.com", "CVS"]
    assert [label for _, label in grid.options] == ["Very positive", "Neutral"]


def test_qualtrics_export_loads_and_harmonises(csi_db, tmp_path):
    sid = qualtrics_export.ingest_export(qualtrics_file(tmp_path), "2025-05-12")
    with csi_db.connect() as conn:
        assert conn.execute(sa.text("SELECT platform, source_ref FROM csi_survey WHERE survey_id = :s"),
                            {"s": sid}).one()[0] == "qualtrics"
        assert conn.execute(sa.text("SELECT COUNT(*) FROM csi_respondent WHERE survey_id = :s"
                                    " AND is_qualified = 1"), {"s": sid}).scalar() == 3
        assert conn.execute(sa.text("SELECT COUNT(*) FROM csi_concept_map WHERE survey_id = :s"),
                            {"s": sid}).scalar() > 0
```

- [ ] **Step 2: Run** → FAIL (`No module named 'etl.qualtrics_export'`).

- [ ] **Step 3: Implement `etl/qualtrics_export.py`**

```python
"""Qualtrics' Excel export: row 1 column codes (B10_3), row 2 question text
("… - Selected Choice - Walmart"), then one row per respondent. No datamap —
types and answer lists are recovered from the columns and their values.

    python -m etl.qualtrics_export --file "…_May 20, 2025_08.00 1.xlsx" --wave 2025-05-12
"""
from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

import openpyxl

from app.data import harmonise
from etl import excel_parsers as xp
from etl.loaders import finish_run, load_definitions, start_run, upsert_survey

log = logging.getLogger("cip.qualtrics")

DROPPED = {"StartDate", "IPAddress", "Progress", "Finished", "RecipientLastName", "RecipientFirstName",
           "RecipientEmail", "ExternalReference", "LocationLatitude", "LocationLongitude",
           "DistributionChannel", "UserLanguage", "RecordedDate", "Status"}
META = {"EndDate", "Duration (in seconds)", "ResponseId"}


def _label(header_text: str) -> str:
    return xp.clean_text(str(header_text).split(" - ")[-1])


def _question_text(header_text: str) -> str:
    return xp.clean_text(re.split(r" - (Selected Choice|Other)", str(header_text))[0]
                         .rsplit(" - ", 1)[0] if " - " in str(header_text) else header_text)


def parse_export(path) -> tuple[list, list[dict]]:
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    codes = [str(c) if c is not None else "" for c in next(rows)]
    texts = [str(t) if t is not None else "" for t in next(rows)]
    data = [list(r) for r in rows if any(v not in (None, "") for v in r)]

    groups: dict[str, list[int]] = {}
    for i, code in enumerate(codes):
        if not code or code in DROPPED or code in META:
            continue
        key = code if code.endswith("_TEXT") or "_" not in code else code.split("_")[0]
        groups.setdefault(key, []).append(i)

    questions, kinds = [], {}
    for key, cols in groups.items():
        values = {i: [xp.clean_text(r[i]) for r in data if r[i] not in (None, "")] for i in cols}
        if key.endswith("_TEXT") or (len(cols) == 1 and len(set(values[cols[0]])) > 50):
            questions.append(xp.ParsedQuestion(qcode=key, qtext=xp.clean_text(texts[cols[0]]), qtype="text"))
            kinds[key] = ("text", cols)
        elif len(cols) > 1 and all(set(values[i]) <= {_label(texts[i])} for i in cols):
            rows_ = [(codes[i], _label(texts[i])) for i in cols]
            questions.append(xp.ParsedQuestion(qcode=key, qtext=_question_text(texts[cols[0]]),
                                               qtype="multi", value_min=0, value_max=1, rows=rows_))
            kinds[key] = ("multi", cols)
        elif len(cols) > 1:
            scale = list(dict.fromkeys(v for i in cols for v in values[i]))
            questions.append(xp.ParsedQuestion(qcode=key, qtext=_question_text(texts[cols[0]]),
                                               qtype="grid_single", value_min=1, value_max=len(scale),
                                               rows=[(codes[i], _label(texts[i])) for i in cols],
                                               options=list(enumerate(scale, start=1))))
            kinds[key] = ("grid", cols)
        else:
            options = list(dict.fromkeys(values[cols[0]]))
            questions.append(xp.ParsedQuestion(qcode=key, qtext=xp.clean_text(texts[cols[0]]), qtype="single",
                                               value_min=1, value_max=len(options),
                                               options=list(enumerate(options, start=1))))
            kinds[key] = ("single", cols)

    at = {c: i for i, c in enumerate(codes)}
    records = []
    for n, r in enumerate(data, start=1):
        rec = {"record": n, "uuid": r[at["ResponseId"]], "status": "Qualified",
               "date": r[at["EndDate"]], "qtime": r[at["Duration (in seconds)"]]}
        for key, (kind, cols) in kinds.items():
            if kind == "multi":
                chosen = [r[i] not in (None, "") for i in cols]
                if any(chosen):
                    for i, was in zip(cols, chosen):
                        rec[codes[i]] = _label(texts[i]) if was else f"{xp.NO_TO}{_label(texts[i])}"
            elif kind == "grid":
                for i in cols:
                    if r[i] not in (None, ""):
                        rec[codes[i]] = xp.clean_text(r[i])
            else:
                i = cols[0]
                if r[i] not in (None, ""):
                    rec[key] = xp.clean_text(r[i])
        records.append(rec)
    return questions, records


def ingest_export(path, wave: str, family: str = "CSI-US") -> int:
    from etl.run_pipeline import _code_lookup, _load_one_respondent, _rebuild_profiles, _rebuild_question_bases
    questions, records = parse_export(path)
    title = re.sub(r"_[A-Z][a-z]+ \d+, \d{4}.*$", "", Path(path).stem)
    survey_id = upsert_survey(host="qualtrics", path=f"xlsx:{title}"[:255], title=title[:500],
                              survey_family=family, wave_label=wave, wave_date=wave,
                              platform="qualtrics", source_ref=f"xlsx:{title}"[:255])
    run = start_run(survey_id, "excel", "data", str(path))
    fields = load_definitions(survey_id, questions, family)
    code_map = _code_lookup(survey_id)
    loaded = sum(_load_one_respondent(survey_id, rec, fields, run, code_map) for rec in records)
    finish_run(run, len(records), loaded)
    _rebuild_profiles(survey_id, None, family)
    _rebuild_question_bases(survey_id)
    log.info("%s -> survey_id=%s: %d respondents; harmonised %s", Path(path).name, survey_id, loaded,
             harmonise.harmonise_survey(survey_id))
    return survey_id


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    ap = argparse.ArgumentParser(description="Load a Qualtrics Excel export into CSI")
    ap.add_argument("--file", required=True)
    ap.add_argument("--wave", required=True, help="first fielding day, e.g. 2025-05-12")
    ap.add_argument("--family", default="CSI-US")
    args = ap.parse_args()
    ingest_export(args.file, args.wave, args.family)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run** `tests/test_phase3.py` → 15 passed. Full suite → 107 passed.

---

### Task 7: The Mappings page at scale

**Files:** `app/pages/7_Mappings.py`

- [ ] **Step 1: Filter and page the queue.** After `queue = repo.mapping_queue()` and its empty check, insert:

```python
waves = ["All waves"] + sorted(queue.wave_label.unique())
pick_wave = st.selectbox("Wave", waves, key="map_wave")
if pick_wave != "All waves":
    queue = queue[queue.wave_label == pick_wave]
PAGE = 25
pages = max(1, -(-len(queue) // PAGE))
page = st.number_input(f"Page (of {pages})", min_value=1, max_value=pages, value=1, key="map_page")
total = len(queue)
queue = queue.iloc[(page - 1) * PAGE: page * PAGE]
```

and change `st.markdown(f"#### {len(queue)} waiting for review")` to `st.markdown(f"#### {total} waiting for review")`.

- [ ] **Step 2: Verify** on the local copy after Task 8's local load: the page lists at most 25, the wave filter narrows it, Accept still works.

---

### Task 8: Load everything on `dwh_stg` and prove it

**Files:** none changed — operational (VPN on). Unset `LOCAL_SQLITE_PATH`.

- [ ] **Step 1: Pre-flight** — TCP to 3306, `scripts/test_connection.py` ✓ `dwh_app_access` / `dwh_stg`; `init_db.py --dry-run` shows no DDL.
- [ ] **Step 2: One wave first** — `.venv/bin/python -m etl.legacy_dwh --id SV_0IHGTy1GPAlUsGa` (Feb 2025 Beauty). Expected log: 406 respondents, skipped questions reported (B11 grid among them). Then `.venv/bin/python scripts/reconcile.py --wave <its wave label>` → every legacy answer matches.
- [ ] **Step 3: All Qualtrics-era waves** — `.venv/bin/python -m etl.legacy_dwh --all` in the background, logged to a file. Expected: 142 waves, oldest first; ETA ~1–2 h over the VPN.
- [ ] **Step 4: May 2025** — `.venv/bin/python -m etl.qualtrics_export --file ~/Downloads/"Shopping and Spending - inc Beauty + Inflation + Tariffs_May 20, 2025_08.00 1.xlsx" --wave 2025-05-12`. Expected: 405 respondents.
- [ ] **Step 5: Reconcile everything** — `.venv/bin/python scripts/reconcile.py`. Expected: both Forsta waves 667/667 and 788/788; every legacy wave all answers matching; May 2025 "no published source". Any mismatch is investigated before the phase is called done.
- [ ] **Step 6: Golden check against the analysts' workbook** — the Beauty retailer question across the five waves Jun 2024 – May 2025, counting respondents who chose each retailer:

```bash
.venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, ".")
from app.core.database import get_engine
from sqlalchemy import text
with get_engine("etl").connect() as c:
    rows = c.execute(text("""
        SELECT co.option_label, COUNT(*) FROM csi_answer a
          JOIN csi_field f ON f.field_id = a.field_id
          JOIN csi_concept_map m ON m.survey_id = a.survey_id AND m.question_id = f.question_id
               AND m.item_id = f.item_id AND m.status = 'confirmed' AND m.concept_option_id IS NOT NULL
          JOIN csi_concept_option co ON co.concept_option_id = m.concept_option_id
          JOIN csi_concept cn ON cn.concept_id = co.concept_id
          JOIN csi_survey s ON s.survey_id = a.survey_id
         WHERE a.value_code = 1 AND s.wave_date BETWEEN '2024-06-01' AND '2025-05-31'
           AND cn.concept_name LIKE 'Which, if any, of the following retailers or platforms have you purchased beauty%'
         GROUP BY co.option_label ORDER BY 2 DESC""")).all()
    for r in rows[:8]: print(r)
EOF
```

Expected: Amazon.com 492 (Beauty Shopper Profiles workbook, five waves Jun 2024 – May 2025); read the other retailers' totals from the same workbook row at run time and compare. A difference is reported with its cause (e.g. a wave whose B10 wording changed and waits in the Mappings queue), not ignored.

- [ ] **Step 7: Mappings queue** — open `http://localhost:8502/mappings` on `dwh_stg`: record the number waiting and the waves they come from. Proposals are an analyst's job; this phase only makes them reviewable (Task 7).

---

### Task 9: Documentation

**Files:** `docs/superpowers/specs/2026-09-29-survey-platform-design.md`, `README.md`, `docs/06-running-locally.md`

- [ ] **Step 1: Spec** — Status line: Phase 3 live; §4: "The legacy adapter moves answers server-side (`INSERT … SELECT`) because source and target share a server; file and API adapters still emit a Wave Package." §12 Known limits: legacy grids were never imported (387 Qualtrics questions without answer rows) — grid history exists only where an Excel export survives.
- [ ] **Step 2: README** — Status table: `| History | Qualtrics 2022 – Aug 2025 (142 waves) + May 2025 Excel, reconciled against source |`; Quick start: `python -m etl.legacy_dwh --all`, `python -m etl.qualtrics_export --file … --wave …`.
- [ ] **Step 3: Running locally** — the two commands above and that `scripts/reconcile.py` now covers legacy waves.
- [ ] **Step 4: Final checkpoint (no commit)** — list, from this phase: new `etl/legacy_dwh.py`, `etl/qualtrics_export.py`, `tests/test_phase3.py`; modified `config/survey_map.yml`, `etl/survey_map.py`, `etl/run_pipeline.py`, `etl/loaders.py`, `app/data/harmonise.py`, `scripts/reconcile.py`, `app/pages/7_Mappings.py`, the three docs.
