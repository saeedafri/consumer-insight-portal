# Harmoniser + Review Queue — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every loaded wave's questions are linked to canonical concepts — exact matches confirmed automatically, everything uncertain queued for an analyst in a new portal page — so the same question can trend across waves and platforms.

**Architecture:** One module, `app/data/harmonise.py`, owns the matching rules and every write to `csi_concept`, `csi_concept_option`, `csi_concept_map`. The loader calls it after each wave; a CLI back-fills existing waves; the portal's new **Mappings** page calls its three decision functions. A view, `v_csi_mapping_queue`, is the queue.

**Tech Stack:** Python 3.13 (`difflib` from the standard library for similarity), SQLAlchemy 2, MySQL 8.0 (`dwh_stg`), SQLite (local copy + tests), Streamlit 1.55, pytest.

**Spec:** `docs/superpowers/specs/2026-09-29-survey-platform-design.md` (§5.2 Harmonisation, §6 step 4, §11 Phase 2)

## Global Constraints

- Target database: `dwh_stg` via `dwh_app_access` (`STG_DB_*` in `.env`). Legacy `dwh_sm*` tables are never written.
- Additive schema only; new columns go through `app/core/schema_upgrade.py` (`COLUMNS`) **and** `sql/001_schema.sql`.
- Exact match → `confirmed` only when normalised wording is identical, the question type is identical, and every answer the wave offers already exists as a concept option (spec §5.2). Answers the concept has but this wave dropped do not block confirmation.
- Nothing trends until confirmed: a proposal writes only its unit-level map row; answer-level rows are written on confirmation.
- A grid is harmonised row by row: one concept per grid row; rows of one grid share `concept_group` (Phase 1 ruling).
- Normalisation folds: non-breaking and repeated whitespace, `Â` encoding debris, curly quotes, case, trailing instructions (`Select all that apply…`, `Select up to three…`, `Please select…`), trailing `.?:;`.
- Similarity threshold `SIMILAR_THRESHOLD = 0.85` (`difflib.SequenceMatcher.ratio`). Evidence: the highest unrelated pair between 09/21 and 09/28 scores 0.796.
- A question with no exact or similar candidate becomes a **new confirmed concept** — creating a concept claims no trend, so it needs no review.
- Portal decisions write through the `etl` role (the existing `save_view` precedent), recording `reviewed_by` / `reviewed_at`.
- **Never run `git commit` or `git push`.** Checkpoints list changed files.
- Naming: plain 1–4 word names, verb-first functions; match surrounding style.
- After Phase 2 on `dwh_stg`: `scripts/reconcile.py` still reports 667/667 and 788/788.

## Review Focus

1. **The same decision made twice** (double-click, two analysts) — the second must fail cleanly, never create a second concept. Test in Task 3.
2. **A wave reloaded after it was harmonised** — question ids are stable (upserts), so existing decisions must survive and the rerun must add nothing. Test in Task 2.
3. **Two identical questions inside one wave** — must not both map to one concept. Test in Task 2.
4. **Wording longer than 255 characters** (one real question is 264; grid rows are longer) — must still match exactly. Test in Task 2.
5. **A text or numeric question with no answer list** — must confirm on wording alone. Test in Task 2.

## Expected results on the real data (the exit test)

Measured on the loaded waves with a replica of these rules:

| Wave | Units (grid rows expanded) | exact | changed → queue | similar → queue | new |
|---|---|---|---|---|---|
| 2026-09-21 (first) | 101 | 0 | 0 | 0 | 101 |
| 2026-09-28 | 124 | 33 | 2 (`D28`, `D32`: both add "Muse") | 0 | 89 |

After both: 190 concepts; after accepting the two proposals the queue is empty and 35 concepts span both waves.

## File Map

| File | Change | Responsibility |
|---|---|---|
| `sql/001_schema.sql`, `app/core/schema_upgrade.py` | modify | `csi_concept.match_text` |
| `app/data/harmonise.py` | create | normalisation, matching, all concept/map writes, the 3 decisions, CLI |
| `sql/002_views.sql` | modify | `v_csi_mapping_queue` |
| `app/data/repository.py` | modify | queue, summary and answer-comparison reads for the page |
| `etl/run_pipeline.py` | modify | harmonise every wave after it loads |
| `app/pages/7_Mappings.py` | create | the review queue |
| `app/components/header.py`, `app/main.py` | modify | navigation entry |
| `tests/conftest.py` | create | `csi_db` fixture: a v2 SQLite database wired to both roles |
| `tests/test_harmonise.py` | create | all tests for this phase |

---

### Task 1: `match_text` column, text normalisation, and the test database fixture

**Files:**
- Modify: `sql/001_schema.sql` (csi_concept), `app/core/schema_upgrade.py` (`COLUMNS`)
- Create: `app/data/harmonise.py` (first part), `tests/conftest.py`, `tests/test_harmonise.py`

**Interfaces:**
- Produces: `harmonise.normalise_text(value) -> str`, `harmonise.slug(value, limit=60) -> str`.
- Produces: fixture `csi_db` → a SQLAlchemy `Engine` on a fresh v2 SQLite file, registered as both the `etl` and `app` engine for the test.
- Produces: column `csi_concept.match_text VARCHAR(2000) NULL`.

- [ ] **Step 1: Write the failing tests**

Create `tests/conftest.py`:

```python
"""Shared fixtures."""
from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.core import database, schema_upgrade


@pytest.fixture()
def csi_db(tmp_path, monkeypatch) -> sa.Engine:
    """A fresh schema-v2 SQLite database, used by every repository and
    loader function in the test (both the 'etl' and the 'app' role)."""
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'csi.db'}", future=True)
    schema_upgrade.install(engine)
    database._install_sqlite_translation(engine)
    monkeypatch.setitem(database._engines, "etl", engine)
    monkeypatch.setitem(database._engines, "app", engine)
    return engine
```

Create `tests/test_harmonise.py`:

```python
"""Phase 2: linking each wave's questions to canonical concepts.

See docs/superpowers/specs/2026-09-29-survey-platform-design.md §5.2.
"""
from __future__ import annotations

import sqlalchemy as sa

from app.data import harmonise


def test_normalise_text_folds_formatting_and_instructions():
    raw = ("Which, if any,\xa0of these  retailers have you bought from? "
           "Select all that apply or “None of these”")
    assert harmonise.normalise_text(raw) == \
        "which, if any, of these retailers have you bought from"
    assert harmonise.normalise_text("Kohl’sÂ (excluding Sephora)") == \
        "kohl's (excluding sephora)"
    assert harmonise.normalise_text(None) == ""


def test_slug_is_short_and_stable():
    assert harmonise.slug("Amazon.com") == "amazon_com"
    assert harmonise.slug("x" * 99, limit=10) == "x" * 10
    assert harmonise.slug("???") == "x"


def test_concepts_store_their_full_matching_wording(csi_db):
    cols = {c["name"] for c in sa.inspect(csi_db).get_columns("csi_concept")}
    assert "match_text" in cols
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_harmonise.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'app.data.harmonise'`.

