"""Cold ETL startup must not allocate optional UI/reporting frameworks."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


PROBE = '''
import importlib, json, resource, socket, sys, time
def blocked(*args, **kwargs):
    raise AssertionError("cold import attempted network access")
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.create_connection = blocked
started = time.perf_counter()
module = importlib.import_module(sys.argv[1])
if len(sys.argv) > 2:
    from pathlib import Path
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as directory:
        module.ERRORS = Path(directory) / "errors.jsonl"
        module.setup_logging()
print(json.dumps({
    "seconds": time.perf_counter() - started,
    "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1048576 if sys.platform == "darwin" else 1024),
    "optional_loaded": sorted(set(sys.modules) & {"pandas", "numpy", "streamlit", "fastapi"}),
}))
'''


@pytest.mark.parametrize('module', ['etl.forsta_etl', 'etl.notify', 'scripts.weekly_forsta'])
def test_etl_cold_import_excludes_optional_frameworks(module):
    result = subprocess.run(
        [sys.executable, '-c', PROBE, module],
        cwd=Path(__file__).resolve().parents[1], env=os.environ.copy(),
        capture_output=True, text=True, timeout=20, check=True,
    )
    measurement = json.loads(result.stdout.splitlines()[-1])
    assert measurement['optional_loaded'] == [], measurement


def test_weekly_logging_does_not_load_the_ui_framework():
    result = subprocess.run(
        [sys.executable, '-c', PROBE, 'scripts.weekly_forsta', '--logging'],
        cwd=Path(__file__).resolve().parents[1], env=os.environ.copy(),
        capture_output=True, text=True, timeout=20, check=True,
    )
    assert json.loads(result.stdout.splitlines()[-1])['optional_loaded'] == []
