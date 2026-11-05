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
