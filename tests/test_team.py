"""The team's saved views, metric alerts and audiences (api/team.py)."""
from datetime import date

import sqlalchemy as sa

from api import team
from etl import forsta_etl, serving
from shared.core import access
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
                             " answer_label, created_by, owner_email, last_checked) SELECT 'Holiday buyers', 'CSI-US', 'tracker', 'XM1',"
                             " qtext, '', 1, 'Yes', 'Analyst', 'ana@coresight.com', 266 FROM cip_question WHERE survey_id = 266"))
    first = team.due_alerts([412, 500])
    assert len(first) == 1 and "50.0%" in first[0][0] and "up 20.0 pts from 30.0%" in first[0][0]
    assert team.due_alerts([412, 500]) == []                    # an alert fires once per wave


def test_an_alert_carries_no_typed_link_into_teams_and_names_its_signed_in_owner(csi_db):
    """The Teams card renders Markdown: a typed name could post a link to anywhere in Coresight's channel, "set by"
    anyone (security review, 15 Nov 2026)."""
    with csi_db.begin() as conn:
        seed(conn, 266, date(2026, 10, 5), qualified=400, xm1_yes=120, xm1_base=400)
        seed(conn, 412, date(2026, 10, 12), qualified=400, xm1_yes=200, xm1_base=400)
    for sid in (266, 412):
        serving.build_wave(sid)
    with csi_db.begin() as conn:
        conn.execute(sa.text("INSERT INTO cip_metric_alert (name, survey_family, study_type, qcode, qtext, item_label, option_code,"
                             " answer_label, created_by, owner_email, last_checked) SELECT '[Reset your password](https://evil.example)',"
                             " 'CSI-US', 'tracker', 'XM1', qtext, '', 1, 'Yes', 'The CEO', 'ana@coresight.com', 266 FROM cip_question"
                             " WHERE survey_id = 266"))
    message = team.due_alerts([412])[0][0]
    assert "[" not in message and "](" not in message and message.endswith("set by ana@coresight.com")


def test_a_wave_loaded_early_is_judged_again_on_its_final_reload_and_fires_once(csi_db, tmp_path, monkeypatch):
    """A tracker wave loads at 400 qualified while Forsta still has it open (srv_wave.in_field), then again once Forsta
    closes it: each alert is judged on the final data too and fires at most once per wave, and the Library's "last
    fired" shows it at once, though the API keeps the alerts list until the team stamp moves (15 Nov 2026)."""
    monkeypatch.setattr(team, "STAMP", tmp_path / "team.stamp")
    monkeypatch.setattr(team, "CACHE", {})
    with csi_db.begin() as conn:
        seed(conn, 266, date(2026, 10, 5), qualified=400, xm1_yes=120, xm1_base=400)
        seed(conn, 412, date(2026, 10, 12), qualified=400, xm1_yes=200, xm1_base=400)   # no field_end: still in field
        conn.execute(sa.text("INSERT INTO cip_metric_alert (name, survey_family, study_type, qcode, qtext, item_label, option_code,"
                             " answer_label, dim, dim_value, created_by, owner_email, last_checked) SELECT :name, 'CSI-US', 'tracker',"
                             " 'XM1', qtext, '', 1, 'Yes', :dim, :value, 'Analyst', 'ana@coresight.com', 266 FROM cip_question"
                             " WHERE survey_id = 266"),
                     [{"name": "All buyers", "dim": "total", "value": "Total"}, {"name": "Gen Z buyers", "dim": "generation", "value": "GenZ"}])
    for sid in (266, 412):
        serving.build_wave(sid)
    assert [a["last_fired"] for a in team.alerts()] == [None, None]   # the Library's list, now kept by the API
    early = team.due_alerts([412])   # Total 30 % → 50 % moves; Gen Z 12 → 20 of 40 not yet (p = 0.07)
    assert len(early) == 1 and "All buyers" in early[0][0]
    assert {a["name"]: a["last_fired"] for a in team.alerts()} == {"All buyers": 412, "Gen Z buyers": None}
    with csi_db.begin() as conn:     # Forsta closes it; the reload adds two Gen Z yeses: 22 of 42 (p = 0.04)
        conn.execute(sa.text("UPDATE cip_survey SET field_end = '2026-10-13 01:00:00' WHERE survey_id = 412"))
        conn.execute(sa.text("UPDATE cip_agg_cell SET base_n = 42 WHERE survey_id = 412 AND dim = 'generation'"))
        conn.execute(sa.text("UPDATE cip_agg_cell SET n = 22 WHERE survey_id = 412 AND dim = 'generation'"
                             " AND option_id IN (SELECT option_id FROM cip_option WHERE value_code = 1)"))
    serving.build_wave(412)
    final = team.due_alerts([412])   # All buyers fired on the early load: not again
    assert len(final) == 1 and "Gen Z buyers" in final[0][0] and "Yes among GenZ is 52.4%" in final[0][0]
    assert team.due_alerts([412]) == []


