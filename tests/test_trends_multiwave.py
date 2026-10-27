"""Trends across two deterministic synthetic waves."""
from __future__ import annotations

import pytest
import sqlalchemy as sa


@pytest.fixture()
def two_wave_db(csi_db):
    with csi_db.begin() as conn:
        for survey_id, wave, respondents, selected in (
            (1, "2026-09-21", 10, 6),
            (2, "2026-09-28", 5, 2),
        ):
            conn.execute(sa.text(
                "INSERT INTO cip_survey (survey_id,forsta_host,forsta_path,title,survey_family,wave_label,wave_date,"
                "platform,source_ref,load_status) VALUES (:s,'synthetic.invalid',:p,'Synthetic trend','CSI-US',:w,:w,"
                "'forsta',:p,'verified')"
            ), {"s": survey_id, "p": f"synthetic/trend/{survey_id}", "w": wave})
            question_id = conn.execute(sa.text(
                "INSERT INTO cip_question (survey_id,qcode,qtext,qtype,is_multi,base_n) "
                "VALUES (:s,'q1','Synthetic trend question','multi',1,:n)"
            ), {"s": survey_id, "n": respondents}).lastrowid
            item_id = conn.execute(sa.text(
                "INSERT INTO cip_item (question_id,item_code,item_label,sort_order) VALUES (:q,'q1r1','Selected',1)"
            ), {"q": question_id}).lastrowid
            field_id = conn.execute(sa.text(
                "INSERT INTO cip_field (survey_id,question_id,item_id,field_name,value_type) "
                "VALUES (:s,:q,:i,'q1r1','code')"
            ), {"s": survey_id, "q": question_id, "i": item_id}).lastrowid
            for record_no in range(1, respondents + 1):
                respondent_id = conn.execute(sa.text(
                    "INSERT INTO cip_respondent (survey_id,record_no,status_code,status_label,is_qualified) "
                    "VALUES (:s,:r,3,'Qualified',1)"
                ), {"s": survey_id, "r": record_no}).lastrowid
                conn.execute(sa.text(
                    "INSERT INTO cip_answer (respondent_id,survey_id,field_id,value_code,value_label) "
                    "VALUES (:r,:s,:f,:v,'Selected')"
                ), {"r": respondent_id, "s": survey_id, "f": field_id,
                    "v": 1 if record_no <= selected else 0})
    return csi_db


def test_trend_joins_two_waves(two_wave_db):
    import app.data.repository as repo
    for name in dir(repo):
        fn = getattr(repo, name)
        if hasattr(fn, "__wrapped__"):
            setattr(repo, name, fn.__wrapped__)

    surveys = repo.list_surveys()
    csi = surveys[surveys.survey_family == "CSI-US"]
    assert len(csi) >= 2, "the fixture must produce at least two waves"

    trend = repo.trend("CSI-US", "q1")
    assert not trend.empty
    assert trend.wave_label.nunique() == len(csi), "every wave must appear in the trend"

    # each wave keeps its own base — the whole reason the page warns about it
    bases = trend.groupby("wave_label")["base_n"].max()
    assert bases.nunique() >= 2, "the synthetic wave has half the respondents"
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
