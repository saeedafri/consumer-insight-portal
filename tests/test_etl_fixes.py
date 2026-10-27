"""The 23 Oct 2026 audit's ETL fixes (docs/REA Claude Opus 2026-10-23/80-fixes-etl.md), one test per gap."""
import importlib
import re
from datetime import date, timedelta

import pytest
import sqlalchemy as sa

from app.core.database import tsv
from etl import forsta_etl, integrity, launch_schedule, serving
from tests.test_forsta_etl import SURVEYS, FakeForsta, record
from tests.test_phase6 import monkey  # noqa: F401  (fixture)

DECIMAL_18_4 = re.compile(r"^-?\d{1,14}(\.\d{1,4})?$")   # what MySQL stores without a Note (1265) in cip_answer.value_number
DECIMAL_6_3 = re.compile(r"^\d{1,3}(\.\d{1,3})?$")       # srv_result.pct, prior_pct, ly_pct


def wave(conn, survey_id, day, family="CSI-US", study="tracker", qualified=400, platform="qualtrics", ref=None, end=None):
    conn.execute(sa.text("INSERT INTO cip_survey (survey_id, forsta_host, forsta_path, title, wave_label, wave_date,"
                         " survey_family, study_type, load_status, platform, source_ref, field_end)"
                         " VALUES (:s, 'h', :p, 'Wave', :d, :d, :f, :t, 'verified', :pl, :p, :e)"),
                 {"s": survey_id, "p": ref or f"ref{survey_id}", "d": day, "f": family, "t": study, "pl": platform, "e": end})
    if qualified:
        conn.execute(sa.text("INSERT INTO cip_respondent (survey_id, record_no, is_qualified) VALUES (:s, :r, 1)"),
                     [{"s": survey_id, "r": r} for r in range(qualified)])


def multi(conn, survey_id, qcode, qtext, items, dims=(("total", "Total"),)):
    """A cubed multi-select question: items = [(label, n chosen, base)]; returns {label or index: item_id}."""
    qid = conn.execute(sa.text("INSERT INTO cip_question (survey_id, qcode, qtext, qtype, is_multi) VALUES (:s, :q, :t, 'multi', 1)"),
                       {"s": survey_id, "q": qcode, "t": qtext}).lastrowid
    ids = []
    for order, (label, n, base) in enumerate(items, 1):
        iid = conn.execute(sa.text("INSERT INTO cip_item (question_id, item_code, item_label, sort_order) VALUES (:q, :c, :l, :o)"),
                           {"q": qid, "c": f"{qcode}r{order}", "l": label, "o": order}).lastrowid
        ids.append(iid)
        for dim, value in dims:
            conn.execute(sa.text("INSERT INTO cip_agg_cell (survey_id, cell_key, map_key, question_id, item_id, dim, dim_value, n, base_n)"
                                 " VALUES (:s, :k, :m, :q, :i, :d, :v, :n, :b)"),
                         {"s": survey_id, "k": f"{qid}:{iid}:{dim}:{value}", "m": f"{qid}:{iid}:0", "q": qid, "i": iid,
                          "d": dim, "v": value, "n": n, "b": base})
    return qid, ids


def served(engine, survey_id, qcode):
    with engine.connect() as conn:
        return conn.execute(sa.text("SELECT * FROM srv_result WHERE survey_id = :s AND qcode = :q AND dim = 'total'"
                                    " ORDER BY sort_order"), {"s": survey_id, "q": qcode}).all()


# ── ETL-01: numbers fit DECIMAL(18,4), so LOAD DATA never warns ────────────
def test_a_numeric_answer_is_rounded_to_the_four_decimals_mysql_stores():
    field = {"kind": "numeric", "multi": False, "item": None, "labels": {}}
    for raw, want in (("12.642123456", 12.6421), ("-0.00005", -0.0001), ("99999999999999.123456", None), ("61.12346", 61.1235)):
        got = forsta_etl._answer(field, raw)
        if want is None:   # 14 integer digits and a fraction: still storable, rounded
            assert DECIMAL_18_4.match(tsv(got["num"]))
            continue
        assert got["num"] == want and DECIMAL_18_4.match(tsv(got["num"])), (raw, got)


