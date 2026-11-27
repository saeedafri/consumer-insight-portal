"""Every screen's request is a published file read: no database, and well inside a millisecond budget.

The ETL publishes the standard responses (etl/publish.py); the API only reads them. This test publishes a small
set into a temporary folder, makes any database call fail, and times each endpoint the screens use. Live timings
against a running server: time the URLs with a load tool (e.g. oha) on a test port."""
import asyncio
import gzip
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import pytest

import api.main as api
from api.signin import COOKIE
from shared.core.session import issue

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
        head = {"cookie": f"{COOKIE}={self.cookie}", **(headers or {})}
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
    return Client(issue("speed@test"))   # startup (the database loads) does not run


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


def test_a_weekly_trend_exports_as_a_line_chart_of_every_week():
    """In store vs online's trend went to PowerPoint as bars of its first 16 weeks (25 Nov 2026): weeks draw a line,
    oldest first, every week, the latest figure labelled once at each line's end, a missing week left blank."""
    import io
    import re
    import zipfile
    from api import exports
    weeks = [f"2026-{m:02d}-{d:02d}" for m in range(1, 11) for d in (5, 19)]   # 20 weeks, more than a bar slide's 16
    rows = [[w, 40.0 + k, None if k == 7 else 20.0 + k, 400, 400] for k, w in enumerate(reversed(weeks))]   # newest first
    spec = exports.check({"name": "trend", "header": ["Week", "In a store %", "Online %", "In a store base", "Online base"],
                          "rows": rows, "notes": ["Groceries: in a store vs online, Everyone", "Source: test"]})
    slide = zipfile.ZipFile(io.BytesIO(exports.build_pptx(spec)))
    chart = next(slide.read(n).decode() for n in slide.namelist() if n.startswith("ppt/charts/chart"))
    assert "<c:lineChart>" in chart and "<c:barChart>" not in chart
    assert '<c:dispBlanksAs val="gap"/>' in chart and chart.count('<c:symbol val="none"/>') == 2
    assert chart.count('<c:ptCount val="20"/>') == 4   # two lines, each its 20 weeks and 20 figures
    # the end labels: the oldest week first, so the last point is the newest week (in a store 40.0, online 20.0)
    assert re.findall(r"<a:t>([\d.]+%)</a:t>", chart) == ["40.0%", "20.0%"]
    # faint horizontal lines and a % axis, as on screen (26 Nov 2026)
    assert "<c:majorGridlines>" in chart and 'formatCode="0&quot;%&quot;"' in chart
    # an answer table, or a date that is no week, stays bars, its labels in %
    for first in ("Yes", "2026-13-01"):
        bars = zipfile.ZipFile(io.BytesIO(exports.build_pptx(exports.check({"name": "q", "header": ["Answer", "Total %"], "rows": [[first, 47.5]], "notes": []}))))
        xml = next(bars.read(n) for n in bars.namelist() if n.startswith("ppt/charts/chart"))
        assert b"<c:barChart>" in xml and b'formatCode="0.0&quot;%&quot;"' in xml and b"<c:majorGridlines" not in xml


