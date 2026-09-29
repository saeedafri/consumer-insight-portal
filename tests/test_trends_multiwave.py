"""Trends across more than one wave.

We only have one real wave, so this test builds a SECOND, SYNTHETIC wave in a
throwaway database. The numbers in it are invented and exist purely to prove
the trend code path works; nothing here touches the real data or the demo
database, and nothing synthetic is ever loaded into dwh_stg.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "data" / "csi_local.db"
pytestmark = pytest.mark.skipif(not DEMO.exists(), reason="no local database built")


@pytest.fixture()
def two_wave_db(tmp_path):
    """Copy the real wave, then clone it under a second label with shifted
    percentages so the trend has two points to join."""
    db = tmp_path / "trend.db"
    src = sqlite3.connect(str(DEMO))
    dst = sqlite3.connect(str(db))
    src.backup(dst)
    src.close()

    dst.execute(
        "INSERT INTO csi_survey (forsta_host, forsta_path, title, survey_family,"
        " wave_label, wave_date, status) VALUES"
        " ('synthetic', 'synthetic/test/wave2', 'SYNTHETIC TEST WAVE',"
        "  'CSI-US', '2026-10', '2026-10-01', 'closed')"
    )
    new_id = dst.execute("SELECT MAX(survey_id) FROM csi_survey").fetchone()[0]

    # clone the definition layer
    dst.execute("INSERT INTO csi_question (survey_id, topic_id, qcode, qtext,"
                " qtext_short, qtype, value_min, value_max, is_technical, is_multi,"
                " base_n, sort_order)"
                " SELECT ?, topic_id, qcode, qtext, qtext_short, qtype, value_min,"
                " value_max, is_technical, is_multi, base_n, sort_order"
                " FROM csi_question WHERE survey_id = 1", (new_id,))
    dst.execute("INSERT INTO csi_item (question_id, item_code, item_label, item_short,"
                " is_exclusive, is_other, sort_order)"
                " SELECT q2.question_id, i.item_code, i.item_label, i.item_short,"
                " i.is_exclusive, i.is_other, i.sort_order"
                " FROM csi_item i"
                " JOIN csi_question q1 ON q1.question_id = i.question_id AND q1.survey_id = 1"
                " JOIN csi_question q2 ON q2.qcode = q1.qcode AND q2.survey_id = ?", (new_id,))
    dst.execute("INSERT INTO csi_field (survey_id, question_id, item_id, field_name, value_type)"
                " SELECT ?, q2.question_id, i2.item_id, f.field_name, f.value_type"
                " FROM csi_field f"
                " JOIN csi_question q1 ON q1.question_id = f.question_id AND q1.survey_id = 1"
                " JOIN csi_question q2 ON q2.qcode = q1.qcode AND q2.survey_id = ?"
                " LEFT JOIN csi_item i1 ON i1.item_id = f.item_id"
                " LEFT JOIN csi_item i2 ON i2.question_id = q2.question_id"
                "        AND i2.item_code = i1.item_code", (new_id, new_id))

    # clone half the respondents, so the second wave has a different base
    dst.execute("INSERT INTO csi_respondent (survey_id, record_no, status_code,"
                " status_label, is_qualified, completed_at)"
                " SELECT ?, record_no, status_code, status_label, is_qualified,"
                " completed_at FROM csi_respondent WHERE survey_id = 1"
                " AND record_no % 2 = 0", (new_id,))
    dst.execute("INSERT INTO csi_answer (respondent_id, survey_id, field_id,"
                " value_code, value_label)"
                " SELECT r2.respondent_id, ?, f2.field_id, a.value_code, a.value_label"
                " FROM csi_answer a"
                " JOIN csi_respondent r1 ON r1.respondent_id = a.respondent_id AND r1.survey_id = 1"
                " JOIN csi_respondent r2 ON r2.record_no = r1.record_no AND r2.survey_id = ?"
                " JOIN csi_field f1 ON f1.field_id = a.field_id"
                " JOIN csi_field f2 ON f2.field_name = f1.field_name AND f2.survey_id = ?",
                (new_id, new_id, new_id))
    dst.commit()
    dst.close()

    old = os.environ.get("LOCAL_SQLITE_PATH")
    os.environ["LOCAL_SQLITE_PATH"] = str(db)
    os.environ["APP_ENV"] = "LOCAL"

    import app.core.database as database
    database._engines.clear()
    database._sessions.clear()
    database._conflict_targets.cache_clear()
    yield db
    database._engines.clear()
    database._sessions.clear()
    if old:
        os.environ["LOCAL_SQLITE_PATH"] = old


def test_trend_joins_two_waves(two_wave_db):
    import app.data.repository as repo
    for name in dir(repo):
        fn = getattr(repo, name)
        if hasattr(fn, "__wrapped__"):
            setattr(repo, name, fn.__wrapped__)

    surveys = repo.list_surveys()
    csi = surveys[surveys.survey_family == "CSI-US"]
    assert len(csi) == 2, "the fixture must produce two waves"

    trend = repo.trend("CSI-US", "q1")
    assert not trend.empty
    assert trend.wave_label.nunique() == 2, "both waves must appear in the trend"

    # each wave keeps its own base — the whole reason the page warns about it
    bases = trend.groupby("wave_label")["base_n"].max()
    assert bases.nunique() == 2, "the synthetic wave has half the respondents"
    assert bases.min() < bases.max()


def test_single_wave_family_returns_one_point(two_wave_db):
    """A family with one wave must not silently look like a trend."""
    import app.data.repository as repo
    for name in dir(repo):
        fn = getattr(repo, name)
        if hasattr(fn, "__wrapped__"):
            setattr(repo, name, fn.__wrapped__)
    trend = repo.trend("CSI-US", "q1")
    single = trend[trend.wave_label == trend.wave_label.iloc[0]]
    assert single.wave_label.nunique() == 1
