"""The operational logs page (api/logs.py) and its admin gate (api/signin.admin)."""
import pytest
from fastapi import HTTPException

from api import logs, metrics, signin

ADMIN = {"role": "super_admin", "email": "mohdsaeedafri@coresight.com"}   # the one role with admin_pages (config/access.yml)


class Asking:   # the request's headers are all admin() reads
    def __init__(self, token=""):
        self.headers = {"x-cip-admin-token": token} if token else {}


def test_a_log_reads_newest_first_and_filters(tmp_path, monkeypatch):
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    (tmp_path / "api.log").write_text("first ok\nsecond ERROR boom\nthird ok\n")
    assert logs.logs("api", "", 10, 1, ADMIN)["lines"] == ["third ok", "second ERROR boom", "first ok"]
    assert logs.logs("api", "error", 10, 1, ADMIN)["lines"] == ["second ERROR boom"]
    assert logs.logs("etl", "", 10, 1, ADMIN)["lines"] == []          # not written yet: empty, not an error
    first, second = logs.logs("api", "", 2, 1, ADMIN), logs.logs("api", "", 2, 2, ADMIN)   # pages of 2, newest first
    assert (first["lines"], first["more"]) == (["third ok", "second ERROR boom"], True)
    assert (second["lines"], second["more"]) == (["first ok"], False)


def test_only_the_listed_logs_can_be_read(tmp_path, monkeypatch):
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    for name in ("../.env", "/etc/passwd", "api.log"):
        with pytest.raises(HTTPException) as refused:
            logs.logs(name, "", 10, 1, ADMIN)
        assert refused.value.status_code == 404


@pytest.mark.parametrize("demo, token, given, allowed", [
    ("", "", "", True),                          # real sign-in (SSO): the admin's email is proven
    ("1", "", "", False),                        # demo sign-in, no token set: admin pages closed
    ("1", "t" * 40, "", False),                  # demo sign-in, token not sent
    ("1", "t" * 40, "wrong" * 8, False),
    ("1", "t" * 40, "t" * 40, True),
    ("1", "short", "short", False),              # a token under 32 characters never counts
])
def test_admin_pages_need_the_token_while_sign_in_is_the_demo(monkeypatch, demo, token, given, allowed):
    monkeypatch.setenv("CIP_DEMO_LOGIN", demo)
    monkeypatch.setenv("CIP_ADMIN_TOKEN", token)
    if allowed:
        assert signin.admin(Asking(given), ADMIN) == ADMIN
    else:
        with pytest.raises(HTTPException):
            signin.admin(Asking(given), ADMIN)


def test_the_dashboard_counts_traffic_per_minute_and_reads_each_line_once(tmp_path, monkeypatch):
    import json as js
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    monkeypatch.setattr(metrics, "TRAFFIC", metrics.Traffic())
    access = tmp_path / "nginx-access.log"
    now = metrics.datetime.now(metrics.timezone.utc).strftime("%Y-%m-%dT%H:%M")
    def line(status, seconds, path="/api/v1/waves/532/book", cache="", api="", client="1.2.3.4"):
        return js.dumps({"time": f"{now}:01+00:00", "client": client, "path": path, "status": status, "bytes": 100,
                         "seconds": seconds, "api_seconds": api, "cache": cache}) + "\n"
    access.write_text(line(200, 0.0) * 8 + line(200, 0.004, cache="HIT", path="/api/v1/waves/7/crosstab?q=x")
                      + line(503, 0.3, api="0.3") + line(200, 0.0, client="127.0.0.1")
                      + line(200, 0.001, path="/healthz") + '{"time": "half-writ')
    first = metrics.metrics(60, ADMIN)
    t = first["totals"]
    assert (t["requests"], t["2xx"], t["5xx"], t["hit"], t["file"], t["api"]) == (10, 9, 1, 1, 8, 1)   # the probe and the keep-warm ping are left out
    assert t["p50_ms"] == 0.5 and t["p99_ms"] == 500 and t["under_1ms"] == 80.0
    assert first["pages"][0] == {"page": "/api/v1/waves/:id/book", "name": "A wave's full question book", "requests": 9,
                                 "share_pct": 90.0, "average_ms": 33.3, "slowest_ms": 300.0, "without_python_pct": 88.9}
    with access.open("a") as f:   # the half-written line finishes, one more arrives: read once each, nothing twice
        f.write('"}\n' + line(404, 0.001))
    assert metrics.metrics(60, ADMIN)["totals"]["requests"] == 11
    india = metrics.datetime.now(metrics.timezone(metrics.timedelta(hours=5, minutes=30))).isoformat(timespec="seconds")
    with access.open("a") as f:   # a server on local time (the VM: IST) lands in the same UTC minute
        f.write(line(200, 0.0).replace(f"{now}:01+00:00", india))
    assert metrics.metrics(60, ADMIN)["totals"]["requests"] == 12
    access.unlink()   # rotated: the new file is read from its start
    access.write_text(line(200, 0.0))
    assert metrics.metrics(60, ADMIN)["totals"]["requests"] == 13
    with access.open("a") as f:   # busy: 3 lines arrive unread, then deploy/etl-loop.sh copies the log to .1 and empties it
        f.write(line(200, 0.0) * 3)
    (tmp_path / "nginx-access.log.1").write_bytes(access.read_bytes())
    access.write_text(line(200, 0.0, path="/"))   # the emptied log starts again, shorter than what was read
    assert metrics.metrics(60, ADMIN)["totals"]["requests"] == 17   # the 3 from the copy, the 1 from the new file


