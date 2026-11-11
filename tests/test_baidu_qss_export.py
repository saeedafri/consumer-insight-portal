"""The China Consumer Survey load (etl/baidu_qss_export.py), on a real week from Baidu QSS: the raw export of 3 Nov 2026
(550 people) and Baidu's own topline of it. Every count CIP serves must equal the topline's."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy import text

from etl import baidu_qss_export

FIXTURES = Path(__file__).resolve().parent / "fixtures"
RAW, TOPLINE = FIXTURES / "baidu_raw_2026-11-03.csv", FIXTURES / "baidu_topline_2026-11-05.xls"
RAW_XLSX = FIXTURES / "baidu_raw_2026-01-26.xlsx"   # the same export saved as .xlsx by an analyst (538 people)


def test_every_count_from_the_raw_file_equals_baidus_topline():
    found = baidu_qss_export.preview(RAW, TOPLINE)
    assert found["problems"] == []
    assert (found["wave"], found["respondents"], found["matched"]) == ("2026-10-26", 550, 123)   # 14 bases + 109 answers
    by_code = {q["qcode"]: q for q in found["questions"]}
    assert by_code["S1"]["answers"][:2] == [["Male", 277, 50.4], ["Female", 273, 49.6]]
    assert by_code["Q3"]["base"] == 295                                    # asked only after "Yes" at Q2
    assert by_code["Q8"]["answers"][0] == ["Positive", 303, 55.1]         # 积极: the old converter said Pessimistic


def test_an_xlsx_copy_of_the_export_reads_like_the_csv():
    questions, records, problems = baidu_qss_export.read_raw(RAW_XLSX, baidu_qss_export.load_codebook())
    assert problems == [] and len(records) == 538 and len(questions) == 14
    assert baidu_qss_export.survey_week(records) == "2026-01-19"   # fielded 26 Jan: the survey of the week before


def test_the_wrong_weeks_topline_or_an_unknown_wording_stops_the_load(tmp_path, csi_db):
    other_week = baidu_qss_export.read_topline(TOPLINE)
    other_week["S1"]["counts"]["男"] += 1
    questions, records, _ = baidu_qss_export.read_raw(RAW, baidu_qss_export.load_codebook())
    _, problems = baidu_qss_export.compare_with_topline(questions, records, other_week, baidu_qss_export.load_codebook())
    assert problems == ["S1 'Male': 277 in the raw file, the topline says 278"]

    renamed = tmp_path / "raw.csv"
    renamed.write_bytes(RAW.read_bytes().replace("躺平".encode("gb18030"), "睡觉".encode("gb18030")))
    with pytest.raises(ValueError, match="Q4 answer not in the codebook: 睡觉"):
        baidu_qss_export.load(renamed, TOPLINE)
    with csi_db.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM cip_survey")).scalar() == 0   # nothing written


def test_seconds_taken_reads_both_of_baidus_spellings():
    assert [baidu_qss_export.seconds_taken(v) for v in ("159秒", "1分12秒", "", None)] == [159, 72, None, None]


def test_a_week_loads_into_the_served_tables_equal_to_the_topline_and_reloads_in_place(csi_db, tmp_path):
    result = baidu_qss_export.load(RAW, TOPLINE)
    assert (result["wave"], result["respondents"], result["matched"]) == ("2026-10-26", 550, 123)
    survey = result["survey_id"]
    topline = baidu_qss_export.read_topline(TOPLINE)
    answers = baidu_qss_export.load_codebook()["questions"]
    with csi_db.connect() as conn:
        assert conn.execute(text("SELECT country, platform, survey_family, load_status FROM cip_survey WHERE survey_id = :s"),
                            {"s": survey}).one() == ("CN", "baidu", "CSI-CN", "verified")
        served = {(q, label): (n, base) for q, label, n, base in conn.execute(text(
            "SELECT qcode, COALESCE(option_label, item_label), n, base_n FROM srv_result"
            " WHERE survey_id = :s AND dim = 'total'"), {"s": survey})}
        for qcode, figures in topline.items():
            for chinese, count in figures["counts"].items():
                assert served.get((qcode, answers[qcode]["answers"][chinese]), (0, figures["base"])) == (count, figures["base"]), (qcode, chinese)
        cuts = dict(conn.execute(text("SELECT dim_value, base_n FROM srv_result WHERE survey_id = :s AND qcode = 'Q1'"
                                      " AND dim = 'urbanicity' AND option_code = 1"), {"s": survey}).all())
        assert cuts == {"Tier 1 city": 128, "Tier 2 city": 368, "Other city": 54}
        bands = dict(conn.execute(text("SELECT age_band, COUNT(*) FROM cip_profile WHERE survey_id = :s GROUP BY age_band"),
                                  {"s": survey}).all())
        assert bands == {"18-25": 125, "26-41": 352, "42-57": 71, "57-76": 2}

    again = baidu_qss_export.load(RAW, TOPLINE)
    with csi_db.connect() as conn:
        assert again["survey_id"] == survey
        assert conn.execute(text("SELECT COUNT(*) FROM cip_respondent WHERE survey_id = :s"), {"s": survey}).scalar() == 550


def test_two_weeks_compare_and_keep_baidus_topline_beside_cips_figures(csi_db):
    """The surveys of Oct 19 and Oct 26 loaded in turn: the later one compares with the earlier, each keeps its topline."""
    first = baidu_qss_export.load(FIXTURES / "baidu_raw_2026-10-26.csv", FIXTURES / "baidu_topline_2026-10-29.xls")
    second = baidu_qss_export.load(RAW, TOPLINE)
    with csi_db.connect() as conn:
        assert conn.execute(text("SELECT prior_survey_id FROM srv_wave WHERE survey_id = :s"),
                            {"s": second["survey_id"]}).scalar() == first["survey_id"]
        prior = conn.execute(text("SELECT pct, prior_pct FROM srv_result WHERE survey_id = :s AND qcode = 'S1'"
                                  " AND dim = 'total' AND option_label = 'Male'"), {"s": second["survey_id"]}).one()
        assert (round(float(prior[0]), 1), round(float(prior[1]), 1)) == (50.4, 51.8)   # 277/550 and 288/556
        kept = conn.execute(text("SELECT survey_id, COUNT(*), SUM(count_n) FROM cip_crosstab GROUP BY survey_id"
                                 " ORDER BY survey_id")).all()
        assert [row[1] for row in kept] == [109, 109]   # every answer Baidu printed, for each week
        compared, mismatched = conn.execute(text(
            "SELECT COUNT(*), SUM(r.n <> c.count_n OR r.base_n <> c.answer_base_n) FROM cip_crosstab c JOIN srv_result r ON r.survey_id = c.survey_id"
            " AND r.question_id = c.question_id AND r.item_id = COALESCE(c.item_id, 0) AND r.option_id = COALESCE(c.option_id, 0)"
            " AND r.dim = 'total'")).one()
        assert compared > 200 and mismatched == 0   # Baidu's figures and the served ones, side by side


def test_submit_times_re_saved_day_first_are_read_day_first():
    """Baidu writes "3/9/26 14:16" (month first); a UK-set Excel re-save writes "26/05/25 20:06" or "03/11/24 09:12"."""
    as_baidu = baidu_qss_export.submit_time_reader(["3/9/26 14:16", "10/21/26 22:19"])
    assert as_baidu("3/9/26 14:16").date().isoformat() == "2026-03-09"
    resaved = baidu_qss_export.submit_time_reader(["03/11/24 09:12", "04/11/24 10:00"])   # no day over 12: zeros tell
    assert resaved("03/11/24 09:12").date().isoformat() == "2024-11-03"
    assert baidu_qss_export.submit_time_reader(["26/05/25 20:06"])("26/05/25 20:06").date().isoformat() == "2025-05-26"


def test_a_months_extra_questions_and_older_wordings_count_into_todays_answers(tmp_path):
    """A topline with a month's extra question ("15.H1.", e.g. luxury or Singles' Day) and the 2023-24 age wording
    ("18-25 周岁") reads as today's: the extra question is skipped, the old wording counts into "18-25岁"."""
    import openpyxl
    rows = baidu_qss_export.read_table(TOPLINE)
    book = openpyxl.Workbook()
    for row in rows:
        first = str(row[0]).strip() if row and row[0] is not None else ""
        book.active.append([first.replace("18-25岁", "18-25 周岁"), *row[1:]])
    for extra in (["15.H1.您在过去的12个月有购买过奢侈品吗？"], ["有", 120], ["没有", 430], ["答题人数：550"]):
        book.active.append(extra)
    book.save(tmp_path / "topline.xlsx")
    ours, theirs = baidu_qss_export.read_topline(TOPLINE), baidu_qss_export.read_topline(tmp_path / "topline.xlsx")
    assert theirs == ours   # nothing from H1 lands in Q9, and the old age wording is today's answer


def test_a_singles_day_week_reads_the_trackers_questions_not_its_own():
    """Nov 17 2025 asked 17 Singles' Day questions as Q1-Q17, then the tracker's Q1-Q9 again: the tracker block is read
    (every figure equal to Baidu's), the Singles' Day questions are skipped."""
    found = baidu_qss_export.preview(FIXTURES / "baidu_raw_2025-11-17_singles_day.csv",
                                     FIXTURES / "baidu_topline_2025-11-18_singles_day.xls")
    assert (found["respondents"], found["matched"], found["problems"]) == (560, 123, [])
