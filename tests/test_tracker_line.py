"""The data team's "Weekly Line-By-Line Survey Data", built by the ETL: one row
per qualified respondent of each weekly tracker wave, the core questions under
the team's own headers, derived columns included (Month, Age Range, Generation).
"""
from __future__ import annotations

import pandas as pd
from etl import forsta_etl, tracker_line

YN = [{"value": 1, "title": "Yes"}]
TRACKER = {"questions": [
    {"qlabel": "q1", "qtitle": "Which, if any, of these have you done in the past two weeks?", "type": "multiple",
     "variables": [{"label": "q1r1", "rowTitle": "Met up with friends or family locally"},
                   {"label": "q1r2", "rowTitle": "Gone to a bar"}]},
    {"qlabel": "CS1", "qtitle": "Your household situation?", "type": "single", "variables": [{"label": "CS1"}],
     "values": [{"value": 1, "title": "Much worse"}, {"value": 3, "title": "About the same"}]},
    {"qlabel": "D1", "qtitle": "What is your gender?", "type": "single", "variables": [{"label": "D1"}],
     "values": [{"value": 1, "title": "Male"}, {"value": 2, "title": "Female"}]},
    {"qlabel": "D2", "qtitle": "What is your age?", "type": "single", "variables": [{"label": "D2"}],
     "values": [{"value": 1, "title": "Under 18"}, {"value": 2, "title": "34"}, {"value": 3, "title": "70 or more"}]},
    {"qlabel": "D8", "qtitle": "In which state is your primary residence?", "type": "single",
     "variables": [{"label": "D8"}], "values": [{"value": 5, "title": "CA"}]},
    {"qlabel": "start_date", "qtitle": "Survey start time", "type": "text", "flags": ["t"],
     "variables": [{"label": "start_date"}]},
]}


def person(n, status="3", **answers):
    base = {"record": str(n), "uuid": f"u{n}", "status": status, "date": f"09/2{8 + n % 2}/2026 10:0{n}",
            "start_date": f"09/2{8 + n % 2}/2026 09:5{n}", "RID": f"p{n}", "session": f"s{n}",
            "q1r1": "1", "q1r2": "0", "CS1": "3", "D1": "2", "D2": "2", "D8": "5"}
    base.update(answers)
    return base


SURVEY = {"path": "selfserve/58f/260907", "title": "Shopping and Spending - inc Beauty", "state": "closed",
          "hibernated": False, "tags": ["Weekly consumer tracker"], "qualified": 3, "total": 4}


class Forsta:
    host = "se1.decipherinc.com"

    def __init__(self, records):
        self.records = records

    def surveys(self):
        return [SURVEY]

    def survey_datamap(self, path):
        return TRACKER

    def survey_data(self, path, **params):
        return self.records


RECORDS = [person(1), person(2, D2="3", q1r2="1"), person(3, D2="1"), person(4, status="1")]


def test_a_tracker_wave_gets_the_teams_line_by_line_rows(csi_db):
    sid = forsta_etl.load_survey(Forsta(RECORDS), "selfserve/58f/260907")
    df = tracker_line.read([sid])
    assert len(df) == 3                                                   # qualified only
    first = df.iloc[0]
    assert first["Month"] == "2026-09-01" and first["date"] == "09/29/2026 10:01"
    assert first["Activities: Met up with friends or family locally"] == "Met up with friends or family locally"
    assert pd.isna(first["Activities: Gone to a bar"])                    # unselected = blank, as the team has it
    assert (first["Household Situation"], first["Gender"], first["Age"], first["State"]) == ("About the same", "Female", 34, "CA")
    assert (first["Age Range"], first["Generation"]) == ("30-44", "Millenial")      # the team's spelling
    assert first["start_date"] == "09/29/2026 09:51"
    older = df.set_index("date").loc["09/28/2026 10:02"]
    assert (older["Age"], older["Age Range"], older["Generation"]) == ("70 or more", "over 60", "Boomer")
    under = df.set_index("date").loc["09/29/2026 10:03"]
    assert under["Age"] == "Under 18" and pd.isna(under["Age Range"])   # never banded "over 60"
    assert "session" not in df.columns and "RID" not in df.columns


def test_the_columns_follow_the_teams_order(csi_db):
    sid = forsta_etl.load_survey(Forsta(RECORDS), "selfserve/58f/260907")
    cols = list(tracker_line.read([sid]).columns)
    assert cols[:4] == ["Month", "date", "Activities: Met up with friends or family locally", "Activities: Gone to a bar"]
    assert cols[-2:] == ["Age Range", "Generation"]


def test_a_reload_replaces_the_lines(csi_db):
    sid = forsta_etl.load_survey(Forsta(RECORDS), "selfserve/58f/260907")
    forsta_etl.load_survey(Forsta(RECORDS[:2]), "selfserve/58f/260907")
    assert len(tracker_line.read([sid])) == 2


def test_waves_outside_the_tracker_get_no_lines(csi_db):
    adhoc = dict(SURVEY, title="Zebra - Elo", tags=[])
    forsta = Forsta(RECORDS)
    forsta.surveys = lambda: [adhoc]
    sid = forsta_etl.load_survey(forsta, "selfserve/58f/260907")
    assert tracker_line.read([sid]).empty


def test_comparing_with_the_teams_file_finds_every_difference(csi_db):
    sid = forsta_etl.load_survey(Forsta(RECORDS), "selfserve/58f/260907")
    ours = tracker_line.read([sid])
    team = ours.copy()
    team["Month"] = pd.to_datetime(team["Month"])                      # the team file holds real dates
    assert tracker_line.compare(team, ours) == []
    team.loc[0, "Gender"] = "Male"
    team = pd.concat([team, team.iloc[[0]]])
    problems = tracker_line.compare(team, ours)
    assert any("Gender" in p for p in problems) and any("respondents" in p for p in problems)


def test_the_scheduled_run_stops_before_loading_into_an_old_schema(csi_db):
    import importlib
    weekly = importlib.import_module("scripts.weekly_forsta")
    with csi_db.begin() as conn:
        conn.exec_driver_sql("DROP TABLE cip_tracker_line")

    class Ok(Forsta):
        def whoami(self):
            return {}
    assert weekly.run(Ok(RECORDS)) == 2
    with csi_db.connect() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM cip_survey").scalar() == 0
