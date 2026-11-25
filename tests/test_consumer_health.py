"""The Consumer Health dataset (etl/consumer_health.py): the team's derived columns, their row order and keys, a wave read
from CIP's tables, and the workbook written back in their format with the history unchanged.

Every rule here was first checked against the team's own workbook (25 Nov 2026): all 62,109 rows for the derived
columns, and the 21,713 rows of the 54 Forsta weeks from Aug 2025 to Aug 2026 rebuilt from CIP, column for column."""
import gzip
import hashlib
import json
from datetime import datetime

import sqlalchemy as sa
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from etl import consumer_health

ORIGINAL = list(consumer_health.settings()["activities"]["original"])   # the 12 asked every year


def answers(*done, none=0, movie=None, live=None):
    return {**{c: int(c in done) for c in ORIGINAL}, "Movie_Theater": movie, "Live_Performance": live, "None_Selected": none,
            "Completed_Flag": 1}


def test_the_derived_columns_follow_the_teams_rules():
    row = consumer_health.derive(answers("Open_Air_Center", "Dine_In_Restaurant", "Bar", "Gym_Fitness", "Played_Sports"))
    assert row["Activity_Count"] == 5 and row["Activity_Count_Band"] == "5+" and row["High_Activity_5Plus"] == 1
    assert row["Mall_and_Restaurant"] == 1          # a strip mall counts as the mall, as the team's rows do
    assert row["Shopping_and_Dining"] == 1 and row["Gym_and_Sports"] == 1 and row["Friends_and_Restaurant"] == 0
    assert row["Shopping_Count"] == 1 and row["Social_Dining_Count"] == 2 and row["Entertainment_Count"] is None   # not asked: blank
    assert row["Activity_Pattern_Code"] == "GYM+DIN+SPT+OAC+BAR" and row["Activity_Pattern_Bitmask"] == 4 + 8 + 64 + 256 + 1024
    assert (row["Q1_Activities_Available"], row["Activity_Question_Version"]) == (12, "12 activities + None")
    coffee = consumer_health.derive(answers("Enclosed_Mall", "Coffee_Shop", movie=1, live=0))
    assert coffee["Shopping_and_Dining"] == 1 and coffee["Mall_and_Restaurant"] == 0       # coffee is dining, not a restaurant
    assert coffee["Entertainment_Count"] == 1 and coffee["Activity_Count"] == 2 and coffee["Activity_Count_All_Available"] == 3
    assert coffee["Q1_Activities_Available"] == 14
    nothing = consumer_health.derive(answers(none=1))
    assert (nothing["Activity_Pattern_Code"], nothing["Activity_Count_Band"], nothing["Core_Valid_Flag"]) == (None, "0", 1)
    skipped, both = consumer_health.derive(answers()), consumer_health.derive(answers("Bar", none=1))
    assert (skipped["Q1_Missing_Flag"], skipped["Core_Valid_Flag"]) == (1, 0)
    assert (both["Q1_Contradiction_Flag"], both["Core_Valid_Flag"]) == (1, 0)


def test_ages_go_in_the_teams_bands():
    assert [consumer_health.age_band(a) for a in ("18", "29", "30", "60", "61", "70 or more", "Under 18", "under 18")] == \
        ["18 - 29", "18 - 29", "30 - 44", "45 - 60", "over 60", "over 60", "18 - 29", "18 - 29"]
    assert [consumer_health.age_band(a) for a in ("30 - 44", "over 60", "prefer not to say", None)] == ["30 - 44", "over 60", "prefer not to say", None]


def person(record, done, start, **more):
    return {"record": record, "uuid": f"uuid{record}", "done": datetime.fromisoformat(done), "start": start, "Gender": "Female",
            "Age_Group": "54", "Relationship_Status": "Single", "Ethnicity": "Caucasian", "Household_Income": "under $25,000",
            "Area_Type": "Urban", "State": "OH", "Met up with friends or family locally": 1, **more}


WAVE = {"survey_id": 9, "wave_date": "2026-03-30", "source_ref": "selfserve/58f/260399", "platform": "forsta"}