- [ ] **Step 3: Add the column**

In `sql/001_schema.sql`, in `CREATE TABLE IF NOT EXISTS csi_concept`, after the `description` line add:

```sql
  match_text    VARCHAR(2000)     NULL     COMMENT 'normalised wording the harmoniser matches on',
```

In `app/core/schema_upgrade.py`, append to `COLUMNS`:

```python
    ("csi_concept", "match_text", "VARCHAR(2000) NULL"),
```

- [ ] **Step 4: Create `app/data/harmonise.py` with normalisation**

```python
"""Link each wave's questions to canonical concepts (spec §5.2).

For every question a wave asked, decide which concept it is:

    exact    same normalised wording and type, and every answer it offers is
             already a concept option                     -> confirmed
    changed  same wording, but it offers answers the concept lacks -> proposed
    similar  wording at least SIMILAR_THRESHOLD alike      -> proposed
    new      nothing close: a new concept                  -> confirmed

A grid is harmonised row by row — each row is its own concept, rows of one
grid share concept_group. A proposal writes only its unit-level map row;
answers are mapped when an analyst confirms it on the Mappings page, so
nothing trends before someone has looked.
"""
from __future__ import annotations

import re

# The highest-scoring unrelated pair between the 09/21 and 09/28 waves is 0.796.
SIMILAR_THRESHOLD = 0.85

_INSTRUCTIONS = re.compile(
    r"\s*(\(?\s*select\s+(all|up to|one|only)\b.*|please select.*)$", re.I)
_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


def normalise_text(value) -> str:
    """The wording two waves must share to be the same question or answer."""
    s = str(value or "").replace("\xa0", " ").replace("Â", "").translate(_QUOTES)
    s = " ".join(s.split()).lower()
    return _INSTRUCTIONS.sub("", s).strip(" .?:;")


def slug(value, limit: int = 60) -> str:
    return (re.sub(r"[^a-z0-9]+", "_", normalise_text(value)).strip("_")[:limit]) or "x"
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_harmonise.py tests/test_schema_v2.py -v`
Expected: 3 + 12 passed (the Phase 1 upgrade-parity test proves the new column arrives on both paths).

- [ ] **Step 6: Checkpoint (no commit)** — `git status --short` shows `sql/001_schema.sql`, `app/core/schema_upgrade.py`, `app/data/harmonise.py`, `tests/conftest.py`, `tests/test_harmonise.py`.

---

### Task 2: Harmonise a wave

**Files:**
- Modify: `app/data/harmonise.py`
- Test: `tests/test_harmonise.py`

**Interfaces:**
- Consumes: `normalise_text`, `slug` (Task 1); `get_engine("etl")`.
- Produces: `harmonise.harmonise_survey(survey_id: int) -> dict[str, int]` with keys `exact`, `changed`, `similar`, `new`, `skipped` (units already mapped).
- Produces (module-internal, used by Task 3): `_units(conn, survey_id) -> list[Unit]`, `_concepts(conn) -> dict[int, Concept]`, `_create_concept(conn, unit, concepts) -> Concept`, `_add_options(conn, concept, unit) -> None`, `_map_choices(conn, survey_id, unit, concept, reviewer) -> None`, `Unit.key -> str`.
- Map keys: unit row `"{question_id}:{grid row item_id or 0}:0"`; answer rows `"{question_id}:{item_id or 0}:{option_id or 0}"`. Unit rows have `concept_option_id NULL`; answer rows always have it set.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_harmonise.py`:

```python
def add_wave(engine, wave: str, questions: list[dict]) -> int:
    """Insert a minimal wave. Each question: qcode, qtext, qtype, and
    `answers` (single options / multi items) or `rows` + `answers` (grid);
    `technical=True` marks paradata."""
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO csi_survey (forsta_host, forsta_path, title, wave_label,"
            " platform, source_ref) VALUES ('h', 'p', 't', :w, 'forsta', 'p')"), {"w": wave})
        sid = conn.execute(sa.text("SELECT survey_id FROM csi_survey WHERE wave_label = :w"),
                           {"w": wave}).scalar()
        for order, q in enumerate(questions, 1):
            conn.execute(sa.text(
                "INSERT INTO csi_question (survey_id, qcode, qtext, qtype, is_technical,"
                " is_multi, sort_order) VALUES (:s, :c, :t, :y, :tech, :m, :o)"),
                {"s": sid, "c": q["qcode"], "t": q["qtext"], "y": q["qtype"],
                 "tech": int(q.get("technical", False)), "m": int(q["qtype"] == "multi"),
                 "o": order})
            qid = conn.execute(sa.text(
                "SELECT question_id FROM csi_question WHERE survey_id = :s AND qcode = :c"),
                {"s": sid, "c": q["qcode"]}).scalar()
            items = q["answers"] if q["qtype"] == "multi" else q.get("rows", [])
            for i, label in enumerate(items, 1):
                conn.execute(sa.text(
                    "INSERT INTO csi_item (question_id, item_code, item_label, sort_order)"
                    " VALUES (:q, :c, :l, :o)"), {"q": qid, "c": f"{q['qcode']}r{i}", "l": label, "o": i})
            if q["qtype"] != "multi":
                for i, label in enumerate(q.get("answers", []), 1):
                    conn.execute(sa.text(
                        "INSERT INTO csi_option (question_id, value_code, value_label, sort_order)"
                        " VALUES (:q, :v, :l, :o)"), {"q": qid, "v": i, "l": label, "o": i})
    return sid


def maps(engine, sid: int) -> list[tuple]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(sa.text(
            "SELECT q.qcode, m.status, m.method, c.concept_code"
            " FROM csi_concept_map m JOIN csi_question q ON q.question_id = m.question_id"
            " JOIN csi_concept c ON c.concept_id = m.concept_id"
            " WHERE m.survey_id = :s AND m.concept_option_id IS NULL ORDER BY q.sort_order, m.item_id"),
            {"s": sid})]


def count(engine, sql: str) -> int:
    with engine.connect() as conn:
        return conn.execute(sa.text(sql)).scalar()


RETAILERS = {"qcode": "q4", "qtype": "multi",
             "qtext": "Which, if any, of these retailers have you bought from? Select all that apply",
             "answers": ["Walmart", "Target", "None of these"]}
GENDER = {"qcode": "D1", "qtype": "single", "qtext": "What is your gender?",
          "answers": ["Male", "Female"]}