def test_the_dashboard_reads_the_machine_samples(tmp_path, monkeypatch):
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    now = metrics.datetime.now(metrics.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "machine.log").write_text('{"time":"2020-01-01T00:00:00Z","cpu_pct":1}\nnot json\n'
                                          f'{{"time":"{now}","cpu_pct":99,"working_set_mb":3800}}\n'   # before 5 Nov 2026: the whole host, no source
                                          f'{{"time":"{now}","source":"cgroup1","cpu_pct":42.5,"working_set_mb":300}}\n')
    metrics.read_log_lists()
    (tmp_path / "machine.log").unlink()   # a refresh answers from what the minute loop read, never from the file (2 s on Azure)
    assert [s["cpu_pct"] for s in metrics.metrics(60, ADMIN)["machine"]] == [42.5]   # old, broken and host-wide lines skipped


def test_the_dashboard_names_visitors_and_explains_problems(tmp_path, monkeypatch):
    import json as js
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    monkeypatch.setattr(metrics, "TRAFFIC", metrics.Traffic())
    now = metrics.datetime.now(metrics.timezone.utc)
    minute = now.strftime("%Y-%m-%dT%H:%M")
    def line(status, user="", client="1.2.3.4", seconds=0.001):
        return js.dumps({"time": f"{minute}:01+00:00", "client": client, "path": "/api/v1/me", "status": status, "bytes": 1,
                         "seconds": seconds, "api_seconds": "0.001", "cache": "", "user": user}) + "\n"
    (tmp_path / "nginx-access.log").write_text(line(200, "ana@coresight.com") + line(401, "forged@x.com", "5.6.7.8")
                                              + line(304) + line(200, seconds=7.5))
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    (tmp_path / "nginx-error.log").write_text(f"{stamp.replace('-', '/')} [error] 20#20: *1 upstream prematurely closed connection\n")
    (tmp_path / "container.log").write_text(f"{now.strftime('%Y-%m-%dT%H:%M:%SZ')} start.sh: started nginx and the API, ETL scheduler on (build abc123)\n"
                                            f"{now.strftime('%Y-%m-%dT%H:%M:%SZ')} machine-log.sh: numbers from cgroup1\n")
    metrics.read_log_lists()
    m = metrics.metrics(60, ADMIN)
    who = {c["client"]: c["user"] for c in m["clients"]}
    assert who == {"1.2.3.4": "ana@coresight.com", "5.6.7.8": ""}   # a refused (401) cookie never names anyone
    assert m["totals"]["browser"] == 1 and m["totals"]["p99_ms"] == 7500.0   # over 5 s: the real slowest, not a made-up 10 s
    shares = {c["name"]: c.get("share_pct") for c in m["caches"]}   # nginx + files + Python = every request
    assert shares["nginx cache"] + shares["Published files"] + shares["API (Python), computed"] == 100.0
    assert m["problems"][0]["meaning"].startswith("The API stopped while answering")
    assert [r["build"] for r in m["restarts"]] == ["abc123"]   # the sampler's own line is not a restart


