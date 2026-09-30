"""Shared fixtures."""
from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.core import database, schema_upgrade


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