LOI = {"qcode": "qtime", "qtype": "numeric", "qtext": "Total Interview Time", "technical": True}


def test_first_wave_seeds_one_confirmed_concept_per_question(csi_db):
    sid = add_wave(csi_db, "2026-09-21", [RETAILERS, GENDER, LOI])
    assert harmonise.harmonise_survey(sid) == \
        {"exact": 0, "changed": 0, "similar": 0, "new": 2, "skipped": 0}
    assert [m[:2] for m in maps(csi_db, sid)] == [("q4", "confirmed"), ("D1", "confirmed")]
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept_option") == 5   # 3 retailers + 2 genders


def test_identical_question_confirms_to_the_same_concept(csi_db):
    a = add_wave(csi_db, "2026-09-21", [RETAILERS])
    harmonise.harmonise_survey(a)
    reformatted = dict(RETAILERS, qtext="Which,\xa0if any, of these retailers have you bought from?")
    b = add_wave(csi_db, "2026-09-28", [dict(reformatted, answers=["Target", "Walmart"])])
    assert harmonise.harmonise_survey(b)["exact"] == 1       # a dropped answer does not block
    assert maps(csi_db, a)[0][3] == maps(csi_db, b)[0][3]
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept") == 1
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept_map WHERE concept_option_id IS NOT NULL") == 3 + 2


def test_an_added_answer_waits_for_review(csi_db):
    harmonise.harmonise_survey(add_wave(csi_db, "2026-09-21", [RETAILERS]))
    b = add_wave(csi_db, "2026-09-28", [dict(RETAILERS, answers=["Walmart", "Target", "Costco"])])
    assert harmonise.harmonise_survey(b)["changed"] == 1
    with csi_db.connect() as conn:
        status, evidence = conn.execute(sa.text(
            "SELECT status, evidence FROM csi_concept_map WHERE survey_id = :s"), {"s": b}).one()
    assert status == "proposed" and "adds: costco" in evidence
    assert count(csi_db, f"SELECT COUNT(*) FROM csi_concept_map WHERE survey_id = {b}") == 1


def test_reworded_question_is_proposed_unrelated_one_is_new(csi_db):
    harmonise.harmonise_survey(add_wave(csi_db, "2026-09-21", [RETAILERS, GENDER]))
    b = add_wave(csi_db, "2026-09-28", [
        dict(RETAILERS, qtext="Which, if any, of these retailers have you purchased from?"),
        {"qcode": "BT1", "qtype": "single", "answers": ["Yes", "No"],
         "qtext": "Have you purchased any beauty products in the past three months?"}])
    assert harmonise.harmonise_survey(b) == \
        {"exact": 0, "changed": 0, "similar": 1, "new": 1, "skipped": 0}
    assert [m[:3] for m in maps(csi_db, b)] == \
        [("q4", "proposed", "similar_text"), ("BT1", "confirmed", "exact_text")]


def test_grid_rows_are_concepts_sharing_a_group(csi_db):
    grid = {"qcode": "BT14", "qtype": "grid_single", "rows": ["Amazon.com", "Walmart"],
            "qtext": "How do you feel about each retailer?", "answers": ["Positive", "Negative"]}
    harmonise.harmonise_survey(add_wave(csi_db, "2026-09-21", [grid]))
    b = add_wave(csi_db, "2026-09-28", [dict(grid, rows=["Amazon.com", "Walmart", "Target"])])
    assert harmonise.harmonise_survey(b) == \
        {"exact": 2, "changed": 0, "similar": 0, "new": 1, "skipped": 0}
    assert count(csi_db, "SELECT COUNT(DISTINCT concept_group) FROM csi_concept") == 1
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept") == 3


def test_harmonise_twice_changes_nothing(csi_db):
    sid = add_wave(csi_db, "2026-09-21", [RETAILERS, GENDER])
    harmonise.harmonise_survey(sid)
    before = count(csi_db, "SELECT COUNT(*) FROM csi_concept_map")
    assert harmonise.harmonise_survey(sid)["skipped"] == 2
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept_map") == before


def test_two_identical_questions_in_one_wave_get_two_concepts(csi_db):
    q3 = dict(RETAILERS, qcode="q5")
    sid = add_wave(csi_db, "2026-09-21", [RETAILERS, q3])
    assert harmonise.harmonise_survey(sid)["new"] == 2
    assert count(csi_db, "SELECT COUNT(DISTINCT concept_id) FROM csi_concept_map") == 2


def test_long_wording_still_matches_exactly(csi_db):
    long_q = dict(GENDER, qcode="HX1", qtext="Looking back, " + "how did your spending compare " * 12)
    harmonise.harmonise_survey(add_wave(csi_db, "2026-09-21", [long_q]))
    b = add_wave(csi_db, "2026-09-28", [long_q])
    assert len(long_q["qtext"]) > 255
    assert harmonise.harmonise_survey(b)["exact"] == 1


def test_text_question_confirms_on_wording_alone(csi_db):
    verbatim = {"qcode": "BT3r17oe", "qtype": "text", "qtext": "Where do you discover beauty? - Other"}
    harmonise.harmonise_survey(add_wave(csi_db, "2026-09-21", [verbatim]))
    assert harmonise.harmonise_survey(add_wave(csi_db, "2026-09-28", [verbatim]))["exact"] == 1
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_harmonise.py -v`
Expected: the 9 new tests FAIL with `AttributeError: module 'app.data.harmonise' has no attribute 'harmonise_survey'`.

- [ ] **Step 3: Implement matching in `app/data/harmonise.py`**

Replace the import block with:

```python
import difflib
import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import text

from app.core.database import get_engine
```

Append:

```python
@dataclass
class Unit:
    """One thing a concept can be: a question, or one row of a grid."""
    question_id: int
    item_id: Optional[int]                 # the grid row; None for a whole question
    qcode: str
    qtype: str
    topic_id: Optional[int]
    wording: str
    group: Optional[str] = None            # concept_group, grid rows only
    choices: list = field(default_factory=list)   # (item_id, option_id, label, is_nonresponse, order)

    @property
    def key(self) -> str:
        return f"{self.question_id}:{self.item_id or 0}:0"

    @property
    def match_text(self) -> str:
        return normalise_text(self.wording)


@dataclass
class Concept:
    concept_id: int
    code: str
    qtype: str
    match_text: str
    options: dict = field(default_factory=dict)      # normalised label -> concept_option_id
    option_codes: set = field(default_factory=set)


def _digest(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:6].upper()