def week():
    """Four people: two finish in the same minute, most answer on the Tuesday after the Monday launch."""
    people = [person(7, "2026-03-31 09:41:00", "03/31/2026 09:35"), person(3, "2026-03-31 09:41:00", "03/31/2026 09:34"),
              person(5, "2026-03-30 23:50:00", "03/30/2026 23:40"), person(9, "2026-03-31 10:00:00", "03/31/2026 09:50")]
    return consumer_health.wave_rows(WAVE, people, {"Met up with friends or family locally"})


def test_a_waves_rows_are_dated_ordered_and_keyed_as_the_team_does():
    rows = week()
    first = rows[0]
    assert first["Survey_Wave_Date"] == "2026-03-31" and first["File_Label_Date"] == "2026-03-30"   # the day most answered
    assert first["Week_ID"] == "2026-W14" and first["Survey_Month"] == "2026-03-01"
    assert [r["Source_Row"] for r in rows] == [3, 2, 4, 5]          # export order: record 5 first; ties in that order
    assert [r["Respondent_Key"] for r in rows] == [f"2026-03-31-R000{n}" for n in (1, 2, 3, 4)]
    assert (first["Response_Date_vs_Wave_Days"], first["Response_Date_Matches_Wave"]) == (-1, 0)
    assert rows[1]["Response_Start_Datetime"] == "2026-03-31 09:34:00" and rows[1]["Response_Hash"] == hashlib.sha256(b"uuid3").hexdigest()[:18]
    assert first["Age_Group"] == "45 - 60" and first["Friends_Family"] == 1 and first["Movie_Theater"] is None
    line = consumer_health.qa_line(WAVE, rows)
    assert (line["File_Date_Diff_Days"], line["Respondents"], line["Recorded_Date_Min"], line["Source_Sheet"]) == (-1, 4, "2026-03-30", "Forsta API")


def history_of(rows):
    """A history like the team's workbook: their header, rows, and the other three sheets."""
    header = list(rows[0])
    return {"header": header, "rows": [[r[c] for c in header] for r in rows],
            "source_qa": [list(consumer_health.qa_line(WAVE, rows)), list(consumer_health.qa_line(WAVE, rows).values())],
            "dictionary": [["Field", "Type / Role", "Source", "Definition / Modeling Use"], ["Survey_Wave_Date", "Model", "Raw", "Date."]],
            "read_me": [["Consumer Health — Master Raw Respondent Dataset", None], [None, None], ["Survey waves", 1],
                        ["Respondent records", 4], [None, None], ["Important methodology notes", None], ["Model filter", "Use Core_Valid_Flag = 1."]]}


def test_the_workbook_keeps_the_history_and_the_teams_format(tmp_path):
    old = week()
    history = history_of(old)
    new = consumer_health.wave_rows({**WAVE, "wave_date": "2027-01-04", "source_ref": "selfserve/58f/270100"},
                       [person(1, "2027-01-04 12:00:00", "01/04/2027 11:50")], set())
    path = consumer_health.save(tmp_path, history, new, [consumer_health.qa_line(WAVE, new)])
    assert path.name == "Consumer_Health_Raw_Respondent_Data_Chronological_2026_2027.xlsx"
    book = load_workbook(path)
    assert book.sheetnames == ["Read Me", "2026", "2027", "Source QA", "Data Dictionary"]
    sheet = book["2026"]
    assert [[c.value for c in r] for r in sheet.iter_rows(min_row=2)] == history["rows"]          # the history, cell for cell
    assert book["2027"]["A2"].value == "2027-01-04"
    header = history["header"]
    colour = lambda name: sheet.cell(1, header.index(name) + 1).fill.fgColor.rgb   # noqa: E731
    assert (colour("Survey_Wave_Date"), colour("Bar"), colour("Activity_Count")) == ("FF4472C4", "FF70AD47", "FF8064A2")
    assert sheet.cell(1, 1).font.b and sheet.cell(1, 1).font.name == "Calibri" and sheet.row_dimensions[1].height == 33.95
    assert sheet.column_dimensions["M"].width == 52.7109375 and sheet.sheet_view.zoomScale == 80 and sheet.auto_filter.ref == "A1:BU5"
    assert (sheet.freeze_panes, book["2027"].freeze_panes) == (None, "N2")   # the first year's sheet unfrozen, as theirs
    flagged = {str(r.sqref) for r in sheet.conditional_formatting}
    letter = lambda name: get_column_letter(header.index(name) + 1)   # noqa: E731
    assert {f"{letter(c)}2:{letter(c)}5" for c in ("Response_Date_Matches_Wave", "Core_Valid_Flag")} <= flagged   # off its day, failing
    read_me = {r[0]: r[1] for r in book["Read Me"].iter_rows(values_only=True) if r[0]}
    assert read_me["Survey waves"] == 2 and read_me["Respondent records"] == 5                   # recounted with the new week
    assert "A1:H1" in book["Read Me"].merged_cells and book["Read Me"].freeze_panes == "A2"
    assert book["Source QA"].max_row == 3 and book["Source QA"].freeze_panes == "E2"


