"""Shared fixtures."""
from __future__ import annotations

import os
import socket
import tempfile

# The repository .env contains live database, Forsta, SMTP, Teams, OIDC and
# backup credentials.  Shadow them before importing any application module:
# load_dotenv() does not overwrite variables already present in the process.
_TEST_ROOT = tempfile.mkdtemp(prefix="cip-tests-")


def _blocked_network(*args, **kwargs):
    address = kwargs.get("address", args[-1] if args else "unknown endpoint")
    raise AssertionError(f"test attempted a real network connection to {address!r}")


# Collection imports application modules before autouse fixtures begin.
socket.socket.connect = _blocked_network
socket.socket.connect_ex = _blocked_network
socket.socket.sendto = _blocked_network
if hasattr(socket.socket, "sendmsg"):
    socket.socket.sendmsg = _blocked_network
socket.create_connection = _blocked_network
os.environ["APP_ENV"] = "LOCAL"
os.environ["LOCAL_SQLITE_PATH"] = os.path.join(_TEST_ROOT, "default.db")
os.environ["CIP_PUBLISH_DIR"] = os.path.join(_TEST_ROOT, "published")
for _live_setting in (
    "ANTHROPIC_API_KEY",
    "APP_DB_PASSWORD",
    "APP_DB_USER",
    "CIP_OIDC_CLIENT_ID",
    "CIP_OIDC_CLIENT_SECRET",
    "CIP_OIDC_ISSUER",
    "CIP_NGINX_URL",
    "CIP_PUBLISH_BACKUP_URL",
    "EMAIL_PASSWORD",
    "FORSTA_API_KEY",
    "IDP_BASE_URL",
    "IDP_TOKEN_URL",
    "IDP_USERINFO_URL",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "STG_DB_HOST",
    "STG_DB_NAME",
    "STG_DB_PASSWORD",
    "STG_DB_USER",
    "TEAMS_WEBHOOK_URL",
):
    os.environ[_live_setting] = ""

import pytest
import sqlalchemy as sa

from app.core import database, schema_upgrade


@pytest.fixture()
def csi_db(tmp_path, monkeypatch):
    """A fresh schema-v2 SQLite database, used by every repository and
    loader function in the test (both the 'etl' and the 'app' role)."""
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'csi.db'}", future=True)

    @sa.event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    schema_upgrade.install(engine)
    database._install_sqlite_translation(engine)
    monkeypatch.setitem(database._engines, "etl", engine)
    monkeypatch.setitem(database._engines, "app", engine)
    monkeypatch.setitem(database._engines, "api_write", engine)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def own_notify_state(tmp_path, monkeypatch):
    """Tests' fake failures must never fill the real throttle (logs/notify-state.json): it would
    silence a real alert for 6 hours."""
    from etl import notify
    monkeypatch.setattr(notify, "STATE", tmp_path / "notify-state.json")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """A missed mock must fail closed before reaching MySQL, HTTP, SMTP or an API."""
    monkeypatch.setattr(socket.socket, "connect", _blocked_network)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked_network)
    monkeypatch.setattr(socket.socket, "sendto", _blocked_network)
    if hasattr(socket.socket, "sendmsg"):
        monkeypatch.setattr(socket.socket, "sendmsg", _blocked_network)
    monkeypatch.setattr(socket, "create_connection", _blocked_network)


@pytest.fixture(autouse=True)
def no_real_messages(monkeypatch, request):
    """Tests run with the real .env, which holds live SMTP and Teams settings: nothing a test does may reach a
    person. Every send is recorded on notify.sent instead; tests of send() itself (test_notify) fake SMTP."""
    import smtplib
    from etl import notify
    monkeypatch.setattr(notify.requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a test tried to post")))
    if request.module.__name__.endswith("test_notify"):
        return
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a test tried to email")))
    sent: list = []
    monkeypatch.setattr(notify, "sent", sent, raising=False)
    monkeypatch.setattr(notify, "send", lambda subject, *a, **k: sent.append(("email", subject)) or True)
    monkeypatch.setattr(notify, "teams", lambda headline: sent.append(("teams", headline)))