def _units(conn, survey_id: int) -> list[Unit]:
    questions = conn.execute(text(
        "SELECT question_id, qcode, qtext, qtype, topic_id FROM csi_question"
        " WHERE survey_id = :sid AND is_technical = 0 ORDER BY sort_order"),
        {"sid": survey_id}).all()
    items, options = defaultdict(list), defaultdict(list)
    for qid, iid, label, order in conn.execute(text(
            "SELECT i.question_id, i.item_id, i.item_label, i.sort_order FROM csi_item i"
            " JOIN csi_question q ON q.question_id = i.question_id"
            " WHERE q.survey_id = :sid ORDER BY i.sort_order"), {"sid": survey_id}):
        items[qid].append((iid, label, order))
    for qid, oid, label, nonresponse, order in conn.execute(text(
            "SELECT o.question_id, o.option_id, o.value_label, o.is_nonresponse, o.sort_order"
            " FROM csi_option o JOIN csi_question q ON q.question_id = o.question_id"
            " WHERE q.survey_id = :sid ORDER BY o.sort_order"), {"sid": survey_id}):
        options[qid].append((oid, label, nonresponse, order))

    units: list[Unit] = []
    for qid, qcode, qtext, qtype, topic_id in questions:
        if qtype.startswith("grid"):
            group = f"{slug(qcode, 20).upper()}_{_digest(normalise_text(qtext))}"
            for iid, row_label, _ in items[qid]:
                units.append(Unit(qid, iid, qcode, qtype, topic_id, f"{qtext} :: {row_label}", group,
                                  [(iid, oid, lab, nr, o) for oid, lab, nr, o in options[qid]]))
        elif qtype == "multi":
            units.append(Unit(qid, None, qcode, qtype, topic_id, qtext, None,
                              [(iid, None, lab, 0, o) for iid, lab, o in items[qid]]))
        else:
            units.append(Unit(qid, None, qcode, qtype, topic_id, qtext, None,
                              [(None, oid, lab, nr, o) for oid, lab, nr, o in options[qid]]))
    return units


def _concepts(conn) -> dict[int, Concept]:
    concepts = {cid: Concept(cid, code, qtype, match or normalise_text(name))
                for cid, code, qtype, match, name in conn.execute(text(
                    "SELECT concept_id, concept_code, qtype, match_text, concept_name FROM csi_concept"))}
    for cid, coid, code, label in conn.execute(text(
            "SELECT concept_id, concept_option_id, option_code, option_label FROM csi_concept_option")):
        concepts[cid].options[normalise_text(label)] = coid
        concepts[cid].option_codes.add(code)
    return concepts


def _decide(unit: Unit, concepts: dict[int, Concept], used: set[int]):
    """-> (kind, concept or None, confidence, evidence)"""
    pool = [c for c in concepts.values() if c.qtype == unit.qtype and c.concept_id not in used]
    labels = {normalise_text(ch[2]) for ch in unit.choices}
    for concept in pool:
        if concept.match_text == unit.match_text:
            added = sorted(labels - set(concept.options))
            if not added:
                return "exact", concept, 1.0, "same wording and answers"
            return "changed", concept, 1.0, f"same wording; adds: {', '.join(added)}"[:1000]
    scored = [(difflib.SequenceMatcher(None, unit.match_text, c.match_text).ratio(), c) for c in pool]
    ratio, best = max(scored, key=lambda s: s[0], default=(0.0, None))
    if best is not None and ratio >= SIMILAR_THRESHOLD:
        return "similar", best, round(ratio, 4), f"{ratio:.0%} similar wording to {best.code}"
    return "new", None, 1.0, "new concept"


def _create_concept(conn, unit: Unit, concepts: dict[int, Concept]) -> Concept:
    base = f"{slug(unit.qcode, 20).upper()}_{_digest(unit.qtype + unit.match_text)}"
    taken = {c.code for c in concepts.values()}
    code, n = base, 1
    while code in taken:
        n += 1
        code = f"{base}_{n}"
    conn.execute(text(
        "INSERT INTO csi_concept (concept_code, concept_name, concept_group, topic_id, qtype, match_text)"
        " VALUES (:code, :name, :grp, :topic, :qtype, :match)"),
        {"code": code, "name": unit.wording[:255], "grp": unit.group, "topic": unit.topic_id,
         "qtype": unit.qtype, "match": unit.match_text[:2000]})
    cid = conn.execute(text("SELECT concept_id FROM csi_concept WHERE concept_code = :c"),
                       {"c": code}).scalar()
    concepts[cid] = Concept(cid, code, unit.qtype, unit.match_text)
    return concepts[cid]


def _add_options(conn, concept: Concept, unit: Unit) -> None:
    """Every answer the unit offers becomes (or already is) a concept option."""
    for _, _, label, nonresponse, order in unit.choices:
        key = normalise_text(label)
        if key in concept.options:
            continue
        code, n = slug(label), 1
        while code in concept.option_codes:
            n += 1
            code = f"{slug(label, 55)}_{n}"
        conn.execute(text(
            "INSERT INTO csi_concept_option (concept_id, option_code, option_label, sort_order, is_nonresponse)"
            " VALUES (:cid, :code, :label, :ord, :nr)"),
            {"cid": concept.concept_id, "code": code, "label": str(label)[:500],
             "ord": order or 0, "nr": nonresponse or 0})
        concept.options[key] = conn.execute(text(
            "SELECT concept_option_id FROM csi_concept_option WHERE concept_id = :cid AND option_code = :code"),
            {"cid": concept.concept_id, "code": code}).scalar()
        concept.option_codes.add(code)


def _map_unit(conn, survey_id: int, unit: Unit, concept: Concept, status: str,
              method: str, confidence: float, evidence: str) -> None:
    conn.execute(text(
        "INSERT INTO csi_concept_map (survey_id, map_key, question_id, item_id, concept_id,"
        " status, method, confidence, evidence)"
        " VALUES (:sid, :key, :qid, :item, :cid, :status, :method, :conf, :evidence)"),
        {"sid": survey_id, "key": unit.key, "qid": unit.question_id, "item": unit.item_id,
         "cid": concept.concept_id, "status": status, "method": method,
         "conf": confidence, "evidence": evidence})


def _map_choices(conn, survey_id: int, unit: Unit, concept: Concept,
                 reviewer: Optional[str] = None) -> None:
    """Answer-level rows, written only once the unit is confirmed."""
    rows = [{"sid": survey_id, "key": f"{unit.question_id}:{item or 0}:{option or 0}",
             "qid": unit.question_id, "item": item, "option": option,
             "cid": concept.concept_id, "coid": concept.options[normalise_text(label)],
             "who": reviewer}
            for item, option, label, _, _ in unit.choices]
    if rows:
        conn.execute(text(
            "INSERT INTO csi_concept_map (survey_id, map_key, question_id, item_id, option_id,"
            " concept_id, concept_option_id, status, method, confidence, reviewed_by)"
            " VALUES (:sid, :key, :qid, :item, :option, :cid, :coid, 'confirmed', 'exact_text', 1, :who)"),
            rows)