def test_a_wave_is_read_from_cips_tables_and_the_history_round_trips(csi_db, tmp_path):
    with csi_db.begin() as conn:
        conn.execute(sa.text("INSERT INTO cip_survey (survey_id, forsta_host, forsta_path, title, wave_label, wave_date, survey_family)"
                             " VALUES (9, 'se1', 'selfserve/58f/260399', 'Shopping and Spending', '2026-03-30', '2026-03-30', 'CSI-US')"))
        conn.execute(sa.text("INSERT INTO cip_respondent (respondent_id, survey_id, record_no, forsta_uuid, is_qualified, completed_at)"
                             " VALUES (1, 9, 4, 'u4', 1, '2026-03-30 10:05:00'), (2, 9, 5, 'u5', 0, '2026-03-30 10:06:00')"))
        conn.execute(sa.text("INSERT INTO cip_question (question_id, survey_id, qcode, qtext, qtype) VALUES"
                             " (1, 9, 'q1', 'Which, if any, of these have you done in the past two weeks?', 'multi'),"
                             " (2, 9, 'D2', 'What is your age?', 'single'), (3, 9, 'start_date', 'Survey start time', 'text')"))
        conn.execute(sa.text("INSERT INTO cip_item (item_id, question_id, item_code, item_label) VALUES"
                             " (1, 1, 'q1r11', 'Gone to a bar'), (2, 1, 'q1r14', 'Gone to a movie theater/cinema')"))
        conn.execute(sa.text("INSERT INTO cip_option (question_id, value_code, value_label) VALUES (2, 44, '60')"))
        conn.execute(sa.text("INSERT INTO cip_field (field_id, survey_id, question_id, item_id, field_name, value_type) VALUES"
                             " (1, 9, 1, 1, 'q1r11', 'code'), (2, 9, 1, 2, 'q1r14', 'code'), (3, 9, 2, NULL, 'D2', 'code'),"
                             " (4, 9, 3, NULL, 'start_date', 'text')"))
        conn.execute(sa.text("INSERT INTO cip_answer (respondent_id, survey_id, field_id, value_code, value_text) VALUES"
                             " (1, 9, 1, 1, NULL), (1, 9, 2, 0, NULL), (1, 9, 3, 44, NULL), (1, 9, 4, NULL, '03/30/2026 09:58'),"
                             " (2, 9, 1, 1, NULL)"))
    with csi_db.connect() as conn:
        people, asked = consumer_health.read_people(conn, 9)
    assert len(people) == 1 and asked == {"Gone to a bar", "Gone to a movie theater/cinema"}   # the unqualified one left out
    row = consumer_health.wave_rows(WAVE, people, asked)[0]
    assert (row["Bar"], row["Movie_Theater"], row["Live_Performance"], row["Age_Group"]) == (1, 0, None, "45 - 60")
    assert row["Response_Start_Datetime"] == "2026-03-30 09:58:00" and row["Q1_Activities_Available"] == 13

    book = consumer_health.save(tmp_path, history_of(week()), [], [])
    assert consumer_health.load_history(book) == 4 and consumer_health.read_history()["rows"] == history_of(week())["rows"]
    out = tmp_path / "version"
    (out / "api/v1").mkdir(parents=True)
    (out / "api/v1/waves.json.gz").write_bytes(gzip.compress(json.dumps([
        {**WAVE, "wave_date": "2026-04-06", "survey_family": "CSI-US", "study_type": "tracker"}]).encode()))
    assert consumer_health.publish(out) > 0
    written = load_workbook(next((out / consumer_health.FOLDER).glob("Consumer_Health_*_2026_2026.xlsx")), read_only=True)
    assert len(list(written["2026"].iter_rows())) == 6                           # header, the 4 kept rows, the newer week's one