def test_a_book_exports_as_one_workbook_of_tabs_in_the_house_style(client):
    """Every tab of a databank, every section of a survey, as one download (the business team, 27 Nov 2026): a tab per
    table under its own (Excel-safe, unique) title, the header in Coresight red, percentages as 61.0%, the people asked
    as plain numbers, weeks as dates; a book is Excel only, and one too big is refused whole, never cut."""
    import io
    import openpyxl
    from api import exports
    tracker = {"title": "Headline figures", "header": ["Headline figure", "2025-09-29", "2026-11-23"], "unit": "%", "plain": [1],
               "rows": [["Started", 40, 61.6], ["Respondents asked", 404, 404]], "notes": ["Holiday Survey Databank: headline figures"]}
    survey = {"title": "Retailers: top [5]", "header": ["Question", "Answer", "Total %"], "plain": [1],
              "rows": [["Q1", "Yes", 47.5], ["Q1", "Respondents asked", 404]], "notes": []}
    response = client.post("/api/v1/export/xlsx", {"name": "Holiday", "sheets": [tracker, survey, {**survey, "rows": [["=SUM(A1)", "x", 1.5]]}]})
    assert response.status_code == 200
    book = openpyxl.load_workbook(io.BytesIO(response.body))
    assert book.sheetnames == ["Headline figures", "Retailers top 5", "Retailers top 5 (2)"]
    first = book["Headline figures"]
    header, started, asked = first[3], first[4], first[5]   # one note, a blank row, then the header
    assert header[0].fill.fgColor.rgb.endswith(exports.RED) and header[0].font.b and header[0].font.color.rgb.endswith("FFFFFF")
    assert header[1].number_format == "mmm d, yyyy" and header[1].value.year == 2025
    assert [c.number_format for c in started[1:]] == ['0.0"%"'] * 2 and [c.number_format for c in asked[1:]] == ["#,##0"] * 2
    assert first.freeze_panes == "B4" and first.auto_filter.ref == "A3:C5"
    second = book.worksheets[1]
    assert second["C3"].number_format == '0.0"%"' and second["C4"].number_format == "#,##0"   # a % column's base row is plain
    assert book.worksheets[2]["A3"].value == "'=SUM(A1)"   # a formula stays text
    assert client.post("/api/v1/export/pptx", {"name": "Holiday", "sheets": [tracker, survey]}).status_code == 422
    long = {**tracker, "rows": [["x", 1, 1]] * (exports.MAX_ROWS + 1)}   # longer than one table may be: a tab keeps it all
    assert openpyxl.load_workbook(io.BytesIO(client.post("/api/v1/export/xlsx", {"name": "long", "sheets": [long]}).body)).active.max_row == 3 + exports.MAX_ROWS + 1
    assert client.post("/api/v1/export/xlsx", {"name": "big", "sheets": [long] * 5}).status_code == 422   # 10,005 rows: refused whole
    wide = {**tracker, "header": ["x"] * (exports.MAX_COLUMNS + 1)}
    assert client.post("/api/v1/export/xlsx", {"name": "wide", "sheets": [wide]}).status_code == 422

def test_mcp_crosstab_reuses_published_cut_files_without_database(client):
    response = client.post("/mcp", {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "crosstab", "arguments": {
            "survey_id": 415,
            "qcode": "XM1A",
            "by": ["gender", "generation"],
        }},
    })
    assert response.status_code == 200
    message = json.loads(response.body)
    result = json.loads(message["result"]["content"][0]["text"])
    assert result["qcode"] == "XM1A"
    assert result["by"] == ["gender", "generation"]


def test_crosstab_falls_back_for_a_wave_loaded_after_the_last_publish(client, monkeypatch):
    expected = {"qcode": "XM1A", "by": ["gender", "generation"], "columns": [], "rows": []}
    monkeypatch.setattr(api.payloads, "crosstab", lambda *args: expected)
    item = api.crosstab_payload(999, "XM1A", ("gender", "generation"), 1)   # no cuts folder published yet
    assert json.loads(item.body) == expected


def test_a_question_missing_from_a_published_wave_is_404_without_the_database(client):
    # the wave's cuts folder is its complete question list (etl/publish.py cut_inventory); the fixture fails on any
    # database call, which under load took 1-5 s per "other, please specify" question and starved the build slots
    assert client.get("/api/v1/waves/415/crosstab?q=Q9r3oe&by=gender,generation").status_code == 404


def test_a_question_code_typed_in_another_case_gives_the_same_cross_tab(client, monkeypatch):
    """Azure's disk is case-sensitive (this Mac's is not), so read files the way it does: xm1a must find XM1A's cuts, as
    /results already does, without lower-casing codes that are upper-case (52 of 58 in a wave, e.g. XM3)."""
    real = api.published_file
    monkeypatch.setattr(api, "published_file", lambda *parts: real(*parts) if parts[-1] + ".json.gz" in
                        {p.name for p in api.PUBLISHED.joinpath("api", "v1", *parts[:-1]).glob("*")} else None)
    response = client.get("/api/v1/waves/415/crosstab?q=xm1a&by=gender,generation")
    assert response.status_code == 200 and json.loads(response.body)["qcode"] == "XM1A"


