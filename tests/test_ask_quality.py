"""Ask Coresight's check of each survey after a publish (etl/ask_quality.py): every question the bank writes about the
survey's questions is asked and scored, and the report says how many were right. Uses tests/test_assistant.py's survey."""
import gzip
import json

from etl import ask_quality
from tests.test_assistant import DATES, index as survey   # noqa: F401 — the fixture builds the published question files


def test_a_survey_is_checked_question_by_question(survey, tmp_path):
    published = tmp_path   # the fixture wrote tmp_path/questions; the check reads the wave list beside it
    (published / "waves.json.gz").write_bytes(gzip.compress(json.dumps(
        [{"survey_id": 100 + i, "wave_date": d, "title": "Shopping and Spending", "modules": []} for i, d in enumerate(DATES)]).encode()))
    report, = ask_quality.check_surveys(published, [107])
    assert report["survey_id"] == 107 and report["questions"] == 1 and report["asked"] >= 5   # XQ1: latest, trend, by generation…
    assert 0 < report["right"] <= report["asked"] and len(report["misses"]) == report["asked"] - report["right"]
