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


def test_every_verified_answer_is_asked_again_and_one_no_longer_found_is_listed(survey, tmp_path, monkeypatch):
    from api import ask_index
    if survey.vectors is None:
        import pytest
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
    (tmp_path / "waves.json.gz").write_bytes(gzip.compress(json.dumps(
        [{"survey_id": 100 + i, "wave_date": d, "title": "Shopping and Spending", "modules": []} for i, d in enumerate(DATES)]).encode()))
    reviewed = tmp_path / "ask_verified.yml"
    reviewed.write_text('- {question: "Retailers people bought from recently", code: XQ1, kind: top, period: latest}\n'
                        '- {question: "A question whose survey question is gone", code: ZZ9, kind: share, period: latest}\n')
    monkeypatch.setattr(ask_index, "VERIFIED", reviewed)
    ask_quality.check_surveys(tmp_path, [107])
    check = json.loads(ask_quality.VERIFIED_REPORT.read_text())
    assert check["verified"] == 1 and check["right"] == 1 and check["wrong"] == []   # still answered from XQ1
    assert check["not_found"] == ["A question whose survey question is gone"]