# ── ETL-02: items sharing a label are two cells, not one ──────────────────
def test_two_items_with_the_same_label_are_both_served_and_compared_only_when_unambiguous(csi_db):
    q7 = "Which social media platforms do you use? Select all that apply."
    with csi_db.begin() as conn:   # survey 97 Q7: YouTube twice; Facebook once
        wave(conn, 1, date(2026, 10, 5))
        multi(conn, 1, "Q7", q7, [("Facebook", 200, 400), ("YouTube", 0, 400), ("YouTube", 190, 400)])
        wave(conn, 2, date(2026, 10, 12))
        multi(conn, 2, "Q7", q7, [("Facebook", 100, 400), ("YouTube", 0, 400), ("YouTube", 188, 400)])
    serving.build_wave(1)
    rows = {(r.item_label, r.sort_order): r for r in served(csi_db, 2, "Q7")} if serving.build_wave(2) else {}
    assert len(rows) == 3                                                    # 3 cube cells, 3 serving rows
    assert float(rows[("YouTube", 3000)].pct) == 47.0 and rows[("YouTube", 2000)].n == 0
    assert rows[("YouTube", 3000)].prior_pct is None                        # "YouTube" is two cells: never guessed
    assert float(rows[("Facebook", 1000)].prior_pct) == 50.0
    for r in rows.values():
        assert DECIMAL_6_3.match(tsv(round(float(r.pct), 3)))


def test_integrity_finds_a_wave_whose_serving_rows_lost_cube_cells(csi_db):
    with csi_db.begin() as conn:
        wave(conn, 1, date(2026, 10, 12))
        multi(conn, 1, "Q7", "Which apps?", [("YouTube", 10, 400), ("YouTube", 190, 400)])
    serving.build_wave(1)
    check = next(c for c in integrity.CHECKS if c.name.startswith("served wave whose serving rows"))
    with csi_db.connect() as conn:
        assert integrity.found(conn, check) == []
    with csi_db.begin() as conn:                                            # as the label-keyed build left it
        conn.execute(sa.text("UPDATE srv_wave SET rows_built = 1 WHERE survey_id = 1"))
    with csi_db.connect() as conn:
        assert integrity.found(conn, check) == [1]
    check.fix(1)
    with csi_db.connect() as conn:
        assert integrity.found(conn, check) == []


def test_serving_integrity_check_does_not_use_the_timeout_prone_correlated_count():
    check = next(c for c in integrity.CHECKS if c.name.startswith("served wave whose serving rows"))

    class Connection:
        def execute(self, statement, params):
            sql = str(statement)
            if "LIMIT :waves" not in sql:
                raise sa.exc.OperationalError(
                    sql, params, Exception("(2013, Lost connection to MySQL server during query (The read operation timed out))")
                )
            assert params["waves"] == 20
            return [(415,)]

    assert integrity.found(Connection(), check) == [415]


# ── ETL-03: confirmed harmonisation reaches serving and its comparisons ───
def test_a_confirmed_concept_fills_serving_and_links_a_reworded_question(csi_db):
    with csi_db.begin() as conn:
        wave(conn, 1, date(2026, 10, 5))
        q1, (i1,) = multi(conn, 1, "SM1", "Which apps do you use for shopping?", [("TikTok", 100, 400)])
        wave(conn, 2, date(2026, 10, 12))
        q2, (i2,) = multi(conn, 2, "SM1", "Which of these apps do you use when you shop?", [("TikTok", 140, 400)])
        cid = conn.execute(sa.text("INSERT INTO cip_concept (concept_code, concept_name, qtype) VALUES ('SM1', 'Apps', 'multi')")).lastrowid
        coid = conn.execute(sa.text("INSERT INTO cip_concept_option (concept_id, option_code, option_label) VALUES (:c, 'tiktok', 'TikTok')"),
                            {"c": cid}).lastrowid
        for sid, qid, iid in ((1, q1, i1), (2, q2, i2)):
            conn.execute(sa.text("INSERT INTO cip_concept_map (survey_id, map_key, question_id, item_id, concept_id, concept_option_id,"
                                 " status, method) VALUES (:s, :k, :q, :i, :c, :o, 'confirmed', 'manual')"),
                         {"s": sid, "k": f"{qid}:{iid}:0", "q": qid, "i": iid, "c": cid, "o": coid})
    serving.build_wave(1), serving.build_wave(2)
    (row,) = served(csi_db, 2, "SM1")
    assert row.concept_option_id == coid and float(row.prior_pct) == 25.0 and "wording_changed_prior" not in row.flags


