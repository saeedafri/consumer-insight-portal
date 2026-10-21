"""Static publishing (etl/publish.py): standard screens become files nginx serves, swapped in atomically."""
import gzip
import json
import time
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
    book = live / "api/v1/waves/412/book.json.gz"
    assert gzip.decompress(book.read_bytes()) == payloads.encode(payloads.book(412))   # identical to the API
    assert len(json.loads(gzip.decompress((live / "api/v1/waves.json.gz").read_bytes()))) == 2
    assert json.loads((live / "manifest.json").read_text())["rebuilt_waves"] == 2
    second = publish.build(tmp_path, jobs=1)                                         # nothing changed: all linked
    assert json.loads((second / "manifest.json").read_text())["rebuilt_waves"] == 0
    assert (second / "api/v1/waves/412/book.json.gz").stat().st_ino == book.resolve().stat().st_ino
    publish.swap(tmp_path, second)
    assert live.resolve() == second.resolve()
    time.sleep(1.1)                                                                  # built_at has one-second resolution
    serving.build_wave(412)                                                          # the ETL reloads one wave
    live_trend = next((second / "api/v1/trends").rglob("*.json.gz"))
    before = live_trend.read_bytes()
    third_dir = publish.build(tmp_path, jobs=1)
    third = json.loads((third_dir / "manifest.json").read_text())
    assert (third["rebuilt_waves"], third["rebuilt_families"]) == (1, 1)
    rewritten = third_dir / live_trend.relative_to(second)                           # the wave asked it: rewritten
    assert rewritten.stat().st_ino != live_trend.stat().st_ino and live_trend.read_bytes() == before   # live copy untouched
    assert publish.rollback(tmp_path).name == first.name and live.resolve() == first.resolve()


def test_a_failed_gate_keeps_the_live_version(csi_db, tmp_path, monkeypatch):
    with csi_db.begin() as conn:
        seed(conn, 412, date(2026, 10, 12), qualified=404, xm1_yes=125, xm1_base=404)
    serving.build_wave(412)
    good = publish.publish(tmp_path, jobs=1)
    (good / "manifest.json").unlink()                                               # forget what was built: every wave rebuilds
    monkeypatch.setattr(payloads, "book", lambda sid: {"wave": {"survey_id": -1}, "questions": None})   # a bad build
    with pytest.raises(RuntimeError, match="gates failed"):
        publish.publish(tmp_path, jobs=1)
    assert (tmp_path / "current").resolve() == good.resolve()
    assert len(list(tmp_path.glob(".build-*"))) == 1                                # the bad folder is gone


def test_a_lost_disk_comes_back_from_the_blob_backup(tmp_path, monkeypatch):
    import io
    from etl import publish

    store = {}

    class Reply:
        def __init__(self, body=b""):
            self.text, self.raw = body.decode(errors="ignore"), io.BytesIO(body)
        def raise_for_status(self): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass

    def put(url, data, headers, timeout):
        store[url.split("?")[0].rsplit("/", 1)[1]] = data if isinstance(data, bytes) else data.read()
        return Reply()

    monkeypatch.setattr(publish, "BACKUP", "https://acct.blob.core.windows.net/cip?sv=x&sig=y")
    monkeypatch.setattr(publish.requests, "put", put)
    monkeypatch.setattr(publish.requests, "get", lambda url, **k: Reply(store[url.split("?")[0].rsplit("/", 1)[1]]))
    version = tmp_path / "old" / ".build-20261021T000000Z"
    (version / "api" / "v1").mkdir(parents=True)
    (version / "api" / "v1" / "waves.json.gz").write_bytes(b"payload")
    publish.backup(version)
    restored = publish.restore(tmp_path / "new")
    assert (tmp_path / "new" / "current" / "api" / "v1" / "waves.json.gz").read_bytes() == b"payload"
    assert restored.name == version.name
