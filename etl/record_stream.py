"""Private, replayable disk snapshots for multi-pass source verification."""
from contextlib import contextmanager
import json
import tempfile


class RecordSnapshot:
    def __init__(self, records):
        self._file = tempfile.TemporaryFile(mode='w+t', encoding='utf-8', newline='\n')
        self.count = 0
        try:
            for record in records:
                if record.get('uuid'):
                    self._file.write(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n')
                    self.count += 1
        except BaseException:
            self.close()
            raise

    def __len__(self):
        return self.count

    def __iter__(self):
        self._file.seek(0)
        for line in self._file:
            yield json.loads(line)

    def close(self):
        self._file.close()


@contextmanager
def source_records(client, path):
    """A survey's respondents as Forsta sends them (GET .../data), qualified only: every screen, cube and weight uses
    qualified respondents alone, and the others were 60 % of the download and of the answers stored (survey 261003,
    7 Nov 2026: 1,044 records and 5.1 MB unfiltered, 403 and 2.0 MB qualified, 3.9 s down to 0.7 s). Used by the
    load (etl/forsta_etl.py load_wave) and the re-check against Forsta (_reconcile); a reloaded wave drops the
    respondents Forsta no longer sends, so older waves lose their unqualified rows as they are reloaded."""
    reader = getattr(client, 'iter_survey_data', None) or client.survey_data
    rows = reader(path, cond="qualified")
    try:
        yield rows
    finally:
        close = getattr(rows, 'close', None)
        if close:
            close()


@contextmanager
def survey_snapshot(client, path):
    with source_records(client, path) as records:
        snapshot = RecordSnapshot(records)
        try:
            yield snapshot
        finally:
            snapshot.close()
