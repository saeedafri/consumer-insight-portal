"""Forsta's own record of each survey (etl/fieldwork.py): what the admins' Fieldwork screen and the Survey preview show,
checked against Forsta's answer for survey 261003 (the 2 Nov 2026 wave; tests/fixtures/fieldwork_261003.json, its
warning events left out); that it is kept in the database (cip_forsta_record); the rules that keep collecting from
ever stopping a load; and that CIP only ever reads from Forsta."""
import gzip
import json
from pathlib import Path

from etl import fieldwork, publish

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "fieldwork_261003.json").read_text())


def test_the_survey_line_reads_forstas_funnel():
    line = fieldwork.summary(FIXTURE, {"survey_id": 532, "wave_date": "2026-11-02", "title": "Weekly"})
    assert (line["opened"], line["qualified"], line["terminated"], line["overquota"], line["partial"]) == (1193, 403, 32, 609, 149)
    assert line["incidence"] == 33.8 and line["median_minutes"] == 6.0          # 403 / 1193; Forsta's median, 361 s
    assert line["pages"][0][:5] == ["q1", "Which, if any, of these have you done in the past two weeks?", 1193, 1124, 69]
    assert line["warnings"]["blocks"] == 34 and line["survey_id"] == 532
    timeline = {"audit_log": {"data": [{"created_on": "2026-11-02T13:25:06Z", "user_email": "a@coresight.com", "event": "State set to live"},
                                       {"created_on": "2026-11-02T13:30:00Z", "user_email": "b@coresight.com", "event": "API: GET rh/surveys in 9 ms"}]}}
    assert fieldwork.summary({**FIXTURE, **timeline}, None)["timeline"] == [["2026-11-02T13:25:06Z", "a@coresight.com", "State set to live"]]


XML = """<survey xmlns:ss="http://decipherinc.com/ss" name="Survey">
  <term label="te1" cond="timeSpent() &lt; 25">Speeder</term>
  <radio label="XM1"><title>Holiday shopping?</title><row label="r1" cond="1">Yes</row></radio>
  <block label="holiday" cond="XM1.r1">
    <checkbox label="XM1A" cond="not(G5.r14)"><title>Which categories?</title></checkbox>
    <text label="XM9"><title>Why?</title></text>
  </block>
</survey>"""


def test_the_questionnaires_conditions_come_from_survey_xml_with_their_blocks():
    found = fieldwork.logic(XML)
    assert found["questions"] == {"XM1A": "(XM1.r1) and (not(G5.r14))", "XM9": "XM1.r1"}   # XM1 always shown
    assert found["terms"] == [["te1", "timeSpent() < 25", "Speeder"]]


def test_records_are_kept_in_the_database_and_published_for_the_screens(csi_db, tmp_path):
    fieldwork.store("selfserve/58f/261003", {**{k: FIXTURE[k] for k in ("survey", "completions", "dropouts", "warnings")},
                                             "survey_xml": XML.encode()})
    fieldwork.store("", {"archived": [
        {"survey_path": "selfserve/58f/250600", "name": "Old", "archived_at": "2026-01-01T00:00:00Z", "delete_at": "2027-01-01T00:00:00Z"},
        {"survey_path": "selfserve/58f/250600", "name": "Old", "archived_at": "2026-02-05T00:00:00Z", "delete_at": "2027-02-05T00:00:00Z"},
        {"survey_path": "selfserve/58f/test", "name": "Test", "archived_at": "2026-03-01T00:00:00Z", "delete_at": "2027-03-01T00:00:00Z"}],
        "historical": ["selfserve/58f/261003", "selfserve/58f/unloaded"], "autoclose_planned": [{"survey": "x"}],
        "retention": {"86": {"server_delete_days": 365}}})
    kept = fieldwork.records()
    assert kept["selfserve/58f/261003"]["survey_xml"] == XML and kept[""]["historical"][1] == "selfserve/58f/unloaded"
    out = tmp_path / "out"
    (out / "api/v1").mkdir(parents=True)
    (out / "api/v1/waves.json.gz").write_bytes(gzip.compress(json.dumps([
        {"survey_id": 532, "source_ref": "selfserve/58f/261003", "wave_date": "2026-11-02", "title": "Weekly"},
        {"survey_id": 90, "source_ref": "selfserve/58f/250600", "wave_date": "2025-06-02", "title": "Old"}]).encode()))
    assert fieldwork.publish(out, publish.write) > 0
    data = json.loads(gzip.decompress((out / "api/v1/admin/fieldwork.json.gz").read_bytes()))
    line = data["surveys"][0]
    assert line["survey_id"] == 532 and line["qualified"] == 403 and line["conditions"] == 2
    assert [(a["path"], a["delete_at"][:10], a["held"]) for a in data["archive"]] == [
        ("selfserve/58f/250600", "2027-02-05", True), ("selfserve/58f/test", "2027-03-01", False)]
    assert [n["path"] for n in data["not_loaded"]] == ["selfserve/58f/unloaded"]
    assert data["planned"] == [{"kind": "autoclose_planned", "items": [{"survey": "x"}]}] and data["retention"] == [{"server_delete_days": 365}]
    logic = json.loads(gzip.decompress((out / "api/v1/waves/532/logic.json.gz").read_bytes()))
    assert logic["questions"]["XM9"] == "XM1.r1"


