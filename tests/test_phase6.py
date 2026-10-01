"""Phase 6: the SurveyMonkey years (2018 – 2022) through the legacy adapter.

See docs/superpowers/plans/2026-10-01-surveymonkey-phase6.md.
"""
from __future__ import annotations

import sqlalchemy as sa

from etl import survey_map


def test_surveymonkey_age_labels():
    assert survey_map.classify_age("< 18") == {"age": 17, "band": None, "gen": None, "mid": 17}
    assert survey_map.classify_age("> 60")["band"] == "Over 60"


def test_surveymonkey_income_ranges_take_the_workbook_midpoint():
    assert survey_map.income_mid_k("$25,000-$49,999") == 37.4995
    assert survey_map.income_mid_k("$0-$9,999") == 4.9995
    assert survey_map.income_mid_k("$200,000+") == 225
    assert survey_map.income_mid_k("Prefer not to answer") is None
    assert survey_map.income_mid_k("$50,000 - $99,999") == 74.9995          # the Forsta/Qualtrics table still wins


def test_census_divisions_roll_up_to_regions():
    assert survey_map.census_region_of_division("South Atlantic") == "South"
    assert survey_map.census_region_of_division("Pacific") == "West"
    assert survey_map.census_region_of_division("New England") == "Northeast"
    assert survey_map.census_region_of_division("East North Central") == "Midwest"
    assert survey_map.census_region_of_division(None) is None


import pytest

from etl import legacy_dwh
from tests.test_phase3 import LEGACY_DDL, answers

DEMOGRAPHY_DDL = ("CREATE TABLE dwh_smdemography (id INTEGER PRIMARY KEY, response_id VARCHAR(100), collector_id VARCHAR(100),"
                  " age VARCHAR(50), gender VARCHAR(50), income VARCHAR(50), region VARCHAR(50), device VARCHAR(50),"
                  " dateprocessed DATETIME, survey_id VARCHAR(100))")


@pytest.fixture()
def monkey(csi_db):
    """A SurveyMonkey wave: a yes/no question and a 2-row × 3-column matrix,
    stored the SurveyMonkey way — "<row> | <column>" in answer_text, the
    column's id in answer_id. Three completes; panel demographics."""
    with csi_db.begin() as conn:
        for ddl in LEGACY_DDL + [DEMOGRAPHY_DDL]:
            conn.execute(sa.text(ddl))
        conn.execute(sa.text("INSERT INTO dwh_smsurveydetail VALUES ('900', 'Shopping and spending: holidays', '2020-11-02', 3, 1)"))
        conn.execute(sa.text("INSERT INTO dwh_smquestion VALUES ('Q1', 'single_choice', 'Did you shop online?', 0, 0, '900'),"
                             " ('QM', 'matrix', 'How do you rate each retailer?', 1, 0, '900'),"
                             " ('QG', 'single_choice', 'What is your gender?', 2, 0, '900')"))
        conn.execute(sa.text("INSERT INTO dwh_smanswer VALUES ('Y', 1, 'Yes', 'Q1', '900'), ('N', 2, 'No', 'Q1', '900'),"
                             " ('RA', 1, 'Amazon', 'QM', '900'), ('C1', 1, 'Poor', 'QM', '900'),"
                             " ('RC', 2, 'CVS', 'QM', '900'), ('C2', 2, 'Fair', 'QM', '900'), ('C3', 3, 'Good', 'QM', '900'),"
                             " ('GM', 1, 'Male', 'QG', '900'), ('GF', 2, 'Female', 'QG', '900')"))
        conn.execute(sa.text("INSERT INTO dwh_smresponse VALUES ('1001', 'completed', '2020-11-03 09:00', 60, '900'),"
                             " ('1002', 'completed', '2020-11-03 10:00', 70, '900'), ('1003', 'completed', '2020-11-04 10:00', 80, '900')"))
        conn.execute(sa.text("INSERT INTO dwh_smresponseqa (answer_text, question_text, answer_othertext, question_id, response_id, answer_id, survey_id) VALUES"
                             " ('Yes', '', 'None', 'Q1', '1001', 'Y', '900'), ('No', '', 'None', 'Q1', '1002', 'N', '900'),"
                             " ('Yes', '', 'None', 'Q1', '1003', 'Y', '900'),"
                             " ('Amazon | Good', '', 'None', 'QM', '1001', 'C3', '900'), ('CVS | Poor', '', 'None', 'QM', '1001', 'C1', '900'),"
                             " ('Amazon | Poor', '', 'None', 'QM', '1002', 'C1', '900'), ('CVS | Fair', '', 'None', 'QM', '1003', 'C2', '900'),"
                             " ('Male', '', 'None', 'QG', '1001', 'GM', '900'), ('Male', '', 'None', 'QG', '1003', 'GM', '900')"))
        conn.execute(sa.text("INSERT INTO dwh_smdemography (response_id, age, gender, income, region, survey_id) VALUES"
                             " ('1001', '30-44', 'Female', '$25,000-$49,999', 'Pacific', '900'),"
                             " ('1001', '30-44', 'Female', '$25,000-$49,999', 'Pacific', '900'),"
                             " ('1002', '> 60', 'Male', 'Prefer not to answer', 'New England', '900')"))
    return csi_db


