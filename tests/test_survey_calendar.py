"""The survey calendar: what Forsta runs, when, and what each wave carries.

Facts from the 90 surveys the key can see (Oct 2026): the weekly tracker leads
with one of 12 retail sectors in a fixed rotation (each sector every 12 weeks),
adds recurring topics (tariffs + inflation, GLP-1, GenAI, financial health),
runs a holiday tracker weekly through the season, and annual studies and
client projects arrive as their own surveys.
"""
from __future__ import annotations

from datetime import date

import sqlalchemy as sa

from etl import forsta_etl, survey_calendar


def modules(title, questions=()):
    return {(m["code"], m["kind"], m["is_lead"]) for m in survey_calendar.classify(title, questions)}


def test_a_tracker_title_gives_its_lead_sector_topics_and_events():
    got = modules("Shopping and Spending - inc Drugstore/Pharmacy + Returns + Inflation + Tariffs")
    assert ("DRUGSTORE", "sector", True) in got and ("TARIFFS_INFLATION", "topic", False) in got
    assert ("RETURNS", "event", False) in got


def test_the_holiday_tracker_is_found_by_its_question_even_when_the_title_misses_it():
    title = "Shopping and Spending - inc Beauty + Holiday + Inflation + Tariffs"
    assert ("HOLIDAY_TRACKER", "seasonal", False) not in modules(title)
    assert ("HOLIDAY_TRACKER", "seasonal", False) in modules(
        title, ["Now we would like to focus on your holiday shopping. What is the current status of your holiday shopping?"])
    assert ("HOLIDAY_TRACKER", "seasonal", False) in modules("Shopping and Spending - inc Luxury + Holiday tracker + Big Deal Days Retro")


def test_the_rotation_predicts_the_next_lead_sector():
    order = [s["code"] for s in survey_calendar.load_config()["sectors"]]
    assert len(order) == 12 and order.index("HOME_IMPROVEMENT") == order.index("HOME_FURNISHINGS") + 1
    assert survey_calendar.next_sector("FOOTWEAR") == "DRUGSTORE"


def test_the_season_of_a_holiday_wave():
    assert survey_calendar.season(date(2026, 9, 28)) == 2026 and survey_calendar.season(date(2026, 1, 5)) == 2025


SURVEYS = [
    {"path": "selfserve/58f/251000", "title": "Shopping and Spending - inc Luxury + Holiday tracker + Big Deal Days Retro",
     "state": "closed", "hibernated": True, "tags": ["Weekly consumer tracker"], "dateLaunched": "2025-10-13T12:30:00Z"},
    {"path": "selfserve/58f/251002", "title": "Shopping and Spending - inc Dept Stores + Holiday Tracking + GLP1",
     "state": "closed", "hibernated": True, "tags": ["Weekly consumer tracker"], "dateLaunched": "2025-10-20T12:30:00Z"},
    {"path": "selfserve/58f/260907", "title": "Shopping and Spending - inc Beauty + Holiday + Inflation + Tariffs",
     "state": "closed", "hibernated": False, "tags": ["Weekly consumer tracker"], "dateLaunched": "2026-09-28T12:30:00Z",
     "closedDate": "2026-09-29T06:00:00Z", "qualified": 2, "total": 2},
    {"path": "selfserve/58f/260908", "title": "Shopping and Spending - inc Home Furnishings + Holiday Tracker + GenAI",
     "state": "closed", "hibernated": False, "tags": ["Weekly consumer tracker"], "dateLaunched": "2026-10-05T12:30:00Z"},
    {"path": "selfserve/58f/260905", "title": "Holiday Shopping 2026", "state": "closed", "hibernated": False,
     "tags": ["holiday", "annual tracker"], "dateLaunched": "2026-09-10T12:00:00Z"},
]
XM3 = {"questions": [{"qlabel": "XM3", "qtitle": "What is the current status of your holiday shopping?", "type": "single",
                      "variables": [{"label": "XM3"}], "values": [{"value": 1, "title": "Not yet started"}]}]}


class Forsta:
    host = "se1.decipherinc.com"

    def surveys(self):
        return SURVEYS

    def survey_datamap(self, path):
        return XM3

    def survey_data(self, path, **params):
        return [{"record": "1", "uuid": "u1", "status": "3", "date": "09/28/2026 10:00", "XM3": "1"}]


def calendar(engine):
    with engine.connect() as conn:
        return {(r.forsta_path[-6:], r.module_code): (r.kind, r.is_lead, r.season, r.series_wave_no) for r in conn.execute(
            sa.text("SELECT forsta_path, module_code, kind, is_lead, season, series_wave_no FROM cip_wave_module"))}


def test_discovery_writes_the_calendar_and_numbers_each_holiday_season(csi_db):
    forsta_etl.discover(Forsta())
    cal = calendar(csi_db)
    assert cal[("251000", "LUXURY")][:2] == ("sector", 1)
    assert cal[("251000", "HOLIDAY_TRACKER")] == ("seasonal", 0, 2025, 1)
    assert cal[("251002", "HOLIDAY_TRACKER")] == ("seasonal", 0, 2025, 2)
    assert cal[("260908", "HOLIDAY_TRACKER")][2:] == (2026, 1)            # titles alone: Sep 28 is not yet known
    assert cal[("260905", "HOLIDAY_SHOPPING")][:1] == ("annual",)


def test_loading_a_wave_corrects_the_calendar_from_its_questions(csi_db):
    forsta_etl.discover(Forsta())
    forsta_etl.load_survey(Forsta(), "selfserve/58f/260907")
    cal = calendar(csi_db)
    assert cal[("260907", "HOLIDAY_TRACKER")][2:] == (2026, 1)
    assert cal[("260908", "HOLIDAY_TRACKER")][2:] == (2026, 2)            # "Wave 2 · week of Oct 5" in the team's databank
