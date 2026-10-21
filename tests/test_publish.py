"""Static publishing (etl/publish.py): standard screens become files nginx serves, swapped in atomically."""
import gzip
import json
from datetime import date

import pytest

from app.data import payloads
from etl import publish, serving
from tests.test_serving import seed


def test_publish_writes_the_api_bytes_swaps_atomically_and_rolls_back(csi_db, tmp_path):
    with csi_db.begin() as conn:
        seed(conn, 266, date(2026, 10, 5), qualified=401, xm1_yes=92, xm1_base=149)
        seed(conn, 412, date(2026, 10, 12), qualified=404, xm1_yes=125, xm1_base=404)
    serving.build_wave(266), serving.build_wave(412)
    first = publish.publish(tmp_path, jobs=2)
    live = tmp_path / "current"
    book = live / "api/v1/waves/412/book.json"
    assert book.read_bytes() == payloads.encode(payloads.book(412))                 # identical to the API
    assert gzip.decompress(book.with_suffix(".json.gz").read_bytes()) == book.read_bytes()
    assert len(json.loads((live / "api/v1/waves.json").read_text())) == 2
    assert json.loads((live / "manifest.json").read_text())["books"] == 2
    second = publish.build(tmp_path, jobs=1)
    publish.swap(tmp_path, second)
    assert live.resolve() == second.resolve()
    assert publish.rollback(tmp_path).name == first.name and live.resolve() == first.resolve()


def test_a_failed_gate_keeps_the_live_version(csi_db, tmp_path, monkeypatch):
    with csi_db.begin() as conn:
        seed(conn, 412, date(2026, 10, 12), qualified=404, xm1_yes=125, xm1_base=404)
    serving.build_wave(412)
    good = publish.publish(tmp_path, jobs=1)
    monkeypatch.setattr(payloads, "book", lambda sid: {"wave": {"survey_id": -1}, "questions": None})   # a bad build
    with pytest.raises(RuntimeError, match="gates failed"):
        publish.publish(tmp_path, jobs=1)
    assert (tmp_path / "current").resolve() == good.resolve()
    assert len(list(tmp_path.glob(".build-*"))) == 1                                # the bad folder is gone
