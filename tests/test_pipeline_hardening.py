"""Pipeline hardening (19 Oct 2026): significance letters, bulk-load escaping, integrity healing, masked logs."""
from __future__ import annotations

import importlib
import json
import logging

import sqlalchemy as sa

from app.core import database
from etl import crosstab_export, forsta_etl, integrity
from tests.test_forsta_etl import FakeForsta, record


def test_the_z_test_gives_forstas_letters_on_the_teams_holiday_banner():
    # q1 "Gone to a shopping mall", 10/12/26: Still shopping 41/117 beats Not yet started 47/222 at 95 % ('B');
    # Finished shopping 11/32 does not beat it even at 90 % (their file: 'E' only, no 'b').
    assert crosstab_export.ztest(41, 117, 47, 222) > crosstab_export.Z95
    assert crosstab_export.ztest(11, 32, 47, 222) < crosstab_export.Z90
    assert crosstab_export.ztest(5, 1, 3, 40) == 0.0                 # no test on a base under 2


def test_stat_groups_read_forstas_notation():
    assert crosstab_export.stat_groups("holiday_status") == [[1, 2, 3, 4], [5, 6]]
    assert crosstab_export.stat_groups("standard") == []


def test_marks_letter_each_column_against_its_group_only():
    block = lambda x, n: [(None, [("Yes", float(x)), ("Count", 1.0)], n)]
    per = [block(150, 300), block(90, 100), block(10, 100), block(50, 100)]   # Total, B, C, D
    letters = crosstab_export.marks(per, 0, [[1, 2]])
    assert letters == {0: ["", "C", "", ""]}                          # D is outside the group; Count gets none


def test_load_data_fields_escape_what_mysql_would_read_as_structure():
    assert database.tsv(None) == r"\N"
    assert database.tsv("a\tb\\c\nd\re") == "a\\tb\\\\c\\nd\\re"
    assert database.tsv(2.5) == "2.5"


def test_integrity_heals_derived_rows_and_reports_base_problems(csi_db):
    forsta_etl.discover(FakeForsta())
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    assert integrity.run() == ["closed Forsta survey still not loaded after 3 days: 1 rows"]   # Holiday, closed 16 Sep
    forsta_etl.load_survey(FakeForsta(data={"selfserve/58f/260905": [record(n) for n in range(6, 9)]}), "selfserve/58f/260905")
    assert integrity.run() == []
    with csi_db.begin() as conn:
        conn.execute(sa.text("DELETE FROM cip_agg_cell WHERE survey_id = :s"), {"s": sid})
        conn.execute(sa.text("DELETE FROM cip_search WHERE survey_id = :s AND kind = 'survey'"), {"s": sid})
        conn.execute(sa.text("INSERT INTO cip_wave_module (forsta_path, module_code, module_name, kind)"
                             " VALUES ('selfserve/58f/gone', 'x', 'x', 'topic')"))
    assert integrity.run() == []                                      # all three are derived: rebuilt or removed
    with csi_db.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM cip_agg_cell WHERE survey_id = :s"), {"s": sid}).scalar() > 0
        assert conn.execute(sa.text("SELECT COUNT(*) FROM cip_wave_module WHERE forsta_path = 'selfserve/58f/gone'")).scalar() == 0
    with csi_db.begin() as conn:
        conn.execute(sa.text("UPDATE cip_forsta_survey SET survey_id = 99999 WHERE forsta_path = 'selfserve/58f/260905'"))
    left = integrity.run()
    assert left == ["register row pointing at a missing wave: 1 rows",
                    "register says loaded, wave not verified: 1 rows"]       # loaded data is never changed by itself


def test_the_logs_never_show_a_secret(monkeypatch):
    weekly = importlib.import_module("scripts.weekly_forsta")
    monkeypatch.setattr(weekly.Masked, "secrets", ["s3cret-api-key-123"])
    record = logging.LogRecord("cip.forsta", logging.ERROR, __file__, 1, "401 for key %s", ("s3cret-api-key-123",), None)
    assert "s3cret" not in weekly.Masked("%(message)s").format(record)
    entry = json.loads(weekly.JsonLines("%(message)s").format(record))
    assert entry["message"] == "401 for key ***" and entry["step"] == "cip.forsta" and entry["level"] == "ERROR"


def test_the_scheduled_run_writes_warnings_to_the_json_error_log(tmp_path, monkeypatch):
    weekly = importlib.import_module("scripts.weekly_forsta")
    monkeypatch.setattr(weekly, "ERRORS", tmp_path / "errors.jsonl")
    root = logging.getLogger()
    kept = root.handlers[:], root.level
    try:
        weekly.setup_logging()
        logging.getLogger("cip.integrity").warning("Integrity: %s", "something")
        logging.getLogger("cip.weekly").info("not an error")
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers[:], root.level = kept
    lines = (tmp_path / "errors.jsonl").read_text().splitlines()
    assert [json.loads(line)["message"] for line in lines] == ["Integrity: something"]