def test_the_dashboard_lists_who_signed_in_and_from_where(tmp_path, monkeypatch):
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    monkeypatch.setattr(metrics, "TRAFFIC", metrics.Traffic())
    stamp = metrics.datetime.now(metrics.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    (tmp_path / "api.log").write_text(f"{stamp},101 INFO    cip.api | GET /api/v1/me\n"
                                      f"{stamp},202 INFO    cip.signin | sign-in: ana@coresight.com role=analyst via demo from 10.1.2.3\n")
    metrics.read_log_lists()
    assert metrics.metrics(60, ADMIN)["sign_ins"] == [{"time": stamp, "email": "ana@coresight.com", "role": "analyst",
                                                       "method": "demo", "address": "10.1.2.3", "place": ""}]


def test_packed_logs_are_listed_and_only_they_can_be_downloaded(tmp_path, monkeypatch):
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    (tmp_path / "archive").mkdir()
    (tmp_path / "archive" / "api-20261106-0910.zip").write_bytes(b"PK")
    (tmp_path / "secret.txt").write_text("no")
    assert [a["name"] for a in logs.archives(ADMIN)] == ["api-20261106-0910.zip"]
    assert str(logs.archive("api-20261106-0910.zip", ADMIN).path).endswith("api-20261106-0910.zip")
    for name in ("../secret.txt", "secret.txt", "../../etc/passwd.zip", "missing.zip"):
        with pytest.raises(HTTPException) as refused:
            logs.archive(name, ADMIN)
        assert refused.value.status_code == 404


def test_an_old_traceback_is_not_counted_as_a_problem_in_every_time_range(tmp_path, monkeypatch):
    """Gunicorn writes "[2026-11-06 19:21:15 +0000] [ERROR] …" and then an undated traceback; the traceback once read as
    minute "TracebackT(mostT", which sorts after every date, so a day-old error showed in every range (7 Nov 2026)."""
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    now = metrics.datetime.now(metrics.timezone.utc)
    old = (now - metrics.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    fresh = now.strftime("%Y-%m-%d %H:%M:%S")
    (tmp_path / "api.log").write_text(f"[{old} +0000] [62] [ERROR] Exception in ASGI application\nTraceback (most recent call last):\n"
                                      f"  File \"api/signin.py\", line 70, in discovery\n[{fresh} +0000] [63] [ERROR] Worker timeout\n")
    assert metrics.minute_of("Traceback (most recent call last):") == "" and metrics.minute_of(f"[{old} +0000] x") == old[:16].replace(" ", "T")
    found = metrics.problems(now.strftime("%Y-%m-%dT%H:%M")[:-2] + "00")
    assert [p["line"][-14:] for p in found] == ["Worker timeout"]


def access_line(when, client="1.2.3.4", user="", agent="Mozilla/5.0 (Macintosh)", path="/api/v1/me", status=200):
    import json as js
    return js.dumps({"time": when.strftime("%Y-%m-%dT%H:%M:01+00:00"), "client": client, "method": "GET", "path": path,
                     "status": status, "bytes": 10, "seconds": 0.002, "api_seconds": "", "cache": "", "user": user,
                     "agent": agent, "referer": ""}) + "\n"


def test_finished_hours_are_saved_once_and_long_ranges_read_them(tmp_path, monkeypatch):
    """A day is kept per minute in memory; each finished hour is also saved (logs/traffic-hours.jsonl, on /home), so
    7 days, 17 weeks or any dates can be shown, and a restart (a new process reading the log again) adds no copy."""
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    now = metrics.datetime.now(metrics.timezone.utc)
    hours_ago = lambda n: now - metrics.timedelta(hours=n)
    (tmp_path / "nginx-access.log").write_text(access_line(hours_ago(3)) * 2 + access_line(hours_ago(2)) + access_line(now))
    for _ in range(2):   # the second process re-reads the same log
        monkeypatch.setattr(metrics, "TRAFFIC", metrics.Traffic())
        metrics.read_traffic()
    saved = (tmp_path / metrics.HOURS_FILE).read_text().splitlines()
    assert [metrics.json.loads(h)["requests"] for h in saved] == [2, 1]
    month = metrics.metrics(60, ADMIN, start=(now - metrics.timedelta(days=30)).strftime("%Y-%m-%dT%H:%MZ"))
    assert month["step"] == "hour" and month["totals"]["requests"] == 4   # the saved hours and the hour still in memory
    assert metrics.metrics(60, ADMIN)["step"] == "minute"


def test_a_visitor_is_told_apart_from_a_bot_and_from_azure(tmp_path, monkeypatch):
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    now = metrics.datetime.now(metrics.timezone.utc)
    (tmp_path / "nginx-access.log").write_text(
        access_line(now, "1.2.3.4", "ana@coresight.com") + access_line(now, "3.224.234.70", agent="Mozilla/5.0 (compatible)", path="/")
        + access_line(now, "169.254.129.1", agent="HealthCheck/1.0", path="/robots933456.txt"))
    assert metrics.visitor("1.2.3.4", ADMIN)["kind"] == "Signed in as ana@coresight.com."
    bot = metrics.visitor("3.224.234.70", ADMIN)
    assert bot["kind"].startswith("An automated program") and bot["requests"][0]["path"] == "/"
    assert metrics.visitor("169.254.129.1", ADMIN)["kind"].startswith("Azure's own health check")
    with pytest.raises(metrics.HTTPException):
        metrics.visitor('1.2.3.4","x', ADMIN)


def test_show_opens_an_error_with_its_traceback(tmp_path, monkeypatch):
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    (tmp_path / "api.log").write_text("2026-11-07 14:00:00,1 INFO    cip.api | GET /x\n"
                                      "2026-11-07 14:00:01,2 ERROR   cip.api | Unhandled error on GET /api/v1/waves/1/book\n"
                                      "Traceback (most recent call last):\n  File \"api/main.py\", line 9\nKeyError: 'wave'\n")
    shown = logs.context("api", "2026-11-07 14:00:01,2 ERROR   cip.api | Unhandled error", ADMIN)
    assert shown["before"] == ["2026-11-07 14:00:00,1 INFO    cip.api | GET /x"] and shown["after"][-1] == "KeyError: 'wave'"


def test_the_whole_page_downloads_as_one_workbook_in_india_time(tmp_path, monkeypatch):
    import io
    from openpyxl import load_workbook
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    monkeypatch.setattr(metrics, "TRAFFIC", metrics.Traffic())
    now = metrics.datetime.now(metrics.timezone.utc)
    (tmp_path / "nginx-access.log").write_text(access_line(now, user="ana@coresight.com"))
    book = load_workbook(io.BytesIO(metrics.download(60, ADMIN).body))
    assert {"Summary", "Requests per minute", "CPU, memory, bandwidth", "Response times", "How requests were answered", "Storage",
            "Busiest pages", "Visitors", "Sign-ins", "Problems", "Requests (newest 50,000)"} <= set(book.sheetnames)
    assert book["Requests (newest 50,000)"]["C2"].value == "ana@coresight.com"
    assert metrics.ist("2026-11-07T14:50:00Z") == "7 Nov 2026, 8:20 PM"


def test_text_a_visitor_sends_never_runs_as_a_formula_in_the_download(tmp_path, monkeypatch):
    import io
    from openpyxl import load_workbook
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    monkeypatch.setattr(metrics, "TRAFFIC", metrics.Traffic())
    now = metrics.datetime.now(metrics.timezone.utc)
    (tmp_path / "nginx-access.log").write_text(access_line(now, agent='=HYPERLINK("http://evil/","x")'))
    sheet = load_workbook(io.BytesIO(metrics.download(60, ADMIN).body))["Requests (newest 50,000)"]
    cells = [c for row in sheet.iter_rows() for c in row if c.value and "HYPERLINK" in str(c.value)]
    assert cells and all(c.data_type == "s" and str(c.value).startswith("'=") for c in cells)   # text, not a formula
