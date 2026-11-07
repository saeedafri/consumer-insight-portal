"""Forsta's fieldwork record (etl/fieldwork.py): what the admins' Fieldwork screen shows, checked against Forsta's own
answer for survey 261003 (the 2 Nov 2026 wave; tests/fixtures/fieldwork_261003.json, its warning events left out),
and the rules that keep collecting from ever stopping a load."""
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


def test_publish_keeps_one_line_per_survey_and_the_latest_archiving(tmp_path, monkeypatch):
    kept = tmp_path / "kept"
    monkeypatch.setattr(fieldwork, "ROOT", kept)
    fieldwork.save(fieldwork.file_of(FIXTURE["path"]), FIXTURE)
    fieldwork.save(kept / "archived.json.gz", [
        {"survey_path": "selfserve/58f/250600", "name": "Old", "archived_at": "2026-01-01T00:00:00Z", "delete_at": "2027-01-01T00:00:00Z"},
        {"survey_path": "selfserve/58f/250600", "name": "Old", "archived_at": "2026-02-05T00:00:00Z", "delete_at": "2027-02-05T00:00:00Z"},
        {"survey_path": "selfserve/58f/test", "name": "Test", "archived_at": "2026-03-01T00:00:00Z", "delete_at": "2027-03-01T00:00:00Z"}])
    out = tmp_path / "out"
    (out / "api/v1").mkdir(parents=True)
    (out / "api/v1/waves.json.gz").write_bytes(gzip.compress(json.dumps([
        {"survey_id": 532, "source_ref": "selfserve/58f/261003", "wave_date": "2026-11-02", "title": "Weekly"},
        {"survey_id": 90, "source_ref": "selfserve/58f/250600", "wave_date": "2025-06-02", "title": "Old"}]).encode()))
    assert fieldwork.publish(out, publish.write) > 0
    data = json.loads(gzip.decompress((out / "api/v1/admin/fieldwork.json.gz").read_bytes()))
    assert [s["survey_id"] for s in data["surveys"]] == [532]
    assert [(a["path"], a["delete_at"][:10], a["held"]) for a in data["archive"]] == [
        ("selfserve/58f/250600", "2027-02-05", True), ("selfserve/58f/test", "2027-03-01", False)]


def test_a_hibernated_survey_is_not_woken_and_a_failure_never_stops_the_run(tmp_path, monkeypatch):
    monkeypatch.setattr(fieldwork, "ROOT", tmp_path)
    monkeypatch.setattr(fieldwork, "due", lambda loaded: loaded)
    asked = []

    class Forsta:
        def archived_surveys(self): return []
        def survey_info(self, path): return {"title": path}
        def hibernation(self, path): return "hibernated" if path == "asleep" else "restored"
        def survey_completions(self, path):
            asked.append(path)
            if path == "broken":
                raise RuntimeError("Forsta 500")
            return {}
        def survey_dropouts(self, path): return {}
        def survey_warnings(self, path): return {}

    assert fieldwork.collect(Forsta(), ["asleep", "broken", "fine"]) == ["asleep", "fine"]
    assert asked == ["broken", "fine"]                                       # the hibernated one is never asked
    assert fieldwork.read(fieldwork.file_of("asleep"))["hibernated"] is True


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