def test_same_wording_proposals_are_confirmed_only_when_asked_and_safe(csi_db):
    from app.data import harmonise
    with csi_db.begin() as conn:
        wave(conn, 1, date(2026, 10, 5), qualified=1)
        q = conn.execute(sa.text("INSERT INTO cip_question (survey_id, qcode, qtext, qtype) VALUES (1, 'Q1', 'Where?', 'single')")).lastrowid
        conn.execute(sa.text("INSERT INTO cip_option (question_id, value_code, value_label) VALUES (:q, 1, 'Costco')"), {"q": q})
        cid = conn.execute(sa.text("INSERT INTO cip_concept (concept_code, concept_name, qtype, match_text) VALUES ('Q1', 'Where?', 'single', 'where')")).lastrowid
        conn.execute(sa.text("INSERT INTO cip_concept_map (survey_id, map_key, question_id, concept_id, status, method)"
                             " VALUES (1, :k, :q, :c, 'proposed', 'exact_text')"), {"k": f"{q}:0:0", "q": q, "c": cid})
    assert harmonise.confirm_same_wording() == {1: 1}                       # a dry run writes nothing
    with csi_db.connect() as conn:
        assert conn.execute(sa.text("SELECT status FROM cip_concept_map WHERE map_key = :k"), {"k": f"{q}:0:0"}).scalar() == "proposed"
    assert harmonise.confirm_same_wording(apply=True) == {1: 1}
    with csi_db.connect() as conn:
        rows = conn.execute(sa.text("SELECT status, concept_option_id FROM cip_concept_map WHERE survey_id = 1 ORDER BY map_id")).all()
    assert rows[0][0] == "confirmed" and rows[1][0] == "confirmed" and rows[1][1] is not None   # the unit and its answer


# ── significance: one verdict, from the pipeline ───────────────────────────
def test_the_z_test_and_benjamini_hochberg_match_the_textbook():
    assert serving.p_value(125, 404, 92, 149) == pytest.approx(4.64e-11, rel=0.01)        # 30.9 % vs 61.7 %
    assert serving.p_value(200, 400, 200, 400) == 1.0
    assert serving.survives([0.01, 0.04, 0.03, 0.005]) == [True, True, True, True]          # 0.04 <= 4/4 × 0.05
    assert serving.survives([0.01, 0.2, 0.03, 0.04]) == [True, False, False, False]          # 0.03 > 2/4 × 0.05


def test_significance_flags_follow_the_written_rule(csi_db):
    q = "Which have you bought this week? Select all that apply."
    real = [(f"Brand {k}", 200, 400) for k in range(3)]
    with csi_db.begin() as conn:
        wave(conn, 1, date(2026, 10, 5))
        multi(conn, 1, "Q1", q, real + [("None of these", 40, 400), ("Tiny", 5, 20)] + [(f"Same {k}", 100, 400) for k in range(40)])
        wave(conn, 2, date(2026, 10, 12))
        multi(conn, 2, "Q1", q, [("Brand 0", 280, 400), ("Brand 1", 200, 400), ("Brand 2", 205, 400),
                                 ("None of these", 100, 400), ("Tiny", 18, 20)] + [(f"Same {k}", 100, 400) for k in range(40)])
    serving.build_wave(1), serving.build_wave(2)
    flags = {r.item_label: r.flags for r in served(csi_db, 2, "Q1")}
    assert "sig_prior" in flags["Brand 0"]                  # 70 % vs 50 %, n = 400 each: p ≈ 1e-8, survives BH
    assert "sig_prior" not in flags["Brand 2"]              # 51 % vs 50 %
    assert "sig_prior" not in flags["None of these"]        # a filler answer is never tested (25 % vs 10 %)
    assert "sig_prior" not in flags["Tiny"]                 # base 20 < TEST_BASE (90 % vs 25 %)
    # 43 rows were tested (Brand ×3 + Same ×40); the filler and the tiny base did not enter BH as p = 1
    with csi_db.connect() as conn:
        cut = conn.execute(sa.text("SELECT COUNT(*) FROM srv_result WHERE survey_id = 2 AND dim <> 'total' AND flags LIKE '%sig_%'")).scalar()
    assert cut == 0                                         # Total rows only