def test_a_matrix_with_answers_is_a_grid():
    assert legacy_dwh.legacy_qtype("matrix", "Rate each", 2, 5) == "grid"
    assert legacy_dwh.legacy_qtype("matrix", "Rate each", None, 5) is None


def test_matrix_answers_land_on_their_own_row(monkey):
    sid = legacy_dwh.load_legacy("900")
    with monkey.connect() as conn:
        qtype, rows, scale = conn.execute(sa.text(
            "SELECT q.qtype, (SELECT COUNT(*) FROM csi_item i WHERE i.question_id = q.question_id),"
            " (SELECT GROUP_CONCAT(value_label, ',') FROM (SELECT value_label FROM csi_option o"
            "   WHERE o.question_id = q.question_id ORDER BY o.value_code))"
            " FROM csi_question q WHERE q.survey_id = :s AND q.qtext LIKE 'How do you rate%'"), {"s": sid}).one()
    assert (qtype, rows, scale) == ("grid_single", 2, "Poor,Fair,Good")
    assert answers(monkey, sid, "Q2r1") == [("1001", 3), ("1002", 1)]          # Amazon
    assert answers(monkey, sid, "Q2r2") == [("1001", 1), ("1003", 2)]          # CVS


def test_matrix_waves_reconcile_cell_by_cell(monkey):
    sid = legacy_dwh.load_legacy("900")
    checked, problems = legacy_dwh.reconcile_legacy(sid)
    assert problems == [] and checked >= 2 + 4
    with monkey.begin() as conn:                     # move one CVS rating to the Amazon row
        conn.execute(sa.text("UPDATE csi_answer SET field_id = (SELECT field_id FROM csi_field WHERE survey_id = :s AND field_name = 'Q2r1')"
                             " WHERE survey_id = :s AND respondent_id = (SELECT respondent_id FROM csi_respondent WHERE forsta_uuid = '1003')"
                             " AND field_id = (SELECT field_id FROM csi_field WHERE survey_id = :s AND field_name = 'Q2r2')"), {"s": sid})
    assert legacy_dwh.reconcile_legacy(sid)[1]



def profiles(engine, sid):
    with engine.connect() as conn:
        return {r[0]: tuple(r[1:]) for r in conn.execute(sa.text(
            "SELECT r.forsta_uuid, p.gender, p.age_band, p.age_mid, p.income_band, p.income_mid_k, p.census_region"
            " FROM csi_profile p JOIN csi_respondent r ON r.respondent_id = p.respondent_id WHERE p.survey_id = :s"),
            {"s": sid})}


def test_panel_demographics_fill_the_profile_and_a_question_answer_wins(monkey):
    sid = legacy_dwh.load_legacy("900")
    got = profiles(monkey, sid)
    # 1001 told the survey "Male"; the panel says Female — the respondent's own answer stands
    assert got["1001"] == ("Male", "30-44", 37.0, "$25,000-$49,999", 37.4995, "West")
    assert got["1002"] == ("Male", "Over 60", 67.0, "Prefer not to answer", None, "Northeast")
    assert got["1003"][0] == "Male" and got["1003"][1:] == (None, None, None, None, None)


def test_reloading_keeps_panel_profiles_stable(monkey):
    sid = legacy_dwh.load_legacy("900")
    first = profiles(monkey, sid)
    legacy_dwh.load_legacy("900")
    assert profiles(monkey, sid) == first


def one_row_matrix(engine):
    """A 'matrix' with one blank row: answers carry no "<row> | " prefix."""
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO dwh_smquestion VALUES ('QS', 'matrix', 'How will your spending change?', 3, 1, '900')"))
        conn.execute(sa.text("INSERT INTO dwh_smanswer VALUES ('S0', 1, '', 'QS', '900'), ('S1', 1, 'Much less', 'QS', '900'),"
                             " ('S2', 2, 'Same', 'QS', '900'), ('S3', 3, 'Much more', 'QS', '900')"))
        conn.execute(sa.text("INSERT INTO dwh_smresponseqa (answer_text, question_text, answer_othertext, question_id, response_id, answer_id, survey_id) VALUES"
                             " ('Same', '', 'None', 'QS', '1001', 'S2', '900'), ('Much more', '', 'None', 'QS', '1002', 'S3', '900')"))


def test_a_one_row_matrix_loads_as_a_single_choice(monkey):
    one_row_matrix(monkey)
    sid = legacy_dwh.load_legacy("900")
    with monkey.connect() as conn:
        qtype, labels = conn.execute(sa.text(
            "SELECT q.qtype, (SELECT GROUP_CONCAT(value_label, ',') FROM (SELECT value_label FROM csi_option o"
            " WHERE o.question_id = q.question_id ORDER BY o.value_code)) FROM csi_question q"
            " WHERE q.survey_id = :s AND q.qtext LIKE 'How will your spending%'"), {"s": sid}).one()
    assert (qtype, labels) == ("single", "Much less,Same,Much more")
    assert legacy_dwh.reconcile_legacy(sid)[1] == []