def harmonise_survey(survey_id: int) -> dict[str, int]:
    """Map every non-technical unit of one wave. Safe to re-run: a unit that
    already has a map row — confirmed, proposed or rejected — is left alone."""
    counts = {"exact": 0, "changed": 0, "similar": 0, "new": 0, "skipped": 0}
    with get_engine("etl").begin() as conn:
        concepts = _concepts(conn)
        done = {k for (k,) in conn.execute(text(
            "SELECT map_key FROM csi_concept_map WHERE survey_id = :sid"), {"sid": survey_id})}
        used = {c for (c,) in conn.execute(text(
            "SELECT DISTINCT concept_id FROM csi_concept_map WHERE survey_id = :sid"), {"sid": survey_id})}
        for unit in _units(conn, survey_id):
            if unit.key in done:
                counts["skipped"] += 1
                continue
            kind, concept, confidence, evidence = _decide(unit, concepts, used)
            if kind == "new":
                concept = _create_concept(conn, unit, concepts)
            if kind in ("exact", "new"):
                _add_options(conn, concept, unit)
                _map_unit(conn, survey_id, unit, concept, "confirmed", "exact_text", confidence, evidence)
                _map_choices(conn, survey_id, unit, concept)
            else:
                method = "exact_text" if kind == "changed" else "similar_text"
                _map_unit(conn, survey_id, unit, concept, "proposed", method, confidence, evidence)
            used.add(concept.concept_id)
            counts[kind] += 1
    return counts
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_harmonise.py -v`
Expected: 12 passed.

- [ ] **Step 5: Checkpoint (no commit)** — `git status --short` adds nothing new beyond Task 1's files.

---

### Task 3: The three decisions and the queue view

**Files:**
- Modify: `app/data/harmonise.py`, `sql/002_views.sql`, `app/data/repository.py`
- Test: `tests/test_harmonise.py`

**Interfaces:**
- Consumes: Task 2's `_units`, `_concepts`, `_create_concept`, `_add_options`, `_map_choices`, `Unit.key`.
- Produces:
  - `harmonise.confirm(survey_id, question_id, item_id, concept_id, reviewer) -> None` — accept a proposal (`concept_id` = the proposed one) or change it (another concept id). Adds the wave's new answers to the concept.
  - `harmonise.keep_separate(survey_id, question_id, item_id, reviewer) -> int` — new concept id.
  - `harmonise.reject(survey_id, question_id, item_id, reviewer) -> None` — the unit is never trended.
  - All three raise `ValueError("… is not awaiting review")` unless the unit's map row is `proposed`.
  - View `v_csi_mapping_queue` (columns: `survey_id, wave_label, survey_title, question_id, item_id, qcode, qtext, qtype, item_label, concept_id, concept_code, concept_name, method, confidence, evidence, created_at`).
  - `repository.mapping_queue() -> DataFrame`, `repository.mapping_summary() -> DataFrame` (wave_label, status, units), `repository.concept_choice(concept_id) -> DataFrame` (option_label, sort_order), `repository.concept_list(qtype) -> DataFrame` (concept_id, concept_code, concept_name).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_harmonise.py`:

```python
import pytest

from app.data import repository


def proposal(engine) -> tuple[int, int, int, int]:
    """A wave whose q4 adds 'Costco' -> (survey_id, question_id, concept_id, first_survey_id)."""
    first = add_wave(engine, "2026-09-21", [RETAILERS])
    harmonise.harmonise_survey(first)
    sid = add_wave(engine, "2026-09-28", [dict(RETAILERS, answers=["Walmart", "Costco"])])
    harmonise.harmonise_survey(sid)
    with engine.connect() as conn:
        qid, cid = conn.execute(sa.text(
            "SELECT question_id, concept_id FROM csi_concept_map WHERE survey_id = :s"), {"s": sid}).one()
    return sid, qid, cid, first


def test_confirm_adds_the_new_answer_and_records_the_reviewer(csi_db):
    sid, qid, cid, _ = proposal(csi_db)
    harmonise.confirm(sid, qid, None, cid, "analyst@coresight.com")
    with csi_db.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT status, reviewed_by FROM csi_concept_map WHERE survey_id = :s"
            " AND concept_option_id IS NULL"), {"s": sid}).one()
    assert tuple(row) == ("confirmed", "analyst@coresight.com")
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept_option WHERE option_code = 'costco'") == 1
    assert count(csi_db, f"SELECT COUNT(*) FROM csi_concept_map WHERE survey_id = {sid}"
                         " AND concept_option_id IS NOT NULL") == 2


def test_confirm_can_point_at_a_different_concept(csi_db):
    sid, qid, cid, first = proposal(csi_db)
    other = add_wave(csi_db, "2026-08-01", [dict(RETAILERS, qcode="q9", qtext="Where did you shop?")])
    harmonise.harmonise_survey(other)
    with csi_db.connect() as conn:
        other_cid = conn.execute(sa.text(
            "SELECT concept_id FROM csi_concept_map WHERE survey_id = :s"
            " AND concept_option_id IS NULL"), {"s": other}).scalar()
    harmonise.confirm(sid, qid, None, other_cid, "analyst@coresight.com")
    assert maps(csi_db, sid)[0][3] == maps(csi_db, other)[0][3] != maps(csi_db, first)[0][3]


def test_keep_separate_creates_a_new_concept(csi_db):
    sid, qid, cid, _ = proposal(csi_db)
    new_cid = harmonise.keep_separate(sid, qid, None, "analyst@coresight.com")
    assert new_cid != cid
    assert maps(csi_db, sid)[0][:3] == ("q4", "confirmed", "manual")


def test_reject_leaves_the_question_untrended(csi_db):
    sid, qid, _, _ = proposal(csi_db)
    harmonise.reject(sid, qid, None, "analyst@coresight.com")
    assert maps(csi_db, sid)[0][1] == "rejected"
    assert count(csi_db, f"SELECT COUNT(*) FROM csi_concept_map WHERE survey_id = {sid}"
                         " AND concept_option_id IS NOT NULL") == 0


def test_a_decision_cannot_be_made_twice(csi_db):
    sid, qid, cid, _ = proposal(csi_db)
    harmonise.confirm(sid, qid, None, cid, "a@coresight.com")
    with pytest.raises(ValueError, match="not awaiting review"):
        harmonise.keep_separate(sid, qid, None, "b@coresight.com")
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept") == 1


def test_queue_lists_only_open_proposals(csi_db):
    sid, qid, cid, _ = proposal(csi_db)
    queue = repository.mapping_queue.__wrapped__()
    assert list(queue.qcode) == ["q4"] and "costco" in queue.evidence.iloc[0]
    harmonise.confirm(sid, qid, None, cid, "a@coresight.com")
    assert repository.mapping_queue.__wrapped__().empty
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_harmonise.py -v`
Expected: the 6 new tests FAIL — `AttributeError: … no attribute 'confirm'` / `'mapping_queue'`.

