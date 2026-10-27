"""Static publishing (etl/publish.py): standard screens become files nginx serves, swapped in atomically."""
import gzip
import json
import time
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa

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
    live_trend = next((second / "api/v1/questions").rglob("*.json.gz"))
    before = live_trend.read_bytes()
    third_dir = publish.build(tmp_path, jobs=1)
    third = json.loads((third_dir / "manifest.json").read_text())
    assert (third["rebuilt_waves"], third["rebuilt_families"]) == (1, 1)
    rewritten = third_dir / live_trend.relative_to(second)                           # the wave asked it: rewritten
    assert rewritten.stat().st_ino != live_trend.stat().st_ino and live_trend.read_bytes() == before   # live copy untouched
    assert publish.rollback(tmp_path).name == first.name and live.resolve() == first.resolve()


def test_publish_preserves_mysql_grouping_and_canonical_payloads(csi_db, tmp_path, caplog):
    from etl import forsta_etl
    from tests.test_forsta_etl import FakeForsta

    caplog.set_level("INFO", logger="cip.publish")
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    with csi_db.connect() as conn:
        grouped = payloads.question_cuts(conn, [sid])
        direct_people = payloads.people(conn, sid)

    statements = []

    def record(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(" ".join(statement.lower().split()))

    sa.event.listen(csi_db, "before_cursor_execute", record)
    try:
        built = publish.build(tmp_path, jobs=1)
    finally:
        sa.event.remove(csi_db, "before_cursor_execute", record)
    answer_sql = [sql for sql in statements if " from srv_answer " in f" {sql} "]
    assert sum(" group by " in f" {sql} " for sql in answer_sql) == 1
    assert len(answer_sql) == 2
    assert not any("select distinct w.survey_family" in sql for sql in statements)
    messages = [record.getMessage() for record in caplog.records if record.name == "cip.publish"]
    assert any("expected_srv_answer_reads=2" in message for message in messages)
    assert any("workers_configured=1 workers_effective=1" in message for message in messages)
    assert any("cut_read_build_seconds=" in message and "wall_seconds=" in message for message in messages)
    assert not any("query_count=" in message for message in messages)
    for (_, qcode), part in grouped.items():
        payload = gzip.decompress((built / f"api/v1/waves/{sid}/cuts/{qcode}.json.gz").read_bytes())
        assert payload == payloads.encode(part)
    people_payload = gzip.decompress((built / f"api/v1/waves/{sid}/people.json.gz").read_bytes())
    assert people_payload == payloads.encode(direct_people)


def test_mysql_collation_forbids_naive_python_grouping():
    schema = (Path(__file__).parents[1] / "sql/005_serving.sql").read_text()
    assert "COLLATE=utf8mb4_0900_ai_ci" in schema
    assert len({"Male", "male", "e", "é"}) == 4


def test_people_closes_the_stream_when_row_iteration_fails():
    class BrokenStream:
        closed = False

        def __iter__(self):
            yield (1, "Q1", 0, 1, "Male", "18-29", "Gen Z", "$25k", "West", "Urban")
            raise RuntimeError("injected stream failure")

        def close(self):
            self.closed = True

    stream = BrokenStream()

    class Connection:
        def execute(self, _statement, _params):
            return stream

    with pytest.raises(RuntimeError, match="injected stream failure"):
        payloads.people(Connection(), 1)
    assert stream.closed


def test_publish_worker_count_is_configurable_and_bounded(monkeypatch):
    monkeypatch.setenv("CIP_PUBLISH_JOBS", "2")
    assert publish.worker_count() == 2
    assert publish.worker_count(1) == 1 and publish.worker_count(4) == 4
    monkeypatch.delenv("CIP_PUBLISH_JOBS")
    assert publish.worker_count() == 4
    monkeypatch.setenv("CIP_PUBLISH_JOBS", "many")
    assert publish.worker_count(3) == 3
    for invalid in (0, 5, "many", ""):
        with pytest.raises(ValueError, match="1 to 4"):
            publish.worker_count(invalid)


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
    monkeypatch.setattr("requests.put", put)
    monkeypatch.setattr("requests.get", lambda url, **k: Reply(store[url.split("?")[0].rsplit("/", 1)[1]]))
    version = tmp_path / "old" / ".build-20261021T000000Z"
    (version / "api" / "v1").mkdir(parents=True)
    (version / "api" / "v1" / "waves.json.gz").write_bytes(b"payload")
    publish.backup(version)
    restored = publish.restore(tmp_path / "new")
    assert (tmp_path / "new" / "current" / "api" / "v1" / "waves.json.gz").read_bytes() == b"payload"
    assert restored.name == version.name


def test_a_reload_that_drops_a_question_leaves_no_stale_question_file(csi_db, tmp_path):
    import sqlalchemy as sa
    with csi_db.begin() as conn:
        seed(conn, 266, date(2026, 10, 5), qualified=401, xm1_yes=92, xm1_base=149)
        seed(conn, 412, date(2026, 10, 12), qualified=404, xm1_yes=125, xm1_base=404)
    serving.build_wave(266), serving.build_wave(412)
    publish.publish(tmp_path, jobs=1)
    target = tmp_path / "current/api/v1/questions/CSI-US/tracker/XM1.json.gz"
    assert [w[0] for w in json.loads(gzip.decompress(target.read_bytes()))["waves"]] == [266, 412]
    time.sleep(1.1)
    with csi_db.begin() as conn:                     # the reload of 412 no longer has XM1
        conn.execute(sa.text("DELETE FROM cip_agg_cell WHERE survey_id = 412"))
    serving.build_wave(412)
    publish.publish(tmp_path, jobs=1)
    assert [w[0] for w in json.loads(gzip.decompress(target.read_bytes()))["waves"]] == [266]


def test_a_new_small_cell_rule_rebuilds_every_wave(csi_db, tmp_path, monkeypatch):
    with csi_db.begin() as conn:
        seed(conn, 266, date(2026, 10, 5), qualified=401, xm1_yes=92, xm1_base=149)
        seed(conn, 412, date(2026, 10, 12), qualified=404, xm1_yes=125, xm1_base=404)
    serving.build_wave(266), serving.build_wave(412)
    publish.publish(tmp_path, jobs=1)
    assert json.loads((publish.build(tmp_path, jobs=1) / "manifest.json").read_text())["rebuilt_waves"] == 0
    monkeypatch.setattr(payloads, "HIDDEN_BASE", 10)                                  # the rule changed: nothing is reused
    assert json.loads((publish.build(tmp_path, jobs=1) / "manifest.json").read_text())["rebuilt_waves"] == 2


def test_a_publish_empties_the_nginx_answer_cache(tmp_path, monkeypatch):
    cache = tmp_path / "nginx-cache"
    (cache / "a" / "bc").mkdir(parents=True)
    (cache / "a" / "bc" / "f00").write_text("old cross-tab")
    monkeypatch.setenv("CIP_NGINX_CACHE", str(cache))
    publish.empty_nginx_cache()
    assert cache.is_dir() and list(cache.iterdir()) == []                 # the folder stays, its answers go
