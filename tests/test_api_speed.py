"""Every screen's request is a published file read: no database, and well inside a millisecond budget.

The ETL publishes the standard responses (etl/publish.py); the API only reads them. This test publishes a small
set into a temporary folder, makes any database call fail, and times each endpoint the screens use. Live timings
against a running server: scripts/api_timing.py."""
import asyncio
import gzip
import json
import time
from urllib.parse import urlsplit

import pytest

import api.main as api

BUDGET_MS = 10        # per request, warm, in-process: anything slower than 10 ms that is not the database is a bug


def put(root, rel, data):
    path = root / "api" / "v1" / f"{rel}.json.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(data).encode()))


class Client:
    """Calls the ASGI app directly (no server, no HTTP library): status, headers and body of one GET."""
    def __init__(self, cookie):
        self.cookie = cookie

    def post(self, url, data):
        return self.get(url, method="POST", body=json.dumps(data).encode(), headers={"content-type": "application/json"})

    def get(self, url, headers=None, method="GET", body=b""):
        parts = urlsplit(url)
        head = {"cookie": f"{api.COOKIE}={self.cookie}", **(headers or {})}
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http",
                 "path": parts.path, "raw_path": parts.path.encode(), "query_string": parts.query.encode(), "root_path": "",
                 "headers": [(k.encode(), v.encode()) for k, v in head.items()], "client": ("test", 1), "server": ("test", 80)}
        sent = []

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            sent.append(message)
        asyncio.run(api.app(scope, receive, send))
        return type("Response", (), {"status_code": sent[0]["status"], "body": b"".join(m.get("body", b"") for m in sent[1:])})


@pytest.fixture()
def client(tmp_path, monkeypatch):
    wave = {"survey_id": 415, "survey_family": "CSI-US", "study_type": "tracker", "prior_survey_id": 412, "wave_date": "2026-10-19"}
    put(tmp_path, "waves", [wave, {**wave, "survey_id": 412, "prior_survey_id": None, "wave_date": "2026-10-12"}])
    put(tmp_path, "waves/415/book", {"wave": wave, "questions": []})
    put(tmp_path, "questions/CSI-US/tracker/XM1A", {"qcode": "XM1A", "waves": [], "versions": [], "answers": [], "cuts": [],
                                                    "w": [], "c": [], "a": [], "n": [], "b": []})
    for sid in (415, 412):
        put(tmp_path, f"waves/{sid}/cuts/XM1A", {"answers": [{"item_id": 0, "option_id": 1, "item_label": "", "option_code": 1,
                                                             "option_label": "Yes", "sort_order": 1, "flags": "", "qtext": "Q?", "concept_option_id": None}],
                                                "counts": [[0, 1, "Male", "18-29", "GenZ", "under $25,000", "South", "Urban", 40]]})
    monkeypatch.setattr(api, "PUBLISHED", tmp_path)
    monkeypatch.setattr(api, "RESULTS", type(api.RESULTS)())
    monkeypatch.setattr(api, "get_engine", lambda *a, **k: pytest.fail("a screen request reached the database"))
    monkeypatch.setattr(api.payloads, "get_engine", lambda *a, **k: pytest.fail("a screen request reached the database"))
    return Client(api.issue("speed@test"))   # startup (the database loads) does not run


@pytest.mark.parametrize("url", [
    "/api/v1/waves",
    "/api/v1/waves/415/book",
    "/api/v1/questions/CSI-US/tracker/XM1A",                       # Compare and Trends
    "/api/v1/waves/415/crosstab?q=XM1A&by=gender,generation&weeks=2",
])
def test_screen_requests_are_file_reads_inside_the_budget(client, url):
    assert client.get(url).status_code == 200                     # first read fills the worker cache
    times = []
    for _ in range(20):
        start = time.perf_counter()
        response = client.get(url, headers={"accept-encoding": "gzip"})
        times.append(1000 * (time.perf_counter() - start))
        assert response.status_code == 200
    assert sorted(times)[18] < BUDGET_MS, f"{url}: p95 {sorted(times)[18]:.1f} ms"


def test_any_table_exports_as_excel_and_powerpoint(client):
    import io
    import zipfile
    table = {"name": "q13", "header": ["Answer", "Total %"], "rows": [["Yes", 47.5], ["No", 52.5]],
             "notes": ["Q13: Did you shop on Cyber Monday?", "Base: Total n=400"]}
    for kind, part in (("xlsx", "xl/worksheets/sheet1.xml"), ("pptx", "ppt/slides/slide1.xml")):
        response = client.post(f"/api/v1/export/{kind}", table)
        assert response.status_code == 200 and part in zipfile.ZipFile(io.BytesIO(response.body)).namelist()