- [ ] **Step 3: Implement the decisions**

Append to `app/data/harmonise.py`:

```python
def _open_unit(conn, survey_id: int, question_id: int, item_id: Optional[int]) -> Unit:
    unit = next((u for u in _units(conn, survey_id)
                 if u.question_id == question_id and u.item_id == item_id), None)
    status = conn.execute(text(
        "SELECT status FROM csi_concept_map WHERE survey_id = :sid AND map_key = :key"),
        {"sid": survey_id, "key": f"{question_id}:{item_id or 0}:0"}).scalar()
    if unit is None or status != "proposed":
        raise ValueError(f"question {question_id} row {item_id} is not awaiting review")
    return unit


def _settle(conn, survey_id: int, unit: Unit, concept_id: int, reviewer: str,
            method: Optional[str] = None) -> None:
    conn.execute(text(
        "UPDATE csi_concept_map SET concept_id = :cid, status = 'confirmed',"
        " method = COALESCE(:method, method), reviewed_by = :who, reviewed_at = CURRENT_TIMESTAMP"
        " WHERE survey_id = :sid AND map_key = :key"),
        {"cid": concept_id, "method": method, "who": reviewer, "sid": survey_id, "key": unit.key})


def confirm(survey_id: int, question_id: int, item_id: Optional[int],
            concept_id: int, reviewer: str) -> None:
    """Accept the proposal, or map the unit to another concept instead."""
    with get_engine("etl").begin() as conn:
        unit = _open_unit(conn, survey_id, question_id, item_id)
        concept = _concepts(conn)[concept_id]
        _add_options(conn, concept, unit)
        _settle(conn, survey_id, unit, concept_id, reviewer)
        _map_choices(conn, survey_id, unit, concept, reviewer)


def keep_separate(survey_id: int, question_id: int, item_id: Optional[int], reviewer: str) -> int:
    """Not the same question after all: give it its own concept."""
    with get_engine("etl").begin() as conn:
        unit = _open_unit(conn, survey_id, question_id, item_id)
        concepts = _concepts(conn)
        concept = _create_concept(conn, unit, concepts)
        _add_options(conn, concept, unit)
        _settle(conn, survey_id, unit, concept.concept_id, reviewer, method="manual")
        _map_choices(conn, survey_id, unit, concept, reviewer)
        return concept.concept_id


def reject(survey_id: int, question_id: int, item_id: Optional[int], reviewer: str) -> None:
    """Never trend this unit."""
    with get_engine("etl").begin() as conn:
        unit = _open_unit(conn, survey_id, question_id, item_id)
        conn.execute(text(
            "UPDATE csi_concept_map SET status = 'rejected', reviewed_by = :who,"
            " reviewed_at = CURRENT_TIMESTAMP WHERE survey_id = :sid AND map_key = :key"),
            {"who": reviewer, "sid": survey_id, "key": unit.key})
```

- [ ] **Step 4: Add the queue view to the end of `sql/002_views.sql`**

```sql

-- Units the harmoniser could not settle alone, with its evidence.
-- Unit rows are the ones without a concept option; answers are mapped only
-- after confirmation, so every row here is one decision.
CREATE OR REPLACE VIEW v_csi_mapping_queue AS
SELECT m.survey_id, s.wave_label, s.title AS survey_title,
       m.question_id, m.item_id, q.qcode, q.qtext, q.qtype, i.item_label,
       m.concept_id, c.concept_code, c.concept_name,
       m.method, m.confidence, m.evidence, m.created_at
  FROM csi_concept_map m
  JOIN csi_survey   s ON s.survey_id   = m.survey_id
  JOIN csi_question q ON q.question_id = m.question_id
  LEFT JOIN csi_item i ON i.item_id    = m.item_id
  JOIN csi_concept  c ON c.concept_id  = m.concept_id
 WHERE m.status = 'proposed' AND m.concept_option_id IS NULL;
```

- [ ] **Step 5: Add the reads to `app/data/repository.py`** (after `list_surveys`)

```python
@st.cache_data(ttl=60, show_spinner=False)
def mapping_queue() -> pd.DataFrame:
    """Harmoniser proposals waiting for an analyst (short TTL: decisions clear it)."""
    return query_df("SELECT * FROM v_csi_mapping_queue ORDER BY wave_label, qcode, item_id")


@st.cache_data(ttl=60, show_spinner=False)
def mapping_summary() -> pd.DataFrame:
    return query_df(
        """
        SELECT s.wave_label, m.status, COUNT(*) AS units
          FROM csi_concept_map m JOIN csi_survey s ON s.survey_id = m.survey_id
         WHERE m.concept_option_id IS NULL
         GROUP BY s.wave_label, m.status
         ORDER BY s.wave_label, m.status
        """
    )


def concept_choice(concept_id: int) -> pd.DataFrame:
    return query_df(
        "SELECT option_label, sort_order FROM csi_concept_option"
        " WHERE concept_id = :cid ORDER BY sort_order", {"cid": concept_id})


def concept_list(qtype: str) -> pd.DataFrame:
    return query_df(
        "SELECT concept_id, concept_code, concept_name FROM csi_concept"
        " WHERE qtype = :qtype ORDER BY concept_code", {"qtype": qtype})
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_harmonise.py -v`
Expected: 18 passed.

- [ ] **Step 7: Checkpoint (no commit)** — adds `sql/002_views.sql`, `app/data/repository.py`.

---

### Task 4: Harmonise on every load, and back-fill existing waves

**Files:**
- Modify: `etl/run_pipeline.py`, `app/data/harmonise.py` (CLI)
- Test: `tests/test_harmonise.py`

**Interfaces:**
- Consumes: `harmonise_survey` (Task 2).
- Produces: `harmonise.harmonise_all() -> dict[str, dict[str, int]]` (wave_label → counts, oldest wave first so the earliest wording seeds each concept).
- Produces: `python -m app.data.harmonise [--wave LABEL | --all]`.
- `ingest_excel` and `ingest_api` call `harmonise_survey(survey_id)` after the data and cross-tabs load and log the counts.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_harmonise.py`:

```python
import os

from etl import run_pipeline


def test_harmonise_all_runs_oldest_wave_first(csi_db):
    late = add_wave(csi_db, "2026-09-28", [RETAILERS])
    early = add_wave(csi_db, "2026-09-21", [dict(RETAILERS, answers=["Walmart"])])
    with csi_db.begin() as conn:
        conn.execute(sa.text("UPDATE csi_survey SET wave_date = wave_label"))
    result = harmonise.harmonise_all()
    assert list(result) == ["2026-09-21", "2026-09-28"]
    assert result["2026-09-28"]["changed"] == 1          # it adds Target + None of these
    assert maps(csi_db, early)[0][1] == "confirmed" and maps(csi_db, late)[0][1] == "proposed"