# ── ETL-04: one bad cycle does not end the Monday watch ────────────────────
def test_the_watch_carries_on_past_a_crashed_cycle(monkeypatch):
    weekly = importlib.import_module("scripts.weekly_forsta")
    from etl import notify
    results = iter([RuntimeError("Forsta 503 after 4 retries"), 0])

    def run():
        outcome = next(results)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(weekly, "run", run)
    monkeypatch.setattr(weekly, "beat", lambda *a, **k: None)
    monkeypatch.setattr(weekly.time, "sleep", lambda s: None)
    monkeypatch.setattr(launch_schedule, "weeks", lambda today=None: {"weeks": [{"date": "2026-10-26", "status": "loaded", "closed": "x"}]})
    week = {"date": date(2026, 10, 26), "topics": [], "names": ["Apparel"], "cycle": 21}
    assert weekly.watch(week) == 0
    assert any("watch cycle crashed" in subject for kind, subject in notify.sent)


# ── ETL-06: annual and ad hoc studies load at close; in-field waves say so ─
def test_a_wave_loaded_while_in_field_is_marked_in_field(csi_db):
    with csi_db.begin() as conn:
        wave(conn, 1, date(2026, 10, 12), platform="forsta", end=None)
        wave(conn, 2, date(2026, 10, 19), platform="forsta", end="2026-10-20 01:00:00")
        multi(conn, 1, "Q1", "Which?", [("A", 10, 400)])
        multi(conn, 2, "Q1", "Which?", [("A", 10, 400)])
    serving.schema_has.cache_clear()
    serving.build_wave(1), serving.build_wave(2)
    with csi_db.connect() as conn:
        assert dict(conn.execute(sa.text("SELECT survey_id, in_field FROM srv_wave")).all()) == {1: 1, 2: 0}


# ── ETL-10: families by config; every wave is served, however small (no exclusions, 23 Oct 2026) ───
def test_an_annual_study_listed_in_the_config_keeps_its_family_and_compares_with_last_year(csi_db):
    assert forsta_etl.family({"path": "selfserve/58f/holiday", "title": "Holiday Shopping and Spending 2025",
                              "tags": ["annual tracker"]}) == "HOLIDAY_SHOPPING"
    q = "Will you spend more on holiday gifts this year?"
    with csi_db.begin() as conn:
        wave(conn, 239, date(2025, 9, 29), "HOLIDAY_SHOPPING", "annual", qualified=2005)
        wave(conn, 261, date(2026, 9, 7), "HOLIDAY_SHOPPING", "annual", qualified=2, ref="selfserve/58f/260903")
        wave(conn, 262, date(2026, 9, 7), "HOLIDAY_SHOPPING", "annual", qualified=2042)
        wave(conn, 300, date(2026, 9, 14), "HOLIDAY_SHOPPING", "annual", qualified=12)
        for sid in (239, 261, 262, 300):
            multi(conn, sid, "XM1", q, [("Yes", 2 if sid == 261 else 500, 2 if sid == 261 else 1000)])
    assert [serving.build_wave(s) for s in (239, 261, 262, 300)] == [1, 1, 1, 1]   # 2 and 12 people are served too
    with csi_db.connect() as conn:
        waves = dict(conn.execute(sa.text("SELECT survey_id, ly_survey_id FROM srv_wave")).all())
    assert waves == {239: None, 261: 239, 262: 239, 300: 239}   # 343–350 days apart: last year for an annual study


def test_a_closed_tiny_ad_hoc_survey_is_loaded_like_any_other(csi_db, monkeypatch):
    tiny = {**SURVEYS[1], "path": "selfserve/58f/260903", "title": "Holiday Shopping and Spending 2026", "qualified": 2, "total": 9}

    class Tiny(FakeForsta):
        def surveys(self):
            return [tiny]
    assert forsta_etl.discover(Tiny()) == {"due": 1}


# ── ETL-07: a reload that fails after its write leaves no stale serving rows ─
def test_a_reload_failing_after_its_write_takes_its_serving_rows_away(csi_db, monkeypatch):
    sid = forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    monkeypatch.setattr(forsta_etl, "verify", lambda *a: ["q1r1: 4 sent, 3 stored"])
    with pytest.raises(RuntimeError):
        forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")
    with csi_db.connect() as conn:
        assert conn.execute(sa.text("SELECT load_status FROM cip_survey WHERE survey_id = :s"), {"s": sid}).scalar() == "failed"
        assert conn.execute(sa.text("SELECT COUNT(*) FROM srv_result WHERE survey_id = :s"), {"s": sid}).scalar() == 0
        assert conn.execute(sa.text("SELECT COUNT(*) FROM srv_wave WHERE survey_id = :s"), {"s": sid}).scalar() == 0