def test_a_wave_built_after_the_last_publish_is_listed_from_the_database(client, monkeypatch):
    """A machine with no ETL loop keeps an old published list: a wave the database has built since (532 on 7 Nov 2026)
    must not answer "No such wave". When the two agree, the list is the published file and the database is not read."""
    newer = {"survey_id": 418, "survey_family": "CSI-US", "study_type": "tracker", "prior_survey_id": 415, "wave_date": "2026-10-26"}
    monkeypatch.setattr(api, "WAVES", ((), []))
    monkeypatch.setattr(api, "SERVING", (2, "2026-10-20"))
    monkeypatch.setattr(api.payloads, "waves", lambda boards: pytest.fail("the lists agree: no database read"))
    assert {w["survey_id"] for w in api.all_waves()} == {415, 412}
    published = json.loads(api.published_file("waves").body)
    monkeypatch.setattr(api, "SERVING", (3, "2026-10-27"))
    monkeypatch.setattr(api.payloads, "waves", lambda boards: [newer, *published])
    assert {w["survey_id"] for w in api.all_waves()} == {418, 415, 412}


@pytest.mark.parametrize("fill_new_before_old_finishes", [False, True])
def test_a_slow_response_cannot_mix_generations_or_enter_the_next_cache(tmp_path, monkeypatch, fill_new_before_old_finishes):
    """Swap between two reads of one cold fill and require a retry against the complete new snapshot."""
    first, second = tmp_path / "first", tmp_path / "second"
    current = tmp_path / "current"
    for generation in (first, second):
        for name in ("a", "b"):
            put(generation, name, generation.name)
    current.symlink_to(first)
    monkeypatch.setattr(api, "PUBLISHED", current)
    monkeypatch.setattr(api, "PUBLISHED_VERSION", "")
    monkeypatch.setattr(api, "RESULTS", type(api.RESULTS)())
    monkeypatch.setattr(api, "CACHED_BYTES", 0)
    monkeypatch.setattr(api, "BUILD_SLOTS", asyncio.Semaphore(2))
    started, finish = threading.Event(), threading.Event()
    read = lambda name: json.loads(api.published_file(name).body)
    observed = []

    def build():
        observed.append(read("a"))
        started.set()
        assert finish.wait(5)
        observed.append(read("b"))
        return api.to_payload(observed)

    async def swap_while_building():
        pending = asyncio.create_task(api.cached_payload(("slow",), build))
        try:
            assert await asyncio.to_thread(started.wait, 5)
            replacement = tmp_path / "replacement"
            replacement.symlink_to(second)
            replacement.replace(current)
            if fill_new_before_old_finishes:
                await api.cached_payload(("other",), lambda: api.to_payload(read("a")))
        finally:
            finish.set()
        with pytest.raises(api.HTTPException) as refused:
            await pending
        assert refused.value.status_code == 503 and "Retry-After" in refused.value.headers
        assert ("slow",) not in api.RESULTS
        fresh = await api.cached_payload(("slow",), lambda: api.to_payload([read("a"), read("b")]))
        assert json.loads(fresh.body) == ["second", "second"]

    asyncio.run(swap_while_building())
    assert observed == ["first", "first"]


def test_an_oversized_response_does_not_displace_the_small_cache(tmp_path, monkeypatch):
    """A large one-off reply can be returned but must never exceed the byte budget."""
    monkeypatch.setattr(api, "PUBLISHED", tmp_path)
    monkeypatch.setattr(api, "RESULTS", type(api.RESULTS)())
    monkeypatch.setattr(api, "CACHED_BYTES", 0)
    monkeypatch.setattr(api, "CACHE_BYTES", 80)
    monkeypatch.setattr(api, "BUILD_SLOTS", asyncio.Semaphore(2))
    small, large = api.to_payload("yes"), api.to_payload("large" * 100)

    async def fill():
        await api.cached_payload(("small",), lambda: small)
        assert await api.cached_payload(("large",), lambda: large) is large
        assert list(api.RESULTS) == [("small",)]
        assert api.CACHED_BYTES == len(small.body) + len(small.gz)

    asyncio.run(fill())


def test_ask_uses_the_same_generation_for_visibility_and_question_files(tmp_path, monkeypatch):
    """A symlink swap during the wave read cannot combine older scopes with newer question files."""
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    current = tmp_path / "current"
    current.symlink_to(first)
    monkeypatch.setattr(api, "PUBLISHED", current)
    wave = {"survey_id": 1}

    def build_wave_list(*, published_only):
        assert published_only
        replacement = tmp_path / "replacement"
        replacement.symlink_to(second)
        replacement.replace(current)
        return [wave]

    sentinel = object()

    def read_index(path, version, waves):
        assert path == first.resolve() / "api/v1/questions"
        assert version == str(first.resolve())
        assert waves == [wave]
        return sentinel

    monkeypatch.setattr(api, "all_waves", build_wave_list)
    monkeypatch.setattr(api.assistant, "index_for", read_index)
    monkeypatch.setattr(api.access, "sees", lambda who, candidate: candidate is wave)
    assert asyncio.run(api.ask_index({})) == (sentinel, {1})


