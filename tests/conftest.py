"""Shared fixtures."""
from __future__ import annotations

import os
import tempfile

import pytest
import sqlalchemy as sa

from app.core import database, schema_upgrade

# before etl.publish is imported: a test's publish must never replace the portal's real files (data/published)
os.environ["CIP_PUBLISH_DIR"] = tempfile.mkdtemp(prefix="cip-published-")


@pytest.fixture()
def csi_db(tmp_path, monkeypatch):
    """A fresh schema-v2 SQLite database, used by every repository and
    loader function in the test (both the 'etl' and the 'app' role)."""
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'csi.db'}", future=True)
    schema_upgrade.install(engine)
    database._install_sqlite_translation(engine)
    monkeypatch.setitem(database._engines, "etl", engine)
    monkeypatch.setitem(database._engines, "app", engine)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def own_notify_state(tmp_path, monkeypatch):
    """Tests' fake failures must never fill the real throttle (logs/notify-state.json): it would
    silence a real alert for 6 hours."""
    from etl import notify
    monkeypatch.setattr(notify, "STATE", tmp_path / "notify-state.json")


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
