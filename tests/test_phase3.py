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


import sqlalchemy as sa

from etl import records as xp
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
    warm = upsert_survey(host="h", path="p", title="t", wave_label="2024-12-25")
    load_definitions(warm, wave_questions(1))                # topics exist from here on
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
        assert conn.execute(sa.text("SELECT study_type FROM cip_survey WHERE survey_id = :s"),
                            {"s": sid}).scalar() == "annual"


from app.data import harmonise


def test_harmonising_a_wave_costs_the_same_whatever_its_size(csi_db):
    small = upsert_survey(host="h", path="p", title="t", wave_label="2025-01-01")
    large = upsert_survey(host="h", path="p", title="t", wave_label="2025-01-08")
    load_definitions(small, wave_questions(3))
    load_definitions(large, [xp.ParsedQuestion(qcode=f"Z{i}", qtext=f"Other question {i}?",
                                               qtype="single", options=[(1, "A"), (2, "B")])
                             for i in range(40)])
    few = statements(csi_db, lambda: harmonise.harmonise_survey(small))
    many = statements(csi_db, lambda: harmonise.harmonise_survey(large))
    assert few == many <= 20


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
    """A Qualtrics-era survey in legacy form: B1 (yes/no, stored as
    'multiple_choice' like the real ones), B10 (a real multi-select), the age
    question and a grid with no answer rows. Three completes, one disqualified."""
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
        return sorted(tuple(r) for r in conn.execute(sa.text(
            "SELECT r.forsta_uuid, a.value_code FROM cip_answer a JOIN cip_field f ON f.field_id = a.field_id"
            " JOIN cip_respondent r ON r.respondent_id = a.respondent_id"
            " WHERE a.survey_id = :s AND f.field_name = :f"), {"s": sid, "f": field}))


def count(engine, sql):
    with engine.connect() as conn:
        return conn.execute(sa.text(sql)).scalar()


def test_legacy_types_are_inferred_from_the_data_not_the_family_label():
    assert legacy_dwh.legacy_qtype("multiple_choice", "Have you purchased beauty?", 1, 2) == "single"
    assert legacy_dwh.legacy_qtype("multiple_choice", "Where? Select all that apply", 1, 3) == "multi"
    assert legacy_dwh.legacy_qtype("multiple_choice", "Which do you use?", 2, 3) == "multi"
    assert legacy_dwh.legacy_qtype("single_choice", "How do you feel about each?", None, 5) is None
    assert legacy_dwh.legacy_qtype("matrix", "Rate each", 3, 5) == "grid"          # Phase 6: matrices load


def test_study_family_and_type_come_from_the_title():
    assert legacy_dwh.study_for("Shopping and Spending - inc Beauty", 406) == ("CSI-US", "tracker")
    assert legacy_dwh.study_for("Online Grocery 2024", 2110) == ("ONLINE_GROCERY_2024", "annual")
    assert legacy_dwh.study_for("Livestream 13 Q survey for $ quote", 300)[1] == "adhoc"


