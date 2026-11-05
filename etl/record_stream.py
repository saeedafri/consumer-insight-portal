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