def test_an_alert_stays_quiet_once_whoever_set_it_lost_access(csi_db, monkeypatch):
    """The pipeline judges alerts with nobody signed in, so it checks each owner as the API would (access.profile, allows,
    sees): someone refused, without Alerts, or no longer seeing the study is never sent its figures (15 Nov 2026)."""
    monkeypatch.setattr(access, "rules", lambda: {
        "features": ["explorer", "alerts"], "unknown": "refuse", "staff": {"domains": ["coresight.com"], "tier": "full"},
        "tiers": {"full": {"features": "*", "study_types": "*"}, "basic": {"features": ["explorer"], "study_types": "*"}},
        "clients": {"acme": {"domains": ["acme.com"], "tier": "full"}, "zeta": {"domains": ["zeta.com"], "tier": "full"},
                    "lite": {"domains": ["lite.com"], "tier": "basic"}},
        "surveys": {"ids": {412: {"client": "acme", "visibility": "client"}}}})   # wave 412 is Acme's own study
    with csi_db.begin() as conn:
        seed(conn, 266, date(2026, 10, 5), qualified=400, xm1_yes=120, xm1_base=400)
        seed(conn, 412, date(2026, 10, 12), qualified=400, xm1_yes=200, xm1_base=400)   # 30 % → 50 %: every alert moves
        conn.execute(sa.text("INSERT INTO cip_metric_alert (name, survey_family, study_type, qcode, qtext, item_label, option_code,"
                             " answer_label, created_by, owner_email, notify_email, last_checked) SELECT :o, 'CSI-US', 'tracker', 'XM1',"
                             " qtext, '', 1, 'Yes', 'x', :o, :o, 266 FROM cip_question WHERE survey_id = 266"),
                     [{"o": owner} for owner in ("pat@acme.com", "gone@nowhere.org", "max@lite.com", "zed@zeta.com")])
    for sid in (266, 412):
        serving.build_wave(sid)
    assert [email for _, email in team.due_alerts([412])] == ["pat@acme.com"]


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


def test_team_saves_and_audiences_wait_on_the_database_off_the_event_loop(csi_db, monkeypatch):
    """The API runs one worker (deploy/start.sh): a save waiting on the database on the event loop held up every other
    request, so the save and audience routes reach it from a worker thread (15 Nov 2026)."""
    import asyncio
    import threading
    import pytest
    from fastapi import HTTPException
    threads, real = [], team.get_engine

    def engine(role):
        threads.append(threading.current_thread())
        return real(role)
    monkeypatch.setattr(team, "get_engine", engine)
    with csi_db.begin() as conn:
        seed(conn, 266, date(2026, 10, 5), qualified=400, xm1_yes=120, xm1_base=400)
    serving.build_wave(266)
    team.wave_of.cache_clear()   # so the audience route below looks its wave up
    spec = {"name": "XM1", "header": ["Answer", "Total %"], "rows": [["Yes", 30.0]], "notes": []}

    async def save_all():
        await team.save_view(Asked("ana@x", {"name": "Holiday", "url": "/w/266", "by": "Ana"}))
        await team.save_alert(Asked("ana@x", {"survey_id": 266, "qcode": "XM1", "option_code": 1, "answer_label": "Yes", "by": "Ana"}))
        await team.save_audience(Asked("ana@x", {"name": "Gen Z", "definition": {"cuts": {"generation": ["GenZ"]}}, "by": "Ana"}))
        board_id = (await team.new_board(Asked("ana@x", {"name": "Read-out"})))["board_id"]
        item_id = (await team.pin(board_id, Asked("ana@x", {"url": "/w/266", "spec": spec})))["item_id"]
        await team.comment(item_id, Asked("ana@x", {"body": "Check next week"}))
        with pytest.raises(HTTPException):
            await team.audience_view(999_999, Asked("ana@x", {"qcode": "XM1", "definition": {"cuts": {"generation": ["GenZ"]}}}))
    asyncio.run(save_all())   # its event loop runs on this thread
    assert threads and threading.current_thread() not in threads


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
