"""Bound source-row retention while exercising the complete offline wave load."""
import pytest
from sqlalchemy import text

from etl import forsta_etl
from tests.test_forsta_etl import FakeForsta, record


class SourceRow(dict):
    active = 0
    peak = 0

    def __init__(self, value):
        super().__init__(value)
        SourceRow.active += 1
        SourceRow.peak = max(SourceRow.peak, SourceRow.active)

    def __del__(self):
        SourceRow.active -= 1


class StreamForsta(FakeForsta):
    def iter_survey_data(self, path, **params):
        for n in range(1, 129):
            yield SourceRow(record(n))

    def survey_data(self, path, **params):
        return list(self.iter_survey_data(path, **params))


def test_load_keeps_only_a_bounded_number_of_source_rows(csi_db):
    SourceRow.active = SourceRow.peak = 0
    sid = forsta_etl.load_survey(StreamForsta(), 'selfserve/58f/260907')
    with csi_db.connect() as conn:
        assert conn.execute(text('SELECT COUNT(*) FROM cip_respondent WHERE survey_id=:s'), {'s': sid}).scalar() == 128
    assert SourceRow.peak <= 4, f'load retained {SourceRow.peak} complete source records'


def test_reconciliation_streams_source_and_still_compares_all_answers(csi_db):
    sid = forsta_etl.load_survey(StreamForsta(), 'selfserve/58f/260907')
    SourceRow.peak = 0
    checked, problems = forsta_etl.reconcile_survey(sid, StreamForsta())
    with csi_db.connect() as conn:
        count = conn.execute(text('SELECT COUNT(*) FROM cip_answer WHERE survey_id=:s'), {'s': sid}).scalar()
    assert checked == count
    assert problems == []
    assert SourceRow.peak <= 4


def test_interrupted_source_preserves_the_verified_wave(csi_db):
    sid = forsta_etl.load_survey(FakeForsta(), 'selfserve/58f/260907')
    with csi_db.connect() as conn:
        before = list(conn.execute(text('SELECT * FROM cip_answer WHERE survey_id=:s ORDER BY answer_id'), {'s': sid}))

    class Interrupted(FakeForsta):
        def iter_survey_data(self, path, **params):
            yield record(1)
            raise ConnectionError('source disconnected')

    with pytest.raises(ConnectionError, match='source disconnected'):
        forsta_etl.load_survey(Interrupted(), 'selfserve/58f/260907')
    with csi_db.connect() as conn:
        assert list(conn.execute(text('SELECT * FROM cip_answer WHERE survey_id=:s ORDER BY answer_id'), {'s': sid})) == before
        assert conn.execute(text('SELECT load_status FROM cip_survey WHERE survey_id=:s'), {'s': sid}).scalar() == 'verified'


def test_private_snapshot_replays_native_values_and_closes_on_failure():
    from etl.record_stream import RecordSnapshot, survey_snapshot
    values = [{'uuid': 'u1', 'value': 0, 'null': None, 'flag': False, 'text': 'café\nsecond line'}]
    snapshot = RecordSnapshot(iter(values))
    try:
        assert len(snapshot) == 1
        assert list(snapshot) == list(snapshot) == values
    finally:
        snapshot.close()
    assert snapshot._file.closed
    closed = []

    class Interrupted:
        def iter_survey_data(self, path, **params):
            try:
                yield values[0]
                raise ConnectionError('interrupted export')
            finally:
                closed.append(True)

    with pytest.raises(ConnectionError):
        with survey_snapshot(Interrupted(), 'path'):
            pytest.fail('partial export escaped')
    assert closed == [True]


def test_only_qualified_respondents_are_downloaded():
    """Forsta filters before sending (cond=qualified): the others were 60 % of every download and never used."""
    asked = []

    class Forsta:
        def iter_survey_data(self, path, **params):
            asked.append(params)
            yield {"uuid": "a", "status": 3}

    from etl.record_stream import survey_snapshot
    with survey_snapshot(Forsta(), "selfserve/58f/261003") as records:
        assert len(records) == 1
    assert asked == [{"cond": "qualified"}]
