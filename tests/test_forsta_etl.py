"""The Forsta ETL build (Oct 2026): schema, API adapter, pipeline, search.

See docs/superpowers/plans/2026-10-07-forsta-etl-build.md and the design in
docs/superpowers/specs/2026-10-07-cip-forsta-etl-and-ui-design.md.
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import schema_upgrade


def columns(engine, table):
    return {c["name"] for c in sa.inspect(engine).get_columns(table)}


def indexes(engine, table):
    return {i["name"] for i in sa.inspect(engine).get_indexes(table)}


def test_the_schema_carries_the_forsta_register_search_and_new_columns(csi_db):
    tables = set(sa.inspect(csi_db).get_table_names())
    assert {"cip_forsta_survey", "cip_search"} <= tables
    assert {"forsta_path", "state", "hibernated", "study_type", "launched_at", "closed_at", "qualified_n",
            "total_n", "load_state", "survey_id", "last_error"} <= columns(csi_db, "cip_forsta_survey")
    assert {"sample_source", "total_n", "tags"} <= columns(csi_db, "cip_survey")
    assert "is_virtual" in columns(csi_db, "cip_question")
    assert {"left_label", "right_label"} <= columns(csi_db, "cip_item")
    assert "ix_survey_pick" in indexes(csi_db, "cip_survey")
    assert "ix_answer_field" not in indexes(csi_db, "cip_answer")          # the covering index serves it


def test_an_older_database_is_upgraded_to_the_same_shape(tmp_path):
    old = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}", future=True)
    schema_upgrade.install(old)
    with old.begin() as conn:                     # as dwh_stg was before this build
        conn.execute(sa.text("DROP TABLE cip_forsta_survey"))
        conn.execute(sa.text("DROP TABLE cip_search"))
        conn.execute(sa.text("CREATE INDEX ix_answer_field ON cip_answer (survey_id, field_id, value_code)"))
    schema_upgrade.install(old)
    assert {"cip_forsta_survey", "cip_search"} <= set(sa.inspect(old).get_table_names())
    assert "ix_answer_field" not in indexes(old, "cip_answer")
    assert not [x for x in schema_upgrade.plan(old) if x.split()[0].upper() in ('ALTER', 'CREATE', 'DROP')]


# ── the API adapter, on the shapes the real datamaps use ───────────────────
from etl import forsta_api

V12 = [{"label": "c1", "value": 1, "title": ""}, {"label": "c2", "value": 2, "title": "&nbsp;"}]
REAL_SHAPES = {"questions": [
    {"qlabel": "vos", "qtitle": "Operating System", "type": "single", "grouping": "cols", "flags": ["v", "t"],
     "values": [{"value": 1, "title": "Windows"}, {"value": 15, "title": "Other"}],
     "variables": [{"label": "vos", "qlabel": "vos", "type": "single", "row": None, "rowTitle": None},
                   {"label": "vosr15oe", "qlabel": "vos", "type": "text", "row": "r15", "rowTitle": "Other"}]},
    {"qlabel": "q1", "qtitle": "Which, if any, of these have you done?", "type": "multiple", "grouping": "cols",
     "variables": [{"label": "q1r1", "type": "multiple", "rowTitle": "Met up with friends", "value": 1},
                   {"label": "q1r2", "type": "multiple", "rowTitle": "Other (please specify)", "value": 1},
                   {"label": "q1r2oe", "type": "text", "rowTitle": "Other (please specify)"}]},
    {"qlabel": "D5", "qtitle": "What was your total household income last year?", "type": "single",
     "grouping": "cols",
     "variables": [{"label": "D5", "type": "single", "values": [{"value": 1, "title": "under $25,000"},
                                                                 {"value": 2, "title": "$25,000 - $49,999"}]}]},
    {"qlabel": "HX6", "qtitle": "Please choose the statement from each row.", "type": "single", "grouping": "rows",
     "values": V12,
     "variables": [{"label": "HX6r1", "type": "single", "row": "r1", "rowTitle": "I start holiday shopping early", "values": V12},
                   {"label": "HX6r2", "type": "single", "row": "r2", "rowTitle": "I set a budget first", "values": V12}]},
    {"qlabel": "HX6_norm", "qtitle": "Please choose the statement from each row. - NORMALIZED", "type": "single",
     "grouping": "rows", "values": V12,
     "variables": [{"label": "HX6_normr1_l", "type": "single", "rowTitle": "I start holiday shopping early", "values": V12},
                   {"label": "HX6_normr1_r", "type": "single", "rowTitle": "I leave holiday shopping late", "values": V12},
                   {"label": "HX6_normr2_l", "type": "single", "rowTitle": "I set a budget first", "values": V12},
                   {"label": "HX6_normr2_r", "type": "single", "rowTitle": "I just spend", "values": V12}]},
    {"qlabel": "qtime", "qtitle": "Total Interview Time", "type": "float", "flags": ["t"],
     "variables": [{"label": "qtime", "type": "float"}]},
    {"qlabel": "q9", "qtitle": "Anything else?", "type": "text", "variables": [{"label": "q9", "type": "text"}]},
]}


def by_code(questions):
    return {q.qcode: q for q in questions}


def test_answer_labels_are_read_from_the_variables_when_the_question_has_none():
    q = by_code(forsta_api.questions_from_datamap(REAL_SHAPES))["D5"]
    assert q.qtype == "single" and q.options == [(1, "under $25,000"), (2, "$25,000 - $49,999")]


def test_other_specify_text_is_its_own_text_field_not_a_row():
    qs = by_code(forsta_api.questions_from_datamap(REAL_SHAPES))
    assert qs["vos"].qtype == "single" and not qs["vos"].rows
    assert [c for c, _ in qs["q1"].rows] == ["q1r1", "q1r2"]
    assert qs["vosr15oe"].qtype == "text" and qs["q1r2oe"].qtype == "text"


def test_flags_mark_technical_and_virtual_questions():
    qs = by_code(forsta_api.questions_from_datamap(REAL_SHAPES))
    assert set(qs["vos"].flags) == {"v", "t"} and qs["qtime"].flags == ("t",) and qs["q1"].flags == ()
    assert "v" in qs["HX6_norm"].flags                          # Forsta's normalised copy of HX6: derived


def test_a_bipolar_grid_takes_its_statements_as_its_answer_meaning():
    hx6 = by_code(forsta_api.questions_from_datamap(REAL_SHAPES))["HX6"]
    assert hx6.qtype == "grid_single"
    assert hx6.bipolar == {"HX6r1": ("I start holiday shopping early", "I leave holiday shopping late"),
                           "HX6r2": ("I set a budget first", "I just spend")}
    assert hx6.options == [(1, "Left statement"), (2, "Right statement")]


# ── the pipeline ───────────────────────────────────────────────────────────
import hashlib

import pytest

from etl import forsta_etl


def record(n, status="3", **answers):
    base = {"record": str(n), "uuid": f"u{n}", "status": status, "date": f"09/2{n % 3 + 1}/2026 1{n % 10}:00",
            "qtime": f"{60 + n}.5", "RID": f"panel-{n}", "userAgent": "Mozilla/5.0", "url": "https://x/s", "session": f"s{n}",
            "vos": "1", "q1r1": "1", "q1r2": "0", "D5": "2", "HX6r1": "1", "HX6r2": "2",
            "HX6_normr1_l": "2", "HX6_normr1_r": "1", "HX6_normr2_l": "1", "HX6_normr2_r": "2", "q9": f"note {n}"}
    base.update(answers)
    return base


SURVEYS = [
    {"path": "selfserve/58f/260907", "title": "Shopping and Spending - inc Beauty", "state": "closed", "hibernated": False,
     "tags": ["Coresight Research", "Weekly consumer tracker"], "createdOn": "2026-09-22T15:31:03Z",
     "dateLaunched": "2026-09-28T12:30:00Z", "closedDate": "2026-09-29T01:00:00Z", "qualified": 4, "total": 5,
     "sampleSources": ["114"]},
    {"path": "selfserve/58f/260905", "title": "Holiday Shopping 2026", "state": "closed", "hibernated": False,
     "tags": ["Coresight Research", "holiday", "annual tracker"], "createdOn": "2026-09-10T20:48:13Z",
     "dateLaunched": "2026-09-14T12:00:00Z", "closedDate": "2026-09-16T12:00:00Z", "qualified": 2042, "total": 2500},
    {"path": "selfserve/58f/260602", "title": "Shopping and Spending - inc Ecommerce", "state": "closed", "hibernated": True,
     "tags": ["Weekly consumer tracker"], "createdOn": "2026-06-10T18:28:23Z", "qualified": 402, "total": 500},
    {"path": "selfserve/58f/261000", "title": "Shopping and Spending - inc DIY", "state": "testing", "hibernated": False,
     "tags": ["Weekly consumer tracker"], "createdOn": "2026-10-06T14:39:18Z", "qualified": 111, "total": 120},
]


class FakeForsta:
    host = "se1.decipherinc.com"

    def __init__(self, data=None, broken=()):
        self.data = data or {"selfserve/58f/260907": [record(n) for n in range(1, 5)] + [record(5, status="1")]}
        self.broken = set(broken)

    def whoami(self):
        return {"user": "fake"}

    def surveys(self):
        return SURVEYS

    def survey_datamap(self, path):
        return REAL_SHAPES

    def survey_data(self, path, **params):
        if path in self.broken:
            raise RuntimeError("Forsta 500")
        return self.data.get(path, [])


def register(engine):
    with engine.connect() as conn:
        return {r.forsta_path: (r.load_state, r.study_type) for r in conn.execute(sa.text(
            "SELECT forsta_path, load_state, study_type FROM cip_forsta_survey"))}


def test_discovery_registers_every_survey_with_what_to_do_about_it(csi_db):
    assert forsta_etl.discover(FakeForsta()) == {"due": 2, "hibernated": 1, "testing": 1}
    assert register(csi_db) == {"selfserve/58f/260907": ("due", "tracker"), "selfserve/58f/260905": ("due", "annual"),
                                "selfserve/58f/260602": ("hibernated", "tracker"), "selfserve/58f/261000": ("testing", "tracker")}
    forsta_etl.discover(FakeForsta())                                        # idempotent
    assert len(register(csi_db)) == 4


def loaded(engine, sql, **params):
    with engine.connect() as conn:
        return conn.execute(sa.text(sql), params).all()


def test_a_wave_loads_codes_directly_and_keeps_no_personal_data(csi_db):
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    survey = loaded(csi_db, "SELECT wave_label, platform, source_ref, study_type, survey_family, load_status, sample_source,"
                            " total_n FROM cip_survey WHERE survey_id = :s", s=sid)[0]
    assert tuple(survey) == ("2026-09-21", "forsta", "selfserve/58f/260907", "tracker", "CSI-US", "verified", "114", 5)
    assert loaded(csi_db, "SELECT COUNT(*), SUM(is_qualified) FROM cip_respondent WHERE survey_id = :s", s=sid)[0] == (5, 4)
    keys = {r[0] for r in loaded(csi_db, "SELECT respondent_key FROM cip_respondent WHERE survey_id = :s", s=sid)}
    assert hashlib.sha256(b"panel-1").hexdigest() in keys
    assert not loaded(csi_db, "SELECT 1 FROM cip_respondent WHERE sample_rid IS NOT NULL OR browser = 'Mozilla/5.0'")
    answer = lambda field: loaded(csi_db, "SELECT a.value_code, a.value_label, a.value_number, a.value_text FROM cip_answer a"
                                          " JOIN cip_field f ON f.field_id = a.field_id JOIN cip_respondent r"
                                          " ON r.respondent_id = a.respondent_id WHERE a.survey_id = :s AND f.field_name = :f"
                                          " AND r.forsta_uuid = 'u1'", s=sid, f=field)[0]
    assert answer("D5")[:2] == (2, "$25,000 - $49,999")
    assert answer("q1r2")[:2] == (0, "Other (please specify)")
    assert answer("HX6r2")[:2] == (2, "Right statement")
    assert answer("qtime")[0] is None and float(answer("qtime")[2]) == 61.5
    assert answer("q9")[0] is None and answer("q9")[3] == "note 1"


def test_question_flags_and_bipolar_statements_are_stored(csi_db):
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    flags = dict((q, (t, v)) for q, t, v in loaded(csi_db, "SELECT qcode, is_technical, is_virtual FROM cip_question"
                                                           " WHERE survey_id = :s", s=sid))
    assert flags["vos"] == (1, 1) and flags["qtime"] == (1, 0) and flags["HX6_norm"][1] == 1 and flags["q1"] == (0, 0)
    assert loaded(csi_db, "SELECT i.item_code, i.left_label, i.right_label FROM cip_item i JOIN cip_question q"
                          " ON q.question_id = i.question_id WHERE q.survey_id = :s AND q.qcode = 'HX6' ORDER BY i.item_code", s=sid) == \
        [("HX6r1", "I start holiday shopping early", "I leave holiday shopping late"), ("HX6r2", "I set a budget first", "I just spend")]


def test_reloading_a_wave_replaces_it(csi_db):
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    count = lambda: loaded(csi_db, "SELECT COUNT(*) FROM cip_answer WHERE survey_id = :s", s=sid)[0][0]
    before = count()
    assert forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907") == sid and count() == before


def test_a_loaded_wave_is_searchable_cubed_and_registered(csi_db):
    forsta_etl.discover(FakeForsta())
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    assert register(csi_db)["selfserve/58f/260907"][0] == "loaded"
    assert loaded(csi_db, "SELECT COUNT(*) FROM cip_agg_cell WHERE survey_id = :s", s=sid)[0][0] > 0
    assert loaded(csi_db, "SELECT COUNT(*) FROM cip_search WHERE survey_id = :s AND kind = 'question'", s=sid)[0][0] > 0


def test_the_due_run_loads_what_is_due_and_carries_on_past_a_failure(csi_db):
    forsta_etl.discover(FakeForsta())
    result = forsta_etl.run_due(FakeForsta(broken={"selfserve/58f/260905"}))
    assert result == {"loaded": ["selfserve/58f/260907"], "failed": ["selfserve/58f/260905"]}
    assert register(csi_db)["selfserve/58f/260905"][0] == "failed"
    assert "Forsta 500" in loaded(csi_db, "SELECT last_error FROM cip_forsta_survey WHERE forsta_path = 'selfserve/58f/260905'")[0][0]


def test_reconcile_compares_every_stored_answer_with_the_api(csi_db, monkeypatch):
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    checked, problems = forsta_etl.reconcile_survey(sid, FakeForsta())
    assert checked > 50 and problems == []
    with csi_db.begin() as conn:
        conn.execute(sa.text("UPDATE cip_answer SET value_code = 1 WHERE survey_id = :s AND value_code = 2"), {"s": sid})
    assert forsta_etl.reconcile_survey(sid, FakeForsta())[1]


def test_the_weekly_run_discovers_loads_and_reports_by_exit_code(csi_db):
    import importlib

    from etl.forsta_client import ForstaAuthError
    weekly = importlib.import_module("scripts.weekly_forsta")
    every_wave = {"selfserve/58f/260907": [record(n) for n in range(1, 5)],
                  "selfserve/58f/260905": [record(n) for n in range(6, 9)]}
    assert weekly.run(FakeForsta(data=every_wave)) == 0
    assert {p: s for p, (s, _) in register(csi_db).items() if s == "loaded"} == dict.fromkeys(every_wave, "loaded")
    assert weekly.run(FakeForsta(data=every_wave)) == 0                      # nothing left to do

    class Rejected(FakeForsta):
        def whoami(self):
            raise ForstaAuthError("401 API user account is not valid")
    assert weekly.run(Rejected()) == 2


def test_the_weekly_run_fails_when_a_wave_fails(csi_db):
    import importlib
    weekly = importlib.import_module("scripts.weekly_forsta")
    assert weekly.run(FakeForsta(broken={"selfserve/58f/260905"})) == 1


def test_a_wave_that_does_not_match_its_payload_is_failed_and_hidden(csi_db, monkeypatch):
    from app.data import repository
    real = forsta_etl._answer
    monkeypatch.setattr(forsta_etl, "_answer", lambda field, value: None if value == "note 3" else real(field, value))
    with pytest.raises(RuntimeError, match="does not match"):
        forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    assert loaded(csi_db, "SELECT load_status FROM cip_survey WHERE source_ref = 'selfserve/58f/260907'")[0][0] == "failed"
    assert "2026-09-21" not in set(getattr(repository.list_surveys, "__wrapped__", repository.list_surveys)().wave_label)


# ── the report UI: search and auto-charting ────────────────────────────────
from app.components import charts
from app.data import repository


def unwrapped(fn):
    return getattr(fn, "__wrapped__", fn)


def test_search_finds_waves_and_questions_by_their_words(csi_db):
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    hits = unwrapped(repository.search)("household income")
    assert ("question", sid) in set(zip(hits.kind, hits.survey_id))
    assert "What was your total household income last year?" in set(hits.title)
    assert "survey" in set(unwrapped(repository.search)("Beauty").kind)
    assert unwrapped(repository.search)("x").empty                         # too short to search


def test_search_hides_waves_that_are_not_verified(csi_db):
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    with csi_db.begin() as conn:
        conn.execute(sa.text("UPDATE cip_survey SET load_status = 'failed' WHERE survey_id = :s"), {"s": sid})
    assert not {"survey", "question"} & set(unwrapped(repository.search)("household income").kind)


def test_the_wave_report_reads_every_chartable_question_once(csi_db):
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    cells, numbers, texts = unwrapped(repository.wave_report)(sid)
    by_q = dict(loaded(csi_db, "SELECT qcode, question_id FROM cip_question WHERE survey_id = :s", s=sid))
    d5 = cells[cells.question_id == by_q["D5"]]
    assert dict(zip(d5.value_label, d5.n)) == {"$25,000 - $49,999": 4} and set(d5.base_n) == {4}   # qualified only
    hx6 = cells[cells.question_id == by_q["HX6"]]
    assert set(zip(hx6.left_label, hx6.right_label)) == {("I start holiday shopping early", "I leave holiday shopping late"),
                                                         ("I set a budget first", "I just spend")}
    assert by_q["vos"] not in set(cells.question_id) and by_q["HX6_norm"] not in set(cells.question_id)
    assert sorted(numbers.value) == []                                      # qtime is technical
    assert sorted(texts[texts.question_id == by_q["q9"]].value) == ["note 1", "note 2", "note 3", "note 4"]


def test_the_catalog_leaves_out_virtual_questions(csi_db):
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    assert "HX6_norm" not in set(unwrapped(repository.question_catalog)(sid).qcode)


@pytest.mark.parametrize("shape, kind", [
    (("numeric", False, 0, 1, False), "distribution"),
    (("text", False, 0, 1, False), "verbatims"),
    (("multi", True, 0, 12, False), "ranked_bar"),
    (("single", False, 4, 1, False), "donut"),
    (("single", False, 9, 1, False), "bar"),
    (("grid_single", False, 2, 5, True), "butterfly"),
    (("grid_single", False, 5, 6, False), "diverging_stack"),
    (("grid_single", False, 11, 6, False), "heatmap"),
    (("grid_single", False, 5, 1, False), "donut"),             # a one-row grid is a single choice
])
def test_each_question_shape_gets_its_chart(shape, kind):
    assert charts.chart_kind(*shape) == kind


def test_the_new_charts_draw():
    import pandas as pd
    grid = pd.DataFrame({"item_label": ["Early", "Early", "Budget", "Budget"], "left_label": ["Early", "Early", "Budget", "Budget"],
                         "right_label": ["Late", "Late", "Spend", "Spend"], "option_order": [1, 2, 1, 2], "pct": [.6, .4, .3, .7]})
    fig = charts.butterfly(grid)
    assert len(fig.data) == 2 and min(fig.data[0].x) < 0 < max(fig.data[1].x)
    assert len(charts.distribution(pd.Series([1, 2, 2, 3, 40])).data) == 1


def test_virtual_questions_are_not_harmonised(csi_db):
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    mapped = {q for (q,) in loaded(csi_db, "SELECT DISTINCT q.qcode FROM cip_concept_map m JOIN cip_question q"
                                           " ON q.question_id = m.question_id WHERE m.survey_id = :s", s=sid)}
    assert "HX6" in mapped and "HX6_norm" not in mapped


# ── review fixes ───────────────────────────────────────────────────────────
def test_a_reload_with_fewer_records_drops_the_missing_respondents(csi_db):
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    fewer = FakeForsta(data={"selfserve/58f/260907": [record(n) for n in range(1, 4)]})
    assert forsta_etl.load_survey(fewer, "selfserve/58f/260907") == sid
    assert loaded(csi_db, "SELECT COUNT(*) FROM cip_respondent WHERE survey_id = :s", s=sid)[0][0] == 3


def test_a_wave_keeps_its_survey_when_its_first_date_moves(csi_db):
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    later = FakeForsta(data={"selfserve/58f/260907": [record(n, date="10/06/2026 10:00") for n in range(1, 4)]})
    assert forsta_etl.load_survey(later, "selfserve/58f/260907") == sid
    assert loaded(csi_db, "SELECT COUNT(*) FROM cip_survey WHERE source_ref = 'selfserve/58f/260907'")[0][0] == 1


def test_personal_fields_are_never_stored_even_when_the_datamap_lists_them(csi_db):
    with_pii = {"questions": REAL_SHAPES["questions"] + [
        {"qlabel": "RID", "qtitle": "RID", "type": "text", "variables": [{"label": "RID", "type": "text"}]},
        {"qlabel": "url", "qtitle": "url", "type": "text", "variables": [{"label": "url", "type": "text"}]}]}

    class WithPii(FakeForsta):
        def survey_datamap(self, path):
            return with_pii
    sid = forsta_etl.load_survey(WithPii(), "selfserve/58f/260907")
    assert not loaded(csi_db, "SELECT 1 FROM cip_answer WHERE survey_id = :s AND value_text LIKE 'panel-%'", s=sid)
    assert not loaded(csi_db, "SELECT 1 FROM cip_field WHERE survey_id = :s AND field_name IN ('RID', 'url')", s=sid)


def test_long_strings_and_impossible_numbers_are_made_storable():
    field = {"kind": "numeric", "multi": False, "item": None, "labels": {}}
    assert forsta_etl._answer(field, "nan") is None and forsta_etl._answer(field, "1e20") is None
    person = forsta_etl._respondent(1, record(1, markers="x" * 5000, vos="y" * 300), 1)
    assert len(person["markers"]) <= 1000 and len(person["os"]) <= 50


def test_reconcile_compares_numbers_at_the_stored_precision(csi_db):
    data = {"selfserve/58f/260907": [record(n, qtime="61.12345") for n in range(1, 4)]}
    sid = forsta_etl.load_survey(FakeForsta(data=data), "selfserve/58f/260907")
    assert forsta_etl.reconcile_survey(sid, FakeForsta(data=data))[1] == []


def test_reconcile_carries_on_past_a_hibernated_wave(csi_db):
    from etl.forsta_client import ForstaError
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")

    class Hibernated(FakeForsta):
        def survey_data(self, path, **params):
            raise ForstaError("428 needs to be reactivated")
    checked, problems = forsta_etl.reconcile_survey(sid, Hibernated())
    assert checked == 0 and problems == [] 


def test_a_reopened_survey_is_due_again(csi_db):
    forsta_etl.discover(FakeForsta())
    forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    more = [dict(s, total=9, closedDate="2026-09-30T01:00:00Z") if s["path"].endswith("260907") else s for s in SURVEYS]

    class Reopened(FakeForsta):
        def surveys(self):
            return more
    forsta_etl.discover(Reopened())
    assert register(csi_db)["selfserve/58f/260907"][0] == "due"


def test_a_failed_reload_leaves_the_verified_wave_visible(csi_db, monkeypatch):
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    monkeypatch.setattr(forsta_etl, "_write", lambda *a: (_ for _ in ()).throw(RuntimeError("db gone")))
    with pytest.raises(RuntimeError):
        forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    assert loaded(csi_db, "SELECT load_status FROM cip_survey WHERE survey_id = :s", s=sid)[0][0] == "verified"


def test_the_butterfly_keeps_rows_with_the_same_left_statement_apart():
    import pandas as pd
    grid = pd.DataFrame({"item_label": ["a", "a", "b", "b"], "left_label": ["Same"] * 4, "right_label": ["X", "X", "Y", "Y"],
                         "item_order": [1, 1, 2, 2], "option_order": [1, 2, 1, 2], "pct": [.6, .4, .3, .7]})
    assert len(set(charts.butterfly(grid).data[0].y)) == 2


def test_a_wave_loaded_another_way_on_the_same_path_is_never_reused(csi_db):
    from etl.loaders import upsert_survey
    old = upsert_survey(host="se1.decipherinc.com", path="selfserve/58f/260907", title="Excel-era copy",
                        survey_family="CSI-US", wave_label="2026-09-14", wave_date="2026-09-14",
                        platform="forsta", source_ref="selfserve/58f/260907")
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    assert sid != old
    assert loaded(csi_db, "SELECT wave_label FROM cip_survey WHERE survey_id = :s", s=old)[0][0] == "2026-09-14"
