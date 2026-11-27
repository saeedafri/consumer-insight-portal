"""The Upload survey page's API (api/ingest.py): admins only, both Baidu files required, nothing written on a preview
or on a failed check, and a load followed by one background publish."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api import ingest
from api.main import app

FIXTURES = Path(__file__).resolve().parent / "fixtures"
RAW, TOPLINE = FIXTURES / "baidu_raw_2026-11-03.csv", FIXTURES / "baidu_topline_2026-11-05.xls"


def files(raw: Path = RAW, topline: Path = TOPLINE) -> dict:
    """As SharePoint downloads them ("….csv.aspx"): the extension before .aspx decides."""
    return {"raw": (raw.name + ".aspx", raw.read_bytes()), "topline": (topline.name + ".aspx", topline.read_bytes())}


@pytest.fixture()
def as_admin():
    app.dependency_overrides[ingest.INGEST_PAGE] = lambda: {"email": "boss@coresight.com", "role": "super_admin"}
    yield TestClient(app)
    app.dependency_overrides.pop(ingest.INGEST_PAGE, None)


def test_preview_checks_both_files_and_writes_nothing(csi_db, as_admin):
    answer = as_admin.post("/api/v1/admin/survey/preview", files=files())
    assert answer.status_code == 200, answer.text
    assert (answer.json()["wave"], answer.json()["matched"], answer.json()["problems"]) == ("2026-10-26", 123, [])
    with csi_db.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM cip_survey")).scalar() == 0


def test_publish_loads_the_week_and_starts_one_publish(csi_db, as_admin, monkeypatch, tmp_path):
    """…and judges the team's alerts on the new week, as every other load does (second audit of 15 Nov 2026: this
    page, the China path in use, never did)."""
    from etl import notify
    started, judged = [], []
    monkeypatch.setattr(ingest, "start_publish", lambda survey_id: started.append(survey_id))
    monkeypatch.setattr(notify, "alerts", lambda survey_ids: judged.append(survey_ids))
    monkeypatch.setattr(ingest, "UPLOAD_DIR", tmp_path / "uploads")
    answer = as_admin.post("/api/v1/admin/survey/publish", files=files())
    assert answer.status_code == 200, answer.text
    assert (answer.json()["wave"], answer.json()["respondents"], started) == ("2026-10-26", 550, [answer.json()["survey_id"]])
    assert judged == [[answer.json()["survey_id"]]]
    assert len(list((tmp_path / "uploads").iterdir())) == 2   # both source files kept


def test_the_background_publish_then_sends_that_surveys_email(tmp_path):
    """start_publish's shell loop with a stand-in Python: etl.publish, and once it succeeds etl.notify (27 Nov 2026)."""
    import subprocess
    python = tmp_path / "python"
    python.write_text('#!/bin/sh\necho "$@" >> "$(dirname "$0")/calls"\n')
    python.chmod(0o755)
    subprocess.run(["sh", "-c", ingest.PUBLISH, str(python), "42"], check=True, timeout=10)
    assert (tmp_path / "calls").read_text().splitlines() == ["-m etl.publish", "-m etl.notify --survey 42 --send"]


def test_wrong_files_are_refused_before_anything_loads(csi_db, as_admin, monkeypatch, tmp_path):
    monkeypatch.setattr(ingest, "start_publish", lambda survey_id: pytest.fail("published after a refused load"))
    monkeypatch.setattr(ingest, "UPLOAD_DIR", tmp_path)
    swapped = as_admin.post("/api/v1/admin/survey/preview", files=files(raw=TOPLINE, topline=RAW))
    assert swapped.status_code == 400 and "raw must be .csv or .xlsx" in swapped.json()["detail"]
    other = tmp_path / "other.csv"
    other.write_bytes(b"\n".join(RAW.read_bytes().split(b"\n")[:-20]))   # a raw file short of its topline's 550
    refused = as_admin.post("/api/v1/admin/survey/publish", files=files(raw=other))
    assert refused.status_code == 422 and "the topline says 550" in refused.json()["detail"]
    with csi_db.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM cip_survey")).scalar() == 0


def test_only_admins_reach_the_upload(csi_db):
    assert TestClient(app).post("/api/v1/admin/survey/preview", files=files()).status_code in (401, 403)


def test_sharepoint_notify_answers_graphs_check_and_leaves_one_note_for_a_right_secret(csi_db, monkeypatch, tmp_path):
    client, secret = TestClient(app), "s" * 40
    monkeypatch.setattr(ingest, "WANTED", tmp_path / "sharepoint.wanted")
    assert client.post("/api/v1/admin/sharepoint/notify").status_code == 404           # not set up: no such address
    monkeypatch.setenv("CIP_SP_WEBHOOK_SECRET", secret)
    check = client.post("/api/v1/admin/sharepoint/notify?validationToken=Validation%3A+abc")
    assert (check.status_code, check.text, check.headers["content-type"][:10]) == (200, "Validation: abc", "text/plain")
    assert client.post("/api/v1/admin/sharepoint/notify", json={"value": [{"clientState": "wrong"}]}).status_code == 403
    assert not ingest.WANTED.exists()
    graph = client.post("/api/v1/admin/sharepoint/notify", json={"value": [{"clientState": secret, "changeType": "updated"}]})
    assert graph.status_code == 202 and ingest.WANTED.exists()                          # Microsoft's webhook
    ingest.WANTED.unlink()
    assert client.post("/api/v1/admin/sharepoint/notify", headers={"X-CIP-Secret": secret}).status_code == 202   # a flow
    assert ingest.WANTED.exists()
