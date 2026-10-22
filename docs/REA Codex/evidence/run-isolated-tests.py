"""Run fixture-isolated audit tests with dotenv and outbound connections disabled."""
from pathlib import Path
import os
import socket
import sys
import tempfile

import dotenv

root = Path(__file__).resolve().parents[3]
os.chdir(root)
sys.path.insert(0, str(root))
dotenv.load_dotenv = lambda *args, **kwargs: False
for name in list(os.environ):
    if name.startswith(("SMTP_", "FORSTA_", "STG_DB_", "APP_DB_", "TEAMS_", "CIP_PUBLISH_BACKUP")):
        os.environ.pop(name, None)
os.environ["APP_ENV"] = "LOCAL"


def no_network(*args, **kwargs):
    raise RuntimeError("Audit test guard: external network disabled")


socket.socket.connect = no_network
with tempfile.TemporaryDirectory(prefix="cip-audit-") as temporary:
    os.environ["LOCAL_SQLITE_PATH"] = str(Path(temporary) / "audit.sqlite")
    import pytest

    raise SystemExit(pytest.main([
        "-q", "tests", "--ignore=tests/test_analysis.py", "--disable-warnings"
    ]))