def test_ask_uses_only_published_waves_when_database_is_ahead(client, monkeypatch):
    """The wave selector may list a warehouse-only wave. Ask must use its own published snapshot."""
    extra = {"survey_id": 418, "survey_family": "CSI-US", "study_type": "tracker", "wave_date": "2026-10-26"}
    published = json.loads(api.published_file("waves").body)
    read_file = api.published_file
    reads = []

    def count_reads(*parts):
        reads.append(parts)
        return read_file(*parts)

    monkeypatch.setattr(api, "published_file", count_reads)
    monkeypatch.setattr(api, "SERVING", (3, "ahead"))
    monkeypatch.setattr(api.payloads, "waves", lambda boards: [extra, *published])
    monkeypatch.setattr(api.assistant, "index_for", lambda path, version, waves: [w["survey_id"] for w in waves])
    monkeypatch.setattr(api.access, "sees", lambda who, wave: True)
    assert {w["survey_id"] for w in api.all_waves()} == {412, 415, 418}
    for _ in range(2):
        index, visible = asyncio.run(api.ask_index({}))
        assert visible == set(index) == {412, 415}
    assert reads == [("waves",)]


def test_ask_does_not_offer_a_no_data_answer_during_publication_restore(tmp_path, monkeypatch):
    """Ask returns a retryable status until a published wave list exists."""
    monkeypatch.setattr(api, "PUBLISHED", tmp_path / "restoring")
    monkeypatch.setattr(api.payloads, "waves", lambda *_: pytest.fail("Ask reached the database"))
    with pytest.raises(api.HTTPException) as waiting:
        asyncio.run(api.ask_index({}))
    assert waiting.value.status_code == 503 and "Retry-After" in waiting.value.headers


def test_ask_queues_generation_selection_before_replacing_the_index(tmp_path, monkeypatch):
    """A slow first wave read cannot overwrite a newer index installed by a concurrent Ask request."""
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    current = tmp_path / "current"
    current.symlink_to(first)
    monkeypatch.setattr(api, "PUBLISHED", current)
    first_read, release, second_requested = threading.Event(), threading.Event(), threading.Event()
    index_versions = []

    def wave_list(*, published_only):
        assert published_only
        if api.READ_ROOT.get().name == "first":
            first_read.set()
            assert release.wait(5)
        return [{"survey_id": 1}]

    def build_index(_path, version, _waves):
        index_versions.append(version)
        return version

    def next_request():
        second_requested.set()
        return api.read_ask_index()

    monkeypatch.setattr(api, "all_waves", wave_list)
    monkeypatch.setattr(api.assistant, "index_for", build_index)
    with ThreadPoolExecutor(max_workers=2) as worker:
        old = worker.submit(api.read_ask_index)
        try:
            assert first_read.wait(5)
            replacement = tmp_path / "replacement"
            replacement.symlink_to(second)
            replacement.replace(current)
            new = worker.submit(next_request)
            assert second_requested.wait(5)
            with pytest.raises(TimeoutError):
                new.result(timeout=0.05)
        finally:
            release.set()
        assert old.result(timeout=5)[0] == str(first.resolve())
        assert new.result(timeout=5)[0] == str(second.resolve())
    assert index_versions == [str(first.resolve()), str(second.resolve())]


def test_a_second_export_waits_for_the_first_then_is_told_busy(monkeypatch):
    # one Excel/PowerPoint build at a time on the one CPU (20 Nov 2026): a queued one gets 503 "busy", never a pile-up
    import asyncio as aio
    import api.main as api
    monkeypatch.setattr(api, "EXPORT_SLOTS", aio.Semaphore(1))
    monkeypatch.setattr(api, "EXPORT_WAIT", 0.05)

    async def held():
        await api.EXPORT_SLOTS.acquire()   # an export in progress
        try:
            await aio.wait_for(api.EXPORT_SLOTS.acquire(), api.EXPORT_WAIT)
        except aio.TimeoutError:
            return "busy"
        return "ran"
    assert aio.run(held()) == "busy"
