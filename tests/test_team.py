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
    assert len(first) == 1 and "50.0%" in first[0][0] and "up 20.0 pts from 30.0%" in first[0][0]
    assert team.due_alerts([412, 500]) == []                    # each wave is judged once


def test_an_audience_is_counted_from_the_cube_rows_and_shown_however_small(csi_db):
    from tests.test_forsta_etl import FakeForsta
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    with csi_db.connect() as conn:   # an audience of the people who gave a question's first answer
        qcode, item, code = conn.execute(sa.text("SELECT qcode, item_label, option_code FROM srv_result WHERE survey_id = :s"
                                                 " AND dim = 'total' AND n > 0 ORDER BY qcode, sort_order LIMIT 1"), {"s": sid}).one()
    out = team.audience(sid, qcode, {"cuts": {}, "answers": [{"qcode": qcode, "qtext": "", "item_label": item, "option_code": code, "label": "x"}]})
    assert out["rows"] and out["skipped"] == [] and all(r[2] is not None for r in out["rows"])   # 4 people: figures shown
    gone = team.audience(sid, qcode, {"cuts": {}, "answers": [{"qcode": "NOPE", "qtext": "", "item_label": "", "option_code": 1, "label": "Not asked"}]})
    assert gone["skipped"] == ["Not asked"]
    assert all(len(r) == 8 for r in out["rows"])   # the index rides last


def test_an_index_says_how_much_more_likely_the_audience_is_than_everyone():
    every, aud = 0b1111111111, 0b11111   # 10 people answered; the audience is the first 5
    question = {"rows": [[1, 0, "Walmart", None, None]], "bits": {(0, 0): every, (1, 0): 0b10111}}
    row = team._compare(question, aud)[0]   # 4 of the audience chose it, 4 of all 10: 80 % against 40 %
    assert row[3] == 80.0 and row[8] == 40.0 and row[7] == 200


class Asked:   # a signed-in request: api/main.user puts the email on request.state
    def __init__(self, email, body=None):
        self.state = type("State", (), {"email": email})()
        self.body = body or {}

    async def json(self):
        return self.body


def test_a_board_keeps_tables_as_pinned_takes_comments_and_downloads_as_one_deck(csi_db):
    import asyncio
    import io
    from fastapi import HTTPException
    from pptx import Presentation
    spec = {"name": "XM1-2026-10-19", "header": ["Answer", "Total %"], "rows": [["Yes", 55.0], ["No", 45.0]],
            "notes": ["XM1: Did you shop?", "Wave 2026-10-19"]}
    run = asyncio.run
    board_id = run(team.new_board(Asked("ana@x", {"name": "Holiday read-out"})))["board_id"]
    item = run(team.pin(board_id, Asked("ana@x", {"title": "Shopping", "url": "/w/415/questions/XM1", "spec": spec})))["item_id"]
    run(team.comment(item, Asked("ben@x", {"body": "Up 5 pts, check next week"})))
    opened = team.open_board(board_id)
    assert opened["items"][0]["spec"]["rows"] == [["Yes", 55.0], ["No", 45.0]] and opened["items"][0]["data_version"]
    assert opened["items"][0]["comments"][0]["author"] == "ben@x"
    deck = Presentation(io.BytesIO(team.deck(board_id).body))
    assert len(deck.slides) == 2                                      # cover + the pinned table
    try:
        team.unpin(item, Asked("ben@x"))                              # only who pinned it removes it
        raise AssertionError("ben removed ana's item")
    except HTTPException as exc:
        assert exc.status_code == 403
    team.drop_board(board_id, Asked("ana@x"))
    assert team.boards() == []


def test_team_views_need_a_name_a_screen_and_only_their_owner_removes_them(csi_db):
    import asyncio
    import pytest
    from fastapi import HTTPException
    view = asyncio.run(team.save_view(Asked("ana@x", {"name": "Prime Day vs last year", "url": "/w/415/compare/q1?pick=event", "by": "Ana"})))
    assert [v["name"] for v in team.views()] == ["Prime Day vs last year"]
    with pytest.raises(HTTPException):
        asyncio.run(team.save_view(Asked("ana@x", {"name": "x", "url": "https://elsewhere", "by": "Ana"})))
    with pytest.raises(HTTPException) as refused:
        team.drop_view(view["view_id"], Asked("ben@x"))
    assert refused.value.status_code == 403
    team.drop_view(view["view_id"], Asked("ana@x"))
    assert team.views() == []
