"""A burst of requests on a fresh container (no published files yet) reads the wave list from the database once, not
once per request: 4 pooled connections ran out under 100 at once on Azure (5 Nov 2026)."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from api import main


def test_a_burst_builds_the_wave_list_once(monkeypatch):
    calls = []
    def slow_waves(boards):
        calls.append(1)
        time.sleep(0.2)
        return [{"survey_id": 1, "survey_family": "CSI-US", "study_type": "tracker"}]
    monkeypatch.setattr(main, "WAVES", ((), []))
    monkeypatch.setattr(main, "published_file", lambda *parts: None)
    monkeypatch.setattr(main.payloads, "waves", slow_waves)
    start = threading.Barrier(40)
    def ask():
        start.wait()
        return main.all_waves()
    with ThreadPoolExecutor(40) as pool:
        answers = list(pool.map(lambda _: ask(), range(40)))
    assert len(calls) == 1
    assert all(a and a[0]["survey_id"] == 1 for a in answers)