@pytest.mark.skipif(not os.getenv("CSI_TEST_RAW"), reason="set CSI_TEST_RAW")
def test_loading_a_wave_harmonises_it(csi_db):
    run_pipeline.ingest_excel(os.environ["CSI_TEST_RAW"], None, "2026-09-21")
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept") == 101
    assert count(csi_db, "SELECT COUNT(*) FROM csi_concept_map"
                         " WHERE status = 'proposed'") == 0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `CSI_TEST_RAW=~/Downloads/"Raw Data 09_21_26.xlsx" .venv/bin/python -m pytest tests/test_harmonise.py -k "harmonise_all or loading_a_wave" -v`
Expected: `test_harmonise_all_runs_oldest_wave_first` FAILS (`no attribute 'harmonise_all'`); `test_loading_a_wave_harmonises_it` FAILS (`assert 0 == 101`).

- [ ] **Step 3: Implement**

Append to `app/data/harmonise.py`:

```python
def harmonise_all() -> dict[str, dict[str, int]]:
    """Every wave, oldest first — the earliest wording seeds each concept."""
    with get_engine("etl").connect() as conn:
        waves = conn.execute(text(
            "SELECT survey_id, wave_label FROM csi_survey"
            " ORDER BY wave_date, wave_label, survey_id")).all()
    return {label: harmonise_survey(sid) for sid, label in waves}


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Link waves' questions to concepts")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--wave", help="one wave label, e.g. 2026-09-28")
    group.add_argument("--all", action="store_true", help="every wave, oldest first")
    args = ap.parse_args()
    if args.all:
        results = harmonise_all()
    else:
        with get_engine("etl").connect() as conn:
            sid = conn.execute(text("SELECT survey_id FROM csi_survey WHERE wave_label = :w"),
                               {"w": args.wave}).scalar()
        if sid is None:
            print(f"No wave labelled {args.wave}")
            return 1
        results = {args.wave: harmonise_survey(sid)}
    for label, counts in results.items():
        print(label, counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

In `etl/run_pipeline.py`, add `from app.data import harmonise` to the imports, then at the end of `ingest_excel` (after the `if crosstab_path: ingest_crosstabs(...)` block) add:

```python
    log.info("Harmonised: %s", harmonise.harmonise_survey(survey_id))
```

and at the end of `ingest_api`, after its last load step, add the same line.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `CSI_TEST_RAW=~/Downloads/"Raw Data 09_21_26.xlsx" .venv/bin/python -m pytest tests/test_harmonise.py -v`
Expected: 20 passed.

- [ ] **Step 5: Full suite**

Run: `APP_ENV=LOCAL LOCAL_SQLITE_PATH=data/csi_local.db CSI_TEST_RAW=~/Downloads/"Raw Data 09_21_26.xlsx" CSI_TEST_XTAB=~/Downloads/"Cross Tabs 09_21_26.xlsx" .venv/bin/python -m pytest -q`
Expected: 85 passed (65 before this phase + 20).

- [ ] **Step 6: Checkpoint (no commit)** — adds `etl/run_pipeline.py`.

---

### Task 5: The Mappings page

**Files:**
- Create: `app/pages/7_Mappings.py`
- Modify: `app/components/header.py` (`NAV`), `app/main.py` (`PAGES`)

**Interfaces:**
- Consumes: `repository.mapping_queue`, `mapping_summary`, `concept_choice`, `concept_list` (Task 3); `harmonise.confirm`, `keep_separate`, `reject` (Task 3); `auth.require_auth` (returns the user, or the local-testing user).

- [ ] **Step 1: Register the page**

In `app/components/header.py` `NAV`, after the `("Trends", "trends", "/trends"),` line add:

```python
    ("Mappings", "mappings", "/mappings"),
```

In `app/main.py` `PAGES`, after the Trends entry add:

```python
    ("Mappings",         "pages/7_Mappings.py",          "mappings"),
