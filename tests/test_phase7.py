"""Phase 7: the Forsta API adapter — proven against the Excel path, since the
key on file is disabled. See docs/superpowers/plans/2026-10-01-forsta-api-phase7.md.
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


def test_an_api_record_becomes_the_label_record_the_loader_proves():
    questions = forsta_api.questions_from_datamap(DATAMAP)
    rec = forsta_api.to_record({"record": 7, "uuid": "u7", "status": 3, "date": "09/21/2026 10:05",
                                "hq1": 2, "q2r1": 1, "q2r2": 0, "q5r1": 3, "q5r2": None, "d2": 34,
                                "q9": "More sales"}, questions)
    assert rec["status"] == "Qualified"
    assert (rec["hq1"], rec["q2r1"], rec["q2r2"], rec["q5r1"]) == ("No", "Met up with friends",
                                                                   "NO TO: Gone to a bar", "Positive")
    assert "q5r2" not in rec and rec["d2"] == 34 and rec["q9"] == "More sales"
    assert (rec["record"], rec["uuid"], rec["date"]) == (7, "u7", "09/21/2026 10:05")


def test_an_unknown_code_or_status_is_kept_not_invented():
    questions = forsta_api.questions_from_datamap(DATAMAP)
    rec = forsta_api.to_record({"record": 1, "status": 9, "hq1": 7}, questions)
    assert rec["status"] == "9" and rec["hq1"] == "7"


import os

import pytest
import sqlalchemy as sa

from etl import excel_parsers as xp
from etl import run_pipeline

RAW = os.getenv("CSI_TEST_RAW")


class FakeClient:
    """Stands in for ForstaClient: serves a datamap and records, like the API."""
    host, survey_path, base_url = "se1.decipherinc.com", "selfserve/58f/260908", "https://fake/api/v1"

    def __init__(self, datamap, records):
        self._datamap, self._records = datamap, records

    def whoami(self):
        return {"user": "fake"}

    def datamap(self, fmt="json"):
        return self._datamap

    def iter_records(self, **kwargs):
        yield from self._records


def api_shaped(raw_path):
    """The 09/21/26 export re-expressed as Forsta API JSON: codes, not labels."""
    questions = xp.parse_datamap(raw_path)
    kinds = {"multi": "multiple", "single": "single", "grid_single": "single", "numeric": "number"}
    datamap = {"questions": [{
        "qlabel": q.qcode, "qtitle": q.qtext, "type": kinds.get(q.qtype, "text"),
        "variables": [{"label": code, "rowTitle": label} for code, label in q.rows] or [{"label": q.qcode}],
        "values": [{"value": c, "title": t} for c, t in q.options]} for q in questions]}
    coded, status = {}, {v: k for k, v in forsta_api.STATUS.items()}
    for q in questions:
        options = {t.lower(): c for c, t in q.options}
        for code in [c for c, _ in q.rows] or [q.qcode]:
            coded[code] = (q.qtype, options)
    records = []
    for rec in xp.iter_raw_records(raw_path):
        out = {}
        for key, value in rec.items():
            kind = coded.get(key)
            if value is None or kind is None or kind[0] not in ("multi", "single", "grid_single"):
                out[key] = status.get(value, value) if key == "status" else value
            elif kind[0] == "multi":
                out[key] = 0 if str(value).startswith(xp.NO_TO) else 1
            else:
                out[key] = kind[1].get(xp.clean_text(value).lower(), value)
        records.append(out)
    return datamap, records


def answer_set(engine, sid):
    with engine.connect() as conn:
        return set(conn.execute(sa.text(
            "SELECT r.forsta_uuid, f.field_name, a.value_code FROM csi_answer a JOIN csi_field f ON f.field_id = a.field_id"
            " JOIN csi_respondent r ON r.respondent_id = a.respondent_id WHERE a.survey_id = :s"), {"s": sid}).all())


@pytest.mark.skipif(not RAW, reason="set CSI_TEST_RAW")
def test_an_api_wave_equals_the_excel_wave_answer_for_answer(csi_db):
    run_pipeline.ingest_excel(RAW, None, "2026-09-21")
    datamap, records = api_shaped(RAW)
    api_sid = run_pipeline.ingest_api("2026-09-21-api", client=FakeClient(datamap, records), full=True)
    with csi_db.connect() as conn:
        excel_sid = conn.execute(sa.text("SELECT survey_id FROM csi_survey WHERE wave_label = '2026-09-21'")).scalar()
        qualified = [conn.execute(sa.text("SELECT COUNT(*) FROM csi_respondent WHERE survey_id = :s AND is_qualified = 1"),
                                  {"s": s}).scalar() for s in (excel_sid, api_sid)]
    assert qualified[0] == qualified[1] > 0
    excel, api = answer_set(csi_db, excel_sid), answer_set(csi_db, api_sid)
    assert len(api) > 10_000 and api == excel


def test_the_wave_is_the_monday_of_the_first_fielding_day():
    assert run_pipeline.wave_from_records([{"date": "09/23/2026 10:05"}, {"date": "09/22/2026 08:00"}]) == "2026-09-21"
    assert run_pipeline.wave_from_records([{"date": "2026-09-28 07:00:00"}]) == "2026-09-28"


RECORDS = [{"record": n, "uuid": f"u{n}", "status": 3, "date": f"09/2{n}/2026 10:0{n}",
            "hq1": 1 + n % 2, "q2r1": n % 2, "q2r2": 1, "q5r1": 1 + n % 3, "d2": 20 + n} for n in range(1, 6)]


def test_an_api_load_verifies_itself_against_the_payload(csi_db):
    sid = run_pipeline.ingest_api("auto", client=FakeClient(DATAMAP, RECORDS), full=True)
    with csi_db.connect() as conn:
        assert conn.execute(sa.text("SELECT wave_label FROM csi_survey WHERE survey_id = :s"), {"s": sid}).scalar() == "2026-09-21"
    assert run_pipeline.verify_api_load(sid, [forsta_api.to_record(r, forsta_api.questions_from_datamap(DATAMAP))
                                              for r in RECORDS]) == []


def test_a_short_load_is_caught(csi_db, monkeypatch):
    real = run_pipeline._load_one_respondent
    monkeypatch.setattr(run_pipeline, "_load_one_respondent",
                        lambda sid, rec, *a: 0 if rec.get("uuid") == "u3" else real(sid, rec, *a))
    with pytest.raises(RuntimeError, match="does not match"):
        run_pipeline.ingest_api("auto", client=FakeClient(DATAMAP, RECORDS), full=True)


def test_the_weekly_run_reports_each_outcome_by_exit_code(csi_db, monkeypatch):
    import importlib
    weekly = importlib.import_module("scripts.weekly_forsta")
    assert weekly.run(FakeClient(DATAMAP, RECORDS)) == 0
    from etl.forsta_client import ForstaAuthError

    class Rejected(FakeClient):
        def whoami(self):
            raise ForstaAuthError("401 API user account is not valid: account disabled")
    assert weekly.run(Rejected(DATAMAP, RECORDS)) == 2


# ── final-review fixes ─────────────────────────────────────────────────────
def test_a_second_incremental_run_verifies_only_what_it_brought(csi_db):
    first = RECORDS[:3]
    sid = run_pipeline.ingest_api("2026-09-21", client=FakeClient(DATAMAP, first), full=True)
    later = RECORDS[:3] + [dict(RECORDS[3], date=RECORDS[2]["date"])]      # same minute as the watermark
    assert run_pipeline.ingest_api("2026-09-21", client=FakeClient(DATAMAP, later)) == sid
    with csi_db.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM csi_respondent WHERE survey_id = :s"), {"s": sid}).scalar() == 4


def test_a_failed_verification_leaves_the_wave_marked_failed_and_out_of_the_lists(csi_db, monkeypatch):
    from app.data import repository
    real = run_pipeline._load_one_respondent
    monkeypatch.setattr(run_pipeline, "_load_one_respondent",
                        lambda sid, rec, *a: 0 if rec.get("uuid") == "u3" else real(sid, rec, *a))
    with pytest.raises(RuntimeError):
        run_pipeline.ingest_api("2026-09-21", client=FakeClient(DATAMAP, RECORDS), full=True)
    with csi_db.connect() as conn:
        assert conn.execute(sa.text("SELECT load_status FROM csi_survey WHERE wave_label = '2026-09-21'")).scalar() == "failed"
    assert "2026-09-21" not in set(getattr(repository.list_surveys, "__wrapped__", repository.list_surveys)().wave_label)


def test_variables_named_apart_from_their_question_still_load(csi_db):
    datamap = {"questions": DATAMAP["questions"] + [
        {"qlabel": "q7", "qtitle": "Pick one", "type": "single", "variables": [{"label": "q7r1", "rowTitle": "Pick one"}],
         "values": [{"value": 1, "title": "A"}, {"value": 2, "title": "B"}]},
        {"qlabel": "q10", "qtitle": "How many?", "type": "number",
         "variables": [{"label": "q10r1", "rowTitle": "Shoes"}, {"label": "q10r2", "rowTitle": "Bags"}]}]}
    records = [dict(r, q7r1=2, q10r1=3, q10r2=1) for r in RECORDS]
    sid = run_pipeline.ingest_api("2026-09-21", client=FakeClient(datamap, records), full=True)
    with csi_db.connect() as conn:
        counts = dict(conn.execute(sa.text("SELECT f.field_name, COUNT(*) FROM csi_answer a JOIN csi_field f"
                                           " ON f.field_id = a.field_id WHERE a.survey_id = :s GROUP BY f.field_name"), {"s": sid}).all())
    assert counts.get("q7r1") == 5 and counts.get("q10r1") == 5 and counts.get("q10r2") == 5


def test_float_codes_and_status_are_read_as_numbers():
    questions = forsta_api.questions_from_datamap(DATAMAP)
    rec = forsta_api.to_record({"record": 1, "status": "3.0", "hq1": 2.0, "q2r1": "1.0", "q2r2": " "}, questions)
    assert (rec["status"], rec["hq1"], rec["q2r1"]) == ("Qualified", "No", "Met up with friends") and "q2r2" not in rec