# ── ETL-16: a failed publish leaves no half-written version ────────────────
def test_a_publish_that_fails_midway_removes_its_folder(csi_db, tmp_path, monkeypatch):
    from etl import publish
    monkeypatch.setattr(publish.payloads, "waves", lambda by_wave: (_ for _ in ()).throw(RuntimeError("db gone")))
    with pytest.raises(RuntimeError):
        publish.build(tmp_path)
    assert list(tmp_path.glob(".build-*")) == []


# ── ETL-09: nothing checked is not a pass ──────────────────────────────────
def test_reconcile_fails_a_wave_nothing_could_be_checked_on(csi_db):
    from etl.forsta_client import ForstaError
    forsta_etl.load_survey(FakeForsta(), "selfserve/58f/260907")

    class Hibernated(FakeForsta):
        def survey_data(self, path, **params):
            raise ForstaError("428 needs to be reactivated")
    assert forsta_etl.reconcile_all(FakeForsta()) == 0
    assert forsta_etl.reconcile_all(Hibernated()) == 1


# ── ETL-17: the schedule never runs out ────────────────────────────────────
def test_past_the_workbook_every_monday_is_a_launch_except_the_skipped(monkeypatch, tmp_path):
    plan = {"weeks": [{"date": date(2027, 1, 11), "cycle": 21, "sectors": ["X"], "names": ["Apparel"], "topics": []}],
            "skip": [date(2027, 1, 25)]}
    monkeypatch.setattr(launch_schedule, "load_plan", lambda: plan)
    days = [w["date"] for w in launch_schedule.plan_weeks(date(2027, 1, 12))]
    assert days[:3] == [date(2027, 1, 11), date(2027, 1, 18), date(2027, 2, 1)]
    assert days[-1] <= date(2027, 1, 12) + timedelta(weeks=launch_schedule.RULE_WEEKS)
    assert launch_schedule.planned_today(date(2027, 2, 1))["names"] == ["Weekly tracker"]
    assert launch_schedule.planned_today(date(2027, 1, 25)) is None
    import plistlib
    target = tmp_path / "etl.plist"
    target.write_bytes(launch_schedule.LAUNCHD.read_bytes())
    monkeypatch.setattr(launch_schedule, "LAUNCHD", target)
    launch_schedule.write_launchd(date(2027, 1, 12))
    assert plistlib.loads(target.read_bytes())["StartCalendarInterval"] == [
        {"Weekday": 1, "Hour": 17, "Minute": 30}, launch_schedule.CATCH_ALL]


# ── DB-03 / ETL-14: rekeying stored keys to the salted hash, once ───────────
def test_rekeying_turns_every_stored_key_into_the_salted_one_new_loads_write(csi_db, monkeypatch):
    rekey = importlib.import_module("scripts.rekey_respondents")
    from etl import records
    with csi_db.begin() as conn:
        wave(conn, 1, date(2026, 10, 12), qualified=0)
        conn.execute(sa.text("INSERT INTO cip_respondent (survey_id, record_no, is_qualified, respondent_key) VALUES (1, :r, 1, :k)"),
                     [{"r": n, "k": records.respondent_key(f"panel-{n}")} for n in range(3)])
    monkeypatch.setenv("CIP_RESPONDENT_SALT", "s" * 32)
    before = [k for (k,) in csi_db.connect().execute(sa.text("SELECT respondent_key FROM cip_respondent ORDER BY record_no"))]
    assert rekey.main(dry_run=True) == 0
    with csi_db.connect() as conn:                                               # a dry run writes nothing
        assert [k for (k,) in conn.execute(sa.text("SELECT respondent_key FROM cip_respondent ORDER BY record_no"))] == before
    assert rekey.main() == 0
    with csi_db.connect() as conn:
        keys = [k for (k,) in conn.execute(sa.text("SELECT respondent_key FROM cip_respondent ORDER BY record_no"))]
    assert keys == [records.respondent_key(f"panel-{n}") for n in range(3)]     # = what a load with the salt writes
    assert rekey.main() == 0                                                     # a second run hashes nothing twice
    with csi_db.connect() as conn:
        assert [k for (k,) in conn.execute(sa.text("SELECT respondent_key FROM cip_respondent ORDER BY record_no"))] == keys