```

- [ ] **Step 2: Create `app/pages/7_Mappings.py`**

```python
"""Mappings — where an analyst settles what the harmoniser could not.

A question only trends across waves once it is confirmed against a concept.
Exact matches confirm themselves; this page holds the rest: the same wording
with new answers, or similar wording. Accept, point it at another concept,
keep it separate, or reject it.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components.footer import render_footer
from app.components.header import page_title, render_header
from app.core import auth
from app.core.config import config
from app.core.database import healthcheck
from app.data import harmonise
from app.data import repository as repo

ok, status = healthcheck("app")
render_header("mappings", status if ok else "database unavailable",
              config.environment.value.upper())
user = auth.require_auth("mappings")
reviewer = user.email if user else "local-dev"
page_title("Mappings", "Confirm which questions are the same across waves — nothing trends until it is.")

if not ok:
    st.error("The portal cannot reach the database.")
    st.stop()


def decide(action, *args) -> None:
    try:
        action(*args)
    except ValueError as exc:            # already settled, e.g. by a colleague
        st.warning(str(exc))
    repo.mapping_queue.clear()
    repo.mapping_summary.clear()
    st.rerun()


summary = repo.mapping_summary()
if not summary.empty:
    st.dataframe(summary.pivot_table(index="wave_label", columns="status", values="units",
                                     aggfunc="sum", fill_value=0), width="stretch")

queue = repo.mapping_queue()
if queue.empty:
    st.success("Nothing waiting — every loaded question is settled.")
    render_footer()
    st.stop()

st.markdown(f"#### {len(queue)} waiting for review")
for row in queue.itertuples():
    item = None if pd.isna(row.item_id) else int(row.item_id)
    label = f"{row.wave_label} · {row.qcode}" + (f" · {row.item_label}" if item else "")
    with st.expander(f"{label} — {row.evidence}", expanded=len(queue) <= 5):
        left, right = st.columns(2)
        with left:
            st.caption("This wave asked")
            st.markdown(f"**{row.qtext}**" + (f"  \nRow: *{row.item_label}*" if item else ""))
        with right:
            st.caption(f"Proposed concept · {row.concept_code} · {row.method}"
                       + (f" · {row.confidence:.0%}" if pd.notna(row.confidence) else ""))
            st.markdown(f"**{row.concept_name}**")
            answers = repo.concept_choice(int(row.concept_id))
            if not answers.empty:
                st.caption("Its answers so far: " + ", ".join(answers.option_label))

        key = f"{row.survey_id}_{row.question_id}_{item}"
        b1, b2, b3 = st.columns(3)
        if b1.button("Accept", key=f"acc_{key}", type="primary"):
            decide(harmonise.confirm, int(row.survey_id), int(row.question_id), item,
                   int(row.concept_id), reviewer)
        if b2.button("Keep separate", key=f"sep_{key}"):
            decide(harmonise.keep_separate, int(row.survey_id), int(row.question_id), item, reviewer)
        if b3.button("Reject", key=f"rej_{key}"):
            decide(harmonise.reject, int(row.survey_id), int(row.question_id), item, reviewer)

        others = repo.concept_list(row.qtype)
        others = others[others.concept_id != row.concept_id]
        if not others.empty:
            names = dict(zip(others.concept_id, others.concept_code + " — " + others.concept_name.str[:80]))
            pick = st.selectbox("…or map it to another concept", list(names),
                                format_func=names.get, key=f"pick_{key}", index=None)
            if pick is not None and st.button("Map to this concept", key=f"map_{key}"):
                decide(harmonise.confirm, int(row.survey_id), int(row.question_id), item,
                       int(pick), reviewer)

render_footer()
```

- [ ] **Step 3: Verify in the browser against the local copy**

Rebuild the local copy (it harmonises on load now) and start the local portal:
```bash
export APP_ENV=LOCAL LOCAL_SQLITE_PATH=data/csi_local.db DEBUG=true
rm -f data/csi_local.db && .venv/bin/python scripts/init_db.py
.venv/bin/python -m etl.run_pipeline --source excel --raw ~/Downloads/"Raw Data 09_21_26.xlsx" --crosstab ~/Downloads/"Cross Tabs 09_21_26.xlsx" --wave 2026-09-21
.venv/bin/python -m etl.run_pipeline --source excel --raw ~/Downloads/"raw data 09-28-2026 2.xlsx" --crosstab ~/Downloads/"Shopping and Spending - inc Beauty + Holiday + Inflation + Cross tab 09-28- 2026  2.xlsx" --wave 2026-09-28
```
Expected log lines: `Harmonised: {'exact': 0, 'changed': 0, 'similar': 0, 'new': 101, 'skipped': 0}` then `Harmonised: {'exact': 33, 'changed': 2, 'similar': 0, 'new': 89, 'skipped': 0}`.

Start `streamlit run app/main.py --server.port 8503` with the same environment, open `http://localhost:8503/mappings`. Expected: summary shows 2026-09-21 confirmed 101, 2026-09-28 confirmed 122 / proposed 2; two expanders, `D28` and `D32`, each "same wording; adds: muse". Click **Accept** on `D28`. Expected: the page reruns showing 1 waiting; summary 2026-09-28 confirmed 123 / proposed 1.

- [ ] **Step 4: Full suite** — as Task 4 Step 5. Expected: 85 passed.

- [ ] **Step 5: Checkpoint (no commit)** — adds `app/pages/7_Mappings.py`, `app/components/header.py`, `app/main.py`.

---

### Task 6: Apply to `dwh_stg`

**Files:** none changed — an operational run (VPN on).

- [ ] **Step 1: Pre-flight** — `nc -z -G 5 csr-mysql8-flex-stg.mysql.database.azure.com 3306` → succeeded; `.venv/bin/python scripts/test_connection.py` → `✓ connected` as `dwh_app_access` on `dwh_stg`. Unset `LOCAL_SQLITE_PATH` in the shell.

- [ ] **Step 2: Schema** — `.venv/bin/python scripts/init_db.py --dry-run`
Expected: `ALTER TABLE csi_concept ADD COLUMN match_text VARCHAR(2000) NULL`, the backfill `UPDATE`, the three `-- apply` lines. Then run `.venv/bin/python scripts/init_db.py`. Expected: `Done.`

- [ ] **Step 3: Back-fill both waves** — `.venv/bin/python -m app.data.harmonise --all`
Expected:
```
2026-09-21 {'exact': 0, 'changed': 0, 'similar': 0, 'new': 101, 'skipped': 0}
2026-09-28 {'exact': 33, 'changed': 2, 'similar': 0, 'new': 89, 'skipped': 0}
```
Re-run it. Expected: every unit `skipped` (101 and 124), nothing else.

- [ ] **Step 4: Settle the queue in the portal** — restart the portal on port 8502 (`dwh_stg`), open `/mappings`; Expected: `D28` and `D32`, both "adds: muse". **Accept** both. Expected: "Nothing waiting".

- [ ] **Step 5: Prove the result** — run:
```bash
.venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, ".")
from app.core.database import get_engine
from sqlalchemy import text
with get_engine("etl").connect() as c:
    print("concepts", c.execute(text("SELECT COUNT(*) FROM csi_concept")).scalar())
    print("spanning both waves", c.execute(text(
        "SELECT COUNT(*) FROM (SELECT concept_id FROM csi_concept_map WHERE status='confirmed'"
        " AND concept_option_id IS NULL GROUP BY concept_id HAVING COUNT(DISTINCT survey_id) = 2) t")).scalar())
    print("open", c.execute(text("SELECT COUNT(*) FROM v_csi_mapping_queue")).scalar())
EOF
.venv/bin/python scripts/reconcile.py; echo "exit=$?"
```
Expected: `concepts 190`, `spanning both waves 35`, `open 0`; reconcile 667/667 and 788/788, `exit=0`.

---

### Task 7: Documentation

**Files:** `docs/superpowers/specs/2026-09-29-survey-platform-design.md`, `README.md`, `docs/06-running-locally.md`

- [ ] **Step 1: Spec** — in §5.2 add: *"`csi_concept.match_text` (≤ 2,000 chars) holds the normalised wording matched on; `concept_name` is the display label, truncated to 255. A unit with no exact or similar candidate becomes a new, confirmed concept — creating a concept claims no trend. Answers a wave drops do not block an exact match; answers it adds do."* Update the Status line: *"Phase 2 (harmoniser + Mappings page) live in dwh_stg."*

- [ ] **Step 2: README** — Status table: add row `| Harmonisation | every wave linked to concepts on load; proposals settled on the Mappings page (/mappings) |`; in Layout add `app/data/harmonise.py` and `app/pages/7_Mappings.py`.

- [ ] **Step 3: Running locally** — in `docs/06-running-locally.md` add: back-fill command `python -m app.data.harmonise --all`, and that loads now harmonise automatically.

- [ ] **Step 4: Final checkpoint (no commit)** — `git status --short` must list, from this phase: `app/data/harmonise.py`, `app/pages/7_Mappings.py`, `tests/conftest.py`, `tests/test_harmonise.py` (new); `sql/001_schema.sql`, `sql/002_views.sql`, `app/core/schema_upgrade.py`, `app/data/repository.py`, `etl/run_pipeline.py`, `app/components/header.py`, `app/main.py`, the three docs (modified). Hand the list to the user.