def test_reconcile_flags_a_question_whose_answers_never_loaded(monkey, monkeypatch):
    real = legacy_dwh.legacy_qtype
    monkeypatch.setattr(legacy_dwh, "legacy_qtype",
                        lambda family, title, *a: None if title.startswith("Did you shop") else real(family, title, *a))
    sid = legacy_dwh.load_legacy("900")
    problems = legacy_dwh.reconcile_legacy(sid)[1]
    assert any("Q1" in p and "not loaded" in p for p in problems), problems


# ── final-review fixes ─────────────────────────────────────────────────────
def test_a_question_answer_keeps_its_whole_group_the_panel_does_not_mix_in(monkey):
    with monkey.begin() as conn:
        conn.execute(sa.text("INSERT INTO dwh_smquestion VALUES ('QI', 'single_choice', 'What was your total household income last year?', 4, 0, '900')"))
        conn.execute(sa.text("INSERT INTO dwh_smanswer VALUES ('IP', 1, 'Prefer not to say', 'QI', '900')"))
        conn.execute(sa.text("INSERT INTO dwh_smresponseqa (answer_text, question_text, answer_othertext, question_id, response_id, answer_id, survey_id)"
                             " VALUES ('Prefer not to say', '', 'None', 'QI', '1001', 'IP', '900')"))
    sid = legacy_dwh.load_legacy("900")
    assert profiles(monkey, sid)["1001"][3:5] == ("Prefer not to say", None)     # not the panel's $25,000-$49,999 midpoint


def test_a_reload_picks_up_changed_panel_data(monkey):
    sid = legacy_dwh.load_legacy("900")
    with monkey.begin() as conn:
        conn.execute(sa.text("UPDATE dwh_smdemography SET region = 'Mountain' WHERE response_id = '1002'"))
    legacy_dwh.load_legacy("900")
    assert profiles(monkey, sid)["1002"][5] == "West"


def test_a_matrix_row_nobody_answered_is_not_a_scale_point(monkey):
    with monkey.begin() as conn:
        conn.execute(sa.text("INSERT INTO dwh_smanswer VALUES ('RW', 3, 'Walmart', 'QM', '900')"))
    sid = legacy_dwh.load_legacy("900")
    with monkey.connect() as conn:
        scale = [r[0] for r in conn.execute(sa.text(
            "SELECT o.value_label FROM csi_option o JOIN csi_question q ON q.question_id = o.question_id"
            " WHERE q.survey_id = :s AND q.qtext LIKE 'How do you rate%' ORDER BY o.value_code"), {"s": sid})]
    assert scale == ["Poor", "Fair", "Good"]


def test_a_matrix_with_plain_answers_and_several_row_labels_is_skipped_not_guessed(monkey):
    with monkey.begin() as conn:
        conn.execute(sa.text("INSERT INTO dwh_smquestion VALUES ('QX', 'matrix', 'Rate these', 5, 0, '900')"))
        conn.execute(sa.text("INSERT INTO dwh_smanswer VALUES ('X1', 1, 'Row one', 'QX', '900'), ('X2', 2, 'Row two', 'QX', '900'),"
                             " ('XC', 1, 'Agree', 'QX', '900')"))
        conn.execute(sa.text("INSERT INTO dwh_smresponseqa (answer_text, question_text, answer_othertext, question_id, response_id, answer_id, survey_id)"
                             " VALUES ('Agree', '', 'None', 'QX', '1001', 'XC', '900')"))
    sid = legacy_dwh.load_legacy("900")
    with monkey.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM csi_question WHERE survey_id = :s AND qtext = 'Rate these'"),
                            {"s": sid}).scalar() == 0
    assert any("not loaded" in p for p in legacy_dwh.reconcile_legacy(sid)[1])      # and reconcile says so


def test_matrix_text_variants_of_one_cell_reconcile_as_one(monkey):
    with monkey.begin() as conn:
        conn.execute(sa.text("INSERT INTO dwh_smresponse VALUES ('1004', 'completed', '2020-11-04 11:00', 80, '900')"))
        conn.execute(sa.text("INSERT INTO dwh_smresponseqa (answer_text, question_text, answer_othertext, question_id, response_id, answer_id, survey_id)"
                             " VALUES ('Amazon  | Good', '', 'None', 'QM', '1004', 'C3', '900')"))
    sid = legacy_dwh.load_legacy("900")
    assert legacy_dwh.reconcile_legacy(sid)[1] == []


def test_one_bad_wave_does_not_stop_the_rest(monkey, monkeypatch):
    loaded = []
    monkeypatch.setattr(legacy_dwh, "legacy_surveys", lambda conn, era: [{"id": "A", "title": "a"}, {"id": "B", "title": "b"}])
    monkeypatch.setattr(legacy_dwh, "load_legacy", lambda lid: (_ for _ in ()).throw(RuntimeError("x")) if lid == "A" else loaded.append(lid))
    monkeypatch.setattr("sys.argv", ["legacy_dwh", "--all", "--era", "surveymonkey"])
    assert legacy_dwh.main() == 1 and loaded == ["B"]