# ── ETL-02 (source): survey 97's shifted answer ids ────────────────────────
def test_a_legacy_answer_takes_the_label_its_respondents_saw(monkey):  # noqa: F811
    from etl import legacy_dwh
    with monkey.begin() as conn:   # listed S1 Facebook, S2 Instagram, S3 LinkedIn; responses carry S3 = Facebook, S4 = Instagram
        conn.execute(sa.text("INSERT INTO dwh_smquestion VALUES ('QS', 'multiple_choice', 'Which apps do you use? Select all that apply', 3, 0, '900')"))
        conn.execute(sa.text("INSERT INTO dwh_smanswer VALUES ('S1', 1, 'Facebook', 'QS', '900'), ('S2', 2, 'Instagram', 'QS', '900'),"
                             " ('S3', 3, 'LinkedIn', 'QS', '900')"))
        conn.execute(sa.text("INSERT INTO dwh_smresponseqa (answer_text, question_text, answer_othertext, question_id, response_id, answer_id, survey_id) VALUES"
                             " ('Facebook', '', 'None', 'QS', '1001', 'S3', '900'), ('Instagram', '', 'None', 'QS', '1001', 'S4', '900'),"
                             " ('Facebook', '', 'None', 'QS', '1002', 'S3', '900')"))
    sid = legacy_dwh.load_legacy("900")
    with monkey.connect() as conn:
        picked = dict(conn.execute(sa.text(
            "SELECT i.item_label, SUM(a.value_code) FROM cip_item i JOIN cip_question q ON q.question_id = i.question_id"
            " JOIN cip_field f ON f.item_id = i.item_id LEFT JOIN cip_answer a ON a.field_id = f.field_id"
            " WHERE q.survey_id = :s AND q.qtext LIKE 'Which apps%' GROUP BY i.item_label"), {"s": sid}).all())
        status = conn.execute(sa.text("SELECT load_status FROM cip_survey WHERE survey_id = :s"), {"s": sid}).scalar()
    assert picked == {"Facebook": 2, "Instagram": 1} and status == "verified"


def test_a_reload_removes_the_empty_answers_the_old_list_left(monkey, monkeypatch):  # noqa: F811
    from etl import legacy_dwh
    with monkey.begin() as conn:   # as survey 97: the list is shifted against what respondents carry
        conn.execute(sa.text("INSERT INTO dwh_smquestion VALUES ('QS', 'multiple_choice', 'Which apps do you use? Select all that apply', 3, 0, '900')"))
        conn.execute(sa.text("INSERT INTO dwh_smanswer VALUES ('S1', 1, 'Facebook', 'QS', '900'), ('S2', 2, 'Instagram', 'QS', '900'),"
                             " ('S3', 3, 'LinkedIn', 'QS', '900')"))
        conn.execute(sa.text("INSERT INTO dwh_smresponseqa (answer_text, question_text, answer_othertext, question_id, response_id, answer_id, survey_id) VALUES"
                             " ('Facebook', '', 'None', 'QS', '1001', 'S3', '900'), ('Instagram', '', 'None', 'QS', '1001', 'S4', '900'),"
                             " ('Facebook', '', 'None', 'QS', '1002', 'S3', '900')"))
    with monkeypatch.context() as m:   # the first load, before relabel existed
        m.setattr(legacy_dwh, "relabel", lambda *a: None)
        sid = legacy_dwh.load_legacy("900")
    assert legacy_dwh.load_legacy("900") == sid
    with monkey.connect() as conn:
        rows = conn.execute(sa.text(
            "SELECT i.item_label, COALESCE(SUM(a.value_code), 0) FROM cip_item i JOIN cip_question q ON q.question_id = i.question_id"
            " LEFT JOIN cip_field f ON f.item_id = i.item_id LEFT JOIN cip_answer a ON a.field_id = f.field_id"
            " WHERE q.survey_id = :s AND q.qtext LIKE 'Which apps%' GROUP BY i.item_id, i.item_label"), {"s": sid}).all()
    assert sorted(rows) == [("Facebook", 2), ("Instagram", 1)]   # no second, empty "Facebook" or "LinkedIn"
