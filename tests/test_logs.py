"""The operational logs page (api/logs.py) and its admin gate (api/signin.admin)."""
import pytest
from fastapi import HTTPException

from api import logs, signin

ADMIN = {"role": "admin", "email": "dataautomation@coresight.com"}


class Asking:   # the request's headers are all admin() reads
    def __init__(self, token=""):
        self.headers = {"x-cip-admin-token": token} if token else {}


def test_a_log_reads_newest_first_and_filters(tmp_path, monkeypatch):
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    (tmp_path / "api.log").write_text("first ok\nsecond ERROR boom\nthird ok\n")
    assert logs.logs("api", "", 10, ADMIN)["lines"] == ["third ok", "second ERROR boom", "first ok"]
    assert logs.logs("api", "error", 10, ADMIN)["lines"] == ["second ERROR boom"]
    assert logs.logs("etl", "", 10, ADMIN)["lines"] == []          # not written yet: empty, not an error


def test_only_the_listed_logs_can_be_read(tmp_path, monkeypatch):
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    for name in ("../.env", "/etc/passwd", "api.log"):
        with pytest.raises(HTTPException) as refused:
            logs.logs(name, "", 10, ADMIN)
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
    monkeypatch.setattr(logs, "TRAFFIC", logs.Traffic())
    access = tmp_path / "nginx-access.log"
    now = logs.datetime.now(logs.timezone.utc).strftime("%Y-%m-%dT%H:%M")
    def line(status, seconds, path="/api/v1/waves/532/book", cache="", api="", client="1.2.3.4"):
        return js.dumps({"time": f"{now}:01+00:00", "client": client, "path": path, "status": status, "bytes": 100,
                         "seconds": seconds, "api_seconds": api, "cache": cache}) + "\n"
    access.write_text(line(200, 0.0) * 8 + line(200, 0.004, cache="HIT", path="/api/v1/waves/7/crosstab?q=x")
                      + line(503, 0.3, api="0.3") + line(200, 0.0, client="127.0.0.1") + '{"time": "half-writ')
    first = logs.metrics(60, ADMIN)
    t = first["totals"]
    assert (t["requests"], t["2xx"], t["5xx"], t["hit"], t["file"], t["api"]) == (10, 9, 1, 1, 8, 1)   # the probe is left out
    assert t["p50_ms"] == 0.5 and t["p99_ms"] == 500 and t["under_1ms"] == 80.0
    assert first["pages"][0] == {"page": "/api/v1/waves/:id/book", "requests": 9, "slowest_ms": 300.0}
    with access.open("a") as f:   # the half-written line finishes, one more arrives: read once each, nothing twice
        f.write('"}\n' + line(404, 0.001))
    assert logs.metrics(60, ADMIN)["totals"]["requests"] == 11
    india = logs.datetime.now(logs.timezone(logs.timedelta(hours=5, minutes=30))).isoformat(timespec="seconds")
    with access.open("a") as f:   # a server on local time (the VM: IST) lands in the same UTC minute
        f.write(line(200, 0.0).replace(f"{now}:01+00:00", india))
    assert logs.metrics(60, ADMIN)["totals"]["requests"] == 12
    access.unlink()   # rotated: the new file is read from its start
    access.write_text(line(200, 0.0))
    assert logs.metrics(60, ADMIN)["totals"]["requests"] == 13


def test_the_dashboard_reads_the_machine_samples(tmp_path, monkeypatch):
    monkeypatch.setattr(logs, "LOGS", tmp_path)
    now = logs.datetime.now(logs.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "machine.log").write_text('{"time":"2020-01-01T00:00:00Z","cpu_pct":1}\nnot json\n'
                                          f'{{"time":"{now}","cpu_pct":42.5,"working_set_mb":300}}\n')
    assert [s["cpu_pct"] for s in logs.metrics(60, ADMIN)["machine"]] == [42.5]   # old and broken lines skipped
