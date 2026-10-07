"""Phase 7: the Forsta API adapter. The pipeline itself is tested in
tests/test_forsta_etl.py.
"""
from __future__ import annotations

from etl import forsta_api

DATAMAP = {"questions": [
    {"qlabel": "hq1", "qtitle": "Have you shopped online?", "type": "single",
     "variables": [{"label": "hq1", "qlabel": "hq1"}],
     "values": [{"value": 1, "title": "Yes"}, {"value": 2, "title": "No"}]},
    {"qlabel": "q2", "qtitle": "Which, if any, of these have you done?", "type": "multiple",
     "variables": [{"label": "q2r1", "row": "r1", "rowTitle": "Met up with friends"},
                   {"label": "q2r2", "row": "r2", "rowTitle": "Gone to a bar"}],
     "values": [{"value": 0, "title": "Unchecked"}, {"value": 1, "title": "Checked"}]},
    {"qlabel": "q5", "qtitle": "How do you feel about each retailer?", "type": "single",
     "variables": [{"label": "q5r1", "row": "r1", "rowTitle": "Amazon"},
                   {"label": "q5r2", "row": "r2", "rowTitle": "CVS"}],
     "values": [{"value": 1, "title": "Negative"}, {"value": 2, "title": "Neutral"}, {"value": 3, "title": "Positive"}]},
    {"qlabel": "d2", "qtitle": "What is your age?", "type": "number", "variables": [{"label": "d2"}]},
    {"qlabel": "q9", "qtitle": "Anything else?", "type": "text", "variables": [{"label": "q9"}]},
]}


def test_the_datamap_is_read_per_question_not_per_variable():
    questions = {q.qcode: q for q in forsta_api.questions_from_datamap(DATAMAP)}
    assert list(questions) == ["hq1", "q2", "q5", "d2", "q9"]
    assert questions["hq1"].qtype == "single" and questions["hq1"].options == [(1, "Yes"), (2, "No")]
    assert questions["q2"].qtype == "multi" and questions["q2"].rows == [("q2r1", "Met up with friends"),
                                                                         ("q2r2", "Gone to a bar")]
    assert (questions["q2"].value_min, questions["q2"].value_max) == (0, 1)
    assert questions["q5"].qtype == "grid_single" and [r for r, _ in questions["q5"].rows] == ["q5r1", "q5r2"]
    assert questions["d2"].qtype == "numeric" and questions["q9"].qtype == "text"


from etl import run_pipeline


def test_the_wave_is_the_monday_of_the_first_fielding_day():
    assert run_pipeline.wave_from_records([{"date": "09/23/2026 10:05"}, {"date": "09/22/2026 08:00"}]) == "2026-09-21"
    assert run_pipeline.wave_from_records([{"date": "2026-09-28 07:00:00"}]) == "2026-09-28"
