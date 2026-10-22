"""The team's saved views, metric alerts and audiences (api/team.py)."""
from datetime import date

import sqlalchemy as sa

from api import team
from etl import forsta_etl, serving
from tests.test_serving import seed


def test_an_alert_fires_once_when_its_answer_moves_significantly_and_never_on_a_reused_code(csi_db):
    with csi_db.begin() as conn:
        seed(conn, 266, date(2026, 10, 5), qualified=400, xm1_yes=120, xm1_base=400)
        seed(conn, 412, date(2026, 10, 12), qualified=400, xm1_yes=200, xm1_base=400)     # 30 % → 50 %
        seed(conn, 500, date(2026, 10, 19), qualified=400, xm1_yes=300, xm1_base=400,
             qtext="Did you buy footwear this week?")                                     # XM1 reused for another question
    for sid in (266, 412, 500):
        serving.build_wave(sid)
    with csi_db.begin() as conn:
        conn.execute(sa.text("INSERT INTO cip_metric_alert (name, survey_family, study_type, qcode, qtext, item_label, option_code,"
                             " answer_label, created_by, last_checked) SELECT 'Holiday buyers', 'CSI-US', 'tracker', 'XM1', qtext, '', 1,"
                             " 'Yes', 'Analyst', 266 FROM cip_question WHERE survey_id = 266"))
    first = team.due_alerts([412, 500])
    assert len(first) == 1 and "50.0%" in first[0] and "up 20.0 pts from 30.0%" in first[0]
    assert team.due_alerts([412, 500]) == []                    # each wave is judged once


def test_an_audience_is_counted_from_the_cube_rows_and_hides_groups_under_30(csi_db):
    from tests.test_forsta_etl import FakeForsta
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    with csi_db.connect() as conn:   # an audience of the people who gave a question's first answer
        qcode, item, code = conn.execute(sa.text("SELECT qcode, item_label, option_code FROM srv_result WHERE survey_id = :s"
                                                 " AND dim = 'total' AND n > 0 ORDER BY qcode, sort_order LIMIT 1"), {"s": sid}).one()
    out = team.audience(sid, qcode, {"cuts": {}, "answers": [{"qcode": qcode, "qtext": "", "item_label": item, "option_code": code, "label": "x"}]})
    assert out["rows"] and out["skipped"] == [] and all(r[3] is None and r[2] < 30 for r in out["rows"])   # 4 people: no figures
    gone = team.audience(sid, qcode, {"cuts": {}, "answers": [{"qcode": "NOPE", "qtext": "", "item_label": "", "option_code": 1, "label": "Not asked"}]})
    assert gone["skipped"] == ["Not asked"]


def test_team_views_need_a_name_a_screen_and_a_person(csi_db):
    import asyncio
    import pytest
    from fastapi import HTTPException

    class Body:
        def __init__(self, data):
            self.data = data

        async def json(self):
            return self.data
    assert asyncio.run(team.save_view(Body({"name": "Prime Day vs last year", "url": "/w/415/compare/q1?pick=event", "by": "Saeed"})))["view_id"]
    assert [v["name"] for v in team.views()] == ["Prime Day vs last year"]
    with pytest.raises(HTTPException):
        asyncio.run(team.save_view(Body({"name": "x", "url": "https://elsewhere", "by": "Saeed"})))