def test_a_legacy_wave_loads_with_the_right_types_codes_and_zeros(legacy):
    sid = legacy_dwh.load_legacy("SV_T")
    with legacy.connect() as conn:
        survey = conn.execute(sa.text(
            "SELECT platform, source_ref, wave_label, survey_family, study_type FROM cip_survey"
            " WHERE survey_id = :s"), {"s": sid}).one()
        types = dict(conn.execute(sa.text(
            "SELECT qtext, qtype FROM cip_question WHERE survey_id = :s"), {"s": sid}).all())
        qualified = conn.execute(sa.text(
            "SELECT COUNT(*) FROM cip_respondent WHERE survey_id = :s AND is_qualified = 1"),
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
        rows = sorted(tuple(r) for r in conn.execute(sa.text(
            "SELECT r.forsta_uuid, p.age_band, p.age_mid, p.generation FROM cip_profile p"
            " JOIN cip_respondent r ON r.respondent_id = p.respondent_id WHERE p.survey_id = :s"),
            {"s": sid}))
    assert rows[:2] == [("R_1", "18-29", 23.5, None), ("R_2", "Over 60", 67.0, "Boomer")]


def test_reloading_a_legacy_wave_replaces_not_duplicates(legacy):
    sid = legacy_dwh.load_legacy("SV_T")
    before = count(legacy, f"SELECT COUNT(*) FROM cip_answer WHERE survey_id = {sid}")
    maps_before = count(legacy, f"SELECT COUNT(*) FROM cip_concept_map WHERE survey_id = {sid}")
    assert legacy_dwh.load_legacy("SV_T") == sid
    assert count(legacy, f"SELECT COUNT(*) FROM cip_answer WHERE survey_id = {sid}") == before
    assert count(legacy, f"SELECT COUNT(*) FROM cip_concept_map WHERE survey_id = {sid}") == maps_before


def test_a_loaded_legacy_wave_reconciles_and_a_tampered_one_does_not(legacy):
    sid = legacy_dwh.load_legacy("SV_T")
    checked, problems = legacy_dwh.reconcile_legacy(sid)
    assert checked == 7 and problems == []           # 2 + 3 + 2 mapped answers
    with legacy.begin() as conn:
        conn.execute(sa.text("DELETE FROM cip_answer WHERE survey_id = :s AND value_code = 2"), {"s": sid})
    assert legacy_dwh.reconcile_legacy(sid)[1]


import openpyxl

from etl import qualtrics_export


def qualtrics_file(tmp_path):
    """The shape of the real May 2025 export: two header rows, no 'Selected
    Choice' marker, Q_* metadata, a code with a space, and Qualtrics' own
    D7 = state / D8 = political order (Forsta's is the reverse)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["StartDate", "EndDate", "IPAddress", "Duration (in seconds)", "ResponseId", "Q_RecaptchaScore",
               "B1", "B10_1", "B10_2", "B11_1", "B11_2", "B9C _10_TEXT", "D7", "D8", "RID"])
    ws.append(["Start Date", "End Date", "IP Address", "Duration (in seconds)", "Response ID", "Q_RecaptchaScore",
               "Have you purchased any beauty products?",
               "Where did you buy beauty? Select all that apply - Amazon.com",
               "Where did you buy beauty? Select all that apply - Dollar store - Dollar Tree",
               "How do you feel about each retailer? - Amazon.com",
               "How do you feel about each retailer? - CVS",
               "What matters most? - Other (please specify) - Text",
               "In which state is your primary residence?",
               "Which of the following best describes your political philosophy?", "RID"])
    ws.append(["2025-05-12 08:00:00", "2025-05-12 08:02:00", "1.2.3.4", 120, "R_a", 0.9,
               "Yes", "Amazon.com", None, "Very positive", "Neutral", "cruelty free", "NH", "Independent", "p1"])
    ws.append(["2025-05-12 09:00:00", "2025-05-12 09:03:00", "5.6.7.8", 180, "R_b", 0.8,
               "Yes", None, "Dollar store - Dollar Tree", "Neutral", None, None, "MI", "Independent", "p2"])
    ws.append(["2025-05-12 10:00:00", "2025-05-12 10:01:00", "9.9.9.9", 60, "R_c", 0.7,
               "No", None, None, None, None, None, "PA", "Republican", "p3"])
    path = tmp_path / "export.xlsx"
    wb.save(path)
    return path


def test_qualtrics_export_parses_types_and_drops_personal_and_system_columns(tmp_path):
    questions, records = qualtrics_export.parse_export(qualtrics_file(tmp_path))
    kinds = {q.qcode: q.qtype for q in questions}
    assert kinds == {"B1": "single", "B10": "multi", "B11": "grid_single", "B9C_10_TEXT": "text",
                     "D7": "single", "D8": "single"}
    multi = next(q for q in questions if q.qcode == "B10")
    assert multi.qtext == "Where did you buy beauty? Select all that apply"
    assert [label for _, label in multi.rows] == ["Amazon.com", "Dollar store - Dollar Tree"]
    assert records[0]["B10_2"] == "NO TO: Dollar store - Dollar Tree"
    assert "B10_1" not in records[2]                              # R_c never answered B10
    assert not any(k in r for r in records for k in ("IPAddress", "RID", "Q_RecaptchaScore"))
    grid = next(q for q in questions if q.qcode == "B11")
    assert grid.qtext == "How do you feel about each retailer?"
    assert [label for _, label in grid.rows] == ["Amazon.com", "CVS"]


def test_qualtrics_export_loads_harmonises_and_finds_state_by_wording(csi_db, tmp_path):
    sid = qualtrics_export.ingest_export(qualtrics_file(tmp_path), "2025-05-12")
    with csi_db.connect() as conn:
        assert tuple(conn.execute(sa.text("SELECT platform, wave_label FROM cip_survey WHERE survey_id = :s"),
                                  {"s": sid}).one()) == ("qualtrics", "2025-05-12")
        assert conn.execute(sa.text("SELECT COUNT(*) FROM cip_respondent WHERE survey_id = :s"
                                    " AND is_qualified = 1"), {"s": sid}).scalar() == 3
        states = {r[0] for r in conn.execute(sa.text(
            "SELECT state_name FROM cip_profile WHERE survey_id = :s"), {"s": sid})}
        assert conn.execute(sa.text("SELECT COUNT(*) FROM cip_concept_map WHERE survey_id = :s"),
                            {"s": sid}).scalar() > 0
    assert states == {"NH", "MI", "PA"}


def test_hand_entered_summary_waves_are_not_listed_as_respondent_data(legacy):
    with legacy.begin() as conn:
        conn.execute(sa.text("INSERT INTO dwh_smsurveydetail VALUES ('SV_MS1', 'Summary', '2025-08-29', 8, 1)"))
        conn.execute(sa.text("INSERT INTO dwh_smresponse VALUES ('SV_MS1_Q1_R1', 'completed', '2025-05-12', 0, 'SV_MS1')"))
    with legacy.connect() as conn:
        assert [s["id"] for s in legacy_dwh.legacy_surveys(conn)] == ["SV_T"]


import re

import pymysql.cursors
from pathlib import Path


def test_every_batched_insert_is_one_round_trip_on_mysql(legacy):
    """PyMySQL sends executemany as ONE multi-row INSERT only when every VALUES
    entry is a placeholder; a literal ('confirmed', 1) silently turns it into a
    round trip per row (101 rows took 27.8 s on dwh_stg)."""
    batched = []
    listener = lambda conn, cur, stmt, params, ctx, many: many and batched.append(stmt)
    sa.event.listen(legacy, "before_cursor_execute", listener)
    legacy_dwh.load_legacy("SV_T")
    sa.event.remove(legacy, "before_cursor_execute", listener)
    assert batched
    for stmt in batched:
        mysql_form = re.split(r"\s+ON CONFLICT", stmt)[0].replace("?", "%s")
        assert pymysql.cursors.RE_INSERT_VALUES.match(mysql_form), " ".join(stmt.split())[:120]


from types import SimpleNamespace


def test_income_is_the_demographic_question_not_one_that_mentions_income():
    questions = [SimpleNamespace(qcode=c, qtext=t) for c, t in [
        ("Q16", "How long could you cover all of your bills ... if everyone in your household lost their source of income?"),
        ("Q17", "What is your best estimate of the ratio of your outstanding unsecured debt to your monthly "
                "household income? ... your total monthly household income is $5,000"),
        ("Q23", "What was your total household income last year?")]]
    assert survey_map.resolve_profile_map(questions)["income_band"] == "Q23"
    annual = [SimpleNamespace(qcode="Q9", qtext="Which of the following includes your total annual household income?")]
    assert survey_map.resolve_profile_map(annual)["income_band"] == "Q9"


def test_state_and_area_detection_ignore_questions_that_merely_mention_them():
    questions = [SimpleNamespace(qcode=c, qtext=t) for c, t in [
        ("Q1", "Which statement best reflects your feelings about back-to-school fashion?"),
        ("Q2", "Which state did you move from?"),
        ("Q3", "Do you think retailers should focus more on opening stores in urban areas, suburban neighborhoods or rural towns?"),
        ("Q4", "Which of the following best describes the area where your primary residence is located?"),
        ("Q5", "In which state do you currently reside?")]]
    resolved = survey_map.resolve_profile_map(questions)
    assert (resolved["state_name"], resolved["urbanicity"]) == ("Q5", "Q4")



def test_age_ranges_get_a_band_or_generation_only_when_they_fit_inside_one():
    assert survey_map.classify_age("26-41") == {"age": None, "band": None, "gen": None, "mid": 33.5}
    assert survey_map.classify_age("18 - 25") == {"age": None, "band": "18-29", "gen": "GenZ", "mid": 21.5}
    assert survey_map.classify_age("30 - 44") == {"age": None, "band": "30-44", "gen": "Millennial", "mid": 37.0}
    assert survey_map.classify_age("77 or more")["band"] == "Over 60"
    assert survey_map.classify_age("under 50") == {"age": None, "band": None, "gen": None, "mid": None}
    assert survey_map.classify_age("34") == {"age": 34, "band": "30-44", "gen": "Millennial", "mid": 34}
    assert survey_map.classify_age("Under 18") == {"age": 17, "band": None, "gen": None, "mid": 17}


def orphan_selection(engine):
    """A real selection whose answer id is missing from dwh_smanswer — 2,167
    such rows exist in dwh_stg; the label survives only in answer_text."""
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO dwh_smresponseqa (answer_text, question_text, answer_othertext,"
                             " question_id, response_id, answer_id, survey_id) VALUES"
                             " ('Clubhouse', '', NULL, 'QB10', 'R_1', 'A_orphan', 'SV_T')"))


def test_reconcile_flags_source_answers_the_load_never_mapped(legacy, monkeypatch):
    sid = legacy_dwh.load_legacy("SV_T")
    orphan_selection(legacy)                      # appears after the load: the load missed it
    assert any("Clubhouse" in p or "unmapped" in p for p in legacy_dwh.reconcile_legacy(sid)[1])


def test_orphan_selections_are_recovered_from_their_answer_text(legacy):
    orphan_selection(legacy)
    sid = legacy_dwh.load_legacy("SV_T")
    with legacy.connect() as conn:
        items = [r[0] for r in conn.execute(sa.text(
            "SELECT i.item_label FROM cip_item i JOIN cip_question q ON q.question_id = i.question_id"
            " WHERE q.survey_id = :s AND q.qcode = 'Q2' ORDER BY i.sort_order"), {"s": sid})]
    assert items[-1] == "Clubhouse"
    assert legacy_dwh.reconcile_legacy(sid)[1] == []


def test_qualtrics_options_follow_the_concept_order_not_first_appearance(legacy, tmp_path):
    legacy_dwh.load_legacy("SV_T")                      # seeds "What is your age group?": 18 - 29, over 60
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["EndDate", "Duration (in seconds)", "ResponseId", "D2"])
    ws.append(["End Date", "Duration (in seconds)", "Response ID", "What is your age group?"])
    ws.append(["2025-05-12 08:00:00", 60, "R_x", "over 60"])
    ws.append(["2025-05-12 09:00:00", 60, "R_y", "18 - 29"])
    wb.save(tmp_path / "order.xlsx")
    sid = qualtrics_export.ingest_export(tmp_path / "order.xlsx", "2025-05-12")
    with legacy.connect() as conn:
        labels = [r[0] for r in conn.execute(sa.text(
            "SELECT o.value_label FROM cip_option o JOIN cip_question q ON q.question_id = o.question_id"
            " WHERE q.survey_id = :s AND q.qcode = 'D2' ORDER BY o.value_code"), {"s": sid})]
    assert labels == ["18 - 29", "over 60"]


def test_mapping_lookups_are_cached_so_a_page_of_25_rows_is_not_50_round_trips():
    # read the source: test_analysis strips the cache wrappers module-wide
    from app.data import repository
    source = Path(repository.__file__).read_text()
    for name in ("concept_choice", "concept_list"):
        assert re.search(rf"@st\.cache_data\([^)]*\)\ndef {name}\(", source), name


def test_waves_without_sort_columns_take_order_and_codes_from_the_qualtrics_qid(legacy):
    """The three Aug 2022 waves have srt1/srt2 NULL; ids sort QID1, QID11, QID2."""
    with legacy.begin() as conn:
        conn.execute(sa.text("INSERT INTO dwh_smsurveydetail VALUES ('SV_OLD', 'Shopping and Spending', '2022-08-01', 1, 1)"))
        for qid, title in [("SV_OLDQID1", "First?"), ("SV_OLDQID11", "Eleventh?"), ("SV_OLDQID2", "Second?")]:
            conn.execute(sa.text("INSERT INTO dwh_smquestion VALUES (:q, 'multiple_choice', :t, NULL, NULL, 'SV_OLD')"),
                         {"q": qid, "t": title})
            conn.execute(sa.text("INSERT INTO dwh_smanswer VALUES (:a, 0, 'Yes', :q, 'SV_OLD')"), {"a": qid + "A1", "q": qid})
            conn.execute(sa.text("INSERT INTO dwh_smresponseqa (answer_text, question_text, answer_othertext,"
                                 " question_id, response_id, answer_id, survey_id) VALUES ('Yes', '', NULL, :q, 'R_old', :a, 'SV_OLD')"),
                         {"q": qid, "a": qid + "A1"})
        conn.execute(sa.text("INSERT INTO dwh_smresponse VALUES ('R_old', 'completed', '2022-08-02', 60, 'SV_OLD')"))
    sid = legacy_dwh.load_legacy("SV_OLD")
    with legacy.connect() as conn:
        codes = [tuple(r) for r in conn.execute(sa.text(
            "SELECT qcode, qtext FROM cip_question WHERE survey_id = :s ORDER BY sort_order"), {"s": sid})]
    assert codes == [("Q1", "First?"), ("Q2", "Second?"), ("Q11", "Eleventh?")]


def test_a_loaded_legacy_wave_is_searchable(legacy):
    sid = legacy_dwh.load_legacy("SV_T")
    assert count(legacy, f"SELECT COUNT(*) FROM cip_search WHERE survey_id = {sid} AND kind = 'question'") > 0