def test_a_hibernated_survey_is_not_woken_and_a_failure_never_stops_the_run(csi_db, monkeypatch):
    monkeypatch.setattr(fieldwork, "due", lambda loaded: loaded)
    asked = []

    class Forsta:
        def read_json(self, endpoint, **params):
            if endpoint == "rh/companies":
                return [{"id": 86}]
            if endpoint == "hibernation/status":
                return {"status": "hibernated" if params["survey"] == "asleep" else "restored"}
            asked.append(endpoint)
            if endpoint.startswith("rh/surveys/broken"):
                raise RuntimeError("Forsta 500")
            return {}

        def survey_file(self, path, name):
            return b"<survey/>"

    assert fieldwork.collect(Forsta(), ["asleep", "broken", "fine"]) == ["asleep", "fine"]
    assert not any("asleep" in e for e in asked if not e.startswith("rh/surveys/asleep"))     # only its record: not woken
    kept = fieldwork.records()
    assert set(kept["asleep"]) == {"path", "fetched_at", "survey", "hibernation"}
    assert "survey_xml" in kept["fine"] and "retention" in kept[""]


def test_the_home_pages_figures_are_counts_and_dates_only(tmp_path):
    (tmp_path / "api/v1/waves/2").mkdir(parents=True)
    waves = [{"survey_id": 1, "wave_date": "2026-10-19", "study_type": "tracker", "qualified_n": 400, "modules": []},
             {"survey_id": 2, "wave_date": "2026-10-26", "study_type": "tracker", "qualified_n": 404, "modules": ["Holiday tracker"]},
             {"survey_id": 3, "wave_date": "2026-03-01", "study_type": "annual", "qualified_n": 2000}]
    (tmp_path / "api/v1/waves.json.gz").write_bytes(gzip.compress(json.dumps(waves).encode()))
    (tmp_path / "api/v1/waves/2/book.json.gz").write_bytes(gzip.compress(json.dumps({"questions": [{}, {}, {}]}).encode()))
    facts = publish.site_facts(tmp_path)
    assert (facts["waves"], facts["responses"], facts["trackers"], facts["annual"]) == (3, 2804, 2, 1)
    assert facts["latestLabel"] == "Week of October 26, 2026" and facts["latestN"] == 404 and facts["questions"] == 3
    assert facts["trackerDates"] == ["2026-10-19", "2026-10-26"] and facts["latestTopics"] == ["Holiday tracker"]


def test_cip_only_ever_reads_from_forsta():
    """Forsta stays read-only for CIP: its one client sends GET and nothing else (no POST, PUT, PATCH or DELETE), and
    every Forsta call in the code goes through that client. Fails if anyone adds a call that could change a survey."""
    import re
    root = Path(__file__).resolve().parents[1]
    client = (root / "etl/forsta_client.py").read_text()
    assert re.findall(r"session\.(\w+)\(", client) == ["get"]
    assert not re.search(r"\.(post|put|patch|delete)\(|method\s*=", client)
    for source in [*root.glob("etl/*.py"), *root.glob("api/*.py"), *root.glob("scripts/*.py"), *root.glob("shared/**/*.py")]:
        text = source.read_text()
        calls_http = any(lib in text for lib in ("import requests", "httpx", "urllib.request", "http.client"))
        if calls_http and ("decipherinc" in text or "x-apikey" in text.lower()):
            assert source.name in ("forsta_client.py", "config.py"), f"{source} talks to Forsta outside the client"
