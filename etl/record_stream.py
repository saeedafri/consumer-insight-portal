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
    """A survey's respondents as Forsta sends them (GET .../data): all of them, qualified, terminated, over quota and
    partial. The screens use qualified respondents only, but nothing Forsta holds is discarded: Forsta deletes
    archived surveys a year on, and the others are the record of the fieldwork. (Asking for qualified only would
    cut the download 60 %, 5.1 MB to 2.0 MB for survey 261003; the load runs in the background, users never wait on it.)
    Used by the load (etl/forsta_etl.py load_wave) and the re-check against Forsta (_reconcile)."""
    reader = getattr(client, 'iter_survey_data', None) or client.survey_data
    rows = reader(path)
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
