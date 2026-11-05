"""Offline synthetic load/reconciliation benchmark; never reaches production services."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import logging
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time
import tracemalloc
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref')
    parser.add_argument('--people', type=int, default=2200)
    parser.add_argument('--fields', type=int, default=300)
    parser.add_argument('--trace-allocations', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.people < 1 or args.fields < 0:
        parser.error('people must be positive and fields nonnegative')

    # The existing fixture blocks sockets and shadows live credentials before
    # any application imports. All tables below live in its temporary SQLite DB.
    from tests import conftest
    import pytest
    from sqlalchemy import inspect, text
    from tests.test_forsta_etl import FakeForsta, REAL_SHAPES, record
    from etl import forsta_etl

    if args.baseline_ref:
        code = subprocess.run(['git', 'show', f'{args.baseline_ref}:etl/forsta_etl.py'],
                              cwd=ROOT, check=True, capture_output=True, text=True).stdout
        original = types.ModuleType('cip_benchmark_baseline')
        exec(compile(code, 'baseline/forsta_etl.py', 'exec'), original.__dict__)
        forsta_etl = original

    class Source(FakeForsta):
        def survey_datamap(self, path):
            return {'questions': REAL_SHAPES['questions'] + [
                {'qlabel': f'm{f}', 'qtitle': f'Measure {f}', 'type': 'single',
                 'values': [{'value': 1, 'title': 'One'}, {'value': 2, 'title': 'Two'}],
                 'variables': [{'label': f'm{f}', 'type': 'single'}]} for f in range(args.fields)]}

        def iter_survey_data(self, path, **params):
            for n in range(1, args.people + 1):
                row = record(n)
                row.update({f'm{f}': str(1 + n % 2) for f in range(args.fields)})
                yield row

        def survey_data(self, path, **params):
            return list(self.iter_survey_data(path, **params))

    def measured(action):
        gc.collect()
        if args.trace_allocations:
            tracemalloc.start()
        start = time.perf_counter()
        value = action()
        duration = time.perf_counter() - start
        peak = tracemalloc.get_traced_memory()[1] / 1048576 if args.trace_allocations else None
        if args.trace_allocations:
            tracemalloc.stop()
        return value, duration, peak

    logging.getLogger().setLevel(logging.ERROR)
    with tempfile.TemporaryDirectory(prefix='cip-offline-bench-') as directory, pytest.MonkeyPatch.context() as patch:
        fixture = conftest.csi_db.__wrapped__(Path(directory), patch)
        engine = next(fixture)
        try:
            sid, load_time, load_peak = measured(lambda: forsta_etl.load_survey(Source(), 'selfserve/58f/260907'))
            (checked, problems), check_time, check_peak = measured(lambda: forsta_etl.reconcile_survey(sid, Source()))
            digests = {}
            with engine.connect() as conn:
                for table in ('cip_respondent', 'cip_answer', 'cip_agg_cell', 'cip_tracker_line', 'srv_result', 'srv_answer'):
                    columns = [c['name'] for c in inspect(engine).get_columns(table)
                               if c['name'] not in {'created_at', 'updated_at', 'loaded_at', 'built_at'}]
                    keys = inspect(engine).get_pk_constraint(table)['constrained_columns']
                    digest, count = hashlib.sha256(), 0
                    for row in conn.execute(text(f'SELECT {", ".join(columns)} FROM {table} ORDER BY {", ".join(keys)}')):
                        digest.update(json.dumps(tuple(row), default=str, ensure_ascii=True, separators=(',', ':')).encode())
                        digest.update(b'\n')
                        count += 1
                    digests[table] = {'rows': count, 'sha256': digest.hexdigest()}
            result = {'environment': 'offline synthetic SQLite; no warehouse/source/SMTP calls',
                      'baseline_ref': args.baseline_ref, 'people': args.people, 'extra_fields': args.fields,
                      'trace_allocations': args.trace_allocations, 'load_seconds': load_time,
                      'load_python_peak_mib': load_peak, 'reconcile_seconds': check_time,
                      'reconcile_python_peak_mib': check_peak, 'checked_answers': checked, 'problems': problems,
                      'tables': digests,
                      'process_peak_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss /
                      (1048576 if sys.platform == 'darwin' else 1024),
                      'limits': 'RSS includes test-fixture imports and SQLite; excludes email, publication, remote DB and live network. Baseline replaces loader only; cold-import results are separate.'}
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result))
            return 1 if problems or checked != digests['cip_answer']['rows'] else 0
        finally:
            try:
                next(fixture)
            except StopIteration:
                pass


if __name__ == '__main__':
    raise SystemExit(main())
